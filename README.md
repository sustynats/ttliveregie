# TikTok Live Regiepult

Streamlit-App fuer ein TikTok-Live-Studio-Overlay: links Regiepult, rechts eine 9:16-Buehne mit anonymisierter Keyword-Cloud.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Dann im Browser oeffnen:

- Regiepult: `http://localhost:8501`
- Overlay-only: `http://localhost:8501?overlay=1`
- TT-Live-Studio-Browserquelle: im Regiepult oben (direkt unter dem Header) erscheint **eine** prominente URL als TikTok-Live-Studio-Browserquelle. Diese zeigt auf GitHub Pages und ist immer ohne Login erreichbar:
  - `https://sustynats.github.io/ttliveregie/stage.html?room=<deine-id>&gist=<user>/<gist-id>`
- Erweiterte Varianten (Debug, Test, Transparent, Lokal) liegen im Regiepult unter `Backup -> Erweiterte URLs`.

### Warum nicht Streamlit Cloud direkt?

`https://<app>.streamlit.app/app/static/...` triggert auf Streamlit Cloud einen Auth-Redirect (HTTP 303 -> /-/login), solange die App nicht wirklich public ist. Der Pfad `/~/+/static/...` liefert nur die Streamlit-Frontend-Shell. Beide taugen nicht als TTLS-Browserquelle. Die App hostet die Buehne deshalb auf GitHub Pages und syncht den Overlay-State ueber einen GitHub Gist. Lokal (`streamlit run`) klappt `http://localhost:8501/app/static/stage.html` weiterhin ohne Gist.

## Gist-Sync einrichten (einmalig)

Damit die Cloud-Buehne Live-Updates aus der Regie sieht, pusht das Regiepult den State in einen GitHub Gist. Die Buehne pollt die Raw-URL alle 2 Sekunden.

1. Personal Access Token erstellen: `https://github.com/settings/tokens/new?scopes=gist&description=ttliveregie` (Scope `gist` reicht).
2. Im Regiepult unter `Backup -> Gist-Sync (TTLS-Live-Updates)` den Token einfuegen.
3. Auf `Neuen Gist anlegen` klicken oder eine bestehende Gist-ID + Username einfuegen.
4. `Sync jetzt testen` -> bei Erfolg erscheint die TTLS-URL oben mit `&gist=<user>/<id>` und die Buehne ist live.

Token bleibt nur in der Streamlit-Session (kein Disk-Write). Optional persistent via `.streamlit/secrets.toml`:

```toml
GITHUB_GIST_TOKEN = "ghp_..."
GITHUB_GIST_ID = "deine-gist-id"
GITHUB_GIST_USER = "sustynats"
```

## Nutzung mit TikTok Live Studio

1. App starten und TikTok-Username oder Live-URL eingeben.
2. `Start` klicken. Die App verbindet sich ueber `TikTokLive` mit dem Live-Chat.
3. Links Szenen, Layout, Cloud-Stil, Thema, Highlight, Countdown, Bilder, Typografie und Safety steuern.
4. Manuelle Cloud-Woerter setzen und Schriftgroessen/Familien fuer Thema, Keywords, Highlight, Countdown und Uhr live anpassen.
5. Mehrere Bilder hochladen, benennen, ausblenden, aktivieren oder aus der Session-Bibliothek loeschen.
6. Unter `Medien / Web` direkte Video-URLs einblenden, Ton stummschalten oder aktiv lassen, Video skalieren/positionieren und entscheiden, ob das Hintergrundbild hinter dem Video sichtbar bleibt. YouTube-Links werden automatisch als YouTube-Embed eingebettet.
7. Direkte MP4/WebM/HLS-Videos koennen direkt auf der Bühne mit Play/Pause und 10-Sekunden-Schritten gesteuert werden. YouTube nutzt die eigenen Embed-Controls.
8. Unter `Medien / Web` Websites als iframe einbetten. Viele Seiten blockieren iframe-Einbettung; `Auto` zeigt fuer bekannte Blocker eine Website-Vorschau oder Link-Karte statt der kaputten Browserflaeche. Embed-URLs funktionieren am zuverlaessigsten.
9. Unter `Bewegung / Heatmap` transparente Motion-Layer wie Nebel, Lagerfeuer, Lichtstaub, Scanlines, Regen, Funkeln und Wellen aktivieren und die Chat-Stimmungs-Heatmap einblenden.
10. Unter `Bilder` per Google API ein KI-Hintergrundbild aus einem Prompt und optional den Chat-Schwerpunkten der letzten 5 Minuten erzeugen. Standard ist Imagen 4 Fast; je nach Google-Konto kann Imagen Paid-Tier erfordern.
11. Unter `KI-Check` eine kurze sichtbare Zusammenfassung erzeugen und als Karte auf die Buehne legen. Die maximale Antwortlaenge ist bis 3000 Zeichen einstellbar.
12. Szenen speichern, ueberschreiben, duplizieren, umbenennen, loeschen, importieren und exportieren.
13. Settings, Szenen und Bildbibliothek werden pro Browser/Host im Browser localStorage gespeichert; zusaetzlich schreibt die App pro Browser-ID eine lokale JSON-Fallback-Datei.
14. In TikTok Live Studio eine Browserquelle mit `TT Live Studio Browserquelle` aus `Persistenz / Backup` anlegen. Diese URL zeigt eine statische HTML/CSS/JS-Seite und pollt alle 2,5 Sekunden den Overlay-State, statt die Streamlit-Oberflaeche zu laden.
15. Falls noetig: `Debug Browserquelle` zeigt Room-ID, Elementanzahl, Szenenanzahl und letzten Refresh. `Test Browserquelle` oder `Health-Test ohne Parameter` muss gross `TT LIVE STUDIO TEST OK` anzeigen.
16. Alternativ das rechte Buehnenfenster im normalen Regiepult als Fensterausschnitt zuschneiden.

