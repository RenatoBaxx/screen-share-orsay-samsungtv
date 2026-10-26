#!/usr/bin/env python3
"""Experimental local video stream to a DLNA/AllShare MediaRenderer (not AirPlay)."""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import os
from pathlib import Path
import secrets
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from threading import Lock, Thread
import time
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET


RENDERER = "urn:schemas-upnp-org:device:MediaRenderer:1"
TRANSPORT = "urn:schemas-upnp-org:service:AVTransport:1"
CONNECTION = "urn:schemas-upnp-org:service:ConnectionManager:1"
SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
PROFILE = "AVC_TS_MP_HD_AAC_ISO"
MAX_XML = 262144
SYSTEM_AUDIO_FD = "{system_audio_fd}"


def local_request(url, tv_ip, method="GET", body=None, headers=None):
    target = urlsplit(url)
    if target.scheme != "http" or target.hostname != tv_ip or target.username or target.password:
        raise ValueError("The renderer advertised an invalid or non-local service URL")
    connection = http.client.HTTPConnection(tv_ip, target.port or 80, timeout=5)
    try:
        path = target.path or "/"
        if target.query:
            path += "?" + target.query
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = response.read(MAX_XML + 1)
        if len(data) > MAX_XML:
            raise ValueError("Renderer response exceeds the XML size limit")
        return response.status, data
    finally:
        connection.close()


def discover(tv_ip, wait=4):
    search = (f'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\n'
              f'MAN: "ssdp:discover"\r\nMX: 2\r\nST: {RENDERER}\r\n\r\n').encode()
    locations = set()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(search, ("239.255.255.250", 1900))
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(min(0.5, remaining))
            try:
                reply, address = sock.recvfrom(16384)
            except socket.timeout:
                continue
            if address[0] != tv_ip:
                continue
            fields = dict((key.strip().lower(), value.strip())
                          for line in reply.decode("ascii", errors="replace").split("\r\n")
                          if ":" in line for key, value in [line.split(":", 1)])
            if fields.get("st") == RENDERER and fields.get("location"):
                locations.add(fields["location"])
    for location in sorted(locations):
        if urlsplit(location).hostname != tv_ip:
            continue
        status, description = local_request(location, tv_ip)
        if status != 200:
            raise RuntimeError(f"Renderer description returned HTTP {status}")
        return service_urls(description, location, tv_ip)
    raise RuntimeError(f"No DLNA MediaRenderer description found at {tv_ip}")


def service_urls(description, location, tv_ip):
    urls = {}
    for service in ET.fromstring(description).findall(".//{*}service"):
        kind = service.findtext("{*}serviceType")
        control = service.findtext("{*}controlURL")
        if kind in (TRANSPORT, CONNECTION) and control:
            url = urljoin(location, control)
            if urlsplit(url).scheme != "http" or urlsplit(url).hostname != tv_ip:
                raise ValueError("The renderer advertised a control URL outside the TV")
            urls[kind] = url
    if TRANSPORT not in urls or CONNECTION not in urls:
        raise RuntimeError("Renderer has no DLNA playback and format endpoints")
    return urls[TRANSPORT], urls[CONNECTION]


def soap_action(url, tv_ip, service, action, arguments=None):
    ET.register_namespace("s", SOAP)
    ET.register_namespace("u", service)
    envelope = ET.Element(f"{{{SOAP}}}Envelope", {f"{{{SOAP}}}encodingStyle":
                                                "http://schemas.xmlsoap.org/soap/encoding/"})
    node = ET.SubElement(ET.SubElement(envelope, f"{{{SOAP}}}Body"), f"{{{service}}}{action}")
    for name, value in (arguments or {}).items():
        ET.SubElement(node, name).text = str(value)
    status, content = local_request(url, tv_ip, "POST", ET.tostring(envelope, encoding="utf-8"),
                                    {"Content-Type": 'text/xml; charset="utf-8"',
                                     "SOAPACTION": f'"{service}#{action}"'})
    root = ET.fromstring(content)
    if status != 200 or root.find(".//{*}Fault") is not None:
        description = root.findtext(".//{*}errorDescription") or root.findtext(".//{*}errorCode") or ""
        raise RuntimeError(f"DLNA {action} failed: HTTP {status} {description}".strip())
    return root


def supported_formats(manager_url, tv_ip):
    root = soap_action(manager_url, tv_ip, CONNECTION, "GetProtocolInfo")
    sink = root.findtext(".//{*}Sink")
    if sink is None:
        raise RuntimeError("Renderer did not return its supported formats")
    entries = sink.split(",")
    mp4 = any(item.startswith("http-get:*:video/mp4:") for item in entries)
    ts = any(item.startswith(f"http-get:*:video/mpeg:DLNA.ORG_PN={PROFILE};") for item in entries)
    return mp4, ts


