# Quick TV test (Samsung UN40FH5303, 2013 F-series)

Goal: install Orsay Lab, check the remote and play the local test video on the
UN40FH5303. This is a diagnostic widget, not a replacement for Smart Hub.
The UN40FH5303 installed and launched build 0.1.1 on 2026-10-24: the user saw
its icon, and native Orsay diagnostics and remote-key events reached the server.
The native player reported completion of the 30-second sample on a second
attempt; physical video and sound remain unconfirmed. The original UE32J4570
remains untested on-device.
The interface uses German labels: **Diagnose** is diagnostics, **Testvideo**
is the test video, **Beenden** is Exit and **Zurück** means Return.

## 1. Prepare the computer

You need Python 3.10+, FFmpeg with libx264 on PATH, and the project folder.
Connect the computer and TV to the same reachable home network. On a Mac,
run `ipconfig getifaddr en0` to find its current LAN IPv4 address (use the
active interface if not `en0`). The example below uses `192.168.1.20`;
replace it with the **Mac's** address, not the TV's address or `127.0.0.1`.
Run from the project folder:

```bash
python3 tools/make_sample.py
python3 tools/build.py --host 192.168.1.20 --port 80 --build-number 1
sudo python3 tools/serve.py --bind 192.168.1.20 --port 80
```

Port 80 requires administrator authorization on macOS. Enter the password
only in the Mac's own Terminal prompt; do not put it in a config file or send
it to anyone. Leave the server window open. On Windows, find the address with
`ipconfig`, use `python` instead of `python3` if needed, omit `sudo` and allow
the server through the private-network firewall if prompted.

On a phone on the same Wi-Fi, open
`http://192.168.1.20/health.txt`. It should show `Orsay Lab installation server OK`.
If it does not, fix the connection before continuing.

## 2. Install on the TV

Note the model, firmware and installed community apps first. Sync can replace
other user apps on some older Smart Hub versions.

For this 2013 F-series model, use the F-series community procedure [S5],
not the H/J-series hold-OK menu:

1. Press **Menu** > **Smart Features** > **Samsung Account** > **Log In**.
   Enter `develop` in the Email field. The F-series reference says the password
   field is inaccessible; if your TV asks for something else, record it.
2. Press **Smart Hub** > **Apps** > **More Apps** > **Options** > **IP Setting**.
   Enter the **computer's** IPv4 address, `192.168.1.20` in this example.
   You do not enter the TV's own IP here.
3. Select **Options** > **Start App Sync**. Watch the server window for a
   request for `widgetlist.xml` and then the ZIP. Reopen Smart Hub if the
   synchronization only reports that it was requested.
4. Open **Orsay Lab** from **More Apps**. The heading should show
   **Build 0.1.1**; **Diagnose** should report the TV's model if NNavi supports it.

Menu names vary with language and firmware. If these options are missing,
record the menus and stop. Do not reset the TV or change its firmware. See
[INSTALL.md](INSTALL.md) for H/J-series steps and troubleshooting.

## 3. Check the remote and logs

Press each arrow once. Selection should move once per press when another tile
exists in that direction. Open **Diagnose** and look for **Log-Rückkanal: HTTP 204**.
Return should close the panel.

Logs appear on the computer in `artifacts/tv-log.jsonl`. Once the file exists,
you can watch it in a second Mac Terminal window:

```bash
tail -f artifacts/tv-log.jsonl
```

On Windows, use PowerShell instead:

```powershell
Get-Content artifacts/tv-log.jsonl -Wait
```

## 4. Play the video

Open **Testvideo**. Check for a moving pattern and an audible tone for at least
20 seconds. Press Return to stop it, then repeat twice. Finally test Exit.
Keep the server running throughout.

A running time counter alone is not a pass. You need visible movement and sound.
Plex and YouTube playback are separate tests; this widget does not include clients.

## 5. Save the result

Record the model, firmware, displayed build, installation result, remote behavior,
picture, sound and any error text. Keep `artifacts/tv-log.jsonl`. If remote logging
fails, photograph the diagnostics screen. Use [DEVICE_TESTS.md](DEVICE_TESTS.md)
for the observations already recorded and the remaining Plex/YouTube checks.
