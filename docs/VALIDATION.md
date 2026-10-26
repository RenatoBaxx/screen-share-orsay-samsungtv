# Local validation report

Status: 2026-10-23. No connection to the TV or its home network was made, and no
real Plex server was queried. Documentation establishes the Samsung model-group
mapping; it does not prove runtime behavior on the device.

## Initial checks on 2026-10-22

Recorded environment: Python 3.12.14, Playwright 1.62.0, Chromium 154.0.8037.57 and
FFmpeg. A virtual environment had access to preinstalled system packages.
Shell network access through the supplied proxy was unavailable, so sources were
read through Firecrawl and the GitHub connector. The build itself runs offline.
Local HTTP/browser checks used permitted network sockets.

| Check | Result and limits |
| --- | --- |
| Four Python unit tests | Passed: ZIP structure, licenses, XML, size, identical ZIP bytes for identical inputs, configuration validation, HTTP Range/HEAD/416 and CORS/probe/404. This is not formal Samsung SDK certification. |
| Actual Chromium, built preview | Passed: arrows/Enter/Escape, Legacy codes, focus, diagnostics, HTTP 200 probe and browser Return/Exit requests. |
| Viewports | At 960×540, 1280×720 and 1366×768 the stage stayed within the window. The 1366×768 screenshot was visually checked. TV overscan was not tested. |
| Actual browser media playback | The generated MP4 loaded through the local range server and HTML5 currentTime advanced. Headless playback does not establish audible sound or Orsay decoder behavior. |
| Mocked Orsay APIs | Passed: Ready, native InitPlayer > SetDisplayArea > StartPlayback, callback, Stop, Return and Exit. Missing native APIs produced a visible error without a silent HTML5 fallback. Mocks do not emulate the hardware. |
| JS runtime errors | No pageerror events in the successful browser checks. |
| Test file checked with ffprobe | 30.000 seconds; H.264 Constrained Baseline L3.1, 1280×720, 25 fps, yuv420p; AAC-LC, two channels; 7,266,045 bytes for that generated file. |

The code uses ES5-style var declarations and functions, without modules, classes,
async/await or Promise construction. No framework or external asset is required.
Neither a formal ES5 parser nor Legacy WebKit was run. Chromium also accepts
modern syntax, so these checks do not replace an Orsay compatibility test.

The browser preview removes only the on-device `$MANAGER_WIDGET` script tags.
The actual widget ZIP retains them. Native integration checks install explicit
mock objects before the app loads.

## Player-fix checks on Windows

Rechecked on 2026-10-22 with Python 3.11.9 and Node.js 22.15.0:

- All four Python unit tests passed.
- Thirteen player regression tests passed with a virtual clock and explicit
  native/HTML5 mocks. They cover stalls despite repeated time callbacks,
  invalid/decreasing values, genuine subsecond progress, delayed events after
  stop/restart, recursive Stop events, synchronous startup errors, missing APIs,
  rejected starts and natural completion.
- The mocks run without a browser or extra packages using
  `node --test tests/player.test.cjs`. Node.js is a development dependency only;
  packaging and the installation server use Python.
- The browser test passed with Playwright 1.62.0 and Chromium 151.0.7922.34 in a
  local virtual environment. The newly generated video played through HTML5.
  Navigation, network probe, viewports and the mocked Orsay lifecycle also
  passed, including a restart with a delayed end callback from the previous
  session. This did not establish TV behavior or audible sound.

## Diagnostic-change checks on 2026-10-23

Checked on Windows with Python 3.13.2, Node.js 24.16.0, Playwright 1.62.0 and
Chromium 151.0.7922.34. Playwright was installed in a local virtual environment.
The existing FFmpeg installation generated a new test video.

- Six Python tests passed, including explicit package versioning, reproducible
  ZIPs, port/bind checks, log receipt, sanitization and rejection of invalid or
  oversized log requests.
- All thirteen existing player tests and three new log transport tests passed.
  The latter cover queued startup errors, timeouts without recursive error
  reporting, a bounded queue and only one request in flight.
- The browser test passed with actual HTML5 video progress, existing navigation
  and the mocked Orsay lifecycle. New checks cover the build label, passive
  SEF/AVPlay detection, one-time key processing and remote logging, including
  an error before UI startup.