def metadata(url, title, protocol):
    didl = "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
    ET.register_namespace("", didl)
    ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")
    ET.register_namespace("upnp", "urn:schemas-upnp-org:metadata-1-0/upnp/")
    root = ET.Element(f"{{{didl}}}DIDL-Lite")
    item = ET.SubElement(root, f"{{{didl}}}item", id="0", parentID="-1", restricted="1")
    ET.SubElement(item, "{http://purl.org/dc/elements/1.1/}title").text = title
    ET.SubElement(item, "{urn:schemas-upnp-org:metadata-1-0/upnp/}class").text = "object.item.videoItem"
    ET.SubElement(item, f"{{{didl}}}res", protocolInfo=protocol).text = url
    return ET.tostring(root, encoding="unicode")


def play(transport_url, tv_ip, url, title, protocol):
    soap_action(transport_url, tv_ip, TRANSPORT, "SetAVTransportURI",
                {"InstanceID": 0, "CurrentURI": url,
                 "CurrentURIMetaData": metadata(url, title, protocol)})
    soap_action(transport_url, tv_ip, TRANSPORT, "Play", {"InstanceID": 0, "Speed": 1})


def check_sample(url):
    target = urlsplit(url)
    address = ipaddress.IPv4Address(target.hostname or "")
    if (target.scheme != "http" or not address.is_private or target.username
            or target.password or target.query or target.fragment):
        raise ValueError("Sample URL must use plain HTTP on the Mac's private LAN IP")
    connection = http.client.HTTPConnection(str(address), target.port or 80, timeout=5)
    try:
        connection.request("HEAD", target.path or "/")
        response = connection.getresponse()
        if response.status != 200 or response.getheader("Content-Type", "").split(";")[0] != "video/mp4":
            raise RuntimeError(f"Sample is not an accessible MP4 (HTTP {response.status})")
        if int(response.getheader("Content-Length", "0")) <= 0:
            raise RuntimeError("Sample has no Content-Length; check the media server")
    finally:
        connection.close()


