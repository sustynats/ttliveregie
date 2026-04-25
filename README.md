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

## Nutzung mit TikTok Live Studio

1. App starten und TikTok-Username oder Live-URL eingeben.
2. `Start` klicken. Die App verbindet sich ueber `TikTokLive` mit dem Live-Chat.
3. Links Szenen, Layout, Cloud-Stil, Thema, Highlight, Countdown, Bilder, Typografie und Safety steuern.
4. Manuelle Cloud-Woerter setzen und Schriftgroessen/Familien fuer Thema, Keywords, Highlight, Countdown und Uhr live anpassen.
5. Mehrere Bilder hochladen, benennen, ausblenden, aktivieren oder aus der Session-Bibliothek loeschen.
6. Szenen speichern, ueberschreiben, duplizieren, umbenennen, loeschen, importieren und exportieren.
7. Settings, Szenen und Bildbibliothek werden im Browser localStorage gespeichert; zusaetzlich schreibt die App eine lokale JSON-Fallback-Datei.
8. In TikTok Live Studio eine Browserquelle mit `http://localhost:8501?overlay=1` anlegen.
9. Alternativ das rechte Buehnenfenster im normalen Regiepult als Fensterausschnitt zuschneiden.

## Streamlit Cloud

1. Repository mit `app.py` und `requirements.txt` deployen.
2. Main file path: `app.py`.
3. Nach dem Deploy die App im Browser oeffnen. Browser-Speicherung funktioniert pro Browser/Geraet ueber localStorage.

## Backup

- `Backup exportieren` speichert alle visuellen Einstellungen, Szenen und die Bildbibliothek als JSON.
- `Backup importieren` stellt diese Daten wieder her.
- `Alles lokal loeschen` entfernt den Browser-Speicher und den lokalen Fallback.

Hinweis: `TikTokLive` ist eine inoffizielle Bibliothek. Wenn TikTok intern etwas aendert, kann die Verbindung zeitweise fehlschlagen. Das Overlay zeigt niemals Usernamen oder einzelne Chatnachrichten, sondern nur aggregierte Keywords.
