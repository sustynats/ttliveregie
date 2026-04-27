# Refactor-Notizen — TikTok Live Regiepult

## Ziele dieses Refactors

1. Flackern und Font-Springen der Bühne abstellen.
2. Eine reine, login-freie Bühnen-URL für TikTok Live Studio.
3. Direct-Manipulation auf der Bühne (Drag/Resize/Hide jeder Layer).
4. Robustes Embedding externer Webseiten (iframe → Screenshot → OG-Karte).
5. Aufgeräumtes Regiepult-UI mit sinnvollen Defaults.

## Architektur-Entscheidung

Bühne wird zu einer **statischen, clientseitig renderden HTML-Seite** (`static/stage.html`).
Der Streamlit-Server schreibt nur den State als JSON in `static/overlay_state_<room>.json`.
Sowohl TikTok Live Studio als auch das Regiepult laden **dieselbe** `stage.html` als
Iframe — TikTok ohne `?edit=1`, das Regiepult mit `?edit=1`. Damit ist die
Bühnen-Darstellung in beiden Welten identisch und der Streamlit-Rerun-Pfad
berührt die Bühne nicht mehr (kein Flackern).

`browser_overlay.html` bleibt als Backwards-Compat-Alias erhalten und leitet auf
`stage.html` weiter.

## Erhaltene Features (kein Funktionsverlust)

### Connection / TikTok Live
- Async TikTokLive-Client mit Connect/Disconnect/LiveEnd-Events
- Username/URL-Normalisierung (`@user`)
- Stable User Hash (anonym)
- Comment-Drain-Loop, deque(maxlen=5000)
- Privacy: keine Usernamen, keine Einzelnachrichten — nur aggregierte Keywords

### Keyword-Engine
- Stoppwörter (DE), Blocklisten (politisch/toxisch, rechts), Profanity
- Custom Blacklist/Whitelist (User-pflegbar)
- Recency-Weighting + Diversität + User-Repeat-Penalty
- 8 Cloud-Stile mit deterministischer Position (MD5-seed)
- Manuelle Cloud-Wörter (mit Emphasis-Toggle)

### Layer-Typen (alle bleiben)
- Hintergrundbild (mit fit, dim, blur, brightness, opacity, zoom, position)
- Topic / Headline (Position, Größe, Font, Weight, Spacing, Transform)
- Highlight-Wort
- Keyword-Cloud (Style, Position, Größe, Tilt, Density, Animation)
- Countdown (Titel, Minuten, Ring-Anzeige)
- Uhr / Live-Since
- Video (YouTube-Embed oder direktes MP4/WebM/HLS)
- Website (iframe / Screenshot-Fallback / Reader-Card / Link-Card)
- PDF-Viewer (PDF.js srcdoc)
- KI-Karte (Gemini Summary)
- Motion-Layer (7 Effekte: Aerosol, Lagerfeuer, Lichtstaub, Scanlines, Regen, Funkeln, Wellen)
- Heatmap (Sentiment)
- Safe-Zones (TikTok-UI-Bereiche)

### Themes (13)
Editorial Dark, Neon Pop, Candy Gradient, Bauhaus Clean, Soft Power,
System Map, Newspaper / Print, Festival / Color Splash, Cyber Newsroom,
Aurora Glass, Protest Poster, Data Bloom, Velvet Studio.

### Safety
- Stoppwortlisten DE
- Politisch-toxische Blockliste
- Hate-Blockliste
- Rechtsextreme-Codes-Blockliste
- Profanity-Liste
- Custom Blacklist/Whitelist

### Persistenz
- Browser localStorage (`ttliveregie_state_v2`)
- Server-Fallback (`.ttliveregie_profiles/<browser_id>.json`)
- Room-spezifischer State (`.ttliveregie_profiles/room_<id>.json`)
- Static-Datei für Overlay-Polling (`static/overlay_state_<room>.json`)
- Backup-Export/Import als JSON
- Szenen-System (Save/Load/Duplicate/Rename/Delete/Export/Import)

## Bug-Quellen identifiziert

1. **Flackern**: Streamlit rendert die Bühne über `st.components.v1.html(render_overlay_html(...))`
   bei jedem Rerun (alle ~4 s). Das ersetzt das gesamte Iframe-Dokument samt
   Fonts und CSS — visueller Reset jedes Mal. → Lösung: Bühne als statische
   `stage.html` per `<iframe>` einbinden, Streamlit füttert nur noch die
   JSON-Datei.

2. **Fonts laden zu spät**: `render_overlay_html` injiziert keine Google-Fonts
   `<link>` im Head; Familien wie "Playfair Display" fallen daher auf
   System-Fonts zurück oder laden mitten ins Layout (FOUT). → Lösung:
   `stage.html` lädt alle benötigten Fonts via `<link rel="preconnect">` +
   `<link href="...">` mit `display=swap` einmalig im `<head>`.

3. **Wholesale `innerHTML` Replace**: `browser_overlay.html` ersetzt komplette
   Layer-DOM-Teile bei jedem Tick. Videos starten neu, Iframes laden neu,
   Listener werden gekippt. → Lösung: `stage.html` hält ein DOM-Element pro
   Layer (`data-id`) und mutiert nur die Properties, die sich geändert haben
   (CSS-Variablen, Text-Content, Klassen). Layer-Element wird nur erstellt /
   entfernt, wenn Layer neu sichtbar / verschwunden.

