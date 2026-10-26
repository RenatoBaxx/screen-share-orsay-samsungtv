#!/usr/bin/env python3
"""Real Chromium smoke checks, plus explicitly simulated Orsay API checks."""
from http.server import ThreadingHTTPServer
from functools import partial
import json
from pathlib import Path
import shutil
import sys
import tempfile
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build import build
from serve import Handler

MOCK = """
window.calls = [];
window.Common = {API: {
  Widget: function () {
    this.sendReadyEvent = function () { window.calls.push('ready'); };
    this.blockNavigation = function (event) { if (!event) throw new Error('Missing key event'); };
    this.sendReturnEvent = function () { window.calls.push('return'); };
    this.sendExitEvent = function () { window.calls.push('exit'); };
  },
  TVKeyValue: function () {}
}};
document.addEventListener('DOMContentLoaded', function () {
  var p = document.getElementById('pluginPlayer');
  p.InitPlayer = function () { window.calls.push('init'); return 1; };
  p.SetDisplayArea = function () { window.calls.push('area'); };
  p.StartPlayback = function () { window.calls.push('play'); return 1; };
  p.Stop = function () { window.calls.push('stop'); };
  var sef = document.getElementById('pluginSEF');
  sef.Open = function () { throw new Error('Diagnosis must not open SEF'); };
  sef.Execute = function () { throw new Error('Diagnosis must not execute SEF'); };
  window.webapis = {avplay: {getAVPlay: function () { throw new Error('Diagnosis must not acquire a player'); }}};
});
"""


def raw(page, code):
    page.evaluate("""code => {
      var event = document.createEvent('Event');
      event.initEvent('keydown', true, true);
      Object.defineProperty(event, 'keyCode', {value: code});
      document.getElementById('key-anchor').dispatchEvent(event);
    }""", code)


