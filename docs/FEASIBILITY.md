# Feasibility

Assessment date: 2026-10-22. Source IDs refer to [SOURCES.md](SOURCES.md).

## Assessment

A small Orsay widget is a reasonable experiment. A reliable Plex/YouTube
replacement running directly on this TV has not been demonstrated.

Community instructions describe installation without firmware changes, but the
available Smart Hub menus and firmware determine whether it works. The first
checks are installation, remote input and actual video playback. Installation
and native remote-key events have since been confirmed on the UN40FH5303;
physical video playback and the original J4570 remain untested.

| Goal | Evidence / assessment | Still to confirm |
| --- | --- | --- |
| Platform | Samsung lists UJ4570 under 15TV_ENTRY, Legacy Platform, SDK 5.1 [S1] | Full model suffix and firmware on the device |
| Custom widgets | ZIP with config.xml, widget.info and index.html; local HTTP and widgetlist.xml [S3-S5] | develop login, sync menu and installation on UE32J4570 |
| Remote input | Legacy Widget API and TVKeyValue; codes from Samsung's implementation [S6-S8] | Physical keys, focus, Return and Exit on this TV |
| Local video | Documented Legacy Player plugin and a matching reference client [S6,S9] | Image, sound, stream events, stop and stability |
| Plex | Official Samsung app support covers Tizen models from 2016 [S10]; historical Orca client is a candidate [S11,S12] | Installed version, login, compatibility with the current PMS and Direct Play |
| YouTube | Reviewed sources do not provide a model-specific assurance [S13,S14] | Installed app, signed-out playback and login |
| UI port | ES5 and small CSS helpers are reusable; the upstream Samsung adapter targets Tizen [S2] | Old WebKit, performance and overscan |

The reported panel resolution, 1366×768, came from the project handoff and was
not measured on the TV. Panel resolution, widget viewport and player coordinates
may differ. Diagnostics therefore report the viewport. The UI scales from
1280×720; the Legacy video plane starts at 960×540 based on [S9]. These assumptions
require a device test and are not a decoder specification.

## Platform and installation

Not every 2015 Samsung TV runs Tizen. Samsung explicitly maps
`UJ4570 > 15TV_ENTRY > Samsung Legacy Platform > TV SDK 5.1` [S1].
The full regional suffix `SSXZG` is not listed separately.

Samsung states that Legacy config.xml and widget.info files are incompatible
with Tizen. Lifecycle, key codes and player APIs also differ [S6]. Tizen WGT,
SDB, TizenBrew and the Tizen "Apps, 12345" procedure are not the installation
method prepared here.

The reference installer [S3] is archived/end of life. Its packaging and server
code were reviewed [S4]; its binary was not run. The local builder uses the same
basic structure: a stable widget ID, ZIP size in bytes and an absolute HTTP
download URL.

The community instructions [S5] describe develop login, holding OK on an app,
IP Setting and Start User App Sync for H and selected J/K models. They do not
explicitly list J4570 as tested. Installation must therefore be checked on the TV.
The same source documents a separate 2013 F-series menu path. The
[UN40FH5303 test guide](TV_TEST.md) follows that path. On this model, the widget
launched and sent native diagnostics and remote-key events to the server;
picture, sound and player stability still require direct observation.

Firmware changes, a service menu, root access and a Smart Hub reset are not
prerequisites. If menus are missing, record the current state first. USB
installation is not a confirmed fallback because support varies by model.
The installation server must be reachable from the TV's LAN.

## Playback risks

