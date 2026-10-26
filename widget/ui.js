/* Minimal shell. fit/setClass/el adapted from Free My TV web/home.js (MIT).
 * See licenses/free-my-tv-MIT.txt and THIRD_PARTY_NOTICES.md.
 */
var Lab = (function () {
  'use strict';
  var selected = 0, panel = -1, playing = false, request = null;
  function $(id) { return document.getElementById(id); }
  function setClass(e, c, on) {
    var has = (' ' + e.className + ' ').indexOf(' ' + c + ' ') >= 0;
    if (on && !has) e.className = (e.className + ' ' + c).replace(/^\s+/, '');
    else if (!on && has) e.className = (' ' + e.className + ' ').replace(' ' + c + ' ', ' ').replace(/^\s+|\s+$/g, '');
  }
  function fit() {
    var scale = Math.min(window.innerWidth / 1280, window.innerHeight / 720);
    $('stage').style.webkitTransform = $('stage').style.transform = scale === 1 ? '' : 'scale(' + scale + ')';
  }
  function focus() {
    for (var i = 0; i < 6; i++) setClass($('tile-' + i), 'focus', i === selected);
    OrsayTV.focus();
  }
  function status(text) { $('status').textContent = text; }
  function show(title, text, help) {
    $('home').style.display = 'none'; $('panel').style.display = 'block';
    $('panel-title').textContent = title; $('panel-text').textContent = text;
    $('panel-help').textContent = help || 'Zurück: Startseite · Exit: Beenden';
  }
  function close() {
    if (request) { request.abort(); request = null; }
    LabPlayer.stop(); playing = false; panel = -1;
    $('playback').style.display = 'none'; $('panel').style.display = 'none';
    $('home').style.display = 'block'; document.body.className = '';
    document.documentElement.className = '';
    focus();
  }
  function activate() {
    if (panel === 4) { probe(LAB_CONFIG.probeUrl, 'Installationsserver'); return; }
    if (panel === 0) {
      if (!LAB_CONFIG.plexBaseUrl) { status('plexBaseUrl fehlt. Siehe local.example.json.'); return; }
      probe(LAB_CONFIG.plexBaseUrl.replace(/\/$/, '') + '/identity', 'Plex /identity'); return;
    }
    if (panel !== -1 || playing) return;
    panel = selected;
    if (selected === 0) {
      show('Plex · noch kein Plex-Client', 'Bestehende Plex-App zuerst direkt im Smart Hub öffnen.\nApp-Version, Serververbindung, Bild/Ton und Direct Play notieren.\n\nKein bestätigter Orsay-Aufrufweg / keine App-ID für dieses Gerät.\nOK prüft optional nur /identity am vorhandenen Plex-Server.\nEin HTTP-Erfolg beweist weder Anmeldung noch Videowiedergabe.', 'OK: Plex-Netztest · Zurück: Startseite');
    } else if (selected === 1) {
      show('YouTube · Gerätetest offen', 'YouTube zuerst direkt im Smart Hub öffnen und ein Video abspielen.\nAnmeldung und anonyme Wiedergabe getrennt testen.\n\nDieser Prototyp enthält keinen YouTube-Client.\nKeine erratene Tizen-App-ID, kein eingebetteter Web-Player.\nBei fehlender Dienstkompatibilität ist HDMI die Ausweichlösung.');
    } else if (selected === 2) {
      show('Gerätediagnose', OrsayTV.diagnostics());
      LabLog.record('diagnostics', OrsayTV.diagnostics());
    } else if (selected === 3) {
      playing = true; $('home').style.display = 'none'; $('panel').style.display = 'none';
      $('playback').style.display = 'block'; document.body.className = 'playing';
      document.documentElement.className = 'playing';
      LabPlayer.play(LAB_CONFIG.mediaUrl, function (text) { $('player-status').textContent = text; });
    } else if (selected === 4) {
      show('Einstellungen / Netztest', 'Konfiguration erfolgt am Rechner über local.json und erneuten Build.\nKeine Bildschirmtastatur nötig. Keine Tokens im Paket.\n\nTestvideo gesetzt: ' + !!LAB_CONFIG.mediaUrl + '\nPlex-Server gesetzt: ' + !!LAB_CONFIG.plexBaseUrl + '\nProbe-URL gesetzt: ' + !!LAB_CONFIG.probeUrl + '\nPlayer-Ebene: ' + LAB_CONFIG.playerWidth + ' x ' + LAB_CONFIG.playerHeight + '\n\nNetztest und Player verwenden getrennte Netzwerkpfade.\nXHR status 0 unterscheidet CORS / TLS / Netzwerk nicht.', 'OK: HTTP-Netztest · Zurück: Startseite');
    } else if (selected === 5) { panel = -1; leave(true); }
  }
  function probe(url, label) {
    if (!url) { status('Keine Probe-URL konfiguriert.'); return; }
    if (request) { status('Netztest läuft bereits.'); return; }
    var xhr = new XMLHttpRequest(), completed = false;
    request = xhr; status(label + ': Anfrage läuft …');
    var timer = setTimeout(function () { finish('Timeout nach 8 s'); xhr.abort(); }, 8000);
    function finish(text) {
      if (completed) return;
      completed = true; clearTimeout(timer); request = null;
      status(label + ': ' + text); LabLog.add(label + ': ' + text);
    }
    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4) finish('HTTP ' + xhr.status + (xhr.status === 0 ? ' (CORS / TLS / Netz offen)' : ' · kein Wiedergabenachweis'));
    };
    xhr.onerror = function () { finish('Netzfehler (CORS / TLS / Netz offen)'); };
    xhr.onabort = function () { finish('abgebrochen'); };
    try { xhr.open('GET', url, true); xhr.send(null); }
    catch (e) { finish('XHR FEHLER: ' + LabLog.clean(e.message)); }
  }
  function leave(exit) {
    LabPlayer.stop();
    var sent = OrsayTV.leave(exit);
    status((sent ? 'TV: ' : 'BROWSER: ') + (exit ? 'Exit' : 'Return') + ' angefordert; Übergang am Gerät prüfen.');
  }
  function key(event) {
    event = event || window.event;
    var code = event.keyCode || event.which, action = OrsayTV.action(code);
    if (!action) { status('Unbekannter Tastencode: ' + code); return; }
    /* Leave EXIT's native default intact. RETURN is blocked only when handled internally. */
    if (action === 'exit') { leave(true); return; }
    if (action === 'back' && panel === -1 && !playing) { leave(false); return; }
    OrsayTV.block(event);
    status('Taste ' + code + ' → ' + action + ' · Auswahl ' + (selected + 1));
    if (action === 'back' || (action === 'stop' && playing)) close();
    else if (action === 'ok') activate();
    else if (panel === -1 && !playing) {
      var row = Math.floor(selected / 3), column = selected % 3;
      if (action === 'left') column = Math.max(0, column - 1);
      if (action === 'right') column = Math.min(2, column + 1);
      if (action === 'up') row = 0;
      if (action === 'down') row = 1;
      selected = row * 3 + column; focus();
    }
    if (panel === 2) $('panel-text').textContent = OrsayTV.diagnostics();
  }
  function start() {
    $('build-label').textContent = 'Build ' + LAB_CONFIG.buildVersion;
    LabLog.add('Build ' + LAB_CONFIG.buildVersion);
    fit(); OrsayTV.init(); focus();
    LabLog.observe(function () {
      if (panel === 2) $('panel-text').textContent = OrsayTV.diagnostics();
    });
    LabLog.record('diagnostics', OrsayTV.diagnostics());
    $('mode').textContent = OrsayTV.nativeMode() ? 'Orsay API erkannt · Installation / Bild / Ton am Gerät bestätigen' : 'BROWSER-VORSCHAU · keine bestätigten TV-Funktionen';
    document.onkeydown = key;
    $('key-anchor').onkeydown = function (event) {
      event = event || window.event;
      /* Anchor handling for legacy engines; prevent duplicate document handling. */
      event.cancelBubble = true;
      if (event.stopPropagation) event.stopPropagation();
      key(event);
    };
    window.onresize = fit;
    for (var i = 0; i < 6; i++) (function (index) {
      $('tile-' + index).onclick = function () { selected = index; focus(); activate(); };
    })(i);
    window.onShow = OrsayTV.focus;
    window.onPause = close;
  }
  function stop() { if (request) request.abort(); LabPlayer.stop(); }
  return {start: start, stop: stop};
})();
