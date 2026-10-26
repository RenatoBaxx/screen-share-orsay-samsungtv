import array
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from threading import Thread, Timer
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import dlna_mirror
from dlna_mirror import (CONNECTION, PROFILE, SOAP, TRANSPORT, StreamServer, check_sample,
                         compile_system_audio, ffmpeg_command, local_request, metadata, play,
                         service_urls, soap_action, supported_formats)


class RendererHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        good = self.path == "/sample.mp4"
        self.send_response(200 if good else 404)
        self.send_header("Content-Type", "video/mp4" if good else "text/plain")
        self.send_header("Content-Length", "512" if good else "0")
        self.end_headers()

    def do_POST(self):
        request = ET.fromstring(self.rfile.read(int(self.headers["Content-Length"])))
        action = request.find(f".//{{{SOAP}}}Body")[0]
        name = action.tag.rsplit("}", 1)[-1]
        self.server.calls.append((name, request, self.headers["SOAPACTION"]))
        if name == self.server.fail_action:
            status = 500
            payload = (f'<s:Envelope xmlns:s="{SOAP}"><s:Body><s:Fault><detail>'
                       '<errorDescription>Rejected</errorDescription></detail></s:Fault>'
                       '</s:Body></s:Envelope>')
        else:
            status = 200
            sink = (f"http-get:*:video/mp4:*,"
                    f"http-get:*:video/mpeg:DLNA.ORG_PN={PROFILE};DLNA.ORG_FLAGS=ED100000")
            payload = (f'<s:Envelope xmlns:s="{SOAP}"><s:Body>'
                       f'<u:{name}Response xmlns:u="{CONNECTION if name == "GetProtocolInfo" else TRANSPORT}">'
                       f'{"<Sink>" + sink + "</Sink>" if name == "GetProtocolInfo" else ""}'
                       f'</u:{name}Response></s:Body></s:Envelope>')
        data = payload.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/xml")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass


