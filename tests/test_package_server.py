import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build import build, configuration, DEFAULT_PORT
from serve import Handler, installation_warnings, MAX_LOG_BYTES


class PackageTests(unittest.TestCase):
    def test_installable_layout_size_license_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            first, digest = build("192.168.1.20", 80, output=folder)
            original = first.read_bytes()
            self.assertEqual(digest, hashlib.sha256(original).hexdigest())
            build("192.168.1.20", 80, output=folder)
            self.assertEqual(original, first.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn("index.html", archive.namelist())
                self.assertIn("widget.info", archive.namelist())
                self.assertIn("licenses/free-my-tv-MIT.txt", archive.namelist())
                self.assertNotIn("local.json", archive.namelist())
                self.assertIn(b"$MANAGER_WIDGET", archive.read("index.html"))
                self.assertNotIn(b"UE32J4570", archive.read("index.html"))
                self.assertNotIn(b"UE32J4570", archive.read("ui.js"))
                root = ET.fromstring(archive.read("config.xml"))
                self.assertEqual(root.tag, "{http://www.samsung.com/}widget")
                self.assertIn(b"192.168.1.20/media/test.mp4", archive.read("config.js"))
            root = ET.parse(folder / "widgetlist.xml").getroot()
            self.assertEqual(root.find("list/widget").attrib["id"], "OrsayLab")
            compression = root.find("list/widget/compression")
            self.assertEqual(int(compression.attrib["size"]), len(original))
            self.assertEqual(root.findtext("list/widget/download"), "http://192.168.1.20/" + first.name)
            self.assertNotIn("$MANAGER_WIDGET", (folder / "preview/index.html").read_text())

    def test_explicit_build_version_and_listener_consistency(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            package, digest = build("192.168.1.20", output=folder, build_number=7)
            self.assertEqual(package.name, "OrsayLab_0.1.7_Europe.zip")
            with zipfile.ZipFile(package) as archive:
                manifest = ET.fromstring(archive.read("config.xml"))
                self.assertEqual(manifest.findtext("{http://www.samsung.com/}ver"), "0.1.7")
                config = json.loads(archive.read("config.js").decode().removeprefix("var LAB_CONFIG = ").strip().rstrip(";"))
                self.assertEqual(config["buildVersion"], "0.1.7")
                self.assertEqual(config["logUrl"], "http://192.168.1.20:8080/log")
            self.assertEqual(digest, build("192.168.1.20", output=folder, build_number=7)[1])
            xml = folder / "widgetlist.xml"
            self.assertEqual(installation_warnings(xml, "192.168.1.20", DEFAULT_PORT), [])
            self.assertEqual(installation_warnings(xml, "0.0.0.0", DEFAULT_PORT), [])
            self.assertEqual(len(installation_warnings(xml, "127.0.0.1", 80)), 2)
            for invalid in [-1, 65536, True]:
                with self.assertRaises(ValueError):
                    build(output=folder, build_number=invalid)

    def test_config_rejects_credentials_and_arbitrary_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local.json"
            for config in [{"token": "secret"}, {"mediaUrl": "http://user:pw@host/video"},
                           {"plexBaseUrl": "https://host/?X-Plex-Token=secret"},
                           {"playerWidth": True}, {"mediaUrl": "javascript:alert(1)"}]:
                with self.subTest(config=config):
                    path.write_text(json.dumps(config))
                    with self.assertRaises(ValueError):
                        configuration("127.0.0.1", 8080, path)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.media = self.folder / "sample.bin"
        self.media.write_bytes(bytes(range(256)) * 4)
        self.log_path = self.folder / "logs" / "tv.jsonl"
        (self.folder / "widgetlist.xml").write_text("<rsp stat='ok'/>")
        def handler(*args, **kwargs):
            return Handler(*args, directory=self.folder, media=self.media, log_path=self.log_path, **kwargs)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, method="GET", headers=None, body=None):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        conn.request(method, path, headers=headers or {}, body=body)
        response = conn.getresponse()
        result = (response.status, dict(response.getheaders()), response.read())
        conn.close()
        return result

    def test_native_player_byte_ranges_and_head(self):
        for byte_range, expected in [("bytes=10-19", self.media.read_bytes()[10:20]),
                                     ("bytes=-10", self.media.read_bytes()[-10:]),
                                     ("bytes=1000-", self.media.read_bytes()[1000:])]:
            with self.subTest(byte_range=byte_range):
                status, headers, data = self.request("/media/test.mp4", headers={"Range": byte_range})
                self.assertEqual(status, 206)
                self.assertEqual(data, expected)
                self.assertEqual(int(headers["Content-Length"]), len(data))
                self.assertEqual(headers["Accept-Ranges"], "bytes")
        status, headers, data = self.request("/media/test.mp4", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"")
        self.assertEqual(int(headers["Content-Length"]), 1024)
        for invalid in ["bytes=9999-", "bytes=20-10", "bytes=0-1,4-5", "bytes=-0"]:
            self.assertEqual(self.request("/media/test.mp4", headers={"Range": invalid})[0], 416)

    def test_probe_cors_and_no_directory_listing(self):
        xml_status, xml_headers, _ = self.request("/widgetlist.xml")
        self.assertEqual(xml_status, 200)
        self.assertEqual({k.lower(): v for k, v in xml_headers.items()}["content-type"], "text/xml; charset=utf-8")
        status, headers, data = self.request("/health.txt")
        self.assertEqual(status, 200)
        self.assertIn(b"OK", data)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(self.request("/")[0], 404)
        self.assertEqual(self.request("/../local.json")[0], 404)
        self.assertEqual(self.request("/health.txt", method="OPTIONS")[0], 204)

    def test_log_receiver_redacts_and_limits_batches(self):
        payload = {"build": "0.1.7", "events": [{"time": "now", "kind": "log",
                   "text": "Error token=private http://host/path"}]}
        status, headers, _ = self.request("/log", method="POST", body=json.dumps(payload),
                                           headers={"Content-Type": "text/plain;charset=UTF-8"})
        self.assertEqual(status, 204)
        self.assertIn("POST", headers["Access-Control-Allow-Methods"])
        record = json.loads(self.log_path.read_text(encoding="utf-8"))
        self.assertEqual(record["build"], "0.1.7")
        self.assertEqual(record["client"], "127.0.0.1")
        self.assertNotIn("private", record["events"][0]["text"])
        self.assertNotIn("http://", record["events"][0]["text"])
        for body in ["bad json", "{}", '{"build":"x","events":[null]}']:
            self.assertEqual(self.request("/log", method="POST", body=body)[0], 400)
        self.assertEqual(self.request("/log", method="POST", body=b"x" * (MAX_LOG_BYTES + 1))[0], 413)
        self.assertEqual(self.request("/other", method="POST", body="{}")[0], 404)
        self.assertEqual(len(self.log_path.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