Wenn die Buehne durch Bild-/Overlay-Regler zu dunkel wird, oben im Regiepult `Aufhellen` oder im Bildbereich `Buehne aufhellen` klicken.

## Streamlit Cloud

1. Repository mit `app.py` und `requirements.txt` deployen.
2. Main file path: `app.py`.
3. Nach dem Deploy die App im Browser oeffnen. Browser-Speicherung funktioniert getrennt pro Browser/Geraet ueber localStorage.
4. Die TTLS-Buehne wird **nicht** ueber Streamlit Cloud ausgeliefert (Auth-Wall), sondern ueber GitHub Pages aus dem `docs/`-Ordner dieses Repos. Pages wurde einmalig per GitHub-API aktiviert (Source: `main` Branch, Folder `/docs`). Aenderungen an `docs/stage.html` sind automatisch nach ~30 s live.
5. Live-Updates aus der Regie laufen ueber einen GitHub Gist (siehe `Gist-Sync einrichten`). Damit funktionieren TTLS-Browserquellen auch bei privaten Streamlit-Apps.

Optional fuer den KI-Check in den Streamlit-Secrets hinterlegen:

```toml
GOOGLE_API_KEY = "dein_google_ai_key"
```

Alternativ funktioniert auch `GEMINI_API_KEY`.

## Backup

- `Backup exportieren` speichert alle visuellen Einstellungen, Szenen und die Bildbibliothek als JSON.
- `Backup importieren` stellt diese Daten wieder her.
- `Alles lokal loeschen` entfernt den Browser-Speicher und den lokalen Fallback fuer den aktuellen Host/Browser.

Hinweis: `TikTokLive` ist eine inoffizielle Bibliothek. Wenn TikTok intern etwas aendert, kann die Verbindung zeitweise fehlschlagen. Das Overlay zeigt niemals Usernamen oder einzelne Chatnachrichten, sondern nur aggregierte Keywords.

## Mini-Browser via Neko (interaktive Webseiten auf der Bühne)

Streamlit Cloud kann selbst keinen echten Browser hosten — viele Webseiten
blockieren zudem `iframe`-Embedding. Mit einem **selbst-gehosteten
[Neko](https://github.com/m1k1o/neko)**-Server bekommst du auf der Bühne
einen vollwertigen, klick- und scrollbaren Browser via WebRTC.

### Server bereitstellen

Empfehlung: ein kleiner Hetzner CX21 oder CX22 (~5 €/Monat) mit Docker.
`docker-compose.yml`:

```yaml
services:
  neko:
    image: m1k1o/neko:firefox
    restart: unless-stopped
    shm_size: "2gb"
    ports:
      - "8080:8080"
      - "52000-52099:52000-52099/udp"
    environment:
      - NEKO_SCREEN=1280x720@30
      - NEKO_PASSWORD=user-secret
      - NEKO_PASSWORD_ADMIN=admin-secret
      - NEKO_EPR=52000-52099
      - NEKO_ICELITE=1
      # Wenn HTTPS hinter einem Reverse Proxy (Caddy/Traefik) terminiert:
      # - NEKO_PROXY=true
```

Mit `NEKO_ICELITE=1` muss der Server eine öffentliche IPv4 haben und die
UDP-Ports 52000–52099 müssen frei sein. Ohne ICE-Lite zusätzlich einen
STUN-Server konfigurieren (`NEKO_NAT1TO1`, `NEKO_ICESERVERS`).

Dahinter unbedingt einen **Reverse Proxy mit HTTPS** (Caddy/Traefik) setzen
— Streamlit Cloud lädt nur über `https://`. Beispiel-Caddyfile:

```caddyfile
neko.example.com {
  reverse_proxy /api/* localhost:8080
  reverse_proxy /static/* localhost:8080
  reverse_proxy /ws localhost:8080
  reverse_proxy * localhost:8080
}
```

### Im Regiepult aktivieren

1. Tab **Medien › Video / Website / PDF**, Abschnitt **Mini-Browser (Neko) Setup** aufklappen.
2. Neko-URL eintragen (z. B. `https://neko.example.com`).
3. Optional Passwort hinterlegen (nur als Notiz im Regie-State; das Login passiert im Iframe).
4. **Mini-Browser aktivieren** klicken.
5. Auf der Bühne erscheint jetzt der WebRTC-Browser. Login mit dem
   `NEKO_PASSWORD` aus deiner docker-compose.

### Sicherheit

- **Niemals public-shared**: setze ein starkes `NEKO_PASSWORD`. Wer den
  Iframe-Inhalt sieht, kann darin alles tun, wozu der Browser autorisiert ist.
- **Kein Browsing eingeloggter Konten** (Banking, Mail, Streaming) — Zuschauer
  des Streams sehen den Bildschirminhalt.
- Optional: dedicated VM nur für Neko, mit Resourcen-Limits in Docker.

### Diagnose

- Bühne mit `?debug=1` öffnen — das eingeblendete Panel zeigt fetch-Status,
  aktive Theme-Werte und Layer-Counts.
- Im Browser-DevTools (`F12` → Console) erscheinen Logs mit Prefix
  `[ttl-stage]`: URL-Params, Theme-Werte, sichtbare Edit-Handles,
  Polling-Fehler. Bei Bug-Reports bitte Screenshot davon mitliefern.
