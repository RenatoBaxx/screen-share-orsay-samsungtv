# Reviewed sources

Retrieved 2026-10-22. Official documentation and community reports are assessed
separately. Linked downloads that were not read do not count as reviewed.

These notes describe the sources at the time of review. Translation does not
constitute a fresh check of current service support.

| ID | Source | Relevant finding |
| --- | --- | --- |
| S1 | [Samsung TV Model Groups](https://developer.samsung.com/smarttv/develop/specifications/tv-model-groups.html) | 2015, 15TV_ENTRY, UJ4570, Samsung Legacy Platform, TV SDK 5.1. Samsung lists the model family, not the full regional suffix. |
| S2 | [Free My TV](https://github.com/simbasjungles/free-my-tv), [tv.js](https://github.com/simbasjungles/free-my-tv/blob/main/web/tv.js), [home.js](https://github.com/simbasjungles/free-my-tv/blob/main/web/home.js), [home.css](https://github.com/simbasjungles/free-my-tv/blob/main/web/home.css), [MIT](https://github.com/simbasjungles/free-my-tv/blob/main/LICENSE) | ES5 web UI, Tizen detection through window.tizen.application, getAppsInfo/launch, Return 10009. No existing Orsay adapter. The README specifies Tizen 3+ from 2017. |
| S3 | [Jellyfin-Orsay-Installer](https://github.com/Apps2Samsung/Jellyfin-Orsay-Installer) | Archived/end of life. Widget packaging, local server and develop/IP/sync flow. A reference only; installation on J4570 was not tested. |
| S4 | [OrsayPackager.cs](https://github.com/Apps2Samsung/Jellyfin-Orsay-Installer/blob/master/Jellyfin-Orsay-Installer/Services/OrsayPackager.cs), [KestrelOrsayServer.cs](https://github.com/Apps2Samsung/Jellyfin-Orsay-Installer/blob/master/Jellyfin-Orsay-Installer/Services/KestrelOrsayServer.cs) | rsp stat=ok, list/widget, compression size/type, absolute download URL and HTTP delivery. The local tool uses this structure without a .NET dependency. |
| S5 | [Emby Orsay Community Install Instructions](https://emby.media/community/topic/9869-samsung-orsay-smarttv-2011-2015-community-app-install-instructions/) | F-series (2013): Menu > Smart Features > Samsung Account > Log In as `develop` (no password), then Smart Hub > Apps > More Apps > Options > IP Setting > Start App Sync. H and selected J/K models use the different hold-Enter menu. Local HTTP server on port 80. The F-series path was subsequently exercised on UN40FH5303 (see [validation](VALIDATION.md)); installation on J4570 remains unverified. Historical community instructions. |
| S6 | [Samsung: Migrating Legacy Platform to Tizen](https://developer.samsung.com/smarttv/develop/migrating-applications/migrating-legacy-platform-to-tizen.html) | Legacy config.xml/widget.info are incompatible with Tizen; Widget.js sendReadyEvent/sendReturnEvent/sendExitEvent, different key codes and player plugin. Some code blocks were served empty; missing signatures were not inferred from them. |
| S7 | [Samsung Legacy API References](https://developer.samsung.com/smarttv/legacy/api-references.html) | Archived Legacy classes including NNavi, TaskManager, AppCommon and Player. A class listing alone does not establish a usable app-launch contract. |
| S8 | [Samsung cordova-sectv-orsay platform.js](https://github.com/samsung/cordova-sectv-orsay/blob/master/cordova-js-src/platform.js) | Original Samsung code with Orsay keys 29460/29461/4/5/29443/88, Exit 45 and Ready/Return lifecycle. No Cordova dependency was introduced. |
| S9 | [MediaBrowser/SamsungSmartTV](https://github.com/MediaBrowser/SamsungSmartTV), [config.xml](https://github.com/MediaBrowser/SamsungSmartTV/blob/master/config.xml), [widget.info](https://github.com/MediaBrowser/SamsungSmartTV/blob/master/widget.info), [index.html](https://github.com/MediaBrowser/SamsungSmartTV/blob/master/index.html), [GuiPlayer.js](https://github.com/MediaBrowser/SamsungSmartTV/blob/master/app/javascript/Gui/GuiPlayer/GuiPlayer.js) | Samsung XML namespace, root-level files, Common API paths, SAMSUNG-INFOLINK-PLAYER classid, named global callback strings and SetDisplayArea at 960×540. Reviewed as an API/package reference, not a server replacement. |
| S10 | [Plex: Which Smart TV models are supported?](https://support.plex.tv/articles/204080173-which-smart-tv-models-are-supported/) | Official Samsung app for Tizen models from 2016. Certificate limitations on many Samsung models. No current support assurance for Orsay/J4570. The generic Limited Playback table is not a J4570 specification. |
| S11 | [kadrim/proxy4plex README](https://github.com/kadrim/proxy4plex/blob/main/README.md) | Historical Orsay candidate: Orca's Plex app 2.014, network sideloading and a TLS proxy for E/F/H with TLS up to 1.1 according to the project. J4570 TLS and current operation are unproven. The linked client binary was not downloaded, adopted or installed. |
| S12 | [Plex Community: link not generating code](https://forums.plex.tv/t/plex-tv-link-not-generating-code-on-samsung-smart-tv/763431/19) | Posts from 2021 describe login/sideloading problems and proxy4plex attempts. Historical reports do not establish behavior on this model or firmware. |
| S13 | [YouTube: Unsupported device models](https://support.google.com/youtube/answer/6098135?hl=en) | New requirements can exclude old devices/apps. No explicit J4570 list. Suggested firmware updates are not a prerequisite of this project. |
| S14 | [YouTube IFrame Player API](https://developers.google.com/youtube/iframe_api_reference) | Embedded player requiring HTML5 postMessage. No Orsay compatibility assurance or direct InitPlayer URL interface. |
| S15 | [rfaile313/samsucks](https://github.com/rfaile313/samsucks) | Search results and repository description target Tizen/AVPlay and newer TVs, not a directly matching Orsay client. No detailed code review was performed. |

The Free My TV source files were read through GitHub and retained as local content
snapshots. Their SHA256 hashes are in `research/upstream-manifest.json`. These
bytes record what was retrieved from main; no unverified Git commit is claimed.
The build does not fetch moving upstream references.

The Samsung Legacy page also links an API archive. That archive and an old SDK
were not downloaded. The reviewed migration notes and reference implementations
support the first prototype; further device-specific APIs remain to be verified.
