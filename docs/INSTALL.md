# Build and installation

For the shortest path, use the [TV test guide](TV_TEST.md). This document covers
build options, installation details and troubleshooting. Source IDs refer
to [SOURCES.md](SOURCES.md).

## 1. Prepare the TV and network

Record the model and firmware from the normal Support / Contact Samsung /
Software Information menus. Find the TV's IP address under Network. Menu names
depend on the firmware. Record the versions and current behavior of any installed
Plex and YouTube apps before syncing.

Note existing community widgets. On some older Smart Hub versions, syncing can
replace previously installed user apps.

The PC or existing Pi and the TV must be on the same reachable home network.
Guest networks and client isolation can block access. Use the IPv4 address of
the installation server, not the TV. The examples use `192.168.1.20`; replace it
with the server's actual address throughout.

Run the project on a computer in that network. Tizen Studio and an old Samsung
SDK download are not required.

## 2. Build a reproducible package

Python 3.10+ is sufficient for the build. From the project folder:

```bash
python3 tools/build.py --host 192.168.1.20 --port 80 --build-number 1
python3 tools/make_sample.py
```

On Windows, use `python` instead of `python3` if needed. Only the second command
requires FFmpeg with libx264. It creates a moving test pattern with a 440 Hz tone
as a one-time offline conversion.

Output:

```text
dist/widgetlist.xml
dist/OrsayLab_0.1.1_Europe.zip
dist/SHA256SUMS
dist/preview/index.html
media/test.mp4
```

The ZIP contains `config.xml`, `widget.info` and `index.html` directly at its root.
The builder uses a stable widget ID, `OrsayLab`, fixed file timestamps and sorted
ZIP entries. Identical inputs with the same Python/zlib versions produce identical
ZIP bytes. Changing the server IP or local configuration changes the checksum.
The test video is outside the ZIP and must remain available on the server.

### Build version

The version source is `<ver>` in `widget/config.xml`. `--build-number N` replaces
the last of its three numeric components, producing `0.1.1` in this example.
Use `--build-number 2` for the next TV build. Without that option, the source
version is used unchanged.

There is no automatic counter or current date in the ZIP name. The ZIP name,
package manifest, TV heading, diagnostics and logs share the same version.
Check the displayed version after syncing.

### Optional Plex network probe

Create an ignored `local.json` file to probe an existing Plex server:

```json
{"plexBaseUrl": "http://192.168.1.30:32400"}
```

Build with:

```bash
python3 tools/build.py --host 192.168.1.20 --port 80 --build-number 1 --config local.json
```

Omitted fields retain the generated defaults. `local.example.json` lists all
supported keys; empty values explicitly override defaults. Media/probe URLs and
player coordinates can be changed this way, followed by rebuilding and syncing.

Do not add tokens, passwords or Plex login details. The builder rejects unknown
keys, URL credentials, query strings and fragments. The optional HTTP probe does
not require changing Plex authentication or TLS settings.

## 3. Start the local HTTP server

The old TV installation menu usually accepts only an IP address, so
`/widgetlist.xml` must be reachable on port 80 [S5,S11]. Other ports work for
the browser preview but are not a confirmed TV installation method.

```bash
python3 tools/serve.py --bind 192.168.1.20 --port 80
```

Without `--port`, both tools use 8080. The server checks the download address
in `dist/widgetlist.xml` and warns if its port or bind address differs.
`--bind 0.0.0.0` listens on all IPv4 interfaces and does not cause a host warning.
The LAN IP embedded in the build must still be correct.

If Linux/macOS requires elevated privileges for port 80, the standard-library
server can be started with:

```bash
sudo python3 tools/serve.py --bind 192.168.1.20 --port 80
```

If port 80 is occupied, use another installation computer or configure an existing
local web server. Do not stop existing services without checking their purpose.
An alternative server must serve `/widgetlist.xml`, the ZIP, `/health.txt` and the
video at the generated URLs. Video delivery needs Content-Length, `video/mp4`
and byte-range/206 support. For remote logs, forward `POST /log` to the Python
server or implement the same receiver contract.

On Windows, allow the server through the firewall for the private network if
prompted. Router port forwarding is not required.

Check these URLs from a second device on the same home network:

```text
http://192.168.1.20/widgetlist.xml
http://192.168.1.20/health.txt
http://192.168.1.20/media/test.mp4
http://192.168.1.20/preview/index.html
```

