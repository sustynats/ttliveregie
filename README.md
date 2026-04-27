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
- TT-Live-Studio-Browserquelle: im Regiepult unter `Persistenz / Backup` den Link `TT Live Studio Browserquelle` nutzen, z. B. `http://localhost:8501/app/static/browser_overlay.html?overlay=1&room=deine-id`
- Debug/Test/Transparent: `...?overlay=1&debug=1&room=deine-id`, `...?overlay=1&test=1` oder `...?overlay=1&bg=transparent&room=deine-id`
- Health-Test ohne Parameter: `http://localhost:8501/app/static/ttls_health.html`

Wichtig: TikTok Live Studio kann keine Streamlit-Cloud-Login-Session halten. Cloud-Browserquellen funktionieren deshalb nur, wenn die Streamlit-App wirklich public/ohne Auth erreichbar ist. Wenn TTLS nur einen Streamlit-Frame oder Spinner zeigt, wird der Link von Streamlit Auth blockiert. Dann entweder die App in Streamlit Cloud public schalten oder lokal `http://localhost:8501/app/static/browser_overlay.html?...` als Browserquelle nutzen.

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
4. Static Serving ist in `.streamlit/config.toml` aktiviert, damit TikTok Live Studio die einfache Browserquellen-Datei unter `/app/static/browser_overlay.html` laden kann.
5. In den Streamlit-Cloud-App-Einstellungen muss die App fuer Browserquellen public/ohne Login erreichbar sein. Ein `HTTP 303` auf `share.streamlit.io/-/auth/app` bedeutet: TTLS wird von Streamlit Auth blockiert.

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