class DlnaProtocolTests(unittest.TestCase):
    def setUp(self):
        self.renderer = ThreadingHTTPServer(("127.0.0.1", 0), RendererHandler)
        self.renderer.calls = []
        self.renderer.fail_action = None
        self.thread = Thread(target=self.renderer.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.renderer.server_port}/control"

    def tearDown(self):
        self.renderer.shutdown()
        self.renderer.server_close()
        self.thread.join()

    def test_local_description_and_same_host_control_urls(self):
        document = (f"<root><service><serviceType>{TRANSPORT}</serviceType>"
                    "<controlURL>/transport</controlURL></service>"
                    f"<service><serviceType>{CONNECTION}</serviceType>"
                    "<controlURL>/manager</controlURL></service></root>").encode()
        urls = service_urls(document, self.url, "127.0.0.1")
        self.assertEqual(urls, (self.url.replace("control", "transport"),
                                self.url.replace("control", "manager")))
        with self.assertRaises(ValueError):
            service_urls(document.replace(b"/transport", b"http://remote.invalid/transport"),
                         self.url, "127.0.0.1")
        with self.assertRaises(ValueError):
            local_request("http://remote.invalid/control", "127.0.0.1")

    def test_probe_and_play_send_valid_dlna_metadata(self):
        self.assertEqual(supported_formats(self.url, "127.0.0.1"), (True, True))
        media = "http://127.0.0.1:8090/live/test.ts"
        protocol = f"http-get:*:video/mpeg:DLNA.ORG_PN={PROFILE};DLNA.ORG_OP=00"
        play(self.url, "127.0.0.1", media, "Synthetic video", protocol)
        self.assertEqual([call[0] for call in self.renderer.calls],
                         ["GetProtocolInfo", "SetAVTransportURI", "Play"])
        _, request, header = self.renderer.calls[1]
        self.assertEqual(header, f'"{TRANSPORT}#SetAVTransportURI"')
        self.assertEqual(request.findtext(".//{*}CurrentURI"), media)
        didl = ET.fromstring(request.findtext(".//{*}CurrentURIMetaData"))
        resource = didl.find(".//{*}res")
        self.assertEqual(resource.text, media)
        self.assertEqual(resource.attrib["protocolInfo"], protocol)
        self.assertEqual(didl.findtext(".//{*}title"), "Synthetic video")

    def test_renderer_fault_is_not_treated_as_success(self):
        self.renderer.fail_action = "Play"
        with self.assertRaisesRegex(RuntimeError, "Play failed: HTTP 500 Rejected"):
            soap_action(self.url, "127.0.0.1", TRANSPORT, "Play", {"InstanceID": 0, "Speed": 1})

    def test_sample_preflight_rejects_missing_video_before_tv_play(self):
        check_sample(self.url.replace("control", "sample.mp4"))
        with self.assertRaisesRegex(RuntimeError, "accessible MP4"):
            check_sample(self.url.replace("control", "missing.mp4"))
        with self.assertRaises(ValueError):
            check_sample("https://127.0.0.1/sample.mp4")
        self.assertEqual(self.renderer.calls, [])

    def test_macos_screen_input_is_named_not_a_camera_index(self):
        command = ffmpeg_command("ffmpeg", "screen", 0)
        self.assertIn("Capture screen 0:none", command)
        self.assertIn("nv12", command)
        self.assertIn("anullsrc=channel_layout=stereo:sample_rate=48000", command)
        self.assertNotIn("0:none", command)
        self.assertIn("-crf", command)
        self.assertNotIn("-b:v", command)
        self.assertNotIn("-maxrate", command)
        self.assertNotIn("-bufsize", command)
        with_audio = ffmpeg_command("ffmpeg", "screen", 0, system_audio=True)
        self.assertIn("pipe:{system_audio_fd}", with_audio)
        self.assertIn("-shortest", with_audio)
        self.assertNotIn("anullsrc=channel_layout=stereo:sample_rate=48000", with_audio)
        with self.assertRaises(ValueError):
            ffmpeg_command("ffmpeg", "test", 0, system_audio=True)
        self.assertIn("object.item.videoItem",
                      metadata("http://127.0.0.1/sample.mp4", "Test", "http-get:*:video/mp4:*"))

    def test_screen_recording_requires_opt_in_before_discovering_tv(self):
        arguments = ["dlna_mirror.py", "--tv", "192.168.1.103", "--bind", "192.168.1.102",
                     "--source", "screen", "--play"]
        with patch.object(sys, "argv", arguments), patch.object(dlna_mirror, "discover") as discover:
            with patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
                with self.assertRaises(SystemExit) as exit_status:
                    dlna_mirror.main()
        self.assertEqual(exit_status.exception.code, 2)
        self.assertIn("--allow-screen-recording", stderr.getvalue())
        discover.assert_not_called()

    def test_system_audio_requires_mac_screen_before_discovering_tv(self):
        arguments = ["dlna_mirror.py", "--tv", "192.168.1.103", "--source", "test",
                     "--system-audio", "--play"]
        with patch.object(sys, "argv", arguments), patch.object(dlna_mirror, "discover") as discover:
            with patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
                with self.assertRaises(SystemExit) as exit_status:
                    dlna_mirror.main()
        self.assertEqual(exit_status.exception.code, 2)
        self.assertIn("--system-audio requires --source screen", stderr.getvalue())
        discover.assert_not_called()

    def test_live_duration_rejects_zero_before_contacting_tv(self):
        arguments = ["dlna_mirror.py", "--tv", "192.168.1.103", "--bind", "192.168.1.102",
                     "--source", "test", "--duration", "0", "--play"]
        with patch.object(sys, "argv", arguments), patch.object(dlna_mirror, "discover") as discover:
            with patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
                with self.assertRaises(SystemExit) as exit_status:
                    dlna_mirror.main()
        self.assertEqual(exit_status.exception.code, 2)
        self.assertIn("--duration", stderr.getvalue())
        discover.assert_not_called()


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools unavailable")
class LiveStreamTests(unittest.TestCase):
    def setUp(self):
        self.server = StreamServer(("127.0.0.1", 0),
                                   ffmpeg_command(shutil.which("ffmpeg"), "test", 0), "127.0.0.1")
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.stop_stream()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, headers=None):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=12)
        conn.request(method, self.server.media_path, headers=headers or {})
        return conn, conn.getresponse()

    def test_synthetic_http_live_video_decodes_and_has_expected_format(self):
        conn, response = self.request("HEAD")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "video/mpeg")
        self.assertIn(PROFILE, response.getheader("contentFeatures.dlna.org"))
        conn.close()
        self.assertIsNone(self.server.process)

        conn, response = self.request("GET", {"Range": "bytes=0-"})
        self.assertEqual(response.status, 416)
        conn.close()

        conn, response = self.request("GET")
        self.assertEqual(response.status, 200)
        content = response.read(700000)
        conn.close()
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "stream=codec_name,profile,level,width,height",
                                "-of", "json", "pipe:0"],
                               input=content, capture_output=True, timeout=15, check=True)
        tracks = json.loads(probe.stdout)["streams"]
        video = next(track for track in tracks if track["codec_name"] == "h264")
        self.assertEqual((video["profile"], video["level"], video["width"], video["height"]),
                         ("Main", 31, 1280, 720))
        self.assertIn("aac", [track["codec_name"] for track in tracks])
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0",
                                  "-vf", "signalstats,metadata=print:file=-",
                                  "-frames:v", "3", "-an", "-f", "null", "-"],
                                 input=content, capture_output=True, timeout=15, check=True)
        spans = re.findall(rb"lavfi.signalstats.YMIN=(\d+).*?"
                           rb"lavfi.signalstats.YMAX=(\d+)",
                           decoded.stdout, flags=re.DOTALL)
        self.assertGreaterEqual(len(spans), 2)
        self.assertTrue(all(int(high) - int(low) > 40 for low, high in spans))

    def test_only_selected_tv_can_request_stream(self):
        self.server.tv_ip = "192.0.2.5"
        conn, response = self.request("HEAD")
        self.assertEqual(response.status, 403)
        conn.close()
        self.assertIsNone(self.server.process)

    def test_stopping_stream_exits_ffmpeg_cleanly(self):
        conn, response = self.request("GET")
        self.assertEqual(response.status, 200)
        self.assertGreater(len(response.read(32768)), 0)
        process = self.server.process
        self.server.stop_stream()
        response.read()
        conn.close()
        self.assertEqual(process.wait(timeout=5), 0)