`widgetlist.xml` must contain the current ZIP address and actual ZIP size.
A check from the server itself does not prove the TV can reach it.

### Receive diagnostics from the TV

The builder sets the log URL to `http://<build-host>:<build-port>/log`, independently
of any custom probe URL. The server appends each event batch as a JSON line to
`artifacts/tv-log.jsonl`, with receipt time, client IP and build version. This file
is outside `dist/`.

After the first events arrive, watch the file in a second PowerShell window:

```powershell
Get-Content artifacts/tv-log.jsonl -Wait
```

Events include startup diagnostics, diagnostic screen visits, raw key codes,
player startup return values and visible log entries, including `window.onerror`.
URLs and known credential patterns are sanitized before sending and on receipt.
API checks detect interfaces only; they do not open SEF or AVPlay players.

Sending is asynchronous, in small batches, with at most 64 queued events.
Failed batches are dropped without recursive error logs or automatic retries.
If the queue fills, older events are discarded; closing the widget can also
lose pending events. The on-screen log remains available. The receiver limits
each POST to 32 KiB. Image and sound must still be checked directly on the TV.

## 4. Sync on the TV

Community instructions distinguish the 2013 F-series menus from H and selected
J/K models [S5]. The UN40FH5303 installed and launched build 0.1.1 through this
route on 2026-10-24, confirmed by the icon on the TV and native diagnostics and
remote-key events reaching the server. Physical picture and sound are not yet
confirmed. Installation on the original J4570 remains unverified.
For the UN40FH5303, follow the [F-series TV test](TV_TEST.md):

1. Menu > Smart Features > Samsung Account > Log In. Enter `develop` as the
   Email; the F-series reference does not require a password.
2. Smart Hub > Apps > More Apps > Options > IP Setting. Enter the **server's**
   IP (`192.168.1.20` in this example), not the TV's IP.
3. Options > Start App Sync. Watch the server for GETs of `widgetlist.xml`
   and the ZIP; leave and reopen Smart Hub if needed.
4. Open Orsay Lab from More Apps and check the displayed build and diagnostics.

For the original J4570 target, H/J community instructions [S5] and the
archived installer [S3] suggest the following path; it is also unverified:

1. Open Menu > Smart Hub > Samsung Account > Sign in. The local developer account
   is `develop`. Some models require no password; the reference otherwise lists
   `000000`. This is not a personal Samsung account password.
2. Open Smart Hub > Samsung Apps / My Apps fully.
3. Highlight an installed app and hold OK/Enter for a few seconds.
4. If available, select **IP Setting** and enter the server IP, `192.168.1.20`.
5. Hold OK again and choose **Start User App Sync**. Watch the server console.
6. Find and open **Orsay Lab** in My Apps. If needed, close and reopen Smart Hub.
   Record the result and the exact menu path.

Other Orsay interfaces use Tools > Settings > Development > Server IP and user
app synchronization. The RED/BLUE menu path in [S3] applies to other Orsay
versions and is not a verified F/J procedure. Do not substitute the Tizen
"Apps, 12345" instructions.

If the account, IP setting or sync option is missing, record the firmware and
visible menus and stop there. A service menu, factory reset or firmware downgrade
is not part of this procedure.

## 5. Troubleshoot using the logs

| Observation | Next check |
| --- | --- |
| No GET for widgetlist.xml | LAN IP, port 80, firewall, develop login and sync menu |
| XML fetched, ZIP not fetched | Download URL, port, widget list and ZIP name |
| ZIP fetched, app missing | Record the TV error; package/firmware compatibility remains open |
| App starts with a blank screen | Record the screen and API/JS errors; Chromium does not prove Legacy WebKit compatibility |
| No navigation | Raw key codes, key-anchor focus and TVKeyValue |
| Black video | Check UI transparency/video plane, plugin events, range requests and codec separately |
| Video without sound | Volume/output and AAC track; a callback does not prove audible sound |
| XHR status 0 | CORS, TLS and network failure are indistinguishable here; compare server logs and local HTTP |

The installed UI works without the server. Keep the server running for video,
network probes and remote logs. To update, rebuild with the same widget ID and
sync again, then verify the displayed build version. To remove the widget, use
the normal app manager and stop the server with Ctrl+C.
