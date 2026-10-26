# Orsay Lab for Samsung Smart TVs

A small diagnostic widget and development environment for Samsung's Legacy
Platform, also known as Orsay. It was originally prepared for the
UE32J4570SSXZG. The [2013 F-series UN40FH5303 test](docs/TV_TEST.md) installed
and launched build 0.1.1 on a real TV: native Orsay diagnostics and remote-key
events reached the server. The original UE32J4570 remains untested on-device.
The native player also reported completion of the 30-second sample. Visible
video and audible sound on the UN40FH5303 have not been confirmed.

The interface has been tested locally. Plex and YouTube are compatibility
checks, not integrated clients.

**Start with the [short TV test guide](docs/TV_TEST.md)** to try installation,
remote control input and the local test video. The widget currently uses German
screen labels; the guide names the buttons exactly as they appear. For the
UN40FH5303, try the F-series Smart Hub menu path, not the H/J-series hold-OK path.

## Browser preview

Build and server require Python 3.10+ and its standard library. Run these commands
from the project folder. On Windows, use `python` instead of `python3` if needed.

```bash
python3 tools/build.py --host 127.0.0.1 --port 8080
python3 tools/serve.py --bind 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/preview/index.html`. Use the arrow keys, Enter,
Escape/Backspace and F9 for a simulated Exit. Directory listings are disabled.

To create the 30-second test video, run `python3 tools/make_sample.py` once.
This requires FFmpeg with libx264 on PATH. The script generates the file locally;
it does not download footage. The server serves `media/test.mp4` separately from
the widget ZIP.

For a TV test, rebuild with the server's LAN IPv4 address and use port 80 for
both build and server. Both tools default to port 8080 for the browser preview.
On macOS, serving port 80 requires administrator authorization on this setup;
no privileges or changes to the TV's firmware are needed. See the
[full installation guide](docs/INSTALL.md) for details.

## Experimental Mac screen over DLNA

The UN40FH5303 advertises a DLNA/AllShare renderer on the LAN. An
[opt-in Mac streaming experiment](docs/MIRROR.md) can probe it without changing
the TV, then test a finite video, a synthetic live pattern and finally the
Mac screen in separate steps. This is **not AirPlay**, does not require
reinstalling the widget and is **not yet confirmed to work on the TV**.
The previous screen stream decoded to gray locally; its bitrate controls
caused gray frames even after the first attempt at a fix. An authorized
sustained local test now decodes desktop pixels and Mac system audio
(opt-in via `--system-audio`) from the same HTTP stream.
After the TV returned to the LAN, it requested the corrected stream and
reported advancing playback; nobody confirmed the picture or sound on its
panel. Screen/audio capture never starts during the read-only probe; see the
guide for the bounded TV test.

## Included

- Native Orsay Ready, key handling, Return and Exit in `widget/tv-orsay.js`.
- Local playback through the INFOLINK player; HTML5 playback in the preview.
- Passive detection of INFOLINK, SEF and Legacy AVPlay interfaces.
- User agent, viewport, raw key codes and error logs sent to the LAN server.
- A visible build version derived from `config.xml`, with an optional build number.
- A small UI adaptation from Free My TV with the full MIT notice.
- A deterministic offline build, `widgetlist.xml`, ZIP and SHA256 checksum.
- An HTTP server with CORS support and byte ranges for the test video.

`POST /log` writes sanitized events to `artifacts/tv-log.jsonl`. An unavailable
log server does not block the UI. The diagnostics screen shows the transfer
status. See [logging and build numbers](docs/INSTALL.md).

The prototype does not require root, firmware changes or a new media server.
It does not replace Smart Hub or provide autostart. Credentials are neither
required nor packaged. Git ignores `local.json`, generated media, build output
and the virtual environment.

## Documentation

| Document | Contents |
| --- | --- |
| [Short TV test](docs/TV_TEST.md) | Setup, installation and a quick pass/fail check |
| [Installation](docs/INSTALL.md) | Build options, LAN setup, sync menus and troubleshooting |
| [Device tests](docs/DEVICE_TESTS.md) | On-device observations and remaining checks |
| [Feasibility](docs/FEASIBILITY.md) | Platform, Plex, YouTube and unresolved limits |
| [Validation](docs/VALIDATION.md) | Local tests, UN40FH5303 observations and pending media checks |
| [Mac mirroring experiment](docs/MIRROR.md) | Optional DLNA checks and screen-capture consent |
| [Sources](docs/SOURCES.md) | Reviewed sources and what they establish |
| [Architecture](docs/ARCHITECTURE.md) | Runtime boundaries and possible next steps |
| [Licenses](THIRD_PARTY_NOTICES.md) | Adapted UI code and third-party references |

## Development tests

Python and Node.js tests require no extra packages. The browser test uses
Playwright and Chromium. An optional virtual environment keeps its dependencies
separate from the system Python installation.

```bash
python3 -m unittest discover -s tests -v
node --test tests/player.test.cjs tests/logging.test.cjs
# Optional browser checks:
python3 -m pip install -r requirements-dev.txt
python3 -m playwright install chromium
python3 tests/browser.py
```

The browser test checks the built preview and mocked Orsay APIs. It uses a
temporary build directory and leaves an existing LAN build in `dist/` intact.
Chromium and mocks do not prove compatibility with the TV.