| Area | Assessment and first check |
| --- | --- |
| Codec / container | The generated MP4 uses H.264 Constrained Baseline, Level 3.1, 8-bit yuv420p, 1280×720 at 25 fps and AAC-LC stereo. This is a conservative test, not a hardware guarantee. Then check real Plex files individually by codec, profile, level, audio, subtitles and bitrate. Do not assume HEVC, AV1, DTS or complex subtitles work. |
| Network | Installation, the XHR probe and native playback use separate paths. Test local HTTP, MIME types, Content-Length and Range/206 first. HTTP 200 from /identity proves reachability only; XHR status 0 can mean CORS, TLS or network failure. Assess LAN throughput separately from decoder performance. |
| TLS / certificates | Legacy clients may fail on TLS versions, cipher suites, SNI or root certificates. proxy4plex reports TLS up to 1.1 for E/F/H [S11]; this is not a measured J4570 limit. Plex documents certificate limitations for many Samsung models [S10]. The local HTTP video avoids TLS only for that test. TLS verification is not disabled. |
| Service / authentication | plex.tv login, current PMS behavior, token use and YouTube player requirements are independent of the decoder. A working MP4 does not repair login, a discontinued app or an obsolete service API. |

### Plex

1. Before making changes, open the installed Plex app. Record its version,
   anonymously/offline-accessible library, login behavior and playback of a
   suitable file.
2. A historical candidate is Orca's Samsung Plex app 2.014. proxy4plex [S11]
   describes the package, network sideloading and a TLS proxy for older E/F/H
   models. The Plex forum thread [S12] records real login and installation
   problems. These are historical community reports, not a current J4570
   compatibility assurance. Package availability, provenance, usage rights and
   current server compatibility were not verified. No client binary was
   downloaded or distributed.
3. If TLS alone blocks control requests, a limited LAN intermediary could be
   investigated. It would not be a new Plex server or a transcoding solution.
   proxy4plex is not installed or required by this project.
4. If the old client is unusable, a small ES5 Plex client is technically
   plausible: protected server access, library metadata, selection of one
   compatible file, Direct Play through the Orsay player, then resume/seek.
   This requires further implementation and device tests.

The prototype's Plex tile explains this order and can optionally request
`/identity` from the existing PMS. It does not browse the library, store a token
or launch an installed app. Free My TV uses `tizen.application.getAppsInfo/launch`
for app discovery/launch [S2]. A working Orsay launch path and reliable IDs for
the installed Plex/YouTube widgets were not established in the reviewed sources.

Jellyfin/Emby Orsay code [S3,S9] demonstrates the widget/player pattern, but does
not replace a Plex client and uses a different server protocol. The reviewed
community Plex client samsucks targets Tizen [S15]. These projects are not
directly usable Plex Orsay replacements.

The Raspberry Pi is treated only as the existing PMS. The first Plex test should
show **Direct Play** in the dashboard. Measure Direct Stream/remux, audio
transcoding and video transcoding separately. Depending on the Pi, file and
subtitles, transcoding may exceed its capacity. If video transcoding is needed,
test a preconverted copy first; do not assume arbitrary real-time conversion or
change server settings automatically.

### YouTube

Open the installed app from Smart Hub. Test playback without login, then with
the existing account. YouTube's general help describes retired devices and
changing security requirements [S13], but does not give a clear UE32J4570 verdict.

A thin custom web client does not automatically solve this. The official IFrame
Player API requires an embedded YouTube player and HTML5 postMessage [S14].
That does not establish compatibility with this old WebKit or its TLS/video
capabilities. It is not an API for passing an arbitrary YouTube page URL to
InitPlayer.

Stream extraction or external resolvers would be a separate maintenance-heavy
project and are not implemented. The reviewed sources did not establish a
reliable current Orsay YouTube client. This was not an exhaustive survey of all
community projects.

## Decision after the first tests

- If installation fails, investigate menus, firmware and network access before
  extending the UI. HDMI remains available without changing the TV OS.
- If the widget, keys and local MP4 work, test Plex Direct Play with the existing
  client. Build a small custom Plex client only if needed.
- If YouTube service access fails, the complete native setup still misses the
  goal even if Plex works. Assess the HDMI fallback.
- If both services work, extend the Free My TV launcher. Investigate autostart
  and Smart Hub replacement later as separate tasks.