4. **Externe Seiten via iframe scheitern stumm**: Aktuell wird nur der
   IFRAME_BLOCKED_DOMAINS-Set geprüft. Viele Seiten liefern X-Frame-Options /
   CSP unangekündigt. → Lösung: Smart-Embed-Pipeline:
     1. iframe versuchen — load-Event in `stage.html` mit Timeout (3 s)
     2. Bei Timeout/Fehler: Screenshot via `https://image.thum.io/get/width/1080/crop/1920/<url>`
        oder `https://api.microlink.io/?url=<url>&screenshot=true`
     3. Fallback: OG-Karte (Titel/Bild/Beschreibung) — schon serverseitig
        vorbereitet via BeautifulSoup

5. **Keine Direct-Manipulation**: Es gibt einen `apply_stage_editor_params`,
   aber der setzt Position via Query-Param-Reload — extrem fragil. → Lösung:
   `stage.html` schickt im Edit-Modus per `postMessage` Layer-Updates an den
   Parent-Window (Streamlit). Streamlit fängt das via `streamlit_js_eval` und
   triggert einen Rerun mit aktualisiertem State.

6. **Editor-Code im Stage**: Bisher liefen Drag/Resize-Handles im
   `render_overlay_html`-Output direkt mit, was die Live-Bühne verlangsamt. →
   Lösung: Edit-Handles werden nur bei `?edit=1` aktiviert.

## Implementierungs-Plan

1. **`static/stage.html`** komplett neu schreiben:
   - `<head>`: Google-Fonts-CDN-`<link>`s mit `display=swap`, alle CSS-Animationen
     (drift, aerosolDrift, flicker, flameDance, emberRise, scan, rain, pulse,
     floaty, ringspin), alle Theme-CSS-Variablen, alle Cloud-Style-Klassen
   - `<body>`: leerer `.stage` mit `<div id="layers"></div>`
   - Polling-Loop mit Last-Modified/ETag → fetch JSON → DOM-diff
   - Edit-Modus (`?edit=1`): pro Layer ein invisibler Drag-/Resize-Handle
     darüber, Pointerevents → postMessage(parent, {type:"layer-update", id, x, y, w, h})
   - Smart-Embed: iframe → Screenshot → OG-Card

2. **`smart_embed.py`** (neues Modul):
   - `screenshot_url(url)` — gibt thum.io-URL zurück (Cache-Busting nach 30 s)
   - `og_card(url)` — fetch + BeautifulSoup, gibt {title, description, image} zurück
   - Fallback-Reihenfolge wird in `stage.html` umgesetzt

3. **`app.py`** modifizieren (chirurgisch):
   - `render_stage` ersetzt durch `render_stage_iframe` → schreibt State via
     `persist_overlay_state()` und embedded `static/stage.html?edit=1&room=<id>`
     als iframe
   - `render_overlay_html` bleibt als Fallback / Legacy-Pfad bestehen, wird
     aber im Hauptfluss nicht mehr aufgerufen
   - `?overlay=1`-Modus leitet ebenfalls auf `stage.html` weiter (statt
     `render_static_overlay_redirect` auf `browser_overlay.html`)
   - postMessage-Handler im Regiepult-iframe via `streamlit_js_eval` —
     liest layer-update aus `localStorage` (von der Bühne geschrieben) und
     wendet auf `st.session_state` an
   - DEFAULTS_VERSION 3 → 4: bessere Defaults setzen

4. **`browser_overlay.html`**: zu reinem Redirect auf `stage.html` ändern
   (Backwards-Compat).

5. **Regie-UI Redesign**: Tab-Struktur (mit `st.tabs`):
   - Bühne (Sichtbarkeit, Highlight, Topic)
   - Live (Verbindung, Safety, Status)
   - Inhalte (Countdown, AI-Karte, Manuelle Wörter)
   - Medien (Bilder, Video, Website, PDF)
   - Stil (Layout, Cloud, Typografie, Bewegung)
   - Szenen (Save/Load)
   - Backup (Persistenz, URLs)

   Um Risiko klein zu halten: bestehende Expander-Reihenfolge bleibt funktionsgleich,
   wird nur in oben genannte Tab-Container gruppiert.

## Defaults (DEFAULTS_VERSION 4)

Neu für 4:
- `layout = "Editorial Dark"` (vorher Neon Pop) — neutraler, weniger schreiend
- `cloud_style` folgt Theme — Magazine Cloud
- `topic_text_size = 92`
- `keyword_size = 50`
- `keyword_density = 38`
- `motion_effects = ["Aerosol-Wolken"]` (nur ein Effekt default, dezenter)
- `motion_opacity = 30`
- `bg_dim = 22`
- `bg_brightness = 110`

Backup-Kompatibilität: alte Backups laden weiterhin (`apply_persistent_payload`
prüft `defaults_version` und appliziert nur dann v4-Defaults, wenn das alte
Backup älter ist und der User keine eigenen Bild-/Cloud-Settings gesetzt hat —
analog zur bestehenden v3-Logik).

## Bekannte Limitationen

- Streamlit Cloud kann keine echten Browser-Engines im Server-Prozess starten;
  Screenshot-Service muss extern sein (thum.io).
- thum.io ist Free-Tier ohne Auth, hat aber Rate-Limits — bei >50 Requests/Min
  liefert es Caching; akzeptabel für Live-Betrieb.
- postMessage Round-Trip dauert ~200–600 ms (warten auf Streamlit-Rerun);
  Drag fühlt sich nicht butterweich an, aber ist genau genug.
- Edit-Mode-Updates schreiben momentan in localStorage und werden bei
  nächstem Rerun gepollt; saubere Lösung wäre ein echter REST-Endpoint, den
  Streamlit aber nicht von Haus aus liefert.