@unittest.skipUnless(sys.platform == "darwin" and os.environ.get("ORSAY_TEST_CAPTURE") == "1",
                     "Set ORSAY_TEST_CAPTURE=1 on an authorized Mac to test screen and system audio")
class AuthorizedCaptureTests(unittest.TestCase):
    def test_real_desktop_and_system_tone_survive_http_transcoding(self):
        if not shutil.which("swiftc") or not shutil.which("afplay"):
            self.fail("Swift compiler and afplay are required for the authorized capture test")
        with tempfile.TemporaryDirectory(prefix="orsay-capture-test-") as directory:
            helper = compile_system_audio(shutil.which("swiftc"),
                                          Path(directory) / "capture_system_audio")
            tone = Path(directory) / "tone.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "sine=frequency=440:sample_rate=48000:duration=2",
                            "-filter:a", "volume=0.15", "-y", str(tone)],
                           capture_output=True, timeout=15, check=True)
            server = StreamServer(("127.0.0.1", 0),
                                  ffmpeg_command(shutil.which("ffmpeg"), "screen", 0, True),
                                  "127.0.0.1", audio_helper=helper)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            timer = None
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=20)
            player = None
            try:
                started = time.monotonic()
                connection.request("GET", server.media_path)
                response = connection.getresponse()
                if response.status != 200:
                    self.fail(f"System audio stream failed: HTTP {response.status} "
                              + response.read(500).decode(errors="replace"))
                print(f"Screen/audio startup: {time.monotonic() - started:.2f} s")
                timer = Timer(7, server.stop_stream)
                timer.start()
                player = subprocess.Popen(["afplay", "-v", "0.2", str(tone)],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                chunks = []
                deadline = time.monotonic() + 16
                while block := response.read(8192):
                    chunks.append(block)
                    if time.monotonic() >= deadline:
                        self.fail("System audio stream did not stop after the time limit")
                content = b"".join(chunks)
                self.assertEqual(player.wait(timeout=8), 0)
            finally:
                if timer is not None:
                    timer.cancel()
                server.stop_stream()
                connection.close()
                if player is not None:
                    if player.poll() is None:
                        player.terminate()
                        player.wait(timeout=3)
                    player.stderr.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
                server.wait_for_stream()
            self.assertIsNone(server.process)
            self.assertIsNone(server.audio_process)
            self.assertGreater(len(content), 20000)
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                    "stream=codec_name,profile,level,width,height,channels",
                                    "-show_entries", "packet=codec_type,pts_time",
                                    "-of", "json", "pipe:0"],
                                   input=content, capture_output=True, timeout=15, check=True)
            media = json.loads(probe.stdout)
            tracks = media["streams"]
            self.assertIn("h264", [track["codec_name"] for track in tracks])
            self.assertIn("aac", [track["codec_name"] for track in tracks])
            positions = {
                kind: [float(packet["pts_time"]) for packet in media["packets"]
                       if packet.get("codec_type") == kind and "pts_time" in packet]
                for kind in ("video", "audio")
            }
            for kind, timestamps in positions.items():
                self.assertGreaterEqual(len(timestamps), 2, kind)
                self.assertGreater(timestamps[-1] - timestamps[0], 3, kind)
            self.assertLess(abs(positions["video"][0] - positions["audio"][0]), 0.3)
            self.assertLess(abs(positions["video"][-1] - positions["audio"][-1]), 1)
            video = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0",
                                    "-vf", "signalstats,metadata=print:file=-",
                                    "-an", "-f", "null", "-"],
                                   input=content, capture_output=True, timeout=15, check=True)
            spans = re.findall(rb"lavfi.signalstats.YMIN=(\d+).*?"
                               rb"lavfi.signalstats.YMAX=(\d+)",
                               video.stdout, flags=re.DOTALL)
            self.assertGreaterEqual(len(spans), 70)
            self.assertGreaterEqual(sum(int(high) - int(low) > 20
                                        for low, high in spans[-50:]), 40)
            audio = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0",
                                    "-map", "0:a:0", "-f", "f32le", "pipe:1"],
                                   input=content, capture_output=True, timeout=15, check=True)
            samples = array.array("f")
            samples.frombytes(audio.stdout)
            self.assertGreaterEqual(len(samples), 48_000 * 2)
            rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
            self.assertGreater(rms, 0.002)
            left = samples[::2]

            def tone_strength(frequency, offset):
                chunk = left[offset:offset + 4800]
                real = sum(sample * math.cos(2 * math.pi * frequency * index / 48_000)
                           for index, sample in enumerate(chunk))
                imaginary = sum(sample * math.sin(2 * math.pi * frequency * index / 48_000)
                                for index, sample in enumerate(chunk))
                return 2 * math.hypot(real, imaginary) / len(chunk)

            strengths = [tone_strength(440, offset)
                         for offset in range(0, len(left) - 4800, 24000)]
            self.assertGreater(max(strengths), 0.004)


if __name__ == "__main__":
    unittest.main()