- An existing build in `dist/` remained byte-identical after the browser test.
  Every file was compared using its SHA256 hash.
- The diagnostics page fit within the checked layout without clipped text.
  The heading and diagnostics at 1366×768 were checked in screenshots.
  Transfer status updated to HTTP 204 without another key press.

These are local browser and mock checks. Library loading, plugin detection,
XHR transmission and remote input still need confirmation on Orsay.
Playback through SEF and AVPlay was not implemented.

## F-series preparation on macOS, 2026-10-24 (before TV sync)

For the proposed UN40FH5303 test, the widget heading no longer claims to be
running on the original UE32J4570. The installation guide now uses the 2013
F-series developer menus rather than the H/J hold-OK path. No TV behavior was
inferred from these changes.

- Six Python package/server tests and sixteen Node.js player/logging tests passed.
- The Playwright Chromium test passed, including the exact generic build label,
  remote navigation, simulated Orsay APIs, HTTP logging and real HTML5 video
  progress. Chromium is not the TV's Legacy WebKit.
- FFmpeg generated a 30-second H.264 Constrained Baseline 1280x720 / AAC-LC
  test file. `ffprobe` confirmed its streams and duration.
- An installation ZIP and `widgetlist.xml` were built for the Mac's current
  LAN IP on port 80. A temporary server on port 8080 answered HTTP 200 for
  health, manifest and ZIP, and HTTP 206 for a video byte range. This checks
  LAN binding on the Mac, not access from the TV or installation via port 80.
- The TV later appeared on the LAN: SSDP/UPnP reported modelName
  `UN40FH5303`, and the host responded to ping. This establishes reachability
  from the Mac, not that the TV can fetch the widget or run it. At this
  preparation stage, port 80 could not be bound without administrator
  authorization; no password or on-device interaction was available.

## UN40FH5303 installation and startup, 2026-10-24

The user started the port-80 server on the Mac and reported **Orsay Lab** in
the TV's apps. The server subsequently received diagnostic batches from the
TV's LAN address, reporting build `0.1.1` in native Orsay mode. The device
reported `Widget: true`, `Ready gesendet: true` and `TVKeyValue: true`;
left/right/up/down/OK key codes arrived from the remote. Samsung's NNavi
reported `13_X12_2D`, while UPnP reported the full model `UN40FH5303`.

The native player reported `InitPlayer` and `StartPlayback` return value `1`,
followed by `StreamInfoReady`, buffering and buffer-ready events. A Return key
arrived about 19 seconds after the first start, before the 20-second
no-progress watchdog could fire. In a second attempt, `OnRenderingComplete`
arrived about 32 seconds after starting the 30-second sample, with no
logged timeout or player error. This is evidence that the native player
reached the end of the stream, **not proof of a visible moving picture or
audible sound**. Progress callbacks update the on-screen status but are not
sent to the server log; their absence there cannot establish a stall. No
physical image/audio result or firmware version has been reported. The native
player was exercised; the other detected Orsay interfaces were not. Physical
video/audio, remote navigation feedback and the other on-device checks below
remain open.

## Not yet tested

- Installation, menus, firmware compatibility and runtime on UE32J4570.
- Physical image/overscan, navigation feedback, Return/Exit and focus after returning on UN40FH5303.
- On-screen playback progress, visible video plane, audible sound, repeated starts and long runs.
- PMS authentication, Direct Play of real library files and Pi load.
- Launch, playback and login in the installed Plex and YouTube apps.
- TV TLS versions, certificate store, codec limits and service compatibility.

## Repeat the checks

```bash
python3 tools/make_sample.py
python3 -m unittest discover -s tests -v
node --test tests/player.test.cjs tests/logging.test.cjs
python3 tests/browser.py
```

Use `python` instead of `python3` on Windows if needed. Install the browser test
dependencies using the [README instructions](../README.md) first.

The video is required for the playback check; without it, the browser test marks
that section as skipped. Screenshots are saved under `artifacts/`. The browser
test builds and serves from a temporary directory on a temporary port, leaving
an existing `dist/` intact. For home-network installation, build with the actual
server IP and port 80.