def ffmpeg_command(ffmpeg, source, screen_index, system_audio=False):
    if source == "test":
        if system_audio:
            raise ValueError("System audio is only available with the Mac screen")
        video = ["-re", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25"]
        audio = ["-re", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
    else:
        video = ["-f", "avfoundation", "-framerate", "25", "-pixel_format", "nv12",
                 "-capture_cursor", "1",
                 "-i", f"Capture screen {screen_index}:none"]
        if system_audio:
            audio = ["-thread_queue_size", "512", "-f", "f32le", "-ar", "48000",
                     "-ac", "2", "-i", f"pipe:{SYSTEM_AUDIO_FD}"]
        else:
            audio = ["-re", "-f", "lavfi", "-i",
                     "anullsrc=channel_layout=stereo:sample_rate=48000"]
    return [ffmpeg, "-hide_banner", "-loglevel", "error", *video, *audio,
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                   "pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
            "-profile:v", "main", "-level:v", "3.1", "-crf", "23",
            "-g", "25",
            "-c:a", "aac", "-ac", "2", "-b:a", "128k", "-ar", "48000",
            *(["-shortest"] if system_audio else []), "-f", "mpegts", "pipe:1"]


def compile_system_audio(swiftc, target):
    source = Path(__file__).with_name("capture_system_audio.swift")
    if not source.is_file():
        raise RuntimeError(f"ScreenCaptureKit helper not found: {source}")
    try:
        result = subprocess.run([swiftc, "-parse-as-library", str(source), "-o", str(target)],
                                capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("ScreenCaptureKit helper compilation timed out") from error
    if result.returncode:
        raise RuntimeError("ScreenCaptureKit helper compilation failed: " + result.stderr.strip())
    return str(target)


def request_stop(process):
    if process is not None and process.poll() is None:
        try:
            process.stdin.write(b"q\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass


class StreamHandler(BaseHTTPRequestHandler):
    def eligible(self):
        if self.path != self.server.media_path:
            self.send_error(404)
        elif self.client_address[0] != self.server.tv_ip:
            self.send_error(403, "Only the selected TV can receive the stream")
        elif self.headers.get("Range"):
            self.send_error(416, "Live video cannot be byte-seeked")
        else:
            return True
        return False

    def headers_for_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "video/mpeg")
        self.send_header("TransferMode.dlna.org", "Streaming")
        self.send_header("contentFeatures.dlna.org",
                         f"DLNA.ORG_PN={PROFILE};DLNA.ORG_OP=00;DLNA.ORG_CI=1")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_HEAD(self):
        if self.eligible():
            self.headers_for_stream()

    def do_GET(self):
        if not self.eligible():
            return
        if not self.server.stream_lock.acquire(blocking=False):
            self.send_error(503, "A stream is already in progress")
            return
        self.connection.settimeout(10)
        process = None
        audio_process = None
        disconnected = False
        ffmpeg_log = tempfile.TemporaryFile()
        audio_log = tempfile.TemporaryFile()
        try:
            audio_read = audio_write = None
            try:
                command = self.server.command
                if self.server.audio_helper:
                    audio_read, audio_write = os.pipe()
                    command = [argument.replace(SYSTEM_AUDIO_FD, str(audio_read))
                               for argument in command]
                process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=ffmpeg_log,
                                           pass_fds=(audio_read,) if audio_read is not None else ())
                self.server.process = process
                if self.server.audio_helper:
                    audio_process = subprocess.Popen([self.server.audio_helper],
                                                     stdin=subprocess.PIPE, stdout=audio_write,
                                                     stderr=audio_log)
                    self.server.audio_process = audio_process
            except OSError as error:
                self.send_error(500, f"Cannot start video or system audio capture: {error}")
                return
            finally:
                for fd in (audio_read, audio_write):
                    if fd is not None:
                        os.close(fd)
            if not select.select([process.stdout], [], [], 20)[0]:
                self.send_error(504, "Video and system audio did not start within 20 seconds")
                return
            first = os.read(process.stdout.fileno(), 32768)
            if not first:
                log = (audio_log if audio_process and audio_process.poll() is not None
                       else ffmpeg_log)
                log.seek(0)
                details = log.read(500).decode(errors="replace").strip()
                self.send_error(502, "Video or system audio failed: " +
                                (details or "FFmpeg produced no video"))
                return
            self.headers_for_stream()
            self.wfile.write(first)
            while block := process.stdout.read(32768):
                self.wfile.write(block)
                if audio_process and audio_process.poll() is not None and not self.server.stopping:
                    audio_log.seek(0)
                    details = audio_log.read(500).decode(errors="replace").strip()
                    print("System audio capture stopped unexpectedly: " +
                          (details or f"exit status {audio_process.returncode}"), flush=True)
                    request_stop(process)
                    break
        except (BrokenPipeError, ConnectionResetError, TimeoutError) as error:
            disconnected = True
            if not self.server.stopping:
                print(f"TV stream disconnected: {error}", flush=True)
        finally:
            for child in (audio_process, process):
                if child is not None:
                    request_stop(child)
                    try:
                        result = child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.terminate()
                        try:
                            result = child.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            result = child.wait()
                    child.stdin.close()
                    if child.stdout is not None:
                        child.stdout.close()
                    if result and not self.server.stopping and not disconnected:
                        log = audio_log if child is audio_process else ffmpeg_log
                        log.seek(0)
                        details = log.read(4096).decode(errors="replace").strip()
                        label = "System audio" if child is audio_process else "FFmpeg"
                        print(f"{label} exited with status {result}: {details}", flush=True)
            ffmpeg_log.close()
            audio_log.close()
            self.server.process = None
            self.server.audio_process = None
            self.server.stream_lock.release()

    def log_message(self, fmt, *args):
        if fmt == '"%s" %s %s':
            print(f"DLNA HTTP {self.command} from {self.client_address[0]}: {args[1]}",
                  flush=True)
        else:
            print("DLNA HTTP: " + fmt % args, flush=True)


class StreamServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, command, tv_ip, audio_helper=None):
        self.command = command
        self.tv_ip = tv_ip
        self.audio_helper = audio_helper
        self.media_path = "/live/" + secrets.token_urlsafe(24) + ".ts"
        self.stream_lock = Lock()
        self.process = None
        self.audio_process = None
        self.stopping = False
        super().__init__(address, StreamHandler)

    def stop_stream(self):
        self.stopping = True
        request_stop(self.audio_process)
        request_stop(self.process)
        if self.audio_helper and self.process is not None and self.process.poll() is None:
            try:
                self.process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass

    def wait_for_stream(self):
        if self.stream_lock.acquire(timeout=10):
            self.stream_lock.release()
            return
        print("Live capture is still active; terminating its processes.", flush=True)
        for child in (self.audio_process, self.process):
            if child is not None and child.poll() is None:
                child.terminate()
        if self.stream_lock.acquire(timeout=5):
            self.stream_lock.release()
            return
        print("Live capture did not terminate; killing its processes.", flush=True)
        for child in (self.audio_process, self.process):
            if child is not None and child.poll() is None:
                child.kill()
        if not self.stream_lock.acquire(timeout=5):
            raise RuntimeError("Live capture did not stop after terminating its processes")
        self.stream_lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tv", required=True, help="IP address of the TV")
    parser.add_argument("--bind", help="Mac's LAN IP; required for live video")
    parser.add_argument("--port", type=int, default=8090, help="Live server port (default: 8090)")
    option = parser.add_mutually_exclusive_group()
    option.add_argument("--sample-url", help="Existing LAN URL of a finite MP4 for a TV playback test")
    option.add_argument("--source", choices=("test", "screen"), help="Live test pattern or Mac screen")
    parser.add_argument("--screen-index", type=int, default=0)
    parser.add_argument("--allow-screen-recording", action="store_true",
                        help="Explicitly permit capturing the Mac screen when the TV requests it")
    parser.add_argument("--system-audio", action="store_true",
                        help="Opt in to capturing Mac system audio via ScreenCaptureKit (macOS)")
    parser.add_argument("--duration", type=int, help="Stop a live stream automatically after N seconds")
    parser.add_argument("--play", action="store_true", help="Opt in to changing TV playback")
    args = parser.parse_args()
    try:
        tv_ip = str(ipaddress.IPv4Address(args.tv))
        if args.screen_index < 0 or not 1 <= args.port <= 65535:
            parser.error("Screen index and port must be valid nonnegative values")
        if args.play != bool(args.sample_url or args.source):
            parser.error("Use --play with either --sample-url or --source")
        if args.source == "screen" and not args.allow_screen_recording:
            parser.error("Screen capture requires --allow-screen-recording")
        if args.allow_screen_recording and args.source != "screen":
            parser.error("--allow-screen-recording requires --source screen")
        if args.system_audio and args.source != "screen":
            parser.error("--system-audio requires --source screen")
        if args.system_audio and sys.platform != "darwin":
            parser.error("--system-audio requires macOS with ScreenCaptureKit")
        if args.duration is not None and (args.duration <= 0 or not args.source):
            parser.error("--duration requires a live --source and a positive number of seconds")
        transport, manager = discover(tv_ip)
        mp4, ts = supported_formats(manager, tv_ip)
        print(f"Renderer {tv_ip}: MP4={mp4}, H.264/AAC MPEG-TS={ts}", flush=True)
        if not args.play:
            return
        if args.sample_url:
            if not mp4:
                parser.error("The TV did not advertise MP4 playback")
            check_sample(args.sample_url)
            if ipaddress.IPv4Address(urlsplit(args.sample_url).hostname).is_loopback:
                parser.error("Use the Mac's LAN IP in --sample-url, not 127.0.0.1")
            play(transport, tv_ip, args.sample_url, "Orsay Lab sample", "http-get:*:video/mp4:*")
            print("Sample requested; confirm picture and sound directly on the TV.", flush=True)
            return
        if not ts:
            parser.error(f"The TV did not advertise the required MPEG-TS profile {PROFILE}")
        if not args.bind:
            parser.error("Pass --bind with the Mac's LAN IP, not the TV's IP")
        bind = ipaddress.IPv4Address(args.bind)
        if bind.is_loopback or bind.is_unspecified or not bind.is_private or str(bind) == tv_ip:
            parser.error("--bind must be the Mac's private LAN IP")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            parser.error("FFmpeg is required for live video")
        with tempfile.TemporaryDirectory(prefix="orsay-system-audio-") as audio_directory:
            audio_helper = None
            if args.system_audio:
                swiftc = shutil.which("swiftc")
                if not swiftc:
                    parser.error("Swift compiler is required for ScreenCaptureKit system audio")
                audio_helper = compile_system_audio(swiftc, Path(audio_directory) / "capture_audio")
                print("Mac system audio will be captured when the TV requests the stream.",
                      flush=True)
            elif args.source == "screen":
                print("WARNING: Screen stream audio is silent without --system-audio.", flush=True)
            server = StreamServer((str(bind), args.port),
                                  ffmpeg_command(ffmpeg, args.source, args.screen_index,
                                                 args.system_audio),
                                  tv_ip, audio_helper=audio_helper)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            active = False
            try:
                url = f"http://{bind}:{args.port}{server.media_path}"
                play(transport, tv_ip, url, "Mac screen" if args.source == "screen"
                     else "Test pattern",
                     f"http-get:*:video/mpeg:DLNA.ORG_PN={PROFILE};DLNA.ORG_OP=00;DLNA.ORG_CI=1")
                active = True
                print("Waiting for the TV's HTTP request; press Ctrl+C to stop.", flush=True)
                thread.join(timeout=args.duration)
                if thread.is_alive():
                    print("Time limit reached; stopping local stream.", flush=True)
            except KeyboardInterrupt:
                print("Stopping local stream.", flush=True)
            finally:
                server.stop_stream()
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
                try:
                    if active:
                        soap_action(transport, tv_ip, TRANSPORT, "Stop", {"InstanceID": 0})
                finally:
                    server.wait_for_stream()
    except (OSError, ValueError, RuntimeError, ET.ParseError) as error:
        parser.exit(1, f"Mirror error: {error}\n")


if __name__ == "__main__":
    main()