def check_browser(folder):
    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    log_path = folder / "tv-log.jsonl"
    handler = partial(Handler, directory=folder / "dist", log_path=log_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_port
    build("127.0.0.1", port, output=folder / "dist", build_number=7)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=executable, args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"])
            page = browser.new_page(viewport={"width": 1366, "height": 768})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            url = "http://127.0.0.1:" + str(port) + "/preview/index.html"
            page.goto(url)
            assert page.locator("#build-label").inner_text() == "Build 0.1.7"
            assert "BROWSER" in page.locator("#mode").inner_text()
            assert "focus" in page.locator("#tile-0").get_attribute("class")
            page.keyboard.press("ArrowRight")
            page.keyboard.press("Enter")
            assert "YouTube" in page.locator("#panel-title").inner_text()
            assert "keinen YouTube-Client" in page.locator("#panel-text").inner_text()
            page.keyboard.press("Escape")
            raw(page, 5)  # legacy Right -> Diagnose
            raw(page, 29443)
            assert "Viewport: 1366 x 768" in page.locator("#panel-text").inner_text()
            assert "Legacy AVPlay getAVPlay: false" in page.locator("#panel-text").inner_text()
            assert page.locator("#panel-text").evaluate("node => node.scrollHeight <= node.clientHeight")
            page.wait_for_function("LabLog.remoteStatus() === 'HTTP 204'")
            assert "Log-Rückkanal: HTTP 204" in page.locator("#panel-text").inner_text()
            page.screenshot(path=str(artifacts / "browser-diagnostics.png"))
            page.evaluate("LabLog.add('Test token=private http://host/private')")
            page.evaluate("window.onerror('Startup test', '', 1)")
            page.wait_for_function("LabLog.remoteStatus() === 'HTTP 204'")
            raw(page, 88)
            raw(page, 29461)  # down -> Exit tile
            raw(page, 4)  # left -> Einstellungen
            raw(page, 29443)
            raw(page, 29443)
            page.wait_for_function("document.getElementById('status').textContent.indexOf('HTTP 200') >= 0")
            raw(page, 88)
            page.screenshot(path=str(artifacts / "browser-home.png"))
            # Rendering at typical legacy viewports; no old WebKit emulation claim.
            for width, height in [(960, 540), (1280, 720), (1366, 768)]:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_function("""size => {
                  var rect = document.getElementById('stage').getBoundingClientRect();
                  return window.innerWidth === size.width && window.innerHeight === size.height &&
                    rect.width <= size.width + 1 && rect.height <= size.height + 1;
                }""", arg={"width": width, "height": height})
                rect = page.locator("#stage").bounding_box()
                assert rect["width"] <= width + 1 and rect["height"] <= height + 1
            raw(page, 4)  # test video
            raw(page, 29443)
            if (ROOT / "media/test.mp4").exists():
                page.wait_for_function("document.getElementById('browser-video').currentTime > 0.2")
                assert "BROWSER" in page.locator("#player-status").inner_text()
                print("PASS: actual Chromium HTML5 video time advances (no TV/audio evidence)")
            else:
                print("SKIP: browser video playback; run tools/make_sample.py")
            raw(page, 88)
            assert page.locator("#home").is_visible()
            raw(page, 88)
            assert "BROWSER: Return" in page.locator("#status").inner_text()
            raw(page, 45)
            assert "BROWSER: Exit" in page.locator("#status").inner_text()
            assert not errors, errors
            # Separate context: native APIs are mocks, not a device emulator.
            native = browser.new_page(viewport={"width": 1280, "height": 720})
            native.add_init_script(MOCK)
            native_errors = []
            native.on("pageerror", lambda error: native_errors.append(str(error)))
            native.goto(url)
            assert native.evaluate("window.calls") == ["ready"]
            raw(native, 5)
            assert native.locator("#tile-1.focus").count() == 1  # one press, one movement
            raw(native, 5)
            raw(native, 29443)
            diagnostic = native.locator("#panel-text").inner_text()
            assert "SEF Open: true | Execute: true" in diagnostic
            assert "Legacy AVPlay getAVPlay: true" in diagnostic
            assert native.evaluate("window.calls") == ["ready"]
            raw(native, 88)
            raw(native, 4)
            raw(native, 4)
            raw(native, 29461)
            raw(native, 29443)
            assert native.evaluate("window.calls") == ["ready", "init", "area", "play"]
            assert native.evaluate("document.getElementById('pluginPlayer').OnCurrentPlayTime").startswith("LabPlayer.session")
            native.evaluate("""() => {
              var name = document.getElementById('pluginPlayer').OnCurrentPlayTime;
              window.LabPlayer[name.split('.')[1]](1000);
            }""")
            assert "Orsay Callback: 1 s" in native.locator("#player-status").inner_text()
            old_end = native.evaluate("document.getElementById('pluginPlayer').OnRenderingComplete")
            raw(native, 88)
            assert native.evaluate("window.calls").count("stop") == 1
            raw(native, 29443)  # restart the selected test video
            assert native.evaluate("window.calls").count("play") == 2
            assert native.evaluate("document.getElementById('pluginPlayer').OnRenderingComplete") != old_end
            native.evaluate("name => window.LabPlayer[name.split('.')[1]]()", old_end)
            assert native.evaluate("window.calls").count("stop") == 1
            assert "Start angefordert" in native.locator("#player-status").inner_text()
            raw(native, 88)
            assert native.evaluate("window.calls").count("stop") == 2
            raw(native, 88)
            raw(native, 45)
            assert native.evaluate("window.calls")[-2:] == ["return", "exit"]
            native.wait_for_function("LabLog.remoteStatus() === 'HTTP 204'")
            native.reload()
            native.evaluate("document.getElementById('pluginPlayer').StartPlayback = null")
            raw(native, 29461)
            raw(native, 29443)
            assert "Player API fehlt" in native.locator("#player-status").inner_text()
            assert native.evaluate("document.getElementById('browser-video').getAttribute('src')") is None
            assert not native_errors, native_errors
            broken = browser.new_page()
            broken.route("**/ui.js", lambda route: route.fulfill(
                content_type="application/javascript", body="throw new Error('Early startup failure');"))
            broken.goto(url)
            broken.wait_for_function("LabLog.remoteStatus() === 'HTTP 204'")
            # Wait for pending batches before inspecting the actual server log.
            native.wait_for_function("LabLog.remoteStatus() === 'HTTP 204'")
            page.wait_for_function("LabLog.remoteStatus() === 'HTTP 204'")
            records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            assert all(record["build"] == "0.1.7" for record in records)
            events = [event for record in records for event in record["events"]]
            assert any(event["kind"] == "key" and event["text"] == "29443" for event in events)
            assert any(event["kind"] == "diagnostics" for event in events)
            assert sum("JS-FEHLER: Startup test" in event["text"] for event in events) == 1
            assert any("Early startup failure" in event["text"] for event in events)
            assert "private" not in log_path.read_text(encoding="utf-8")
            print("PASS: packaged preview, navigation, Orsay key codes, return/exit, network probe, viewports")
            print("PASS: simulated Orsay lifecycle/player order, stop and missing-API failure")
            print("PASS: build label, passive API diagnosis, single key dispatch, remote logs and redaction")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def main():
    with tempfile.TemporaryDirectory(prefix="orsay-browser-") as tmp:
        check_browser(Path(tmp))


if __name__ == "__main__":
    main()
