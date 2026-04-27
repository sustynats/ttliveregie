from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import math
import os
import queue
import re
import threading
import time
import uuid
from io import BytesIO
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import regex
import streamlit as st
from streamlit_autorefresh import st_autorefresh

try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    requests = None
    BeautifulSoup = None

try:
    from streamlit_js_eval import get_local_storage, streamlit_js_eval
except Exception:
    get_local_storage = None
    streamlit_js_eval = None

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None

try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent, LiveEndEvent
except Exception:  # TikTokLive may be installed after first launch.
    TikTokLiveClient = None
    CommentEvent = ConnectEvent = DisconnectEvent = LiveEndEvent = None


# ---------------------------------------------------------------------------
# Konstanten und Konfiguration
# ---------------------------------------------------------------------------

APP_DIR = Path(__file__).parent
RUNTIME_STATE_FILE = APP_DIR / ".overlay_runtime_state.json"
SERVER_STATE_DIR = APP_DIR / ".ttliveregie_profiles"
STATIC_DIR = APP_DIR / "static"
STATIC_OVERLAY_FILE = STATIC_DIR / "browser_overlay.html"
STATIC_STAGE_FILE = STATIC_DIR / "stage.html"
LOCAL_STORAGE_KEY = "ttliveregie_state_v2"
LOCAL_BROWSER_ID_KEY = "ttliveregie_browser_id_v1"
COMMENT_WINDOW_SECONDS = 4 * 60
KEYWORD_REFRESH_SECONDS = 20
MAX_KEYWORDS = 32
MIN_WORD_LENGTH = 3
DEFAULT_ASPECT = "9:16"
DEFAULTS_VERSION = 10
AI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-pro",
]
AI_MODEL_LABELS = {
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite",
    "gemini-2.0-flash": "Gemini 2.0 Flash",
    "gemini-2.0-flash-lite": "Gemini 2.0 Flash Lite",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
}
IMAGE_MODELS = [
    "auto",
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
    "gemini-2.0-flash-preview-image-generation",
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-generate-001",
    "imagen-3.0-generate-002",
]
IMAGE_MODEL_LABELS = {
    "auto": "Auto: Gemini Bildmodell",
    "gemini-2.5-flash-image": "Gemini 2.5 Flash Image",
    "gemini-2.5-flash-image-preview": "Gemini 2.5 Flash Image Preview",
    "gemini-2.0-flash-preview-image-generation": "Gemini 2.0 Flash Image Preview",
    "imagen-4.0-fast-generate-001": "Imagen 4 Fast",
    "imagen-4.0-generate-001": "Imagen 4 Standard",
    "imagen-3.0-generate-002": "Imagen 3",
}
MOTION_EFFECTS = ["Aerosol-Wolken", "Lagerfeuer", "Lichtstaub", "Scanlines", "Regen", "Funkeln", "Wellen"]
MOTION_EFFECT_MAP = {"Nebel": "Aerosol-Wolken"}
POSITIVE_WORDS = {
    "gut", "super", "liebe", "stark", "danke", "yes", "ja", "richtig", "wichtig", "hoffnung", "freude",
    "cool", "top", "fair", "solidaritaet", "solidarisch", "mut", "klar", "respekt",
}
NEGATIVE_WORDS = {
    "angst", "schlecht", "wut", "hass", "nein", "falsch", "krass", "problem", "lüge", "luege", "sorge",
    "traurig", "schlimm", "gefährlich", "gefaehrlich", "eskalation", "chaos", "weg", "nervt",
}
LEGACY_AI_MODEL_MAP = {
    "gemini-1.5-flash": "gemini-2.5-flash",
    "gemini-1.5-pro": "gemini-2.5-pro",
    "gemini-pro": "gemini-2.5-flash",
}

FONT_PRESETS = {
    "System Sans": 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    "Inter": 'Inter, ui-sans-serif, system-ui, sans-serif',
    "Arial": "Arial, Helvetica, sans-serif",
    "Helvetica": "Helvetica, Arial, sans-serif",
    "Georgia": "Georgia, serif",
    "Times New Roman": '"Times New Roman", Times, serif',
    "Playfair Display": '"Playfair Display", Georgia, serif',
    "Merriweather": "Merriweather, Georgia, serif",
    "Montserrat": "Montserrat, Arial, sans-serif",
    "Poppins": "Poppins, Arial, sans-serif",
    "Bebas Neue": '"Bebas Neue", Impact, sans-serif',
}

CLOUD_STYLES = [
    "Classic Word Cloud",
    "Vertical Cloud",
    "Orbital Cloud",
    "Bubble Cloud",
    "Magazine Cloud",
    "Network Cloud",
    "Color Burst",
    "Minimal Cloud",
]

THEMES = {
    "Editorial Dark": {
        "key": "editorial",
        "bg": "#151413",
        "panel": "rgba(25, 24, 22, .78)",
        "text": "#f4efe5",
        "muted": "#c7bba8",
        "accent": "#d6b15e",
        "accent2": "#8f7747",
        "glow": "rgba(214,177,94,.28)",
        "cloud_style": "Magazine Cloud",
        "font": "Playfair Display",
        "cloud_x": 50,
        "cloud_y": 50,
    },
    "Neon Pop": {
        "key": "neon",
        "bg": "#050614",
        "panel": "rgba(9, 10, 26, .76)",
        "text": "#f4f7ff",
        "muted": "#b8c1ff",
        "accent": "#ff3df2",
        "accent2": "#2dfcff",
        "accent3": "#baff29",
        "glow": "rgba(255,61,242,.38)",
        "cloud_style": "Color Burst",
        "font": "Poppins",
        "cloud_x": 50,
        "cloud_y": 50,
    },
    "Candy Gradient": {
        "key": "candy",
        "bg": "#ff8cc6",
        "panel": "rgba(255,255,255,.30)",
        "text": "#26133a",
        "muted": "#6e3f75",
        "accent": "#ff6b35",
        "accent2": "#00d1c7",
        "accent3": "#ffe14f",
        "glow": "rgba(255,225,79,.32)",
        "cloud_style": "Bubble Cloud",
        "font": "Poppins",
        "cloud_x": 50,
        "cloud_y": 50,
    },
    "Bauhaus Clean": {
        "key": "bauhaus",
        "bg": "#f4efe2",
        "panel": "rgba(255,255,255,.80)",
        "text": "#111111",
        "muted": "#4e4b45",
        "accent": "#e53935",
        "accent2": "#1d4ed8",
        "accent3": "#f5c400",
        "glow": "rgba(229,57,53,.15)",
        "cloud_style": "Classic Word Cloud",
        "font": "Montserrat",
        "cloud_x": 50,
        "cloud_y": 50,
    },
    "Soft Power": {
        "key": "soft",
        "bg": "#eaded5",
        "panel": "rgba(255, 247, 241, .76)",
        "text": "#2f2928",
        "muted": "#776a67",
        "accent": "#b04e6f",
        "accent2": "#383130",
        "accent3": "#d5a6bd",
        "glow": "rgba(176,78,111,.20)",
        "cloud_style": "Bubble Cloud",
        "font": "Playfair Display",
        "cloud_x": 50,
        "cloud_y": 50,
    },
    "System Map": {
        "key": "map",
        "bg": "#101415",
        "panel": "rgba(17, 23, 24, .72)",
        "text": "#eaf1ed",
        "muted": "#9fb0a8",
        "accent": "#7bd7a8",
        "accent2": "#7aa4ff",
        "accent3": "#f2e682",
        "glow": "rgba(123,215,168,.24)",
        "cloud_style": "Network Cloud",
        "font": "Inter",
        "cloud_x": 50,
        "cloud_y": 50,
    },
    "Newspaper / Print": {
        "key": "print",
        "bg": "#f5f0e6",
        "panel": "rgba(255,255,255,.72)",
        "text": "#16120d",
        "muted": "#695f53",
        "accent": "#b91c1c",
        "accent2": "#111111",
        "accent3": "#d7c7ad",
        "glow": "rgba(185,28,28,.14)",
        "cloud_style": "Magazine Cloud",
        "font": "Georgia",
        "cloud_x": 50,
        "cloud_y": 50,
    },
    "Festival / Color Splash": {
        "key": "festival",
        "bg": "#11131f",
        "panel": "rgba(20,20,35,.68)",
        "text": "#fffaf0",
        "muted": "#e7d7ff",
        "accent": "#ff4d6d",
        "accent2": "#ffd166",
        "accent3": "#06d6a0",
        "glow": "rgba(255,209,102,.32)",
        "cloud_style": "Color Burst",
        "font": "Bebas Neue",
        "cloud_x": 50,
        "cloud_y": 50,
    },
    "Cyber Newsroom": {
        "key": "cyber",
        "bg": "#02040a",
        "panel": "rgba(5, 12, 22, .72)",
        "text": "#f8fbff",
        "muted": "#8ee8ff",
        "accent": "#00f5ff",
        "accent2": "#ff2bd6",
        "accent3": "#f8ff4d",
        "glow": "rgba(0,245,255,.34)",
        "cloud_style": "Network Cloud",
        "font": "Montserrat",
        "cloud_x": 50,
        "cloud_y": 52,
    },
    "Aurora Glass": {
        "key": "aurora",
        "bg": "#07110f",
        "panel": "rgba(230,255,245,.16)",
        "text": "#ecfff6",
        "muted": "#b6e9d6",
        "accent": "#70ffca",
        "accent2": "#9a8cff",
        "accent3": "#fff38a",
        "glow": "rgba(112,255,202,.28)",
        "cloud_style": "Orbital Cloud",
        "font": "Inter",
        "cloud_x": 50,
        "cloud_y": 52,
    },
    "Protest Poster": {
        "key": "poster",
        "bg": "#f7efe2",
        "panel": "rgba(20, 18, 15, .10)",
        "text": "#111111",
        "muted": "#4b4134",
        "accent": "#ff2a2a",
        "accent2": "#111111",
        "accent3": "#ffd400",
        "glow": "rgba(255,42,42,.18)",
        "cloud_style": "Magazine Cloud",
        "font": "Bebas Neue",
        "cloud_x": 50,
        "cloud_y": 52,
    },
    "Data Bloom": {
        "key": "bloom",
        "bg": "#071014",
        "panel": "rgba(12, 28, 34, .74)",
        "text": "#f0fff9",
        "muted": "#a7c8be",
        "accent": "#7cff6b",
        "accent2": "#ffb86b",
        "accent3": "#6bd6ff",
        "glow": "rgba(124,255,107,.22)",
        "cloud_style": "Bubble Cloud",
        "font": "Poppins",
        "cloud_x": 50,
        "cloud_y": 52,
    },
    "Velvet Studio": {
        "key": "velvet",
        "bg": "#160713",
        "panel": "rgba(38, 10, 32, .72)",
        "text": "#fff1fa",
        "muted": "#dfb8d1",
        "accent": "#ff5da8",
        "accent2": "#ffcf70",
        "accent3": "#8bd3ff",
        "glow": "rgba(255,93,168,.30)",
        "cloud_style": "Minimal Cloud",
        "font": "Playfair Display",
        "cloud_x": 50,
        "cloud_y": 52,
    },
}

LEGACY_LAYOUT_MAP = {
    "Neon Pulse": "Neon Pop",
    "Clean Studio": "Bauhaus Clean",
    "Feminist Soft Power": "Soft Power",
}

PRESET_SCENES = ["Intro", "Diskussion", "Q&A", "Deep Dive", "Fazit"]
IFRAME_BLOCKED_DOMAINS = {
    "zdf.de",
    "www.zdf.de",
    "zdfheute.de",
    "www.zdfheute.de",
    "ardmediathek.de",
    "www.ardmediathek.de",
    "tagesschau.de",
    "www.tagesschau.de",
    "spiegel.de",
    "www.spiegel.de",
    "zeit.de",
    "www.zeit.de",
    "sueddeutsche.de",
    "www.sueddeutsche.de",
}


# ---------------------------------------------------------------------------
# Safety-Listen
# ---------------------------------------------------------------------------

STOPWORDS_DE = {
    "aber", "alle", "allem", "allen", "aller", "alles", "als", "also", "am", "an", "ander", "andere",
    "anderem", "anderen", "anderer", "anderes", "anderm", "andern", "anderr", "anders", "auch", "auf",
    "aus", "bei", "bin", "bis", "bist", "da", "damit", "dann", "der", "den", "des", "dem", "die", "das",
    "dass", "daß", "derselbe", "derselben", "denselben", "desselben", "demselben", "dieselbe", "dieselben",
    "dasselbe", "dazu", "dein", "deine", "deinem", "deinen", "deiner", "deines", "denn", "derer", "dessen",
    "dich", "dir", "du", "dies", "diese", "diesem", "diesen", "dieser", "dieses", "doch", "dort", "durch",
    "ein", "eine", "einem", "einen", "einer", "eines", "einig", "einige", "einigem", "einigen", "einiger",
    "einiges", "einmal", "er", "ihn", "ihm", "es", "etwas", "euer", "eure", "eurem", "euren", "eurer",
    "eures", "für", "fuer", "gegen", "gewesen", "hab", "habe", "haben", "hat", "hatte", "hatten", "hier",
    "hin", "hinter", "ich", "mich", "mir", "ihr", "ihre", "ihrem", "ihren", "ihrer", "ihres", "euch",
    "im", "in", "indem", "ins", "ist", "jede", "jedem", "jeden", "jeder", "jedes", "jene", "jenem",
    "jenen", "jener", "jenes", "jetzt", "kann", "kein", "keine", "keinem", "keinen", "keiner", "keines",
    "können", "koennen", "könnte", "koennte", "machen", "man", "manche", "manchem", "manchen", "mancher",
    "manches", "mein", "meine", "meinem", "meinen", "meiner", "meines", "mit", "muss", "musste", "nach",
    "nicht", "nichts", "noch", "nun", "nur", "ob", "oder", "ohne", "sehr", "sein", "seine", "seinem",
    "seinen", "seiner", "seines", "selbst", "sich", "sie", "ihnen", "sind", "so", "solche", "solchem",
    "solchen", "solcher", "solches", "soll", "sollte", "sondern", "sonst", "über", "ueber", "um", "und",
    "uns", "unse", "unsem", "unsen", "unser", "unses", "unter", "viel", "vom", "von", "vor", "während",
    "waehrend", "war", "waren", "warst", "was", "weg", "weil", "weiter", "welche", "welchem", "welchen",
    "welcher", "welches", "wenn", "werde", "werden", "wie", "wieder", "will", "wir", "wird", "wirst",
    "wo", "wollen", "wollte", "würde", "wuerde", "würden", "wuerden", "zu", "zum", "zur", "zwar", "zwischen",
    "ja", "nein", "mal", "echt", "ganz", "mehr", "heute", "immer", "bitte", "danke", "lol", "haha", "omg",
}

BLOCKLIST_POLITICAL_TOXIC = {
    "afd", "remigration", "lügenpresse", "luegenpresse", "ausländerhetze", "auslaenderhetze",
    "migrantenhetze", "klimaleugnung", "genderhetze", "grünenbashing", "gruenenbashing",
    "grünebashing", "gruenebashing", "volksverräter", "volksverraeter", "systempresse",
    "altparteien", "messermigration", "umvolkung", "schuldkult", "globalisten",
}

BLOCKLIST_HATE = {
    "nazi", "nazis", "hitler", "fascho", "faschist", "faschisten", "rassist", "rassisten",
    "kanake", "kanaken", "zigeuner", "judensau", "antisemit", "antisemiten", "homosau",
    "schwuchtel", "transe", "behindert", "fotze", "hurensohn", "hure", "nutte",
}

BLOCKLIST_RIGHTWING = {
    "reichsbürger", "reichsbuerger", "querfront", "identitäre", "identitaere", "patrioten",
    "heimatschutz", "volksaustausch", "deutschland-den-deutschen", "deutschlanddendeutschen",
    "asylflut", "flüchtlingsflut", "fluechtlingsflut", "invasoren", "invasion",
}

CUSTOM_BLACKLIST: set[str] = set()
CUSTOM_WHITELIST: set[str] = set()
HARD_BLOCKLIST = BLOCKLIST_HATE | {"hitler", "judensau"}


# ---------------------------------------------------------------------------
# TikTok-Verbindung
# ---------------------------------------------------------------------------

@dataclass
class LiveMessage:
    ts: float
    user_hash: str
    text: str


@dataclass
class LiveRuntime:
    status: str = "idle"
    status_detail: str = "Nicht verbunden"
    started_at: float | None = None
    stopped_at: float | None = None
    unique_id: str = ""
    comments: "queue.Queue[LiveMessage]" = field(default_factory=queue.Queue)
    events: "queue.Queue[str]" = field(default_factory=queue.Queue)
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    client: Any = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def set_status(self, status: str, detail: str) -> None:
        with self.lock:
            self.status = status
            self.status_detail = detail
            if status == "connected" and self.started_at is None:
                self.started_at = time.time()
            if status in {"stopped", "error", "ended"}:
                self.stopped_at = time.time()


@st.cache_resource
def live_runtime() -> LiveRuntime:
    return LiveRuntime()


def normalize_tiktok_input(value: str) -> str:
    value = (value or "").strip()
    value = value.replace("https://www.tiktok.com/", "").replace("http://www.tiktok.com/", "")
    match = re.search(r"@([A-Za-z0-9._-]+)", value)
    if match:
        return f"@{match.group(1)}"
    value = value.strip("/ ")
    if value and not value.startswith("@"):
        value = f"@{value}"
    return value


def stable_user_hash(raw_user: Any) -> str:
    raw = "unknown"
    for attr in ("unique_id", "user_id", "id", "sec_uid", "nickname"):
        candidate = getattr(raw_user, attr, None)
        if candidate:
            raw = str(candidate)
            break
    return hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()[:16]


def start_live_connection(unique_id: str) -> None:
    rt = live_runtime()
    unique_id = normalize_tiktok_input(unique_id)
    if not unique_id:
        rt.set_status("error", "Bitte TikTok-Username oder Live-URL eingeben.")
        return
    if TikTokLiveClient is None:
        rt.set_status("error", "TikTokLive ist nicht installiert. Bitte `pip install -r requirements.txt` ausfuehren.")
        return
    if rt.thread and rt.thread.is_alive():
        rt.set_status("connected", f"Bereits verbunden mit {rt.unique_id}")
        return

    rt.stop_event.clear()
    rt.started_at = None
    rt.unique_id = unique_id
    rt.set_status("connecting", f"Verbinde mit {unique_id} ...")

    def runner() -> None:
        # Bewährtes Pattern aus dem Schwester-Repo `sustynats/ttlive`: einfach
        # `TikTokLiveClient(unique_id=...)` + Handler + `client.run()`. Das
        # `client.start(fetch_room_info=True)` aus dem alten Code holt
        # Raum-Infos vorab, was bei Lives mit Alters-Restriction-Flag fehl-
        # schlägt — `run()` macht den Connect ohne diesen Vorab-Fetch.
        try:
            client = TikTokLiveClient(unique_id=unique_id)
            rt.client = client

            @client.on(ConnectEvent)
            async def on_connect(event: Any) -> None:
                rt.set_status("connected", f"Verbunden mit {getattr(event, 'unique_id', unique_id)}")
                rt.events.put("connected")

            @client.on(CommentEvent)
            async def on_comment(event: Any) -> None:
                text = getattr(event, "comment", "") or ""
                user_hash = stable_user_hash(getattr(event, "user", None))
                rt.comments.put(LiveMessage(time.time(), user_hash, text))

            @client.on(DisconnectEvent)
            async def on_disconnect(_: Any) -> None:
                rt.set_status("stopped", "Verbindung geschlossen")
                rt.events.put("disconnect")

            @client.on(LiveEndEvent)
            async def on_live_end(_: Any) -> None:
                rt.set_status("ended", "Live beendet")
                rt.events.put("ended")

            client.run()
        except Exception as exc:
            # Echten Exception-Text zurückspielen, damit der User im UI
            # sieht, woran's hängt (statt nur "Verbindung fehlgeschlagen").
            rt.set_status("error", f"{type(exc).__name__}: {exc}")

    rt.thread = threading.Thread(target=runner, daemon=True)
    rt.thread.start()


def stop_live_connection() -> None:
    rt = live_runtime()
    rt.stop_event.set()
    rt.set_status("stopped", "Stop angefordert")
    client = rt.client
    if client is not None:
        # TikTokLiveClient hat eine eigene Stop-Methode; ruf sie best-effort
        # auf, damit der run()-Loop sauber endet. Fehler ignorieren — der
        # Daemon-Thread wird sowieso beim App-Stop aufgeräumt.
        for attr in ("stop", "disconnect", "close"):
            stop_fn = getattr(client, attr, None)
            if callable(stop_fn):
                try:
                    result = stop_fn()
                    if asyncio.iscoroutine(result):
                        # Sollte aus dem Streamlit-Hauptthread aus möglich sein
                        try:
                            asyncio.run(result)
                        except RuntimeError:
                            pass
                    break
                except Exception:
                    continue


# ---------------------------------------------------------------------------
# Keyword-Extraktion und Safety-Filter
# ---------------------------------------------------------------------------

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@\w+", re.IGNORECASE)
WORD_RE = regex.compile(r"[\p{L}][\p{L}\p{Mn}\-]{2,}", regex.IGNORECASE)
EMOJI_RE = regex.compile(r"[\p{Emoji_Presentation}\p{Extended_Pictographic}]")


def strip_emojis(text: str) -> str:
    return EMOJI_RE.sub(" ", text)


def normalize_word(word: str) -> str:
    word = word.lower().strip("-_.,:;!?()[]{}\"'")
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
    for source, target in replacements.items():
        word = word.replace(source, target)
    return word


def custom_blacklist_values() -> set[str]:
    try:
        return parse_word_list(st.session_state.get("custom_blacklist_text", ""))
    except Exception:
        return CUSTOM_BLACKLIST


def custom_whitelist_values() -> set[str]:
    try:
        return parse_word_list(st.session_state.get("custom_whitelist_text", ""))
    except Exception:
        return CUSTOM_WHITELIST


def is_safe_keyword(word: str) -> bool:
    original = (word or "").strip().lower()
    normalized = normalize_word(original)
    if not normalized or len(normalized) < MIN_WORD_LENGTH:
        return False
    if normalized.isnumeric() or re.fullmatch(r"[\d\W_]+", normalized):
        return False
    if URL_RE.search(original) or original.startswith("@"):
        return False
    if normalized in HARD_BLOCKLIST:
        return False
    if normalized in {normalize_word(w) for w in custom_whitelist_values()}:
        return True
    blocked_sets = (
        STOPWORDS_DE,
        BLOCKLIST_POLITICAL_TOXIC,
        BLOCKLIST_HATE,
        BLOCKLIST_RIGHTWING,
        custom_blacklist_values(),
    )
    for block_set in blocked_sets:
        if normalized in {normalize_word(w) for w in block_set}:
            return False
    return True


def extract_words(text: str) -> list[str]:
    text = URL_RE.sub(" ", text or "")
    text = MENTION_RE.sub(" ", text)
    text = strip_emojis(text)
    return [normalize_word(match.group(0)) for match in WORD_RE.finditer(text)]


def drain_live_comments() -> None:
    rt = live_runtime()
    while True:
        try:
            msg = rt.comments.get_nowait()
        except queue.Empty:
            break
        st.session_state.chat_window.append(msg)
    cutoff = time.time() - COMMENT_WINDOW_SECONDS
    while st.session_state.chat_window and st.session_state.chat_window[0].ts < cutoff:
        st.session_state.chat_window.popleft()


def compute_keywords(force: bool = False) -> None:
    now = time.time()
    if st.session_state.freeze_keywords and not force:
        return
    if not force and now - st.session_state.last_keyword_update < KEYWORD_REFRESH_SECONDS:
        return

    word_counts: Counter[str] = Counter()
    word_users: defaultdict[str, set[str]] = defaultdict(set)
    filtered_counts: Counter[str] = Counter()
    message_seen: Counter[tuple[str, str]] = Counter()
    total_filtered = 0

    for msg in st.session_state.chat_window:
        normalized_message = " ".join(extract_words(msg.text))[:160]
        repeated_by_user = message_seen[(msg.user_hash, normalized_message)]
        message_seen[(msg.user_hash, normalized_message)] += 1
        repeat_penalty = 1 / (1 + repeated_by_user * 0.75)
        age = max(0, now - msg.ts)
        recency_weight = max(0.25, 1 - age / COMMENT_WINDOW_SECONDS)
        per_user_seen: Counter[str] = Counter()
        for word in extract_words(msg.text):
            if not is_safe_keyword(word):
                filtered_counts[word] += 1
                total_filtered += 1
                continue
            per_user_seen[word] += 1
            capped_user_weight = min(1.4, 0.65 + 0.35 / per_user_seen[word])
            word_counts[word] += recency_weight * repeat_penalty * capped_user_weight
            word_users[word].add(msg.user_hash)

    scored = []
    old_words = {item["word"] for item in st.session_state.keywords}
    for word, base_score in word_counts.items():
        diversity = math.log1p(len(word_users[word])) * 1.8
        score = base_score + diversity
        scored.append((word, score, len(word_users[word])))
    scored.sort(key=lambda item: item[1], reverse=True)

    top_score = scored[0][1] if scored else 1
    next_keywords = []
    for idx, (word, score, users) in enumerate(scored[:MAX_KEYWORDS]):
        freshness = 1.0 if word not in old_words else 0.0
        next_keywords.append(
            {
                "word": word,
                "score": round(score, 3),
                "size": round(0.62 + (score / top_score) * 1.45, 3),
                "rank": idx + 1,
                "users": users,
                "fresh": freshness,
                "x": keyword_position(word, idx)[0],
                "y": keyword_position(word, idx)[1],
            }
        )

    if next_keywords:
        st.session_state.keywords = next_keywords
        st.session_state.last_keywords_snapshot = next_keywords
    elif not st.session_state.chat_window and st.session_state.get("keywords"):
        st.session_state.last_keywords_snapshot = st.session_state.keywords
    elif not st.session_state.chat_window and st.session_state.get("last_keywords_snapshot") and not force:
        st.session_state.keywords = st.session_state.last_keywords_snapshot
    else:
        st.session_state.keywords = []
    st.session_state.filtered_total += total_filtered
    st.session_state.filtered_top = filtered_counts.most_common(12)
    st.session_state.last_keyword_update = now


def keyword_position(word: str, idx: int) -> tuple[int, int]:
    digest = hashlib.md5(word.encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    columns = [10, 24, 40, 57, 71]
    rows = [26, 36, 47, 58, 68]
    x = columns[(idx + seed) % len(columns)] + (seed % 7) - 3
    y = rows[(idx * 2 + seed) % len(rows)] + ((seed // 7) % 7) - 3
    return max(7, min(78, x)), max(18, min(74, y))


def cloud_style_position(style: str, word: str, idx: int, total: int) -> tuple[float, float, float]:
    digest = hashlib.md5(f"{style}-{word}".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    total = max(1, total)
    angle = (idx / total) * math.tau + (seed % 40) / 40
    if style == "Vertical Cloud":
        x = 45 + ((idx % 3) - 1) * 16 + (seed % 9) - 4
        y = 10 + (idx / max(1, total - 1)) * 78
        rotation = 90 if idx % 5 == 0 else 0
    elif style == "Orbital Cloud":
        radius = 16 + (idx % 4) * 9
        x = 50 + math.cos(angle) * radius
        y = 50 + math.sin(angle) * radius * 0.78
        rotation = 0
    elif style == "Network Cloud":
        radius = 12 + (idx % 5) * 8
        x = 50 + math.cos(angle) * radius
        y = 50 + math.sin(angle * 1.17) * radius
        rotation = 0
    elif style == "Magazine Cloud":
        x, y = keyword_position(word, idx)
        rotation = [-4, 0, 0, 3, -2][idx % 5]
    elif style == "Minimal Cloud":
        x = 28 + (idx % 2) * 34 + (seed % 5)
        y = 30 + (idx // 2) * 13
        rotation = 0
    elif style == "Color Burst":
        x, y = keyword_position(word, idx)
        rotation = [0, 0, 90, -7, 5][idx % 5]
    elif style == "Bubble Cloud":
        x, y = keyword_position(word, idx)
        rotation = 0
    else:
        x, y = keyword_position(word, idx)
        rotation = 90 if idx % 9 == 0 else 0
    return max(7, min(93, x)), max(8, min(92, y)), rotation


def font_stack(name: str) -> str:
    return FONT_PRESETS.get(name, FONT_PRESETS["System Sans"])


def layout_font(layout: str | None = None) -> str:
    theme = THEMES.get(layout or st.session_state.get("layout", "Neon Pop"), THEMES["Neon Pop"])
    font = theme.get("font", "Poppins")
    return font if font in FONT_PRESETS else "Poppins"


def mark_typography_adjusted() -> None:
    st.session_state.user_adjusted_typography = True


def mark_image_look_adjusted() -> None:
    st.session_state.user_adjusted_image_look = True


def layout_typography(layout: str | None = None) -> dict[str, Any]:
    font = layout_font(layout)
    if font == "Bebas Neue":
        return {"topic_weight": 400, "topic_spacing": 1, "topic_size": 102, "keyword_weight": 400}
    if font in {"Playfair Display", "Georgia", "Merriweather"}:
        return {"topic_weight": 850, "topic_spacing": 0, "topic_size": 92, "keyword_weight": 760}
    if font == "Montserrat":
        return {"topic_weight": 850, "topic_spacing": 0, "topic_size": 88, "keyword_weight": 780}
    return {"topic_weight": 850, "topic_spacing": 0, "topic_size": 90, "keyword_weight": 760}


def apply_layout_typography(layout: str | None = None) -> None:
    font = layout_font(layout)
    typo = layout_typography(layout)
    st.session_state.topic_font_family = font
    st.session_state.highlight_font_family = font
    st.session_state.topic_font_weight = typo["topic_weight"]
    st.session_state.topic_letter_spacing = typo["topic_spacing"]
    st.session_state.topic_text_size = typo["topic_size"]
    st.session_state.topic_text_transform = "normal"
    st.session_state.keyword_font_family = "Inter"
    st.session_state.keyword_font_weight = typo["keyword_weight"]
    st.session_state.highlight_font_weight = max(700, int(typo["topic_weight"]))
    st.session_state.highlight_letter_spacing = 0
    st.session_state.countdown_font_family = "Inter"
    st.session_state.countdown_font_weight = 850
    st.session_state.user_adjusted_typography = False


def stabilize_image_look_for_layout_switch() -> None:
    st.session_state.bg_dim = min(int(st.session_state.get("bg_dim", 12) or 12), 18)
    st.session_state.bg_blur = min(int(st.session_state.get("bg_blur", 0) or 0), 4)
    st.session_state.bg_brightness = max(int(st.session_state.get("bg_brightness", 125) or 125), 125)
    st.session_state.bg_opacity = max(int(st.session_state.get("bg_opacity", 100) or 100), 100)
    st.session_state.overlay_opacity = max(int(st.session_state.get("overlay_opacity", 100) or 100), 100)


# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------

def init_state() -> None:
    existing_defaults_version = int(st.session_state.get("defaults_version", 0) or 0)
    defaults = {
        "target_input": "",
        "defaults_version": DEFAULTS_VERSION,
        "topic": "Worueber sprechen wir gerade?",
        "topic_draft": "Worueber sprechen wir gerade?",
        "highlight_word": "",
        "highlight_draft": "",
        "auto_highlight": False,
        "manual_cloud_words_text": "",
        "manual_word_size": 130,
        "manual_words_emphasis": True,
        "countdown_title": "Q&A startet in",
        "countdown_minutes": 10,
        "countdown_total": 10 * 60,
        "countdown_remaining": 10 * 60,
        "countdown_running": False,
        "countdown_started_at": None,
        "show_live_since": True,
        "layout": "Neon Pop",
        "cloud_style": "Color Burst",
        "cloud_style_locked": False,
        "aspect": DEFAULT_ASPECT,
        "show_topic": True,
        "show_cloud": True,
        "show_highlight": False,
        "show_countdown": False,
        "show_clock": True,
        "show_background": True,
        "show_animations": True,
        "show_safe_zones": False,
        "show_overlay_frame": False,
        "minimal_mode": False,
        "freeze_keywords": False,
        "focus_mode": False,
        "clear_overlay": False,
        "bg_dim": 12,
        "bg_blur": 0,
        "bg_brightness": 125,
        "keyword_size": 50,
        "keyword_density": 38,
        "animation_intensity": 55,
        "show_motion_layers": True,
        "motion_effects": ["Aerosol-Wolken"],
        "motion_opacity": 45,
        "motion_speed": 55,
        "show_heatmap": False,
        "heatmap_opacity": 28,
        "cloud_pos_x": 50,
        "cloud_pos_y": 55,
        "cloud_width": 60,
        "cloud_height": 58,
        "cloud_tilt": 0,
        "topic_x": 36,
        "topic_y": 18,
        "topic_width": 68,
        "topic_height": 24,
        "highlight_x": 35,
        "highlight_y": 43,
        "highlight_width": 62,
        "highlight_height": 18,
        "countdown_x": 24,
        "countdown_y": 82,
        "countdown_width": 32,
        "countdown_height": 12,
        "clock_x": 82,
        "clock_y": 12,
        "clock_width": 24,
        "clock_height": 9,
        "ai_x": 36,
        "ai_y": 70,
        "ai_width": 58,
        "ai_height": 26,
        "topic_text_size": 92,
        "highlight_text_size": 100,
        "countdown_text_size": 100,
        "clock_text_size": 100,
        "topic_font_family": "Poppins",
        "topic_font_weight": 850,
        "topic_letter_spacing": 0,
        "topic_text_transform": "normal",
        "keyword_font_family": "Inter",
        "keyword_font_weight": 760,
        "keyword_random_weight": False,
        "highlight_font_family": "Poppins",
        "highlight_font_weight": 900,
        "highlight_letter_spacing": 0,
        "countdown_font_family": "Inter",
        "countdown_font_weight": 850,
        "overlay_opacity": 100,
        "transition_speed": 55,
        "bg_opacity": 100,
        "bg_zoom": 100,
        "bg_pos_x": 50,
        "bg_pos_y": 50,
        "bg_fit": "cover",
        "images": [],
        "active_image_id": None,
        "stage_images": [],
        "active_stage_image_id": None,
        "show_stage_image": False,
        "stage_image_x": 50,
        "stage_image_y": 52,
        "stage_image_width": 42,
        "stage_image_height": 32,
        "stage_image_opacity": 100,
        "stage_image_fit": "contain",
        "stage_image_radius": 10,
        "show_video": False,
        "video_url": "",
        "video_show_background": True,
        "video_x": 50,
        "video_y": 54,
        "video_width": 70,
        "video_height": 40,
        "video_opacity": 100,
        "video_fit": "contain",
        "video_muted": False,
        "show_website": False,
        "website_url": "",
        "website_mode": "Auto",
        "website_preview_title": "",
        "website_preview_text": "",
        "website_preview_image": "",
        "website_preview_error": "",
        "neko_url": "",
        "neko_password": "",
        "website_proxy_html": "",
        "website_proxy_error": "",
        "website_x": 50,
        "website_y": 54,
        "website_width": 76,
        "website_height": 58,
        "show_pdf": False,
        "pdf_name": "",
        "pdf_data": "",
        "pdf_orientation": "Hochformat",
        "pdf_x": 50,
        "pdf_y": 54,
        "pdf_width": 76,
        "pdf_height": 72,
        "pdf_zoom": 100,
        "show_ai_card": False,
        "ai_prompt": "",
        "ai_response": "",
        "ai_error": "",
        "ai_model": "gemini-2.5-flash",
        "ai_max_chars": 1200,
        "image_prompt": "",
        "image_model": "auto",
        "image_prompt_use_chat": True,
        "image_generation_error": "",
        "overlay_room_id": "",
        "chat_window": deque(maxlen=5000),
        "keywords": [],
        "last_keywords_snapshot": [],
        "last_keyword_update": 0.0,
        "filtered_total": 0,
        "filtered_top": [],
        "custom_blacklist_text": "",
        "custom_whitelist_text": "",
        "scenes": {},
        "last_active_scene": "",
        "persist_loaded": False,
        "browser_id": "",
        "backup_import_text": "",
        "user_adjusted_cloud_position": False,
        "user_adjusted_image_look": False,
        "user_adjusted_typography": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.layout in LEGACY_LAYOUT_MAP:
        st.session_state.layout = LEGACY_LAYOUT_MAP[st.session_state.layout]
    if not st.session_state.get("user_adjusted_typography", False):
        apply_layout_typography(st.session_state.layout)
    else:
        if st.session_state.get("topic_font_family") not in FONT_PRESETS:
            st.session_state.topic_font_family = layout_font(st.session_state.layout)
        if st.session_state.get("highlight_font_family") not in FONT_PRESETS:
            st.session_state.highlight_font_family = st.session_state.topic_font_family
        if st.session_state.get("keyword_font_family") not in FONT_PRESETS:
            st.session_state.keyword_font_family = "Inter"
    if st.session_state.get("ai_model") in LEGACY_AI_MODEL_MAP:
        st.session_state.ai_model = LEGACY_AI_MODEL_MAP[st.session_state.ai_model]
    if st.session_state.get("ai_model") not in AI_MODELS:
        st.session_state.ai_model = "gemini-2.5-flash"
    if is_ai_error_text(st.session_state.get("ai_response", "")):
        st.session_state.ai_error = st.session_state.ai_response
        st.session_state.ai_response = ""
        st.session_state.show_ai_card = False
    st.session_state.motion_effects = normalize_motion_effects(st.session_state.get("motion_effects", []))
    if st.session_state.get("keywords") and not st.session_state.get("last_keywords_snapshot"):
        st.session_state.last_keywords_snapshot = st.session_state.keywords
    if "bg_brightness" not in st.session_state:
        st.session_state.bg_brightness = 115
    if not st.session_state.get("user_adjusted_cloud_position"):
        st.session_state.cloud_pos_x = 50
        st.session_state.cloud_pos_y = 50
    if not st.session_state.get("user_adjusted_image_look") and st.session_state.get("bg_dim", 25) > 45:
        st.session_state.bg_dim = 25
        st.session_state.bg_brightness = max(115, st.session_state.get("bg_brightness", 115))
    if not st.session_state.overlay_room_id:
        st.session_state.overlay_room_id = safe_profile_id(st.session_state.browser_id or str(uuid.uuid4()))[:18]
    if not st.session_state.scenes:
        st.session_state.scenes = build_default_scenes()
    if existing_defaults_version < DEFAULTS_VERSION:
        apply_visual_defaults_v3()


def build_default_scenes() -> dict[str, dict[str, Any]]:
    base = {
        "show_topic": True,
        "show_cloud": True,
        "show_highlight": True,
        "show_countdown": False,
        "show_clock": True,
        "show_live_since": True,
        "show_background": True,
        "show_animations": True,
        "show_safe_zones": False,
        "show_overlay_frame": True,
        "minimal_mode": False,
        "focus_mode": False,
        "clear_overlay": False,
    }
    return {
        "Intro": {**base, "layout": "Editorial Dark", "cloud_style": "Magazine Cloud", "topic": "Willkommen im Live", "show_countdown": True, "animation_intensity": 35},
        "Diskussion": {**base, "layout": "Neon Pop", "cloud_style": "Color Burst", "topic": "Diskussion", "cloud_width": 58, "keyword_density": 45, "show_highlight": False},
        "Q&A": {**base, "layout": "Neon Pop", "cloud_style": "Color Burst", "topic": "Q&A", "show_countdown": True, "animation_intensity": 68},
        "Deep Dive": {**base, "layout": "System Map", "cloud_style": "Network Cloud", "topic": "Deep Dive", "focus_mode": False, "cloud_width": 74},
        "Fazit": {**base, "layout": "Soft Power", "cloud_style": "Minimal Cloud", "topic": "Fazit", "focus_mode": True, "keyword_density": 45},
    }


def snapshot_scene() -> dict[str, Any]:
    keys = [
        "defaults_version",
        "layout", "cloud_style", "cloud_style_locked", "active_image_id", "show_topic", "show_cloud", "show_highlight", "show_countdown",
        "show_clock", "show_background", "show_animations", "show_safe_zones", "show_overlay_frame",
        "show_live_since",
        "minimal_mode", "topic", "highlight_word", "manual_cloud_words_text", "manual_word_size",
        "manual_words_emphasis", "countdown_title", "countdown_total",
        "countdown_remaining", "countdown_running", "bg_dim", "bg_blur", "bg_brightness", "bg_opacity", "bg_zoom",
        "bg_pos_x", "bg_pos_y", "bg_fit", "keyword_size", "keyword_density", "animation_intensity",
        "motion_effects", "motion_opacity", "motion_speed", "show_heatmap", "heatmap_opacity",
        "show_motion_layers",
        "cloud_pos_x", "cloud_pos_y", "cloud_width", "cloud_height", "cloud_tilt",
        "topic_x", "topic_y", "topic_width", "topic_height",
        "highlight_x", "highlight_y", "highlight_width", "highlight_height",
        "countdown_x", "countdown_y", "countdown_width", "countdown_height",
        "clock_x", "clock_y", "clock_width", "clock_height",
        "ai_x", "ai_y", "ai_width", "ai_height",
        "show_stage_image", "active_stage_image_id", "stage_image_x", "stage_image_y", "stage_image_width", "stage_image_height",
        "stage_image_opacity", "stage_image_fit", "stage_image_radius",
        "topic_text_size",
        "highlight_text_size", "countdown_text_size", "clock_text_size", "topic_font_family", "topic_font_weight",
        "topic_letter_spacing", "topic_text_transform", "keyword_font_family", "keyword_font_weight",
        "keyword_random_weight", "highlight_font_family", "highlight_font_weight", "highlight_letter_spacing",
        "countdown_font_family", "countdown_font_weight", "overlay_opacity", "transition_speed",
        "focus_mode", "clear_overlay", "user_adjusted_cloud_position", "user_adjusted_image_look", "user_adjusted_typography",
        "show_video", "video_url", "video_show_background", "video_x", "video_y", "video_width", "video_height",
        "video_opacity", "video_fit", "video_muted", "show_website", "website_url", "website_mode",
        "website_preview_title", "website_preview_text", "website_preview_error", "website_proxy_html", "website_proxy_error", "website_x", "website_y",
        "website_width", "website_height", "show_pdf", "pdf_name", "pdf_data", "pdf_orientation", "pdf_x", "pdf_y",
        "pdf_width", "pdf_height", "pdf_zoom", "show_ai_card", "ai_prompt", "ai_response", "ai_error", "ai_model", "overlay_room_id",
        "ai_max_chars", "image_prompt", "image_model", "image_prompt_use_chat", "image_generation_error",
    ]
    return {key: st.session_state.get(key) for key in keys}


def apply_visual_defaults_v3() -> None:
    """Legacy migration helper, jetzt v5. Setzt den aktuellen Regie-Default."""
    st.session_state.layout = "Neon Pop"
    st.session_state.cloud_style = "Color Burst"
    st.session_state.show_highlight = False
    st.session_state.auto_highlight = False
    st.session_state.keyword_size = min(int(st.session_state.get("keyword_size", 50) or 50), 55)
    st.session_state.keyword_density = min(int(st.session_state.get("keyword_density", 38) or 38), 45)
    st.session_state.cloud_pos_x = 50
    st.session_state.cloud_pos_y = 55
    st.session_state.cloud_width = min(int(st.session_state.get("cloud_width", 60) or 60), 64)
    st.session_state.cloud_height = min(int(st.session_state.get("cloud_height", 58) or 58), 60)
    apply_layout_typography("Neon Pop")
    st.session_state.motion_effects = ["Aerosol-Wolken"]
    st.session_state.show_motion_layers = True
    st.session_state.motion_opacity = max(45, int(st.session_state.get("motion_opacity", 45) or 45))
    st.session_state.bg_dim = min(18, int(st.session_state.get("bg_dim", 18) or 18))
    st.session_state.bg_brightness = max(125, int(st.session_state.get("bg_brightness", 125) or 125))
    st.session_state.show_clock = True
    st.session_state.show_overlay_frame = False
    st.session_state.defaults_version = DEFAULTS_VERSION


def normalize_motion_effects(effects: Any) -> list[str]:
    normalized: list[str] = []
    for effect in effects or []:
        mapped = MOTION_EFFECT_MAP.get(effect, effect)
        if mapped in MOTION_EFFECTS and mapped not in normalized:
            normalized.append(mapped)
    return normalized


def apply_scene(scene: dict[str, Any]) -> None:
    for key, value in scene.items():
        if key in st.session_state:
            st.session_state[key] = value
    if st.session_state.layout in LEGACY_LAYOUT_MAP:
        st.session_state.layout = LEGACY_LAYOUT_MAP[st.session_state.layout]
    if st.session_state.get("ai_model") in LEGACY_AI_MODEL_MAP:
        st.session_state.ai_model = LEGACY_AI_MODEL_MAP[st.session_state.ai_model]
    if st.session_state.get("ai_model") not in AI_MODELS:
        st.session_state.ai_model = "gemini-2.5-flash"
    if is_ai_error_text(st.session_state.get("ai_response", "")):
        st.session_state.ai_error = st.session_state.ai_response
        st.session_state.ai_response = ""
        st.session_state.show_ai_card = False
    st.session_state.motion_effects = normalize_motion_effects(st.session_state.get("motion_effects", []))
    st.session_state.topic_draft = st.session_state.topic
    st.session_state.highlight_draft = st.session_state.highlight_word


def persistent_payload() -> dict[str, Any]:
    payload = snapshot_scene()
    payload.update(
        {
            "version": 2,
            "browser_id": st.session_state.browser_id or str(uuid.uuid4()),
            "overlay_room_id": st.session_state.overlay_room_id,
            "images": st.session_state.images,
            "active_image_id": st.session_state.active_image_id,
            "stage_images": st.session_state.stage_images,
            "active_stage_image_id": st.session_state.active_stage_image_id,
            "scenes": st.session_state.scenes,
            "custom_blacklist_text": st.session_state.custom_blacklist_text,
            "custom_whitelist_text": st.session_state.custom_whitelist_text,
            "last_active_scene": st.session_state.last_active_scene,
        }
    )
    return payload


def safe_profile_id(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]", "", value or "")
    return value[:80] or "default"


def profile_state_file(browser_id: str | None = None) -> Path:
    SERVER_STATE_DIR.mkdir(exist_ok=True)
    return SERVER_STATE_DIR / f"{safe_profile_id(browser_id or st.session_state.get('browser_id', 'default'))}.json"


def room_state_file(room_id: str | None = None) -> Path:
    SERVER_STATE_DIR.mkdir(exist_ok=True)
    return SERVER_STATE_DIR / f"room_{safe_profile_id(room_id or st.session_state.get('overlay_room_id', 'default'))}.json"


def static_state_file(room_id: str | None = None) -> Path:
    STATIC_DIR.mkdir(exist_ok=True)
    return STATIC_DIR / f"overlay_state_{safe_profile_id(room_id or st.session_state.get('overlay_room_id', 'default'))}.json"


# GitHub-Pages-URL der öffentlichen Bühne. Diese URL ist immer ohne Auth
# erreichbar — das ist der einzige Pfad, der zuverlässig in TikTok Live Studio
# als Browserquelle funktioniert. State-Sync läuft über GitHub Gist (siehe
# render_gist_sync_panel / push_state_to_gist).
GITHUB_PAGES_BASE = "https://sustynats.github.io/ttliveregie"


def _is_streamlit_cloud_runtime() -> bool:
    """Erkennt, ob das Regiepult auf Streamlit Cloud läuft.

    Prüft Host-Header (über st.context, sofern verfügbar) und Cloud-typische
    Environment-Variablen.
    """
    try:
        ctx = getattr(st, "context", None)
        if ctx is not None:
            headers = getattr(ctx, "headers", None)
            if headers is not None:
                host = (headers.get("Host") or headers.get("host") or "").lower()
                if host.endswith(".streamlit.app") or host.endswith(".streamlitapp.com"):
                    return True
    except Exception:
        pass
    if os.environ.get("HOSTNAME", "").startswith("streamlit-"):
        return True
    if os.environ.get("STREAMLIT_RUNTIME_ENV", "").lower() == "cloud":
        return True
    if os.environ.get("STREAMLIT_SHARING_MODE", "").lower() in {"cloud", "share"}:
        return True
    return False


def static_overlay_url(base_url: str, room_id: str, **params: str) -> str:
    """Lokale Streamlit-Static-URL der Bühne (nur für `streamlit run` zuhause).

    Für Streamlit Cloud nicht geeignet — dort triggert `/app/static/` einen
    Auth-Redirect, solange die App nicht wirklich public ist. Verwende stattdessen
    `github_pages_stage_url()` für die produktive TTLS-Browserquelle.
    """
    query: dict[str, str] = {"room": safe_profile_id(room_id), "v": str(DEFAULTS_VERSION)}
    query.update({key: value for key, value in params.items() if value})
    encoded = "&".join(f"{key}={value}" for key, value in query.items())
    return f"{base_url.rstrip('/')}/app/static/{STATIC_STAGE_FILE.name}?{encoded}"


def github_pages_stage_url(
    room_id: str | None = None,
    gist_id: str | None = None,
    gist_user: str | None = None,
    **params: str,
) -> str:
    """Public GitHub-Pages-URL der Bühne mit Gist-State-Quelle.

    Genau diese URL gehört in TikTok Live Studio als Browserquelle. Sie ist
    nicht auth-protected, lädt direkt eine statische HTML-Datei und pollt einen
    GitHub-Gist (Raw-URL) für State-Updates aus dem Regiepult.
    """
    room = safe_profile_id(room_id or st.session_state.get("overlay_room_id", "default") or "default")
    query: dict[str, str] = {"room": room, "v": str(DEFAULTS_VERSION)}
    if gist_id:
        query["gist"] = gist_id
    if gist_user:
        query["gist_user"] = gist_user
    query.update({k: v for k, v in params.items() if v})
    encoded = "&".join(f"{k}={v}" for k, v in query.items())
    return f"{GITHUB_PAGES_BASE}/stage.html?{encoded}"


def apply_persistent_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    allowed = set(snapshot_scene()) | {
        "browser_id",
        "images",
        "active_image_id",
        "stage_images",
        "active_stage_image_id",
        "scenes",
        "custom_blacklist_text",
        "custom_whitelist_text",
        "last_active_scene",
        "overlay_room_id",
        "defaults_version",
    }
    for key, value in payload.items():
        if key in allowed:
            st.session_state[key] = value
    if st.session_state.layout in LEGACY_LAYOUT_MAP:
        st.session_state.layout = LEGACY_LAYOUT_MAP[st.session_state.layout]
    if st.session_state.get("ai_model") in LEGACY_AI_MODEL_MAP:
        st.session_state.ai_model = LEGACY_AI_MODEL_MAP[st.session_state.ai_model]
    if st.session_state.get("ai_model") not in AI_MODELS:
        st.session_state.ai_model = "gemini-2.5-flash"
    if int(payload.get("defaults_version", 0) or 0) < DEFAULTS_VERSION:
        apply_visual_defaults_v3()
    elif not st.session_state.get("user_adjusted_typography", False):
        apply_layout_typography(st.session_state.layout)
    else:
        if st.session_state.get("topic_font_family") not in FONT_PRESETS:
            st.session_state.topic_font_family = layout_font(st.session_state.layout)
        if st.session_state.get("highlight_font_family") not in FONT_PRESETS:
            st.session_state.highlight_font_family = st.session_state.topic_font_family
        if st.session_state.get("keyword_font_family") not in FONT_PRESETS:
            st.session_state.keyword_font_family = "Inter"
    if is_ai_error_text(st.session_state.get("ai_response", "")):
        st.session_state.ai_error = st.session_state.ai_response
        st.session_state.ai_response = ""
        st.session_state.show_ai_card = False
    st.session_state.motion_effects = normalize_motion_effects(st.session_state.get("motion_effects", []))
    # Wichtig: Ein gespeicherter Zustand mit allen Elementen aus ist kein
    # kaputter State, sondern ein legitimer Live-Cue ("Hide All" / "Clear").
    # Frueher wurden hier Safe-Defaults erzwungen; dadurch sprang das Thema
    # nach dem Ausschalten scheinbar von selbst wieder auf die Buehne.
    if not payload.get("user_adjusted_cloud_position"):
        st.session_state.cloud_pos_x = 50
        st.session_state.cloud_pos_y = 50
    if not payload.get("user_adjusted_image_look") and st.session_state.get("bg_dim", 25) > 45:
        st.session_state.bg_dim = 25
        st.session_state.bg_brightness = max(115, st.session_state.get("bg_brightness", 115))
    st.session_state.topic_draft = st.session_state.topic
    st.session_state.highlight_draft = st.session_state.highlight_word


def reset_stage_to_safe_defaults() -> None:
    st.session_state.layout = "Neon Pop"
    st.session_state.cloud_style = "Color Burst"
    st.session_state.cloud_style_locked = False
    st.session_state.show_topic = True
    st.session_state.show_cloud = True
    st.session_state.show_highlight = False
    st.session_state.show_countdown = False
    st.session_state.show_clock = True
    st.session_state.show_live_since = True
    st.session_state.show_background = True
    st.session_state.show_overlay_frame = True
    st.session_state.show_animations = True
    st.session_state.show_motion_layers = True
    st.session_state.clear_overlay = False
    st.session_state.minimal_mode = False
    st.session_state.focus_mode = False
    apply_layout_typography("Neon Pop")
    st.session_state.topic_font_weight = 850
    st.session_state.keyword_font_weight = 760
    st.session_state.topic_letter_spacing = 0
    st.session_state.topic_text_transform = "normal"
    st.session_state.topic_text_size = 90
    st.session_state.keyword_size = 55
    st.session_state.keyword_density = 45
    st.session_state.cloud_pos_x = 50
    st.session_state.cloud_pos_y = 50
    st.session_state.cloud_width = 58
    st.session_state.cloud_height = 58
    st.session_state.topic_x = 36
    st.session_state.topic_y = 18
    st.session_state.topic_width = 68
    st.session_state.topic_height = 24
    st.session_state.bg_dim = 12
    st.session_state.bg_blur = 0
    st.session_state.bg_brightness = 125
    st.session_state.bg_opacity = 100
    st.session_state.overlay_opacity = 100


def load_persisted_state_once() -> None:
    if st.session_state.persist_loaded:
        return
    loaded = None
    browser_id = None
    if get_local_storage is not None:
        try:
            browser_id = get_local_storage(LOCAL_BROWSER_ID_KEY, component_key="browser_id_load")
            if not browser_id:
                browser_id = str(uuid.uuid4())
                if streamlit_js_eval is not None:
                    streamlit_js_eval(
                        js_expressions=f"localStorage.setItem({json.dumps(LOCAL_BROWSER_ID_KEY)}, {json.dumps(browser_id)})",
                        key="browser_id_create",
                    )
            st.session_state.browser_id = browser_id
            raw = get_local_storage(LOCAL_STORAGE_KEY, component_key="persist_load")
            fallback_file = profile_state_file(browser_id)
            if raw is None and not fallback_file.exists():
                if not st.session_state.browser_id:
                    st.session_state.browser_id = str(uuid.uuid4())
                return
            if raw:
                loaded = json.loads(raw)
        except Exception:
            loaded = None
    fallback_file = profile_state_file(browser_id or st.session_state.browser_id)
    if loaded is None and fallback_file.exists():
        try:
            loaded = json.loads(fallback_file.read_text(encoding="utf-8"))
        except Exception:
            loaded = None
    if loaded:
        apply_persistent_payload(loaded)
    if not st.session_state.browser_id:
        st.session_state.browser_id = str(uuid.uuid4())
    st.session_state.persist_loaded = True


def save_persisted_state(reason: str = "auto") -> None:
    payload = persistent_payload()
    data = json.dumps(payload, ensure_ascii=False)
    try:
        profile_state_file(payload.get("browser_id")).write_text(data, encoding="utf-8")
        room_state_file(payload.get("overlay_room_id")).write_text(json.dumps(current_overlay_state(), ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    if streamlit_js_eval is not None:
        digest = hashlib.sha1(data.encode("utf-8")).hexdigest()[:12]
        js = (
            f"localStorage.setItem({json.dumps(LOCAL_BROWSER_ID_KEY)}, {json.dumps(payload.get('browser_id'))});"
            f"localStorage.setItem({json.dumps(LOCAL_STORAGE_KEY)}, {json.dumps(data)})"
        )
        try:
            streamlit_js_eval(js_expressions=js, key=f"persist_save_{reason}_{digest}")
        except Exception:
            pass


def clear_persisted_state() -> None:
    if streamlit_js_eval is not None:
        streamlit_js_eval(
            js_expressions=f"localStorage.removeItem({json.dumps(LOCAL_STORAGE_KEY)})",
            key=f"persist_clear_{int(time.time())}",
        )
    try:
        profile_state_file().unlink(missing_ok=True)
    except Exception:
        pass


def update_countdown() -> None:
    if st.session_state.countdown_running and st.session_state.countdown_started_at:
        elapsed = time.time() - st.session_state.countdown_started_at
        st.session_state.countdown_remaining = max(0, int(st.session_state.countdown_total - elapsed))
        if st.session_state.countdown_remaining <= 0:
            st.session_state.countdown_running = False


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return "00:00:00"
    seconds = int(max(0, seconds))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def readable_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = f"https://{value}"
    return value


def youtube_embed_url(value: str, autoplay: bool = False, muted: bool = False) -> str:
    url = readable_url(value)
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    video_id = ""
    if "youtu.be" in host:
        video_id = parsed.path.strip("/").split("/")[0]
    elif "youtube.com" in host:
        if parsed.path.startswith("/watch"):
            query = dict(part.split("=", 1) for part in parsed.query.split("&") if "=" in part)
            video_id = query.get("v", "")
        elif "/shorts/" in parsed.path or "/embed/" in parsed.path:
            parts = [part for part in parsed.path.split("/") if part]
            video_id = parts[-1] if parts else ""
    if not video_id:
        return ""
    params = (
        f"controls=1&rel=0&playsinline=1&enablejsapi=0"
        f"&autoplay={1 if autoplay else 0}&mute={1 if muted else 0}"
    )
    return f"https://www.youtube-nocookie.com/embed/{html.escape(video_id)}?{params}"


def is_youtube_url(value: str) -> bool:
    host = url_host(value)
    return "youtube.com" in host or "youtu.be" in host


def url_host(value: str) -> str:
    try:
        return urlparse(readable_url(value)).netloc.lower()
    except Exception:
        return ""


def is_known_iframe_blocked(value: str) -> bool:
    host = url_host(value)
    return host in IFRAME_BLOCKED_DOMAINS or any(host.endswith(f".{domain}") for domain in IFRAME_BLOCKED_DOMAINS)


def fetch_website_og(url: str) -> dict[str, str]:
    """Holt og:title/og:description/og:image für eine URL — best effort.

    Wird vom Bühnen-iFrame als Fallback genutzt, wenn iframe oder Screenshot
    scheitern. Sehr klein gehalten, weil es im selben Request-Pfad wie
    fetch_website_preview läuft.
    """
    cleaned = readable_url(url)
    out = {"title": "", "description": "", "image": ""}
    if not cleaned or requests is None or BeautifulSoup is None:
        return out
    try:
        resp = requests.get(
            cleaned,
            timeout=6,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; TTLiveRegie/1.0; +https://ttliveregie.streamlit.app)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        ot = soup.find("meta", property="og:title")
        out["title"] = (ot.get("content") if ot else "") or (soup.title.get_text(" ", strip=True) if soup.title else "")
        od = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        out["description"] = od.get("content", "") if od else ""
        oi = soup.find("meta", property="og:image")
        out["image"] = oi.get("content", "") if oi else ""
        if out["image"] and not out["image"].startswith(("http://", "https://")):
            out["image"] = urljoin(cleaned, out["image"])
    except Exception:
        pass
    return out


def fetch_website_preview(url: str) -> tuple[bool, str, str]:
    url = readable_url(url)
    if not url:
        return False, "", "Bitte erst eine Website-URL eingeben."
    if requests is None or BeautifulSoup is None:
        return False, "", "Website-Vorschau benoetigt requests und beautifulsoup4 aus requirements.txt."
    try:
        response = requests.get(
            url,
            timeout=8,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; TTLiveRegie/1.0; +https://ttliveregie.streamlit.app)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "footer"]):
            tag.decompose()
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title.get("content", "").strip()
        if not title and soup.title:
            title = soup.title.get_text(" ", strip=True)
        description = ""
        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            description = og_desc.get("content", "").strip()
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all(["h1", "h2", "p", "li"])]
        paragraphs = [text for text in paragraphs if len(text) > 45]
        body = " ".join([description] + paragraphs)
        body = re.sub(r"\s+", " ", body).strip()
        if len(body) > 2600:
            body = body[:2580].rsplit(" ", 1)[0] + " ..."
        if not title:
            title = url_host(url) or url
        if not body:
            body = "Die Seite wurde erreicht, aber es konnte kein gut lesbarer Text extrahiert werden."
        return True, title[:180], body
    except Exception as exc:
        return False, "", f"Website-Vorschau fehlgeschlagen: {exc}"


def fetch_website_proxy_html(url: str) -> tuple[bool, str]:
    url = readable_url(url)
    if not url:
        return False, "Bitte erst eine Website-URL eingeben."
    if requests is None or BeautifulSoup is None:
        return False, "Website-Proxy benoetigt requests und beautifulsoup4 aus requirements.txt."
    try:
        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
            },
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        if soup.head is None:
            head = soup.new_tag("head")
            if soup.html:
                soup.html.insert(0, head)
            else:
                soup.insert(0, head)
        base = soup.new_tag("base", href=url, target="_blank")
        soup.head.insert(0, base)
        for tag in soup.find_all(["script", "iframe", "object", "embed", "form"]):
            tag.decompose()
        for tag in soup.find_all(True):
            for attr in ("src", "href", "poster"):
                value = tag.get(attr)
                if value and not str(value).startswith(("data:", "blob:", "mailto:", "tel:", "#")):
                    tag[attr] = urljoin(url, value)
            for attr in ("srcset", "data-srcset"):
                if tag.get(attr):
                    tag[attr] = ""
        style = soup.new_tag("style")
        style.string = """
        html, body { margin:0; min-height:100%; background:#f7f4ee; color:#151515; font-family:Arial, Helvetica, sans-serif; }
        body { padding:24px; overflow:auto; }
        img, video { max-width:100%; height:auto; }
        a { color:#a01642; }
        article, main, body > div { max-width:1100px; }
        * { box-sizing:border-box; }
        """
        soup.head.append(style)
        proxied = "<!doctype html>\n" + str(soup)
        max_chars = 220_000
        if len(proxied) > max_chars:
            ok, title, text = fetch_website_preview(url)
            if ok:
                proxied = (
                    "<!doctype html><html><head><meta charset='utf-8'><style>"
                    "body{margin:0;padding:32px;background:#f7f4ee;color:#151515;font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:1.35}"
                    "h1{font-size:48px;line-height:1;margin:0 0 24px}small{color:#777;word-break:break-all}"
                    "</style></head><body>"
                    f"<h1>{html.escape(title)}</h1><p>{html.escape(text)}</p><small>{html.escape(url)}</small>"
                    "</body></html>"
                )
        return True, proxied
    except Exception as exc:
        return False, f"Website-Proxy fehlgeschlagen: {exc}"


def brighten_stage() -> None:
    st.session_state.bg_dim = 18
    st.session_state.bg_blur = 0
    st.session_state.bg_brightness = 125
    st.session_state.bg_opacity = 100
    st.session_state.overlay_opacity = 100
    st.session_state.clear_overlay = False
    set_background_visible(True)
    st.session_state.user_adjusted_image_look = True


_LAYER_FIELD_MAP: dict[str, dict[str, str]] = {
    "topic": {"label": "Thema", "x": "topic_x", "y": "topic_y", "w": "topic_width", "h": "topic_height", "show": "show_topic"},
    "highlight": {"label": "Highlight", "x": "highlight_x", "y": "highlight_y", "w": "highlight_width", "h": "highlight_height", "show": "show_highlight"},
    "cloud": {"label": "Wortwolke", "x": "cloud_pos_x", "y": "cloud_pos_y", "w": "cloud_width", "h": "cloud_height", "show": "show_cloud"},
    "countdown": {"label": "Countdown", "x": "countdown_x", "y": "countdown_y", "w": "countdown_width", "h": "countdown_height", "show": "show_countdown"},
    "clock": {"label": "Uhr", "x": "clock_x", "y": "clock_y", "w": "clock_width", "h": "clock_height", "show": "show_clock"},
    "video": {"label": "Video", "x": "video_x", "y": "video_y", "w": "video_width", "h": "video_height", "show": "show_video"},
    "website": {"label": "Website", "x": "website_x", "y": "website_y", "w": "website_width", "h": "website_height", "show": "show_website"},
    "pdf": {"label": "PDF", "x": "pdf_x", "y": "pdf_y", "w": "pdf_width", "h": "pdf_height", "show": "show_pdf"},
    "ai": {"label": "KI-Karte", "x": "ai_x", "y": "ai_y", "w": "ai_width", "h": "ai_height", "show": "show_ai_card"},
}
_LAYER_MIN_SIZE: dict[str, tuple[int, int]] = {
    "topic": (18, 8), "highlight": (16, 8), "cloud": (35, 35),
    "countdown": (18, 8), "clock": (12, 6), "video": (15, 10),
    "website": (20, 15), "pdf": (20, 20), "ai": (20, 12),
}


def google_api_key() -> str:
    import os as _os
    for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        try:
            value = st.secrets.get(key, "")
        except Exception:
            value = ""
        if value:
            return str(value)
    try:
        google_section = st.secrets.get("google", {})
        for key in ("api_key", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
            if google_section.get(key):
                return str(google_section.get(key))
    except Exception:
        pass
    # Fallback: Environment-Variablen (für lokale Entwicklung ohne Streamlit Secrets)
    for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_API_KEY"):
        value = _os.environ.get(key, "")
        if value:
            return value
    return ""


def is_ai_error_text(text: str) -> bool:
    markers = ("KI-Anfrage fehlgeschlagen", "RESOURCE_EXHAUSTED", "NOT_FOUND", "quota", "429", "404")
    return any(marker.lower() in (text or "").lower() for marker in markers)


def clamp_text(text: str, max_chars: int) -> str:
    max_chars = int(max(300, min(3000, max_chars or 1200)))
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 4].rstrip() + " ..."


def friendly_ai_error(exc: Exception) -> str:
    raw = str(exc)
    low = raw.lower()
    if "resource_exhausted" in low or "quota" in low or "429" in low:
        return (
            "Google hat das aktuelle Kontingent fuer dieses Modell/API-Projekt erreicht. "
            "Bitte spaeter erneut versuchen, in Google AI Studio das Kontingent prüfen oder ein anderes Modell waehlen."
        )
    if "not_found" in low or "404" in low or "is not found" in low:
        return "Dieses Gemini-Modell ist fuer deinen API-Key oder diese API-Version nicht verfuegbar. Bitte Gemini 2.5 Flash oder 2.5 Flash Lite waehlen."
    if "api key" in low or "permission" in low or "unauth" in low:
        return "Der Google API-Key wurde abgelehnt oder hat keine Berechtigung fuer Gemini. Bitte Streamlit Secrets und Google AI Studio pruefen."
    return f"KI-Anfrage fehlgeschlagen: {raw[:420]}"


def friendly_image_error(exc: Exception, model: str = "") -> str:
    raw = str(exc)
    low = raw.lower()
    label = IMAGE_MODEL_LABELS.get(model, model)
    if "resource_exhausted" in low or "quota" in low or "429" in low:
        return (
            f"{label}: Google-Kontingent fuer dieses Bildmodell/API-Projekt erreicht. "
            "Bitte anderes Bildmodell testen oder Kontingent/Billing in Google AI Studio pruefen."
        )
    if "not_found" in low or "404" in low or "is not found" in low:
        return f"{label}: Dieses Bildmodell ist fuer deinen API-Key oder diese API-Version nicht verfuegbar."
    if "api key" in low or "permission" in low or "unauth" in low or "forbidden" in low or "403" in low:
        return f"{label}: API-Key oder Berechtigung fuer Google-Bildgenerierung fehlt."
    if "safety" in low or "blocked" in low or "policy" in low:
        return f"{label}: Google hat den Bildprompt aus Safety-Gruenden blockiert. Bitte abstrakter und weniger politisch formulieren."
    return f"{label}: Bildgenerierung fehlgeschlagen: {raw[:360]}"


def render_copyable_url(label: str, url: str, key: str) -> None:
    st.markdown(f"**{label}**")
    st.text_input(label, value=url, key=f"{key}_url", label_visibility="collapsed", disabled=True)
    st.components.v1.html(
        f"""
        <button id="copy-{key}" style="
            width:100%;height:40px;border-radius:8px;border:1px solid rgba(255,255,255,.18);
            background:#242a31;color:#fff6ea;font-weight:800;cursor:pointer;font-family:system-ui;">
            URL kopieren
        </button>
        <script>
        const button = document.getElementById("copy-{key}");
        button.addEventListener("click", async () => {{
            try {{
                await navigator.clipboard.writeText({json.dumps(url)});
                button.textContent = "Kopiert";
                setTimeout(() => button.textContent = "URL kopieren", 1400);
            }} catch (error) {{
                button.textContent = "Kopieren fehlgeschlagen";
                setTimeout(() => button.textContent = "URL kopieren", 1800);
            }}
        }});
        </script>
        """,
        height=46,
        scrolling=False,
    )


def run_ai_summary(prompt: str) -> tuple[bool, str]:
    prompt = (prompt or "").strip()
    max_chars = int(max(300, min(3000, st.session_state.get("ai_max_chars", 1200))))
    model = LEGACY_AI_MODEL_MAP.get(st.session_state.get("ai_model", ""), st.session_state.get("ai_model", "gemini-2.5-flash"))
    if model not in AI_MODELS:
        model = "gemini-2.5-flash"
        st.session_state.ai_model = model
    if not prompt:
        return False, "Bitte erst eine Frage oder einen Text eingeben."
    if genai is None:
        return False, "Google GenAI Paket fehlt. Bitte requirements.txt deployen/installieren."
    api_key = google_api_key()
    if not api_key:
        return False, "Kein GOOGLE_API_KEY oder GEMINI_API_KEY in Streamlit Secrets gefunden."
    instruction = (
        "Fasse fuer ein TikTok-Live-Publikum sachlich, knapp und verstaendlich zusammen. "
        f"Antworte mit maximal {max_chars} Zeichen inklusive Leerzeichen. "
        "Schreibe nicht laenger als diese Zeichenbegrenzung. Keine personenbezogenen Daten erfinden. "
        "Wenn Fakten unsicher sind, klar kennzeichnen.\n\n"
        f"Prompt:\n{prompt}"
    )
    try:
        client = genai.Client(api_key=api_key)
        kwargs: dict[str, Any] = {"model": model, "contents": instruction}
        if genai_types is not None:
            token_budget = max(128, min(1100, math.ceil(max_chars / 2.6)))
            kwargs["config"] = genai_types.GenerateContentConfig(max_output_tokens=token_budget, temperature=0.25)
        response = client.models.generate_content(**kwargs)
        text = getattr(response, "text", "") or ""
        text = clamp_text(text, max_chars)
        return True, text or "Keine Antwort erhalten."
    except Exception as exc:
        return False, friendly_ai_error(exc)


def recent_chat_words(limit_messages: int = 120) -> list[str]:
    cutoff = time.time() - 5 * 60
    words: list[str] = []
    for msg in list(st.session_state.chat_window)[-limit_messages:]:
        if msg.ts >= cutoff:
            words.extend(word for word in extract_words(msg.text) if is_safe_keyword(word))
    return words


def chat_context_for_prompt() -> str:
    top_words = [word for word, _ in Counter(recent_chat_words()).most_common(18)]
    if st.session_state.keywords:
        top_words = [item["word"] for item in st.session_state.keywords[:18]] or top_words
    topic = st.session_state.get("topic", "")
    return f"Thema: {topic}. Chat-Schwerpunkte der letzten 5 Minuten: {', '.join(top_words) or 'noch keine Chatdaten'}."


def store_generated_background(data: bytes | str, mime_type: str = "image/png", model: str = "") -> str:
    encoded = data if isinstance(data, str) else base64.b64encode(data).decode("ascii")
    data_url = f"data:{mime_type or 'image/png'};base64,{encoded}"
    image_id = hashlib.sha1(data_url.encode("utf-8")).hexdigest()[:12]
    title = f"KI-Bild {time.strftime('%H:%M:%S')}"
    for item in st.session_state.images:
        if item.get("id") == image_id or item.get("data_url") == data_url:
            st.session_state.active_image_id = item.get("id", image_id)
            set_background_visible(True)
            st.session_state.bg_brightness = 118
            st.session_state.bg_dim = 24
            st.session_state.image_generation_error = ""
            return f"Vorhandenes Hintergrundbild mit {IMAGE_MODEL_LABELS.get(model, model)} wieder aktiviert."
    st.session_state.images.append({"id": image_id, "name": title, "title": title, "data_url": data_url})
    st.session_state.active_image_id = image_id
    set_background_visible(True)
    st.session_state.bg_brightness = 118
    st.session_state.bg_dim = 24
    st.session_state.image_generation_error = ""
    return f"Hintergrundbild mit {IMAGE_MODEL_LABELS.get(model, model)} generiert und aktiviert."


def normalize_image_library() -> None:
    images = st.session_state.get("images", [])
    if not isinstance(images, list):
        st.session_state.images = []
        st.session_state.active_image_id = None
        return
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_data: set[str] = set()
    active_id = st.session_state.get("active_image_id")
    active_data = ""
    for item in images:
        if isinstance(item, dict) and item.get("id") == active_id:
            active_data = item.get("data_url", "")
            break
    for index, item in enumerate(images):
        if not isinstance(item, dict):
            continue
        data_url = str(item.get("data_url", "") or "")
        if not data_url or data_url in seen_data:
            continue
        raw_id = str(item.get("id", "") or hashlib.sha1(data_url.encode("utf-8")).hexdigest()[:12])
        image_id = re.sub(r"[^a-zA-Z0-9_-]", "", raw_id)[:48] or hashlib.sha1(data_url.encode("utf-8")).hexdigest()[:12]
        if image_id in seen_ids:
            image_id = f"{hashlib.sha1((data_url + str(index)).encode('utf-8')).hexdigest()[:12]}_{index}"
        seen_ids.add(image_id)
        seen_data.add(data_url)
        item = dict(item)
        item["id"] = image_id
        item.setdefault("name", item.get("title", "Bild"))
        item.setdefault("title", item.get("name", "Bild"))
        normalized.append(item)
    st.session_state.images = normalized
    if active_id and not any(item.get("id") == active_id for item in normalized):
        replacement = next((item.get("id") for item in normalized if active_data and item.get("data_url") == active_data), None)
        st.session_state.active_image_id = replacement


def normalize_stage_image_library() -> None:
    images = st.session_state.get("stage_images", [])
    if not isinstance(images, list):
        st.session_state.stage_images = []
        st.session_state.active_stage_image_id = None
        return
    normalized: list[dict[str, Any]] = []
    seen_data: set[str] = set()
    active_id = st.session_state.get("active_stage_image_id")
    active_data = ""
    for item in images:
        if isinstance(item, dict) and item.get("id") == active_id:
            active_data = item.get("data_url", "")
            break
    for index, item in enumerate(images):
        if not isinstance(item, dict):
            continue
        data_url = str(item.get("data_url", "") or "")
        if not data_url or data_url in seen_data:
            continue
        image_id = str(item.get("id") or hashlib.sha1(data_url.encode("utf-8")).hexdigest()[:12])
        image_id = re.sub(r"[^a-zA-Z0-9_-]", "", image_id)[:48] or hashlib.sha1(data_url.encode("utf-8")).hexdigest()[:12]
        if any(existing.get("id") == image_id for existing in normalized):
            image_id = f"{hashlib.sha1((data_url + str(index)).encode('utf-8')).hexdigest()[:12]}_{index}"
        seen_data.add(data_url)
        item = dict(item)
        item["id"] = image_id
        item.setdefault("name", item.get("title", "Buehnenbild"))
        item.setdefault("title", item.get("name", "Buehnenbild"))
        normalized.append(item)
    st.session_state.stage_images = normalized
    if active_id and not any(item.get("id") == active_id for item in normalized):
        replacement = next((item.get("id") for item in normalized if active_data and item.get("data_url") == active_data), None)
        st.session_state.active_stage_image_id = replacement


def create_local_prompt_background(prompt: str, errors: list[str] | None = None) -> str:
    seed = int(hashlib.sha1((prompt or "ttliveregie").encode("utf-8")).hexdigest()[:8], 16)
    palettes = [
        ("#111827", "#ff4fd8", "#29f3ff", "#d9ff42"),
        ("#16120f", "#d6b15e", "#fff7ea", "#7dd3fc"),
        ("#20151d", "#f2a6c7", "#8b5cf6", "#f7d6a4"),
        ("#071014", "#36f2b4", "#5a7dff", "#f5f0e8"),
        ("#f5efe4", "#e11d48", "#2563eb", "#facc15"),
    ]
    bg, c1, c2, c3 = palettes[seed % len(palettes)]
    circles = []
    for idx in range(12):
        local = (seed >> (idx % 16)) + idx * 7919
        x = 8 + (local % 84)
        y = 6 + ((local // 7) % 88)
        r = 10 + ((local // 13) % 24)
        color = [c1, c2, c3][idx % 3]
        opacity = 0.10 + ((local % 9) / 100)
        circles.append(f'<circle cx="{x}%" cy="{y}%" r="{r}%" fill="{color}" opacity="{opacity:.2f}"/>')
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920">
      <rect width="1080" height="1920" fill="{bg}"/>
      <defs>
        <filter id="blur"><feGaussianBlur stdDeviation="52"/></filter>
        <linearGradient id="shade" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stop-color="{c1}" stop-opacity=".22"/>
          <stop offset=".52" stop-color="{c2}" stop-opacity=".12"/>
          <stop offset="1" stop-color="{c3}" stop-opacity=".18"/>
        </linearGradient>
        <pattern id="grid" width="90" height="90" patternUnits="userSpaceOnUse">
          <path d="M90 0H0V90" fill="none" stroke="#ffffff" stroke-opacity=".045" stroke-width="2"/>
        </pattern>
      </defs>
      <g filter="url(#blur)">{''.join(circles)}</g>
      <rect width="1080" height="1920" fill="url(#shade)"/>
      <rect width="1080" height="1920" fill="url(#grid)"/>
      <rect x="0" y="0" width="1080" height="1920" fill="none" stroke="{c1}" stroke-opacity=".28" stroke-width="2"/>
    </svg>
    """
    message = store_generated_background(svg.encode("utf-8"), "image/svg+xml", "Lokaler Prompt-Fallback")
    detail = " ".join(errors[:2]) if errors else ""
    return f"{message} Google war gerade nicht verfuegbar; lokaler abstrakter Prompt-Fallback wurde erstellt. {detail}".strip()


def response_parts(response: Any) -> list[Any]:
    parts = list(getattr(response, "parts", []) or [])
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        parts.extend(getattr(content, "parts", []) or [])
    return parts


def image_from_generate_content_response(response: Any) -> tuple[bytes | str, str] | None:
    for part in response_parts(response):
        inline_data = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
        if inline_data is not None:
            data = getattr(inline_data, "data", b"")
            mime_type = getattr(inline_data, "mime_type", None) or getattr(inline_data, "mimeType", None) or "image/png"
            if data:
                return data, mime_type
        as_image = getattr(part, "as_image", None)
        if callable(as_image):
            try:
                image = as_image()
                buffer = BytesIO()
                image.save(buffer, format="PNG")
                return buffer.getvalue(), "image/png"
            except Exception:
                pass
    return None


def image_generation_models_to_try(selected: str) -> list[str]:
    selected = selected if selected in IMAGE_MODELS else "auto"
    if selected == "auto":
        return [
            "gemini-2.5-flash-image",
            "gemini-2.5-flash-image-preview",
            "gemini-2.0-flash-preview-image-generation",
            "imagen-4.0-fast-generate-001",
            "imagen-3.0-generate-002",
        ]
    fallback = {
        "gemini-2.5-flash-image": ["gemini-2.5-flash-image-preview", "gemini-2.0-flash-preview-image-generation"],
        "gemini-2.5-flash-image-preview": ["gemini-2.5-flash-image", "gemini-2.0-flash-preview-image-generation"],
        "gemini-2.0-flash-preview-image-generation": ["gemini-2.5-flash-image", "gemini-2.5-flash-image-preview"],
        "imagen-4.0-fast-generate-001": ["imagen-3.0-generate-002"],
        "imagen-4.0-generate-001": ["imagen-4.0-fast-generate-001", "imagen-3.0-generate-002"],
        "imagen-3.0-generate-002": ["gemini-2.5-flash-image", "gemini-2.0-flash-preview-image-generation"],
    }
    result = [selected]
    for model in fallback.get(selected, []):
        if model not in result:
            result.append(model)
    return result


def generate_background_image(prompt: str, use_chat: bool = True) -> tuple[bool, str]:
    prompt = (prompt or "").strip()
    if use_chat:
        prompt = f"{prompt}\n\nLive-chat context: {chat_context_for_prompt()}".strip()
    if not prompt:
        return False, "Bitte einen Bildprompt eingeben oder Chatdaten sammeln."
    if genai is None:
        return False, "Google GenAI Paket fehlt. Bitte requirements.txt deployen/installieren."
    api_key = google_api_key()
    if not api_key:
        return False, "Kein GOOGLE_API_KEY oder GEMINI_API_KEY in Streamlit Secrets gefunden. Lege den Schlüssel in der Streamlit-Cloud unter App-Settings → Secrets ab."
    selected_model = st.session_state.get("image_model", "auto")
    if selected_model not in IMAGE_MODELS:
        selected_model = "auto"
    visual_prompt = (
        "Create a high-quality vertical 9:16 abstract livestream overlay background. "
        "No text, no logos, no readable words, no people. Leave calm negative space on the right and bottom. "
        "Professional, subtle, readable behind typography. "
        f"Prompt: {prompt}"
    )
    errors: list[str] = []
    try:
        client = genai.Client(api_key=api_key)
    except Exception as exc:
        st.session_state.image_generation_error = f"genai.Client-Fehler: {type(exc).__name__}: {exc}"
        return False, st.session_state.image_generation_error
    for model in image_generation_models_to_try(selected_model):
        try:
            if model.startswith("imagen-"):
                config = None
                if genai_types is not None:
                    config = genai_types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="9:16",
                        person_generation="dont_allow",
                    )
                response = client.models.generate_images(model=model, prompt=visual_prompt, config=config)
                for generated in getattr(response, "generated_images", []) or []:
                    image_obj = getattr(generated, "image", None)
                    data = getattr(image_obj, "image_bytes", None) or getattr(image_obj, "imageBytes", None)
                    if data:
                        st.session_state.image_generation_error = ""
                        return True, store_generated_background(data, "image/png", model)
                errors.append(f"{IMAGE_MODEL_LABELS.get(model, model)}: Google hat kein Bild zurueckgegeben.")
                continue

            kwargs: dict[str, Any] = {"model": model, "contents": [visual_prompt]}
            if model.endswith("image-generation") and genai_types is not None:
                kwargs["config"] = genai_types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
            elif model.endswith("flash-image") and genai_types is not None:
                # gemini-2.5-flash-image / -preview brauchen ebenfalls IMAGE in modalities
                try:
                    kwargs["config"] = genai_types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
                except Exception:
                    pass
            response = client.models.generate_content(**kwargs)
            image_result = image_from_generate_content_response(response)
            if image_result:
                data, mime_type = image_result
                st.session_state.image_generation_error = ""
                return True, store_generated_background(data, mime_type, model)
            errors.append(f"{IMAGE_MODEL_LABELS.get(model, model)}: Google hat nur Text oder kein Bild zurueckgegeben.")
        except Exception as model_exc:
            err = friendly_image_error(model_exc, model)
            errors.append(err)
            # Auch den rohen Exception-String mitloggen
            errors.append(f"  → raw: {type(model_exc).__name__}: {model_exc}")
            continue
    # Kein Modell hat geliefert: Fallback auf lokales SVG, aber Fehler sichtbar machen
    st.session_state.image_generation_error = "\n".join(errors[:6])
    fallback_msg = create_local_prompt_background(prompt, errors)
    return True, fallback_msg + " (Echter Fehler im Caption-Block sichtbar.)"


def test_genai_api() -> tuple[bool, str]:
    """Diagnose-Test: einen kleinen Aufruf an Gemini machen und alles zurückmelden.

    Wird vom UI-Button "API-Test" aufgerufen. Hilft dem User zu sehen, ob
    der Schlüssel passt und welche Modelle erreichbar sind, ohne dass er
    erst eine ganze Bildgenerierung durchprobieren muss.
    """
    if genai is None:
        return False, "Google GenAI Paket fehlt im Environment."
    api_key = google_api_key()
    if not api_key:
        return False, "Kein GOOGLE_API_KEY oder GEMINI_API_KEY gefunden (st.secrets / os.environ)."
    masked = api_key[:4] + "…" + api_key[-3:] if len(api_key) > 8 else "****"
    lines = [f"API-Key gefunden: {masked} (Länge {len(api_key)})"]
    try:
        client = genai.Client(api_key=api_key)
        lines.append("genai.Client OK")
    except Exception as exc:
        return False, "\n".join(lines + [f"Client-Fehler: {type(exc).__name__}: {exc}"])
    try:
        text_resp = client.models.generate_content(
            model=st.session_state.get("ai_model", "gemini-2.5-flash") or "gemini-2.5-flash",
            contents=["Antworte mit genau dem Wort: PONG"],
        )
        text = (getattr(text_resp, "text", "") or "").strip()
        lines.append(f"Text-Modell antwortet: {text[:80] or '(leer)'}")
    except Exception as exc:
        lines.append(f"Text-Modell-Fehler: {type(exc).__name__}: {exc}")
    try:
        models = list(client.models.list())
        lines.append(f"Verfügbare Modelle: {len(models)}")
        image_capable = [m for m in models if "image" in (getattr(m, "name", "") or "").lower() or "imagen" in (getattr(m, "name", "") or "").lower()]
        for m in image_capable[:8]:
            lines.append(f"  · {getattr(m, 'name', '?')}")
    except Exception as exc:
        lines.append(f"models.list-Fehler: {type(exc).__name__}: {exc}")
    return True, "\n".join(lines)


def chat_sentiment_state() -> dict[str, Any]:
    words = recent_chat_words()
    if not words:
        return {"score": 0.0, "label": "neutral", "intensity": 0.18}
    pos = sum(1 for word in words if normalize_word(word) in POSITIVE_WORDS)
    neg = sum(1 for word in words if normalize_word(word) in NEGATIVE_WORDS)
    score = (pos - neg) / max(1, pos + neg)
    label = "positiv" if score > 0.18 else "angespannt" if score < -0.18 else "neutral"
    intensity = min(1.0, (pos + neg) / max(12, len(words) * 0.18))
    return {"score": score, "label": label, "intensity": max(0.16, intensity)}


# ---------------------------------------------------------------------------
# Bild-Manager
# ---------------------------------------------------------------------------

def image_to_data_url(uploaded_file: Any) -> str:
    raw = uploaded_file.getvalue()
    suffix = uploaded_file.type or "image/png"
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{suffix};base64,{encoded}"


def pdf_to_data_url(uploaded_file: Any) -> str:
    raw = uploaded_file.getvalue()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:application/pdf;base64,{encoded}"


def pdf_viewer_srcdoc(pdf_data: str, title: str, zoom: int = 100) -> str:
    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        html, body {{ margin:0; width:100%; height:100%; overflow:hidden; background:#2a2d33; font-family:Arial, sans-serif; }}
        #viewer {{ position:fixed; inset:0; overflow:auto; padding:46px 18px 18px; display:flex; flex-direction:column; align-items:center; gap:14px; }}
        #bar {{ position:fixed; left:0; right:0; top:0; height:36px; display:flex; align-items:center; gap:8px; padding:5px 8px; background:rgba(0,0,0,.72); color:#fff; z-index:2; }}
        button {{ height:26px; border:1px solid rgba(255,255,255,.25); background:#20242b; color:#fff; border-radius:6px; font-weight:800; }}
        #title {{ flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; font-weight:900; }}
        canvas {{ max-width:100%; height:auto; background:#fff; box-shadow:0 10px 28px rgba(0,0,0,.35); }}
        #status {{ color:#fff; font-size:13px; padding-top:70px; text-align:center; }}
      </style>
      <script src="https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.min.mjs" type="module"></script>
    </head>
    <body>
      <div id="bar"><button id="out">-</button><button id="in">+</button><span id="zoom">{zoom}%</span><span id="title">{html.escape(title)}</span></div>
      <div id="viewer"><div id="status">PDF wird geladen...</div></div>
      <script type="module">
        const pdfjsLib = globalThis.pdfjsLib;
        pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.mjs";
        const dataUrl = {json.dumps(pdf_data)};
        const viewer = document.getElementById("viewer");
        const status = document.getElementById("status");
        const zoomLabel = document.getElementById("zoom");
        let pdf = null;
        let scale = {max(0.5, min(2.0, zoom / 100)):.2f};
        function bytesFromDataUrl(url) {{
          const base64 = (url || "").split(",")[1] || "";
          const raw = atob(base64);
          const bytes = new Uint8Array(raw.length);
          for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
          return bytes;
        }}
        async function render() {{
          if (!pdf) return;
          viewer.innerHTML = "";
          zoomLabel.textContent = Math.round(scale * 100) + "%";
          for (let pageNo = 1; pageNo <= pdf.numPages; pageNo++) {{
            const page = await pdf.getPage(pageNo);
            const viewport = page.getViewport({{ scale }});
            const canvas = document.createElement("canvas");
            const context = canvas.getContext("2d");
            canvas.width = Math.floor(viewport.width);
            canvas.height = Math.floor(viewport.height);
            viewer.appendChild(canvas);
            await page.render({{ canvasContext: context, viewport }}).promise;
          }}
        }}
        document.getElementById("in").onclick = () => {{ scale = Math.min(2.5, scale + .1); render(); }};
        document.getElementById("out").onclick = () => {{ scale = Math.max(.4, scale - .1); render(); }};
        try {{
          pdf = await pdfjsLib.getDocument({{ data: bytesFromDataUrl(dataUrl) }}).promise;
          await render();
        }} catch (error) {{
          status.textContent = "PDF konnte nicht gerendert werden: " + error.message;
        }}
      </script>
    </body>
    </html>
    """


def active_image_data() -> str:
    active_id = st.session_state.active_image_id
    for item in st.session_state.images:
        if item["id"] == active_id:
            return item["data_url"]
    return ""


def active_image_name() -> str:
    active_id = st.session_state.active_image_id
    for item in st.session_state.images:
        if item["id"] == active_id:
            return item["name"]
    return ""


def active_stage_image_data() -> str:
    active_id = st.session_state.get("active_stage_image_id")
    for item in st.session_state.get("stage_images", []):
        if item.get("id") == active_id:
            return item.get("data_url", "")
    return ""


def active_stage_image_name() -> str:
    active_id = st.session_state.get("active_stage_image_id")
    for item in st.session_state.get("stage_images", []):
        if item.get("id") == active_id:
            return item.get("title") or item.get("name") or "Buehnenbild"
    return ""


# ---------------------------------------------------------------------------
# Overlay-Rendering
# ---------------------------------------------------------------------------

def css_for_streamlit() -> str:
    return """
    <style>
    .stApp { background: #0d0f12; color: #f7f2ea; }
    /* Streamlit markiert waehrend Auto-Refresh/Rerun alte Elemente kurz als
       "stale" und blendet sie ab. Im Live-Regiepult wirkt das wie ein
       unerwuenschtes Atmen der Buehne. Wir halten die Anzeige stabil; die
       eigentliche Buehne aktualisiert sich ueber ihr eigenes Polling. */
    .stApp [data-testid="stAppViewContainer"],
    .stApp [data-testid="stMain"],
    .stApp [data-testid="stVerticalBlock"],
    .stApp [data-testid="stHorizontalBlock"],
    .stApp [data-testid="stElementContainer"],
    .stApp .element-container,
    .stApp .stElementContainer,
    .stApp .st-key-control_panel_scroll,
    .stApp .st-key-stage_panel_fixed,
    .stApp iframe,
    .stApp [data-stale="true"],
    .stApp [class*="stale"],
    .stApp [class*="Stale"] {
        opacity: 1 !important;
        transition: none !important;
        animation: none !important;
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { display: none; }
    /* Streamlit-Header (1440x60, z-index 999990) deckt unseren Topbar zu und
       blockt Klicks auf den Edit-Modus-Toggle. Der Header ist größtenteils
       leer; nur die Action-Buttons rechts (Deploy, Hamburger-Menü) brauchen
       Klicks. Daher: Header und seine leeren Wrapper komplett auf
       pointer-events:none, dann nur die echten Buttons wieder aktivieren. */
    header.stAppHeader,
    header[data-testid="stHeader"],
    .stAppToolbar,
    [data-testid="stToolbar"],
    header.stAppHeader > div,
    .stAppToolbar > div {
        pointer-events: none !important;
    }
    header.stAppHeader .stToolbarActions,
    header.stAppHeader .stToolbarActionButton,
    header.stAppHeader .stMainMenu,
    header.stAppHeader button,
    header.stAppHeader a {
        pointer-events: auto !important;
    }
    /* streamlit_js_eval-Components sind unsichtbar gedacht. Auf Streamlit
       Cloud bleiben deren Skeleton-Loader (weiße Balken) manchmal hängen,
       wenn der Component-Bundle nicht zuverlässig lädt. Wir verstecken den
       gesamten Container, damit nichts durchscheint. */
    iframe[title^="streamlit_js_eval"],
    iframe[title*="js_eval"] {
        display: none !important;
    }
    div.element-container:has(> div.stCustomComponentV1 iframe[title*="js_eval"]) {
        display: none !important;
    }
    /* Streamlit-Skeleton-Streifen bei langsamem Component-Load — nur für leere
       Iframe-Slots (höhe < 16) ausblenden, damit keine weißen Balken bleiben. */
    div.element-container > div.stCustomComponentV1[data-testid="stCustomComponentV1"]:has(> iframe[height="0"]),
    div.element-container > div.stCustomComponentV1[data-testid="stCustomComponentV1"]:has(> iframe[src=""]) {
        display: none !important;
    }
    .block-container {
        max-width: 100%;
        padding: 1rem 1rem 1.5rem;
    }
    .st-key-control_panel_scroll {
        background: #12161a;
        border: 1px solid rgba(255,255,255,.16);
        border-radius: 8px;
        padding: .8rem .75rem;
        max-height: none;
        color: #f7f2ea;
    }
    .st-key-control_panel_scroll * {
        color: inherit;
        opacity: 1 !important;
    }
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] *,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] *,
    label,
    label *,
    div[data-baseweb] p,
    div[data-baseweb] span {
        color: #f0e6da !important;
        opacity: 1 !important;
    }
    .st-key-control_panel_scroll label,
    .st-key-control_panel_scroll p,
    .st-key-control_panel_scroll span,
    .st-key-control_panel_scroll [data-testid="stWidgetLabel"],
    .st-key-control_panel_scroll [data-testid="stWidgetLabel"] *,
    .st-key-control_panel_scroll [data-testid="stMarkdownContainer"],
    .st-key-control_panel_scroll [data-testid="stMarkdownContainer"] *,
    .st-key-control_panel_scroll [data-baseweb="checkbox"] *,
    .st-key-control_panel_scroll [data-baseweb="switch"] * {
        color: #f0e6da !important;
        opacity: 1 !important;
    }
    .st-key-control_panel_scroll [data-testid="stCaptionContainer"],
    .st-key-control_panel_scroll [data-testid="stCaptionContainer"] *,
    .st-key-control_panel_scroll small {
        color: #c9bdb0 !important;
    }
    .st-key-control_panel_scroll h1,
    .st-key-control_panel_scroll h2,
    .st-key-control_panel_scroll h3 {
        color: #fff8ed !important;
    }
    .st-key-control_panel_scroll div[data-testid="stTabs"] button p {
        color: #cfc4b8 !important;
        font-weight: 750;
    }
    .st-key-control_panel_scroll div[data-testid="stTabs"] button[aria-selected="true"] p {
        color: #ff5a61 !important;
    }
    .st-key-stage_panel_fixed {
        position: fixed;
        top: 1rem;
        right: 1rem;
        width: calc(72vw - 2rem);
        height: calc(100vh - 2rem);
        overflow: hidden;
        z-index: 3;
        background: #0d0f12;
    }
    .st-key-stage_panel_fixed iframe {
        max-height: calc(100vh - 5.5rem);
    }
    @media (max-width: 900px) {
        .st-key-stage_panel_fixed {
            position: static;
            width: auto;
            height: auto;
            overflow: visible;
        }
        .st-key-stage_panel_fixed iframe {
            max-height: none;
        }
    }
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,.16);
        background: #242a31;
        color: #fff6ea !important;
        min-height: 2.4rem;
        font-weight: 650;
    }
    div.stButton > button:hover { border-color: #d6b15e; color: #fff; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        background: #0b0e12;
        color: #fff6ea !important;
        border-color: rgba(255,255,255,.42);
        border-radius: 8px;
    }
    .stTextInput input:disabled, .stTextArea textarea:disabled {
        -webkit-text-fill-color: #fff6ea !important;
        color: #fff6ea !important;
        opacity: 1 !important;
    }
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: #8f98a4 !important;
    }
    .stSelectbox [data-baseweb="select"] > div {
        background: #0b0e12 !important;
        border-color: rgba(255,255,255,.42) !important;
        border-radius: 8px !important;
    }
    .stSelectbox [data-baseweb="select"] span,
    .stSelectbox [data-baseweb="select"] div,
    .stSelectbox [data-baseweb="select"] svg {
        color: #fff6ea !important;
        fill: #fff6ea !important;
        opacity: 1 !important;
    }
    .stTabs [data-baseweb="tab-list"] { gap: .25rem; }
    .stTabs [data-baseweb="tab"] { height: 2.2rem; padding: 0 .55rem; }
    .regie-title { font-size: 1.05rem; font-weight: 800; margin: .15rem 0 .65rem; }
    .control-hero {
        padding: .75rem .72rem;
        border: 1px solid rgba(255,255,255,.18);
        border-radius: 8px;
        background: linear-gradient(135deg, rgba(255,255,255,.095), rgba(255,255,255,.035));
        margin-bottom: .75rem;
    }
    .control-hero h2 {
        margin: 0 0 .35rem;
        font-size: 1.05rem;
        line-height: 1.05;
        color: #fff8ed !important;
    }
    .control-meta {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: .35rem;
        margin-top: .55rem;
    }
    .control-chip {
        border: 1px solid rgba(255,255,255,.15);
        border-radius: 7px;
        padding: .38rem .45rem;
        background: rgba(255,255,255,.055);
        font-size: .72rem;
        line-height: 1.15;
        color: #f4eadc !important;
        min-height: 2.2rem;
    }
    .control-chip b { display:block; color:#ffffff !important; font-size:.78rem; margin-bottom:.08rem; }
    .status-dot {
        display:inline-block; width:.58rem; height:.58rem; border-radius:999px; margin-right:.35rem;
        background:#69717d; box-shadow:0 0 0 3px rgba(255,255,255,.06);
    }
    .status-dot.live { background:#43e37f; box-shadow:0 0 18px rgba(67,227,127,.42); }
    .status-dot.warn { background:#ffd166; box-shadow:0 0 18px rgba(255,209,102,.32); }
    .section-note {
        border-left: 3px solid #ff5a61;
        background: rgba(255,255,255,.055);
        padding: .45rem .55rem;
        border-radius: 0 7px 7px 0;
        margin: .4rem 0 .6rem;
        color: #d9cec3 !important;
        font-size: .78rem;
    }
    .layout-card {
        padding: .52rem .58rem;
        border: 1px solid rgba(255,255,255,.16);
        border-radius: 8px;
        background: rgba(255,255,255,.052);
        margin: .35rem 0 .2rem;
    }
    .layout-card b { color:#fff8ed !important; }
    .layout-card span { color:#cfc3b6 !important; font-size:.76rem; }
    .font-preview {
        margin: .35rem 0 .7rem;
        padding: .55rem .65rem;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,.14);
        background: rgba(255,255,255,.055);
        color: #fff8ed !important;
        font-size: 1.28rem;
        line-height: 1.15;
    }
    .font-preview.compact { font-size: .95rem; color: #f2e5d7 !important; }
    div[data-testid="stExpander"] {
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 8px;
        background: rgba(255,255,255,.035);
        margin-bottom: .5rem;
        overflow: hidden;
    }
    div[data-testid="stExpander"] summary {
        background: rgba(255,255,255,.055);
        color: #fff8ed !important;
        font-weight: 850;
    }
    .status-pill {
        padding: .45rem .6rem;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,.22);
        background: rgba(255,255,255,.075);
        color: #fff6ea !important;
        font-size: .84rem;
    }
    .layout-grid { display: grid; grid-template-columns: 1fr; gap: .35rem; }
    </style>
    """


def css_for_overlay_mode() -> str:
    return """
    <style>
    html,
    body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    .main,
    .block-container {
        margin: 0 !important;
        padding: 0 !important;
        width: 100vw !important;
        max-width: none !important;
        min-width: 100vw !important;
        height: 100vh !important;
        min-height: 100vh !important;
        max-height: 100vh !important;
        overflow: hidden !important;
        background: #050608 !important;
    }
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    #MainMenu,
    header,
    footer {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
    }
    .block-container > div,
    .element-container,
    [data-testid="stElementContainer"] {
        width: 100vw !important;
        height: 100vh !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    iframe {
        position: fixed !important;
        inset: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        min-height: 100vh !important;
        border: 0 !important;
        display: block !important;
        background: #050608 !important;
    }
    </style>
    """




def current_overlay_state() -> dict[str, Any]:
    state = snapshot_scene()
    rt = live_runtime()
    with rt.lock:
        live_started_at = rt.started_at
    live_duration = format_duration(time.time() - live_started_at) if live_started_at else "00:00:00"
    live_since_time = time.strftime("%H:%M:%S", time.localtime(live_started_at)) if live_started_at else "--:--:--"
    # Theme-Farben mit reinschreiben. WICHTIG: Wir nehmen das aktuell
    # gewählte Theme aus THEMES[layout] und MERGEN es kompromisslos in den
    # State — auch wenn snapshot_scene() ältere Werte aus Backups
    # mitschleppt. Die Theme-Felder kommen IMMER aus THEMES[layout],
    # niemals aus dem persistierten State.
    layout = st.session_state.layout
    if layout not in THEMES:
        layout = "Editorial Dark"
    theme = THEMES[layout]
    preset_font = layout_font(layout)
    preset_typo = layout_typography(layout)
    if not st.session_state.get("user_adjusted_typography", False):
        state["topic_font_family"] = preset_font
        state["highlight_font_family"] = preset_font
        state["keyword_font_family"] = "Inter"
        state["topic_font_weight"] = preset_typo["topic_weight"]
        state["topic_letter_spacing"] = preset_typo["topic_spacing"]
        state["topic_text_size"] = preset_typo["topic_size"]
        state["topic_text_transform"] = "normal"
        state["keyword_font_weight"] = preset_typo["keyword_weight"]
        state["highlight_font_weight"] = max(700, int(preset_typo["topic_weight"]))
        state["highlight_letter_spacing"] = 0
        state["countdown_font_family"] = "Inter"
        state["countdown_font_weight"] = 850
    else:
        state["topic_font_family"] = state.get("topic_font_family") if state.get("topic_font_family") in FONT_PRESETS else preset_font
        state["highlight_font_family"] = (
            state.get("highlight_font_family") if state.get("highlight_font_family") in FONT_PRESETS else state["topic_font_family"]
        )
        state["keyword_font_family"] = state.get("keyword_font_family") if state.get("keyword_font_family") in FONT_PRESETS else "Inter"
    state["layout"] = layout
    state.update(
        {
            "keywords": st.session_state.keywords or st.session_state.get("last_keywords_snapshot", []),
            "manual_cloud_words": parse_manual_cloud_words(st.session_state.manual_cloud_words_text),
            "active_image_data": active_image_data(),
            "active_image_name": active_image_name(),
            "stage_image_data": active_stage_image_data(),
            "stage_image_name": active_stage_image_name(),
            "aspect": st.session_state.aspect,
            "filtered_total": st.session_state.filtered_total,
            "filtered_top": st.session_state.filtered_top,
            "live_started_at": live_started_at,
            "live_duration": live_duration,
            "live_since_time": live_since_time,
            "sentiment": chat_sentiment_state(),
            "bg": theme.get("bg") or "#050608",
            "panel": theme.get("panel") or "rgba(8,10,16,.62)",
            # Achtung: Schlüssel heißt im Theme "text", auf der Bühne "text_color".
            # NIE state["text"] schreiben — das würde mit der Topic-Headline
            # kollidieren (snapshot_scene hat "topic", aber alte Backups
            # könnten "text" enthalten).
            "text_color": theme.get("text") or "#fff7ea",
            "muted": theme.get("muted") or "#d6c9b8",
            "accent": theme.get("accent") or "#ff4fd8",
            "accent2": theme.get("accent2") or "#29f3ff",
            "accent3": theme.get("accent3") or "#f8ff4d",
            "glow": theme.get("glow") or "rgba(255,79,216,.30)",
            "neko_url": st.session_state.get("neko_url", ""),
            "neko_password": st.session_state.get("neko_password", ""),
            "website_og": {
                "title": st.session_state.get("website_preview_title", ""),
                "description": st.session_state.get("website_preview_text", ""),
                "image": st.session_state.get("website_preview_image", ""),
            },
        }
    )
    # Defensive: falls aus alten Backups noch ein "text"-Feld in state
    # steht (von früheren Refactors), löschen wir es hier — sonst greift
    # in stage.html die `state.text_color || state.text`-Fallback-Kette
    # auf die Topic-Headline und färbt damit die Schrift.
    state.pop("text", None)
    if st.session_state.auto_highlight and not st.session_state.highlight_word and st.session_state.keywords:
        state["highlight_word"] = st.session_state.keywords[0]["word"]
    return state


def persist_overlay_state() -> None:
    data = current_overlay_state()
    data["updated_at"] = time.time()
    data["room_id"] = st.session_state.overlay_room_id
    data["scenes_count"] = len(st.session_state.get("scenes", {}))
    safe = json.dumps(data, ensure_ascii=False)
    RUNTIME_STATE_FILE.write_text(safe, encoding="utf-8")
    try:
        room_state_file(st.session_state.overlay_room_id).write_text(safe, encoding="utf-8")
        static_state_file(st.session_state.overlay_room_id).write_text(safe, encoding="utf-8")
        static_state_file("default").write_text(safe, encoding="utf-8")
    except Exception:
        pass
    # Gist-Sync: pusht den State zu GitHub Gist, damit die GitHub-Pages-Bühne ihn lesen kann.
    # Debounced (max. 1x pro 2s) und still — Fehler landen nur in session_state.gist_status.
    try:
        push_state_to_gist_if_due(safe)
    except Exception as exc:
        st.session_state["gist_status"] = {"ok": False, "msg": f"Sync-Fehler: {exc}", "at": time.time()}


# ---- GitHub-Gist State-Sync --------------------------------------------------


def _gist_token() -> str:
    """Liefert den GitHub-PAT aus Secrets oder Session-State (User-Eingabe)."""
    try:
        secret = st.secrets.get("GITHUB_GIST_TOKEN", "") if hasattr(st, "secrets") else ""
    except Exception:
        secret = ""
    return (secret or st.session_state.get("gist_token", "") or "").strip()


def _gist_id() -> str:
    try:
        secret = st.secrets.get("GITHUB_GIST_ID", "") if hasattr(st, "secrets") else ""
    except Exception:
        secret = ""
    return (secret or st.session_state.get("gist_id", "") or "").strip()


def _gist_user() -> str:
    try:
        secret = st.secrets.get("GITHUB_GIST_USER", "") if hasattr(st, "secrets") else ""
    except Exception:
        secret = ""
    return (secret or st.session_state.get("gist_user", "sustynats") or "sustynats").strip()


def push_state_to_gist_if_due(serialized_state: str) -> None:
    """Debounced PATCH-Push des State-JSON an einen GitHub Gist.

    Throttle: max. 1 Push pro 2 Sekunden. Pläne fürs nächste Push-Fenster werden
    in `st.session_state.gist_pending` gehalten und beim nächsten Streamlit-Rerun
    nachgeholt. Beim nächsten Rerun (z.B. ausgelöst durch Slider, Toggle oder den
    leichten Auto-Refresh) checken wir ZUERST, ob pending vorliegt und das
    Throttle-Fenster geöffnet hat — sonst gehen Layout-Änderungen verloren, die
    direkt nach einem 200-OK-Push reinkommen.
    """
    token = _gist_token()
    gist_id = _gist_id()
    if not token or not gist_id:
        return  # Sync nicht konfiguriert — still ignorieren
    now = time.time()
    last = float(st.session_state.get("gist_last_push_at", 0.0))
    pending = st.session_state.get("gist_pending")
    # Falls ein pending-State älter ist als der aktuelle, überschreiben wir ihn
    # mit dem aktuellen — wir wollen am Ende immer den letzten Stand pushen.
    if now - last < 2.0:
        st.session_state["gist_pending"] = serialized_state
        return
    # Throttle ist offen. Pending hat Vorrang — aber der aktuelle Aufruf
    # überschreibt es ja, also pushen wir gleich serialized_state und löschen
    # pending. (Äquivalent: serialized_state IST der neueste Stand.)
    if pending is not None:
        st.session_state.pop("gist_pending", None)
    _push_state_to_gist_now(serialized_state, token, gist_id)


def _push_state_to_gist_now(serialized_state: str, token: str, gist_id: str) -> None:
    import random
    import urllib.request
    import urllib.error

    room = safe_profile_id(st.session_state.get("overlay_room_id", "default") or "default")
    fname = f"state-{room}.json"
    body = json.dumps({"files": {fname: {"content": serialized_state}}}).encode("utf-8")

    def _build_req() -> urllib.request.Request:
        return urllib.request.Request(
            f"https://api.github.com/gists/{gist_id}",
            data=body,
            method="PATCH",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "ttliveregie/1.0",
            },
        )

    # Bei 409 Conflict (Race-Condition zwischen parallelen PATCH-Calls) einmal
    # mit kleinem Jitter retryen. Andere Fehler werden direkt geloggt.
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(_build_req(), timeout=5) as resp:
                ok = 200 <= resp.status < 300
                st.session_state["gist_last_push_at"] = time.time()
                st.session_state["gist_status"] = {
                    "ok": ok,
                    "msg": f"OK ({resp.status})" if ok else f"HTTP {resp.status}",
                    "at": time.time(),
                }
                st.session_state.pop("gist_pending", None)
                return
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 409 and attempt == 0:
                time.sleep(0.3 + random.random() * 0.5)
                continue
            hint = ""
            if e.code == 403:
                hint = " - Token/Gist pruefen: Classic PAT braucht Scope gist und muss zum Gist-Owner passen."
            st.session_state["gist_status"] = {
                "ok": False,
                "msg": f"HTTP {e.code}: {e.reason}{hint}",
                "at": time.time(),
            }
            st.session_state.pop("gist_pending", None)
            return
        except Exception as e:
            last_error = e
            st.session_state["gist_status"] = {
                "ok": False,
                "msg": f"{type(e).__name__}: {e}",
                "at": time.time(),
            }
            return
    # Falls beide Versuche mit 409 endeten
    if isinstance(last_error, urllib.error.HTTPError):
        st.session_state["gist_status"] = {
            "ok": False,
            "msg": f"HTTP {last_error.code}: {last_error.reason} (nach Retry)",
            "at": time.time(),
        }


def create_gist_for_user(token: str, room: str, initial_state: str) -> tuple[str, str]:
    """Legt einen neuen Public Gist an und gibt (gist_id, owner_login) zurück."""
    import urllib.request
    import urllib.error

    fname = f"state-{safe_profile_id(room)}.json"
    body = json.dumps({
        "description": "ttliveregie overlay state",
        "public": True,
        "files": {fname: {"content": initial_state}},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/gists",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ttliveregie/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data.get("id", "")), str((data.get("owner") or {}).get("login", ""))


def load_overlay_state() -> dict[str, Any]:
    room = st.query_params.get("room", "")
    if room:
        room_file = room_state_file(room)
        if room_file.exists():
            try:
                data = json.loads(room_file.read_text(encoding="utf-8"))
                data.setdefault("keywords", [])
                data.setdefault("manual_cloud_words", parse_manual_cloud_words(data.get("manual_cloud_words_text", "")))
                if not data.get("active_image_data") and data.get("active_image_id") and data.get("images"):
                    for image in data.get("images", []):
                        if image.get("id") == data.get("active_image_id"):
                            data["active_image_data"] = image.get("data_url", "")
                            break
                return data
            except Exception:
                pass
    if RUNTIME_STATE_FILE.exists():
        try:
            return json.loads(RUNTIME_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return current_overlay_state()


def render_stage(state: dict[str, Any], height: int = 860) -> None:
    """Bettet die Bühne ins Regiepult ein.

    Die Regie-Vorschau verwendet bewusst immer den same-origin Static-Pfad
    der Streamlit-App. Die externe Browserquelle fuer TikTok Live Studio laeuft
    ueber GitHub Pages + Gist, aber diese Runde kann in der Regie-Vorschau zu
    sichtbarem Flackern fuehren, wenn der Gist/CDN kurz einen alten State
    liefert. In der Regie muss dagegen der frisch geschriebene lokale State
    sofort und stabil sichtbar sein.

    Layout-Änderungen passieren über den Layout-Tab in der Regie
    (Slider/Number-Inputs), nicht mehr per Drag in der Bühne. Die Bühne
    ist reine Anzeige.
    """
    room = safe_profile_id(st.session_state.get("overlay_room_id", "default") or "default")
    src = f"./app/static/{STATIC_STAGE_FILE.name}?room={room}&v={DEFAULTS_VERSION}"
    iframe_html = (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        'html,body{margin:0;padding:0;height:100%;background:#050608;overflow:hidden;}'
        'iframe{display:block;width:100%;height:100%;border:0;background:#050608;}'
        '</style></head><body>'
        f'<iframe id="stageframe" src="{html.escape(src)}" allow="autoplay; encrypted-media; fullscreen; microphone; camera; clipboard-read; clipboard-write" referrerpolicy="no-referrer"></iframe>'
        '</body></html>'
    )
    st.components.v1.html(iframe_html, height=height, scrolling=False)


def render_static_overlay_redirect() -> None:
    """Wenn jemand ?overlay=1 öffnet (alte URL), auf stage.html weiterleiten."""
    room = safe_profile_id(st.query_params.get("room", st.session_state.overlay_room_id))
    params = {
        "debug": st.query_params.get("debug", ""),
        "test": st.query_params.get("test", ""),
        "bg": st.query_params.get("bg", ""),
        "transparent": st.query_params.get("transparent", ""),
    }
    # Relativer Redirect-Target auf den lokalen Static-Pfad (nur lokal sinnvoll;
    # Cloud-Nutzer sollten direkt die GitHub-Pages-URL nutzen).
    query: dict[str, str] = {"room": room, "v": str(DEFAULTS_VERSION)}
    query.update({k: v for k, v in params.items() if v})
    encoded = "&".join(f"{k}={v}" for k, v in query.items())
    target = f"./app/static/{STATIC_STAGE_FILE.name}?{encoded}"
    absolute_target = github_pages_stage_url(room, **params)
    st.markdown(
        f"""
        <style>
        html, body, .stApp, .block-container {{
            margin:0 !important; padding:0 !important; width:100vw !important; height:100vh !important;
            overflow:hidden !important; background:#050608 !important;
        }}
        [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer, #MainMenu {{
            display:none !important;
        }}
        .overlay-redirect {{
            position:fixed; inset:0; display:grid; place-items:center; background:#050608; color:#fff;
            font:800 24px system-ui, sans-serif; text-align:center; padding:32px;
        }}
        .overlay-redirect a {{ color:#29f3ff; word-break:break-all; font-size:16px; display:block; margin-top:18px; }}
        </style>
        <meta http-equiv="refresh" content="0; url={html.escape(target)}">
        <script>
        var target = {json.dumps(target)};
        var absoluteTarget = {json.dumps(absolute_target)};
        try {{ window.location.replace(target); }} catch (error) {{}}
        setTimeout(function () {{
            try {{ window.top.location.href = target; }} catch (error) {{}}
        }}, 80);
        </script>
        <div class="overlay-redirect">
            <div>
                <div>Bühne wird geladen...</div>
                <a href="{html.escape(target)}" target="_self">{html.escape(absolute_target)}</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Control-Panel-Rendering
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    st.markdown(f"### {title}")


def render_director_header() -> None:
    rt = live_runtime()
    with rt.lock:
        status = rt.status
        started_at = rt.started_at
    is_live = status == "connected"
    is_warn = status in {"connecting", "error"}
    dot_cls = "live" if is_live else "warn" if is_warn else ""
    runtime = format_duration(time.time() - started_at) if started_at and is_live else "00:00:00"
    scene = st.session_state.last_active_scene or "nicht gesetzt"
    st.markdown(
        f"""
        <div class="control-hero">
          <h2>Live-Regiepult</h2>
          <div><span class="status-dot {dot_cls}"></span><b>{html.escape(status)}</b> · Laufzeit {runtime}</div>
          <div class="control-meta">
            <div class="control-chip"><b>Szene</b>{html.escape(scene)}</div>
            <div class="control-chip"><b>Look</b>{html.escape(st.session_state.layout)}</div>
            <div class="control-chip"><b>Cloud</b>{html.escape(st.session_state.cloud_style)}</div>
            <div class="control-chip"><b>Keywords</b>{len(st.session_state.keywords)} aktiv</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_note(text: str) -> None:
    st.markdown(f'<div class="section-note">{html.escape(text)}</div>', unsafe_allow_html=True)


def render_connection_panel() -> None:
    rt = live_runtime()
    section("Verbindung")
    st.session_state.target_input = st.text_input("TikTok-Username / Live-URL", value=st.session_state.target_input, placeholder="@username oder Live-URL")
    c1, c2 = st.columns(2)
    if c1.button("Start", key="connection_start", use_container_width=True):
        start_live_connection(st.session_state.target_input)
    if c2.button("Stop", key="connection_stop", use_container_width=True):
        stop_live_connection()
    with rt.lock:
        status = rt.status
        detail = rt.status_detail
        started_at = rt.started_at
    live_for = format_duration(time.time() - started_at) if started_at and status == "connected" else "00:00:00"
    live_clock_since = time.strftime("%H:%M:%S", time.localtime(started_at)) if started_at else "--:--:--"
    st.markdown(f'<div class="status-pill"><b>Status:</b> {html.escape(status)}<br>{html.escape(detail)}<br><b>Live seit:</b> {live_for}<br><b>Startzeit:</b> {live_clock_since}</div>', unsafe_allow_html=True)


def render_toggle_panel() -> None:
    section("Sichtbarkeit")
    st.session_state.background_visible_control = bool(st.session_state.get("show_background", True))
    toggles = [
        ("show_topic", "Thema anzeigen"),
        ("show_cloud", "Keyword-Cloud anzeigen"),
        ("show_highlight", "Highlight-Wort anzeigen"),
        ("show_countdown", "Countdown anzeigen"),
        ("show_clock", "Live-Uhr anzeigen"),
        ("show_live_since", "Live seit Uhrzeit anzeigen"),
        ("show_stage_image", "Buehnenbild anzeigen"),
        ("show_animations", "Animationen anzeigen"),
        ("show_motion_layers", "Bewegung anzeigen"),
        ("show_heatmap", "Heatmap anzeigen"),
        ("show_safe_zones", "Safe-Zones anzeigen"),
        ("show_overlay_frame", "Overlay-Frame anzeigen"),
        ("minimal_mode", "Minimal Mode"),
    ]
    for key, label in toggles:
        st.toggle(label, key=key)
    st.toggle("Hintergrundbild anzeigen", key="background_visible_control", on_change=sync_background_visibility)


def render_topic_panel() -> None:
    section("Thema")
    st.session_state.topic_draft = st.text_input("Aktuelles Thema", value=st.session_state.topic_draft)
    if st.button("Übernehmen", key="topic_apply", use_container_width=True):
        st.session_state.topic = st.session_state.topic_draft.strip() or st.session_state.topic


def render_highlight_panel() -> None:
    section("Highlight-Wort")
    st.session_state.highlight_draft = st.text_input("Manuelles Highlight-Wort", value=st.session_state.highlight_draft)
    c1, c2 = st.columns(2)
    if c1.button("Highlight setzen", key="highlight_set", use_container_width=True):
        word = normalize_word(st.session_state.highlight_draft)
        st.session_state.highlight_word = word if is_safe_keyword(word) else ""
        st.session_state.auto_highlight = False
    if c2.button("Auto-Highlight", key="highlight_auto", use_container_width=True):
        st.session_state.auto_highlight = True
        st.session_state.highlight_word = ""
    if st.button("Highlight löschen", key="highlight_clear", use_container_width=True):
        st.session_state.highlight_word = ""
        st.session_state.highlight_draft = ""
        st.session_state.auto_highlight = False
    st.session_state.manual_cloud_words_text = st.text_area(
        "Manuelle Cloud-Wörter",
        value=st.session_state.manual_cloud_words_text,
        height=88,
        help="Ein Wort pro Zeile oder mit Komma trennen. Die Wörter laufen durch den Safety-Filter und werden im Overlay hervorgehoben.",
    )
    st.toggle("Manuelle Wörter hervorheben", key="manual_words_emphasis")
    if st.button("Manuelle Wörter löschen", key="manual_words_clear", use_container_width=True):
        st.session_state.manual_cloud_words_text = ""


def render_countdown_panel() -> None:
    section("Countdown")
    st.session_state.countdown_title = st.text_input("Countdown-Titel", value=st.session_state.countdown_title)
    st.session_state.countdown_minutes = st.number_input("Minuten", min_value=1, max_value=240, value=int(st.session_state.countdown_minutes), step=1)
    c1, c2, c3 = st.columns(3)
    if c1.button("Start", key="countdown_start", use_container_width=True):
        if st.session_state.countdown_remaining <= 0 or st.session_state.countdown_remaining == st.session_state.countdown_total:
            st.session_state.countdown_total = int(st.session_state.countdown_minutes) * 60
            st.session_state.countdown_remaining = st.session_state.countdown_total
        st.session_state.countdown_started_at = time.time() - (st.session_state.countdown_total - st.session_state.countdown_remaining)
        st.session_state.countdown_running = True
        st.session_state.show_countdown = True
    if c2.button("Pause", key="countdown_pause", use_container_width=True):
        update_countdown()
        st.session_state.countdown_running = False
    if c3.button("Reset", key="countdown_reset", use_container_width=True):
        st.session_state.countdown_total = int(st.session_state.countdown_minutes) * 60
        st.session_state.countdown_remaining = st.session_state.countdown_total
        st.session_state.countdown_started_at = None
        st.session_state.countdown_running = False
    st.caption(f"Restzeit: {format_duration(st.session_state.countdown_remaining)}")


def render_position_panel() -> None:
    """Slider/Inputs für Position und Größe jeder Bühnen-Ebene.

    Ersetzt den früheren Drag-/Resize-Edit-Mode der Bühne. Änderungen schreiben
    direkt in `st.session_state` und fließen über `current_overlay_state()` und
    den Gist-Push an die Bühne.
    """
    section("Position & Größe")
    st.caption("Pro Layer X/Y/Breite/Höhe in Prozent der Bühne. Sichtbarkeit toggelbar.")
    # Wichtig: Mehrere kanonische Keys (z.B. `cloud_pos_x`, `video_x`, ...) sind
    # bereits an anderer Stelle als Widget-Keys belegt. Streamlit erlaubt einen
    # Key nur einmal pro Render-Pass als Widget. Daher arbeiten wir hier mit
    # Mirror-Keys (`pos_<layer>_<dim>`), lesen vor dem Render aus dem
    # kanonischen Key und spiegeln per on_change zurück.
    def _make_sync(canonical_key: str, mirror_key: str, lo: int, hi: int):
        def _sync() -> None:
            try:
                v = int(st.session_state.get(mirror_key, lo) or lo)
            except (TypeError, ValueError):
                v = lo
            st.session_state[canonical_key] = max(lo, min(hi, v))
        return _sync

    def _make_show_sync(show_key: str, mirror_key: str):
        def _sync() -> None:
            st.session_state[show_key] = bool(st.session_state.get(mirror_key))
        return _sync

    for layer_id, fields in _LAYER_FIELD_MAP.items():
        label = fields.get("label", layer_id)
        min_w, min_h = _LAYER_MIN_SIZE.get(layer_id, (8, 8))
        with st.expander(label, expanded=False):
            dims = [
                ("x", "X (%)", 0, 100),
                ("y", "Y (%)", 0, 100),
                ("w", "Breite (%)", min_w, 100),
                ("h", "Höhe (%)", min_h, 100),
            ]
            # Mirror-Keys vorbefüllen aus den kanonischen Werten
            for short, _lab, lo, hi in dims:
                mirror = f"pos_{layer_id}_{short}"
                try:
                    cur = int(st.session_state.get(fields[short], lo) or lo)
                except (TypeError, ValueError):
                    cur = lo
                cur = max(lo, min(hi, cur))
                # Auch kanonisch clampen, falls altes Backup außerhalb lag.
                st.session_state[fields[short]] = cur
                if st.session_state.get(mirror) != cur:
                    st.session_state[mirror] = cur
            show_key = fields["show"]
            show_mirror = f"pos_show_{layer_id}"
            current_show = bool(st.session_state.get(show_key, True))
            if st.session_state.get(show_mirror) != current_show:
                st.session_state[show_mirror] = current_show

            st.toggle("Anzeigen", key=show_mirror, on_change=_make_show_sync(show_key, show_mirror))
            cols = st.columns(2)
            order = [("x", 0), ("w", 0), ("y", 1), ("h", 1)]
            for short, col_idx in order:
                lab = next(d[1] for d in dims if d[0] == short)
                lo = next(d[2] for d in dims if d[0] == short)
                hi = next(d[3] for d in dims if d[0] == short)
                mirror = f"pos_{layer_id}_{short}"
                with cols[col_idx]:
                    st.slider(lab, lo, hi, key=mirror,
                              on_change=_make_sync(fields[short], mirror, lo, hi))
            if layer_id == "cloud":
                # Sobald der User die Wolke selbst positioniert, soll ein
                # Layout-Wechsel die Position nicht mehr resetten.
                st.session_state.user_adjusted_cloud_position = True


def render_layout_panel() -> None:
    section("Layout")
    descriptions = {
        "Editorial Dark": "ruhig, politisch, Magazin-Look",
        "Neon Pop": "bunt, Glow, TikTok-Energie",
        "Candy Gradient": "weich, poppig, freundlich",
        "Bauhaus Clean": "hell, sachlich, geometrisch",
        "Soft Power": "warm, weich, hochwertig",
        "System Map": "Netzwerk, Analyse, Denklandkarte",
        "Newspaper / Print": "Zeitung, Essay, Kommentar",
        "Festival / Color Splash": "aktiv, bunt, verspielt",
        "Cyber Newsroom": "Hightech, Breaking-News, leuchtende Raster",
        "Aurora Glass": "glasig, aurora, elegant fließend",
        "Protest Poster": "laut, plakativer Aktivismus, Print-Kante",
        "Data Bloom": "organische Datenblüte, Analyse trifft Natur",
        "Velvet Studio": "dunkel, luxuriös, Talkshow-Nachtlook",
    }
    for name, theme in THEMES.items():
        active = "✓ " if st.session_state.layout == name else ""
        st.markdown(
            f'<div class="layout-card"><b>{active}{html.escape(name)}</b><br><span>{html.escape(descriptions.get(name, ""))}</span></div>',
            unsafe_allow_html=True,
        )
        if st.button(f"{active}{name}", key=f"layout_{theme['key']}", use_container_width=True):
            st.session_state.layout = name
            apply_layout_typography(name)
            stabilize_image_look_for_layout_switch()
            if not st.session_state.cloud_style_locked:
                st.session_state.cloud_style = theme.get("cloud_style", st.session_state.cloud_style)
                if not st.session_state.user_adjusted_cloud_position:
                    st.session_state.cloud_pos_x = 50
                    st.session_state.cloud_pos_y = 50


def render_image_panel() -> None:
    section("Bild-Manager")
    normalize_image_library()
    st.session_state.image_prompt = st.text_area(
        "KI-Hintergrund-Prompt",
        value=st.session_state.image_prompt,
        height=90,
        placeholder="z. B. ruhige abstrakte Studiobühne, goldene Akzente, viel Platz rechts",
    )
    st.toggle("Chat der letzten 5 Minuten in Bildprompt einbeziehen", key="image_prompt_use_chat")
    if st.session_state.get("image_model") not in IMAGE_MODELS:
        st.session_state.image_model = "gemini-2.5-flash-image"
    st.selectbox("Bildmodell", IMAGE_MODELS, key="image_model", format_func=lambda value: IMAGE_MODEL_LABELS.get(value, value))
    st.caption("Auto / `gemini-2.5-flash-image` ist Free-Tier-tauglich. Imagen-4 erfordert oft Paid-Tier.")
    cols_img = st.columns([0.6, 0.4])
    if cols_img[0].button("KI-Hintergrund erstellen", key="image_generate_ai", use_container_width=True):
        ok, message = generate_background_image(st.session_state.image_prompt, st.session_state.image_prompt_use_chat)
        if ok:
            st.success(message)
        else:
            st.session_state.image_generation_error = message
            st.error(message)
    if cols_img[1].button("API-Test", key="image_api_test", use_container_width=True, help="Prüft, ob der Google-API-Key passt und welche Modelle erreichbar sind."):
        ok, report = test_genai_api()
        if ok:
            st.success("API erreichbar:")
        else:
            st.error("API nicht erreichbar:")
        st.code(report)
    if st.session_state.image_generation_error:
        st.text_area("Letzter Bildgenerierungs-Fehler (raw)", value=st.session_state.image_generation_error, height=120, disabled=True)
    st.divider()
    uploads = st.file_uploader("Hintergrundbilder", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
    if uploads:
        known = {item["id"] for item in st.session_state.images}
        for up in uploads:
            if len(up.getvalue()) > 5 * 1024 * 1024:
                st.warning(f"{up.name} ist groesser als 5 MB. Bitte kleiner exportieren, damit Browser-Speicherung stabil bleibt.")
                continue
            image_id = hashlib.sha1(up.getvalue()).hexdigest()[:12]
            if image_id not in known:
                st.session_state.images.append({"id": image_id, "name": up.name, "title": up.name, "data_url": image_to_data_url(up)})
                known.add(image_id)
                if not st.session_state.active_image_id:
                    st.session_state.active_image_id = image_id

    if st.session_state.images:
        for idx, item in enumerate(list(st.session_state.images)):
            cols = st.columns([1, 1, 1])
            cols[0].image(item["data_url"], use_container_width=True)
            new_title = cols[0].text_input("Titel", value=item.get("title", item.get("name", "Bild")), key=f"img_title_{item['id']}_{idx}", label_visibility="collapsed")
            item["title"] = new_title
            cols[1].button(
                ("Aktiv" if item["id"] == st.session_state.active_image_id else "Aktivieren"),
                key=f"img_on_{item['id']}",
                use_container_width=True,
                on_click=activate_image,
                args=(item["id"],),
            )
            if cols[2].button("Löschen", key=f"img_del_{item['id']}", use_container_width=True):
                st.session_state.images = [img for img in st.session_state.images if img["id"] != item["id"]]
                if st.session_state.active_image_id == item["id"]:
                    st.session_state.active_image_id = None
    st.caption("Ausblenden behaelt das aktive Bild in der Galerie. Abwaehlen entfernt nur die aktive Auswahl. Loeschen entfernt ein Bild aus der Session-Galerie.")
    c1, c2, c3 = st.columns(3)
    hide_label = "Bild einblenden" if not st.session_state.show_background else "Bild ausblenden"
    c1.button(hide_label, key="image_toggle_visibility", use_container_width=True, on_click=toggle_background_visibility)
    if c2.button("Aktives Bild abwählen", key="image_remove", use_container_width=True):
        st.session_state.active_image_id = None
    c3.button("Look optimieren", key="image_auto_optimize", use_container_width=True, on_click=optimize_image_look)
    if st.button("Bühne aufhellen", key="image_brighten_stage", use_container_width=True):
        brighten_stage()
    st.selectbox("Bild-Fit", ["cover", "contain"], key="bg_fit", on_change=mark_image_look_adjusted)
    st.slider("Helligkeit", 20, 140, key="bg_brightness", on_change=mark_image_look_adjusted)
    st.session_state.bg_blur = st.slider(
        "Bild-Blur", 0, 18, value=st.session_state.bg_blur, key="image_bg_blur", on_change=mark_image_look_adjusted
    )
    st.session_state.bg_dim = st.slider(
        "Overlay-Dunkelung Bild", 0, 90, value=st.session_state.bg_dim, key="image_bg_dim", on_change=mark_image_look_adjusted
    )
    st.session_state.bg_opacity = st.slider(
        "Bild-Transparenz", 0, 100, value=st.session_state.bg_opacity, key="image_bg_opacity", on_change=mark_image_look_adjusted
    )
    st.session_state.bg_zoom = st.slider(
        "Bild-Zoom", 80, 150, value=st.session_state.bg_zoom, key="image_bg_zoom", on_change=mark_image_look_adjusted
    )
    st.session_state.bg_pos_x = st.slider(
        "Bild-Position X", 0, 100, value=st.session_state.bg_pos_x, key="image_bg_pos_x", on_change=mark_image_look_adjusted
    )
    st.session_state.bg_pos_y = st.slider(
        "Bild-Position Y", 0, 100, value=st.session_state.bg_pos_y, key="image_bg_pos_y", on_change=mark_image_look_adjusted
    )

    st.divider()
    section("Buehnenbilder")
    normalize_stage_image_library()
    st.caption("Diese Bilder liegen als eigenständige Elemente auf der Bühne, nicht als Hintergrund.")
    stage_uploads = st.file_uploader(
        "Buehnenbilder hochladen",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="stage_image_upload",
    )
    if stage_uploads:
        known = {item["id"] for item in st.session_state.stage_images}
        for up in stage_uploads:
            data = up.getvalue()
            if len(data) > 5 * 1024 * 1024:
                st.warning(f"{up.name} ist groesser als 5 MB. Bitte kleiner exportieren.")
                continue
            image_id = hashlib.sha1(data).hexdigest()[:12]
            if image_id not in known:
                st.session_state.stage_images.append({"id": image_id, "name": up.name, "title": up.name, "data_url": image_to_data_url(up)})
                known.add(image_id)
                if not st.session_state.active_stage_image_id:
                    st.session_state.active_stage_image_id = image_id
                    st.session_state.show_stage_image = True

    if st.session_state.stage_images:
        for idx, item in enumerate(list(st.session_state.stage_images)):
            cols = st.columns([1, 1, 1])
            cols[0].image(item["data_url"], use_container_width=True)
            new_title = cols[0].text_input("Titel", value=item.get("title", item.get("name", "Buehnenbild")), key=f"stage_img_title_{item['id']}_{idx}", label_visibility="collapsed")
            item["title"] = new_title
            cols[1].button(
                ("Aktiv" if item["id"] == st.session_state.active_stage_image_id else "Einblenden"),
                key=f"stage_img_on_{item['id']}",
                use_container_width=True,
                on_click=activate_stage_image,
                args=(item["id"],),
            )
            if cols[2].button("Löschen", key=f"stage_img_del_{item['id']}", use_container_width=True):
                st.session_state.stage_images = [img for img in st.session_state.stage_images if img["id"] != item["id"]]
                if st.session_state.active_stage_image_id == item["id"]:
                    st.session_state.active_stage_image_id = None
                    st.session_state.show_stage_image = False
    csi0, csi1, csi2 = st.columns(3)
    if csi0.button(
        "Buehnenbild ausblenden" if st.session_state.show_stage_image else "Buehnenbild zeigen",
        key="stage_img_toggle_visibility",
        use_container_width=True,
        disabled=not bool(st.session_state.active_stage_image_id),
    ):
        st.session_state.show_stage_image = not st.session_state.show_stage_image
    if csi1.button("Buehnenbild zentrieren", key="stage_img_center", use_container_width=True):
        st.session_state.stage_image_x = 50
        st.session_state.stage_image_y = 52
    if csi2.button("Buehnenbild entfernen", key="stage_img_remove", use_container_width=True):
        st.session_state.active_stage_image_id = None
        st.session_state.show_stage_image = False
    st.selectbox("Buehnenbild Fit", ["contain", "cover", "fill"], key="stage_image_fit")
    st.slider("Buehnenbild Position X", 0, 100, key="stage_image_x")
    st.slider("Buehnenbild Position Y", 0, 100, key="stage_image_y")
    st.slider("Buehnenbild Breite", 10, 100, key="stage_image_width")
    st.slider("Buehnenbild Hoehe", 10, 90, key="stage_image_height")
    st.slider("Buehnenbild Deckkraft", 0, 100, key="stage_image_opacity")
    st.slider("Buehnenbild Rundung", 0, 40, key="stage_image_radius")


def render_scene_panel() -> None:
    section("Szenen")
    name = st.text_input("Neue Szene", value="Meine Szene")
    if st.button("Save Scene", key="scene_save", use_container_width=True):
        if name.strip():
            st.session_state.scenes[name.strip()] = snapshot_scene()
            st.session_state.last_active_scene = name.strip()
    for scene_name, scene in list(st.session_state.scenes.items()):
        cols = st.columns([1.2, .7, .7])
        if cols[0].button(scene_name, key=f"scene_{scene_name}", use_container_width=True):
            apply_scene(scene)
            st.session_state.last_active_scene = scene_name
            if st.session_state.active_image_id and not any(img["id"] == st.session_state.active_image_id for img in st.session_state.images):
                st.session_state.active_image_id = None
        if cols[1].button("Überschr.", key=f"scene_over_{scene_name}", use_container_width=True):
            st.session_state.scenes[scene_name] = snapshot_scene()
        if cols[2].button("Dupl.", key=f"scene_dup_{scene_name}", use_container_width=True):
            st.session_state.scenes[f"{scene_name} Kopie"] = dict(scene)
        new_name = st.text_input("Umbenennen", value=scene_name, key=f"scene_rename_{scene_name}", label_visibility="collapsed")
        r1, r2 = st.columns(2)
        if r1.button("Name ändern", key=f"scene_rename_btn_{scene_name}", use_container_width=True) and new_name.strip() and new_name.strip() != scene_name:
            st.session_state.scenes[new_name.strip()] = st.session_state.scenes.pop(scene_name)
        if r2.button("Löschen", key=f"scene_delete_{scene_name}", use_container_width=True):
            st.session_state.scenes.pop(scene_name, None)
    st.download_button(
        "Szenen exportieren",
        data=json.dumps(st.session_state.scenes, ensure_ascii=False, indent=2),
        file_name="ttliveregie_szenen.json",
        mime="application/json",
        use_container_width=True,
    )
    import_file = st.file_uploader("Szenen importieren", type=["json"], key="scene_import_file")
    if import_file and st.button("Szenen-Import anwenden", key="scene_import_apply", use_container_width=True):
        try:
            imported = json.loads(import_file.getvalue().decode("utf-8"))
            if isinstance(imported, dict):
                st.session_state.scenes.update(imported)
        except Exception as exc:
            st.error(f"Import fehlgeschlagen: {exc}")


def render_quick_actions() -> None:
    section("Live-Schalter")
    actions = [
        ("Freeze", "freeze"),
        ("Reset", "reset"),
        ("Bühne reparieren", "repair_stage"),
        ("Auto-Highlight", "auto_highlight_action"),
        ("Aufhellen", "brighten"),
        ("Focus", "focus"),
        ("Minimal", "minimal"),
        ("Clear", "clear"),
        ("Show All", "show_all"),
        ("Hide All", "hide_all"),
    ]
    for i in range(0, len(actions), 2):
        c1, c2 = st.columns(2)
        for col, (label, action) in zip((c1, c2), actions[i:i + 2]):
            if col.button(label, key=f"qa_{action}", use_container_width=True):
                apply_quick_action(action)


def apply_quick_action(action: str) -> None:
    if action == "freeze":
        st.session_state.freeze_keywords = not st.session_state.freeze_keywords
    elif action == "reset":
        st.session_state.chat_window.clear()
        st.session_state.keywords = []
        st.session_state.last_keywords_snapshot = []
        st.session_state.filtered_top = []
        st.session_state.filtered_total = 0
    elif action == "repair_stage":
        reset_stage_to_safe_defaults()
    elif action == "auto_highlight_action":
        st.session_state.auto_highlight = True
        st.session_state.highlight_word = ""
    elif action == "brighten":
        brighten_stage()
    elif action == "focus":
        st.session_state.focus_mode = not st.session_state.focus_mode
    elif action == "minimal":
        st.session_state.minimal_mode = not st.session_state.minimal_mode
    elif action == "clear":
        st.session_state.clear_overlay = not st.session_state.clear_overlay
    elif action == "show_all":
        for key in ["show_topic", "show_cloud", "show_highlight", "show_countdown", "show_clock", "show_background", "show_stage_image"]:
            st.session_state[key] = True
        st.session_state.clear_overlay = False
        st.session_state.minimal_mode = False
    elif action == "hide_all":
        for key in ["show_topic", "show_cloud", "show_highlight", "show_countdown", "show_clock", "show_stage_image"]:
            st.session_state[key] = False


def render_faders() -> None:
    section("Cloud / Visual Mixing")
    live_count = len(st.session_state.get("keywords") or st.session_state.get("last_keywords_snapshot") or [])
    manual_count = len(parse_manual_cloud_words(st.session_state.manual_cloud_words_text))
    st.caption(f"Cloud-Status: {live_count} Live-Keywords · {manual_count} manuelle Wörter · sichtbar: {'ja' if st.session_state.show_cloud and not st.session_state.clear_overlay and not st.session_state.minimal_mode else 'nein'}")
    selected_style = st.selectbox("Cloud-Stil", CLOUD_STYLES, index=CLOUD_STYLES.index(st.session_state.cloud_style) if st.session_state.cloud_style in CLOUD_STYLES else 0)
    if selected_style != st.session_state.cloud_style:
        st.session_state.cloud_style = selected_style
        st.session_state.cloud_style_locked = True
    st.toggle("Cloud-Stil manuell fixieren", key="cloud_style_locked")
    st.slider("Keyword-Dichte", 10, 100, key="keyword_density")
    st.slider("Animationsintensität", 0, 100, key="animation_intensity")
    st.slider("Cloud Position X", 0, 100, key="cloud_pos_x")
    st.slider("Cloud Position Y", 0, 100, key="cloud_pos_y")
    if st.session_state.cloud_pos_x != 50 or st.session_state.cloud_pos_y != 50:
        st.session_state.user_adjusted_cloud_position = True
    if st.button("Cloud zentrieren", key="center_cloud", use_container_width=True):
        st.session_state.cloud_pos_x = 50
        st.session_state.cloud_pos_y = 50
        st.session_state.cloud_width = 58
        st.session_state.cloud_height = 58
        st.session_state.cloud_tilt = 0
        st.session_state.user_adjusted_cloud_position = False
    st.slider("Cloud-Breite", 35, 90, key="cloud_width")
    st.slider("Cloud-Höhe", 35, 90, key="cloud_height")
    st.slider("Cloud Rotation / Tilt", -10, 10, key="cloud_tilt")
    st.slider("Overlay-Transparenz", 20, 100, key="overlay_opacity")
    st.slider("Übergangsgeschwindigkeit", 10, 100, key="transition_speed")


def render_motion_panel() -> None:
    section("Bewegung / Heatmap")
    st.caption("Ein/Aus fuer Bewegung und Heatmap sitzt auch im Bereich Sichtbarkeit.")
    st.multiselect("Transparente Bewegungs-Layer", MOTION_EFFECTS, key="motion_effects")
    st.slider("Bewegungs-Transparenz", 0, 80, key="motion_opacity")
    st.slider("Bewegungs-Geschwindigkeit", 10, 100, key="motion_speed")
    st.slider("Heatmap-Transparenz", 0, 75, key="heatmap_opacity")
    sentiment = chat_sentiment_state()
    st.caption(f"Aktuelle Stimmung: {sentiment['label']} · Score {sentiment['score']:.2f}")


def clear_pdf_state() -> None:
    st.session_state.pdf_name = ""
    st.session_state.pdf_data = ""
    st.session_state.show_pdf = False
    st.session_state.pdf_visible_control = False


def sync_pdf_visibility() -> None:
    st.session_state.show_pdf = bool(st.session_state.get("pdf_visible_control", False))


def sync_background_visibility() -> None:
    st.session_state.show_background = bool(st.session_state.get("background_visible_control", True))


def set_background_visible(value: bool) -> None:
    st.session_state.show_background = bool(value)


def activate_image(image_id: str) -> None:
    st.session_state.active_image_id = image_id
    set_background_visible(True)


def activate_stage_image(image_id: str) -> None:
    st.session_state.active_stage_image_id = image_id
    st.session_state.show_stage_image = True


def toggle_background_visibility() -> None:
    set_background_visible(not st.session_state.get("show_background", True))


def optimize_image_look() -> None:
    st.session_state.bg_dim = 34
    st.session_state.bg_blur = 2
    st.session_state.bg_brightness = 112
    st.session_state.bg_opacity = 96
    st.session_state.user_adjusted_image_look = True
    st.session_state.cloud_width = 62
    set_background_visible(True)


def render_media_panel() -> None:
    section("Video")
    st.session_state.video_url = st.text_input(
        "Video-URL",
        value=st.session_state.video_url,
        placeholder="https://.../video.mp4 oder direkte WebM/HLS-URL",
    )
    st.caption("Direkte MP4/WebM/HLS-Links laufen im Videoplayer. YouTube wird als Embed geladen. Autoplay mit Ton wird von Browserquellen oft blockiert; stabiler ist Play per Klick oder stummgeschaltetes Autoplay.")
    v1, v2 = st.columns(2)
    with v1:
        st.toggle("Video anzeigen", key="show_video")
        st.toggle("Ton stummschalten", key="video_muted")
    with v2:
        st.toggle("Hintergrund hinter Video sichtbar", key="video_show_background")
        st.selectbox("Video Fit", ["contain", "cover", "fill"], key="video_fit")
    if st.session_state.video_url:
        st.session_state.video_url = readable_url(st.session_state.video_url)
    st.slider("Video Position X", 0, 100, key="video_x")
    st.slider("Video Position Y", 0, 100, key="video_y")
    st.slider("Video Breite", 15, 100, key="video_width")
    st.slider("Video Höhe", 10, 90, key="video_height")
    st.slider("Video Deckkraft", 20, 100, key="video_opacity")

    section("Website / Browser")
    st.session_state.website_url = st.text_input(
        "Website-URL",
        value=st.session_state.website_url,
        placeholder="https://example.com",
    )
    st.caption("Normale Websites blockieren haeufig iframe-Einbettung. Nutze Website-Proxy fuer Artikel-/News-Seiten; Interaktiver Browser funktioniert nur mit embed-freundlichen Seiten.")
    if st.session_state.website_url:
        st.session_state.website_url = readable_url(st.session_state.website_url)
    c1, c2 = st.columns(2)
    if c1.button("Website-Proxy laden", key="website_proxy_load", use_container_width=True):
        ok, result = fetch_website_proxy_html(st.session_state.website_url)
        if ok:
            st.session_state.website_proxy_html = result
            st.session_state.website_proxy_error = ""
            st.session_state.website_mode = "Website-Proxy"
            st.session_state.show_website = True
            st.success("Website-Proxy geladen.")
        else:
            st.session_state.website_proxy_error = result
            st.error(result)
    if c2.button("Website-Vorschau laden", key="website_preview_load", use_container_width=True):
        ok, title, text = fetch_website_preview(st.session_state.website_url)
        if ok:
            st.session_state.website_preview_title = title
            st.session_state.website_preview_text = text
            st.session_state.website_preview_error = ""
            st.session_state.website_mode = "Website-Vorschau"
            st.session_state.show_website = True
            og = fetch_website_og(st.session_state.website_url)
            st.session_state.website_preview_image = og.get("image", "")
            st.success("Vorschau geladen.")
        else:
            st.session_state.website_preview_error = text
            st.error(text)
    if st.button("Live-Screenshot anzeigen", key="website_screenshot_load", use_container_width=True):
        if st.session_state.website_url:
            st.session_state.website_mode = "Screenshot"
            st.session_state.show_website = True
            st.success("Screenshot-Modus aktiviert. Die Bühne lädt das Bild von image.thum.io.")
        else:
            st.warning("Bitte erst eine URL eingeben.")
    st.toggle("Website anzeigen", key="show_website")
    st.selectbox(
        "Website Darstellung",
        ["Auto", "Screenshot", "Website-Proxy", "Website-Vorschau", "Interaktiver Browser", "Link-Karte", "Mini-Browser (Neko)"],
        key="website_mode",
        help="Auto: erst iframe, bei Blockern Screenshot. Screenshot: image.thum.io. Mini-Browser (Neko): echter klickbarer Browser via selbst-gehostetem Neko-Server (siehe README).",
    )

    with st.expander("Mini-Browser (Neko) Setup", expanded=False):
        st.caption(
            "Streamlit Cloud kann selbst keinen echten Browser hosten. Mit einem "
            "selbst-gehosteten Neko-Server (https://github.com/m1k1o/neko, ~5 €/Monat "
            "auf Hetzner) bekommst du einen WebRTC-Browser, den du auf der Bühne "
            "klicken/scrollen kannst. Anleitung im README → Abschnitt **Mini-Browser via Neko**."
        )
        st.session_state.neko_url = st.text_input(
            "Neko-URL",
            value=st.session_state.get("neko_url", ""),
            placeholder="https://neko.example.com",
            help="Vollständige HTTPS-URL deines Neko-Servers. Empfehlung: passwortgeschützt, kein public-shared.",
        )
        st.session_state.neko_password = st.text_input(
            "Neko-Passwort (optional)",
            value=st.session_state.get("neko_password", ""),
            type="password",
            help="Wenn dein Neko-Server NEKO_PASSWORD setzt, kannst du es hier hinterlegen — wird nur als Hinweis im Embed angezeigt.",
        )
        cn1, cn2 = st.columns(2)
        if cn1.button("Mini-Browser aktivieren", key="neko_activate", use_container_width=True):
            if st.session_state.neko_url:
                st.session_state.website_mode = "Mini-Browser (Neko)"
                st.session_state.show_website = True
                st.success("Mini-Browser-Modus aktiv. Bühne lädt jetzt deinen Neko-Server.")
            else:
                st.warning("Bitte erst eine Neko-URL eingeben.")
        if cn2.button("Mini-Browser deaktivieren", key="neko_deactivate", use_container_width=True):
            st.session_state.website_mode = "Auto"
            st.success("Zurück zum Auto-Modus.")
    if st.session_state.website_url and is_known_iframe_blocked(st.session_state.website_url):
        st.warning("Diese Domain blockiert sehr wahrscheinlich iframe-Einbettung. Nutze Website-Vorschau, Link-Karte oder eine offizielle Embed-/Video-URL.")
    c3, c4 = st.columns(2)
    if c3.button("Proxy löschen", key="website_proxy_clear", use_container_width=True):
        st.session_state.website_proxy_html = ""
        st.session_state.website_proxy_error = ""
    if c4.button("Vorschau löschen", key="website_preview_clear", use_container_width=True):
        st.session_state.website_preview_title = ""
        st.session_state.website_preview_text = ""
        st.session_state.website_preview_error = ""
    if st.session_state.website_proxy_error:
        st.caption(st.session_state.website_proxy_error)
    if st.session_state.website_preview_error:
        st.caption(st.session_state.website_preview_error)
    if st.session_state.website_proxy_html:
        st.caption(f"Website-Proxy aktiv ({len(st.session_state.website_proxy_html):,} Zeichen HTML).")
    if st.session_state.website_preview_text:
        st.text_area("Geladene Vorschau", value=st.session_state.website_preview_text, height=110, disabled=True)
    st.slider("Website Position X", 0, 100, key="website_x")
    st.slider("Website Position Y", 0, 100, key="website_y")
    st.slider("Website Breite", 20, 100, key="website_width")
    st.slider("Website Höhe", 15, 90, key="website_height")

    section("PDF")
    st.session_state.pdf_visible_control = bool(st.session_state.get("show_pdf", False))
    pdf_upload = st.file_uploader("PDF hochladen", type=["pdf"], key="pdf_upload")
    if pdf_upload is not None:
        st.session_state.pdf_name = pdf_upload.name
        st.session_state.pdf_data = pdf_to_data_url(pdf_upload)
        st.session_state.show_pdf = True
        st.session_state.pdf_visible_control = True
        st.success(f"PDF geladen: {pdf_upload.name}")
    p1, p2 = st.columns(2)
    with p1:
        st.toggle("PDF anzeigen", key="pdf_visible_control", on_change=sync_pdf_visibility)
    with p2:
        st.button("PDF entfernen", key="pdf_clear", use_container_width=True, on_click=clear_pdf_state)
    if st.session_state.pdf_name:
        st.caption(f"Aktives PDF: {st.session_state.pdf_name}")
    st.radio("PDF Ausrichtung", ["Hochformat", "Querformat"], key="pdf_orientation", horizontal=True)
    if st.button("PDF zentrieren", key="pdf_center", use_container_width=True):
        st.session_state.pdf_x = 50
        st.session_state.pdf_y = 54
        if st.session_state.pdf_orientation == "Hochformat":
            st.session_state.pdf_width = 76
            st.session_state.pdf_height = 72
        else:
            st.session_state.pdf_width = 88
            st.session_state.pdf_height = 54
    st.slider("PDF Position X", 0, 100, key="pdf_x")
    st.slider("PDF Position Y", 0, 100, key="pdf_y")
    st.slider("PDF Breite", 20, 100, key="pdf_width")
    st.slider("PDF Höhe", 20, 95, key="pdf_height")
    st.slider("PDF Start-Zoom", 50, 200, key="pdf_zoom")


def render_ai_panel() -> None:
    section("KI-Check")
    st.caption("Nutzt Google Gemini ueber Streamlit Secrets: GOOGLE_API_KEY oder GEMINI_API_KEY. Die Antwort kann als Karte auf der Bühne angezeigt werden.")
    if st.session_state.get("ai_model") in LEGACY_AI_MODEL_MAP:
        st.session_state.ai_model = LEGACY_AI_MODEL_MAP[st.session_state.ai_model]
    if st.session_state.get("ai_model") not in AI_MODELS:
        st.session_state.ai_model = "gemini-2.5-flash"
    st.selectbox("Modell", AI_MODELS, key="ai_model", format_func=lambda value: AI_MODEL_LABELS.get(value, value))
    st.caption(f"Aktiv: {AI_MODEL_LABELS.get(st.session_state.ai_model, st.session_state.ai_model)}")
    st.slider("Maximale Antwortlänge", 300, 3000, key="ai_max_chars", step=100, help="Diese Zeichenbegrenzung wird der KI im Prompt mitgegeben und danach zusätzlich hart abgesichert.")
    st.session_state.ai_prompt = st.text_area("Prompt / Text für die Live-Prüfung", value=st.session_state.ai_prompt, height=130)
    c1, c2 = st.columns(2)
    if c1.button("KI prüfen", key="ai_run", use_container_width=True):
        ok, text = run_ai_summary(st.session_state.ai_prompt)
        if ok:
            st.session_state.ai_response = text
            st.session_state.ai_error = ""
            st.session_state.show_ai_card = True
            st.success("Antwort ist bereit.")
        else:
            st.session_state.ai_error = text
            st.session_state.ai_response = ""
            st.session_state.show_ai_card = False
            st.error(text)
    if c2.button("KI-Karte löschen", key="ai_clear", use_container_width=True):
        st.session_state.ai_response = ""
        st.session_state.ai_error = ""
        st.session_state.show_ai_card = False
    st.toggle("KI-Karte auf Bühne anzeigen", key="show_ai_card", disabled=not bool(st.session_state.ai_response))
    if st.session_state.ai_error:
        st.error(st.session_state.ai_error)
    if st.session_state.ai_response:
        st.text_area("Aktuelle KI-Antwort", value=st.session_state.ai_response, height=160, disabled=True)


def render_typography_panel() -> None:
    section("Typografie")
    fonts = list(FONT_PRESETS)
    transforms = ["normal", "uppercase"]
    st.selectbox("Thema Font", fonts, key="topic_font_family", on_change=mark_typography_adjusted)
    st.markdown(
        f'<div class="font-preview" style="font-family:{font_stack(st.session_state.topic_font_family)}">Thema Vorschau: Worueber sprechen wir gerade?</div>',
        unsafe_allow_html=True,
    )
    st.slider("Thema Größe", 65, 180, key="topic_text_size", on_change=mark_typography_adjusted)
    st.slider("Thema Gewicht", 300, 950, key="topic_font_weight", step=50, on_change=mark_typography_adjusted)
    st.slider("Thema Letter Spacing", -8, 18, key="topic_letter_spacing", on_change=mark_typography_adjusted)
    st.selectbox("Thema Text Transform", transforms, key="topic_text_transform", on_change=mark_typography_adjusted)
    st.selectbox("Keyword Font", fonts, key="keyword_font_family", on_change=mark_typography_adjusted)
    st.markdown(
        f'<div class="font-preview compact" style="font-family:{font_stack(st.session_state.keyword_font_family)}">Keyword Vorschau: demokratie dialog fakten live</div>',
        unsafe_allow_html=True,
    )
    st.slider("Keyword Basisgröße", 30, 180, key="keyword_size", on_change=mark_typography_adjusted)
    st.slider("Keyword Gewicht", 300, 950, key="keyword_font_weight", step=50, on_change=mark_typography_adjusted)
    st.toggle("Zufällige Keyword-Gewichtung", key="keyword_random_weight", on_change=mark_typography_adjusted)
    st.selectbox("Highlight Font", fonts, key="highlight_font_family", on_change=mark_typography_adjusted)
    st.markdown(
        f'<div class="font-preview" style="font-family:{font_stack(st.session_state.highlight_font_family)}">Highlight Vorschau</div>',
        unsafe_allow_html=True,
    )
    st.slider("Highlight Größe", 60, 190, key="highlight_text_size", on_change=mark_typography_adjusted)
    st.slider("Highlight Gewicht", 300, 950, key="highlight_font_weight", step=50, on_change=mark_typography_adjusted)
    st.slider("Highlight Letter Spacing", -8, 18, key="highlight_letter_spacing", on_change=mark_typography_adjusted)
    st.selectbox("Countdown / Uhr Font", fonts, key="countdown_font_family", on_change=mark_typography_adjusted)
    st.markdown(
        f'<div class="font-preview compact" style="font-family:{font_stack(st.session_state.countdown_font_family)}">LIVE 12:34 · seit 00:12:08</div>',
        unsafe_allow_html=True,
    )
    st.slider("Countdown Größe", 70, 160, key="countdown_text_size", on_change=mark_typography_adjusted)
    st.slider("Live-Uhr Größe", 70, 160, key="clock_text_size", on_change=mark_typography_adjusted)
    st.slider("Countdown / Uhr Gewicht", 300, 950, key="countdown_font_weight", step=50, on_change=mark_typography_adjusted)


def safety_status() -> tuple[str, str]:
    recent_filtered = sum(count for _, count in st.session_state.filtered_top[:5])
    if recent_filtered >= 18:
        return "Rot", "#ff5b5b"
    if recent_filtered >= 7:
        return "Gelb", "#ffd166"
    return "Grün", "#5be37d"


def parse_word_list(text: str) -> set[str]:
    return {normalize_word(part) for part in re.split(r"[\n,; ]+", text or "") if normalize_word(part)}


def parse_manual_cloud_words(text: str) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[\n,;]+", text or ""):
        cleaned = normalize_word(part)
        if cleaned and cleaned not in seen and is_safe_keyword(cleaned):
            seen.add(cleaned)
            words.append(cleaned)
    return words[:10]


def render_safety_panel() -> None:
    section("Safety")
    status, color = safety_status()
    st.markdown(f'<div class="status-pill"><b>Safety Status:</b> <span style="color:{color};font-weight:900">{status}</span><br><b>Gefiltert:</b> {st.session_state.filtered_total}</div>', unsafe_allow_html=True)
    if st.session_state.filtered_top:
        st.caption("Top gefilterte Begriffe")
        st.write(", ".join(f"{word} ({count})" for word, count in st.session_state.filtered_top[:10]))
    st.session_state.custom_blacklist_text = st.text_area("Editierbare Blacklist", value=st.session_state.custom_blacklist_text, height=90)
    if st.button("Blacklist anwenden", key="blacklist_apply", use_container_width=True):
        CUSTOM_BLACKLIST.clear()
        CUSTOM_BLACKLIST.update(custom_blacklist_values())
        compute_keywords(force=True)
    st.session_state.custom_whitelist_text = st.text_area("Editierbare Whitelist", value=st.session_state.custom_whitelist_text, height=90)
    if st.button("Whitelist anwenden", key="whitelist_apply", use_container_width=True):
        CUSTOM_WHITELIST.clear()
        CUSTOM_WHITELIST.update(custom_whitelist_values())
        compute_keywords(force=True)


def primary_browser_source_url() -> str:
    """Liefert die EINE Browserquellen-URL, die der User in TikTok Live Studio einfügt.

    Das ist immer die GitHub-Pages-URL der Bühne, parametrisiert mit der aktuellen
    Room-ID und (sofern konfiguriert) der Gist-ID für State-Sync. Public, kein Auth.
    """
    room = safe_profile_id(st.session_state.get("overlay_room_id", "default") or "default")
    gid = _gist_id() or None
    return github_pages_stage_url(room, gist_id=gid, gist_user=(_gist_user() if gid else None))


def render_primary_browser_source(prefix: str = "stage_topbar") -> None:
    """Prominente, kopierbare Browserquellen-URL — eine einzige.

    Wird oben über der Bühne im Regiepult angezeigt. Der User soll genau
    eine URL kennen, die er in TikTok Live Studio einfügt.
    """
    url = primary_browser_source_url()
    st.markdown("##### TikTok Live Studio Browserquelle")
    st.code(url, language=None)
    has_gist = bool(_gist_id() and _gist_token())
    if has_gist:
        status = st.session_state.get("gist_status") or {}
        if status.get("ok"):
            st.caption(f"Gist-Sync aktiv — letzter Push: {status.get('msg','')}.")
        elif "HTTP 403" in str(status.get("msg", "")):
            st.error(
                "Gist-Sync bekommt HTTP 403. Der Token darf diesen Gist nicht schreiben. "
                "Bitte im Backup-Tab einen Classic GitHub-Token mit Scope `gist` nutzen oder einen neuen Gist anlegen."
            )
        elif status.get("msg"):
            st.caption(f"Gist-Sync konfiguriert, letzter Status: {status.get('msg')}.")
        else:
            st.caption("Gist-Sync konfiguriert. State wird beim nächsten Update gepusht.")
    else:
        st.caption(
            "Diese URL ist auf GitHub Pages gehostet — immer ohne Login erreichbar. "
            "Für Live-Updates aus der Regie noch Gist-Sync einrichten (Tab Backup → Gist-Sync)."
        )


def render_persistence_panel() -> None:
    section("Persistenz / Backup")
    st.caption("Settings, Szenen und Bildbibliothek werden im Browser localStorage gesichert. Zusätzlich wird lokal eine JSON-Datei als Fallback geschrieben.")
    st.session_state.overlay_room_id = safe_profile_id(
        st.text_input(
            "Geheime Host-Overlay-ID",
            value=st.session_state.overlay_room_id,
            help="Diese ID verbindet Regiepult und Browserquelle. Sie ist nicht an den TikTok-Usernamen gebunden.",
        )
    )

    # EINE prominente Browserquellen-URL — exakt das, was der User in TikTok Live Studio einfügt.
    render_primary_browser_source(prefix="stage_backup")

    if st.button("Neue geheime Overlay-ID erzeugen", key="room_rotate", use_container_width=True):
        st.session_state.overlay_room_id = safe_profile_id(str(uuid.uuid4()))[:18]
        save_persisted_state("rotate_room")
        st.rerun()
    if st.button("Jetzt speichern", key="persist_save_btn", use_container_width=True):
        save_persisted_state("manual")
        st.success("Gespeichert.")
    backup = json.dumps(persistent_payload(), ensure_ascii=False, indent=2)
    st.download_button("Backup exportieren", backup, file_name="ttliveregie_backup.json", mime="application/json", use_container_width=True)
    backup_file = st.file_uploader("Backup importieren", type=["json"], key="backup_import_file")
    if backup_file and st.button("Backup importieren anwenden", key="backup_import_apply", use_container_width=True):
        try:
            payload = json.loads(backup_file.getvalue().decode("utf-8"))
            apply_persistent_payload(payload)
            save_persisted_state("import")
            st.success("Backup importiert.")
        except Exception as exc:
            st.error(f"Backup-Import fehlgeschlagen: {exc}")
    if st.button("Alles lokal löschen", key="persist_clear_btn", use_container_width=True):
        clear_persisted_state()
        st.warning("Lokaler Speicher wurde geleert. Bitte App neu laden.")

    render_gist_sync_panel()

    with st.expander("Erweiterte URLs (Debug, Test, Lokal, Transparent)", expanded=False):
        room = st.session_state.overlay_room_id
        gist_id = _gist_id() or None
        gist_user = (_gist_user() or None) if gist_id else None
        gh_main = github_pages_stage_url(room, gist_id=gist_id, gist_user=gist_user)
        gh_debug = github_pages_stage_url(room, gist_id=gist_id, gist_user=gist_user, debug="1")
        gh_transparent = github_pages_stage_url(room, gist_id=gist_id, gist_user=gist_user, bg="transparent")
        gh_test = f"{GITHUB_PAGES_BASE}/stage.html?test=1"
        local_url = static_overlay_url("http://localhost:8501", room)
        render_copyable_url("GitHub Pages Bühne (Standard)", gh_main, "gh_main")
        render_copyable_url("GitHub Pages Debug (Debug-Banner)", gh_debug, "gh_debug")
        render_copyable_url("GitHub Pages Transparent (kein BG)", gh_transparent, "gh_transparent")
        render_copyable_url("GitHub Pages Test (TT LIVE STUDIO TEST OK)", gh_test, "gh_test")
        render_copyable_url("Lokale Bühne (nur für `streamlit run` zuhause)", local_url, "ttls_local")


def render_gist_sync_panel() -> None:
    """Konfiguration für GitHub-Gist-State-Sync."""
    with st.expander("Gist-Sync (TTLS-Live-Updates)", expanded=not bool(_gist_id() and _gist_token())):
        st.caption(
            "Damit die GitHub-Pages-Bühne in TikTok Live Studio Live-Updates aus der Regie sieht, "
            "pusht das Regiepult den Overlay-State in einen GitHub Gist. Du brauchst einmalig einen "
            "Personal Access Token mit Scope `gist`."
        )
        st.markdown(
            "[Token erstellen → github.com/settings/tokens (classic, Scope `gist`)]"
            "(https://github.com/settings/tokens/new?scopes=gist&description=ttliveregie)"
        )
        cur_token = st.session_state.get("gist_token", "")
        cur_gist = st.session_state.get("gist_id", "")
        cur_user = st.session_state.get("gist_user", "sustynats")
        token_in = st.text_input(
            "GitHub Personal Access Token (Scope `gist`)",
            value=cur_token,
            type="password",
            key="gist_token_input",
            help="Wird nicht persistiert, lebt nur in dieser Browser-Session.",
        )
        gist_in = st.text_input(
            "Gist-ID (leer = neu anlegen)",
            value=cur_gist,
            key="gist_id_input",
            help="Beispiel: 9c1a8e... — oder leer lassen und Button unten drücken.",
        )
        user_in = st.text_input(
            "GitHub-Username (Gist-Eigentümer)",
            value=cur_user,
            key="gist_user_input",
        )
        if st.button("Übernehmen", key="gist_apply"):
            st.session_state["gist_token"] = token_in.strip()
            st.session_state["gist_id"] = gist_in.strip()
            st.session_state["gist_user"] = user_in.strip() or "sustynats"
            st.success("Gist-Konfiguration gespeichert. Beim nächsten State-Update wird gepusht.")
        if st.button("Neuen Gist anlegen", key="gist_create", help="Erzeugt einen neuen Public Gist mit dem aktuellen State."):
            tok = (token_in or cur_token).strip()
            if not tok:
                st.error("Token fehlt.")
            else:
                try:
                    serialized = json.dumps(current_overlay_state(), ensure_ascii=False)
                    new_id, owner = create_gist_for_user(tok, st.session_state.overlay_room_id, serialized)
                    if new_id:
                        st.session_state["gist_token"] = tok
                        st.session_state["gist_id"] = new_id
                        if owner:
                            st.session_state["gist_user"] = owner
                        st.success(f"Gist {new_id} angelegt (Owner: {owner or 'unbekannt'}). URL oben aktualisiert.")
                        st.rerun()
                    else:
                        st.error("Gist-Erstellung fehlgeschlagen — keine ID erhalten.")
                except Exception as exc:
                    st.error(f"Gist-Erstellung fehlgeschlagen: {exc}")
        if st.button("Sync jetzt testen", key="gist_test"):
            tok = _gist_token(); gid = _gist_id()
            if not tok or not gid:
                st.error("Token oder Gist-ID fehlt.")
            else:
                _push_state_to_gist_now(json.dumps(current_overlay_state(), ensure_ascii=False), tok, gid)
                status = st.session_state.get("gist_status", {})
                if status.get("ok"):
                    st.success(f"Push erfolgreich: {status.get('msg')}")
                else:
                    st.error(f"Push-Fehler: {status.get('msg')}")


def render_control_panel() -> None:
    render_director_header()
    # EINE prominente TTLS-Browserquellen-URL direkt oben — das ist die wichtigste
    # URL der App. Genau diese fügt der User in TikTok Live Studio als Browserquelle
    # ein. Alle anderen Varianten (Debug, Test, Lokal, Transparent) bleiben im
    # Backup-Tab unter "Erweiterte URLs" versteckt.
    render_primary_browser_source(prefix="stage_topbar")
    render_quick_actions()
    if st.button("Szene jetzt speichern", key="quick_save_scene_top", use_container_width=True):
        scene_name = st.session_state.last_active_scene or f"Szene {len(st.session_state.scenes) + 1}"
        st.session_state.scenes[scene_name] = snapshot_scene()
        st.session_state.last_active_scene = scene_name

    tab_buehne, tab_live, tab_inhalte, tab_medien, tab_stil, tab_szenen, tab_backup = st.tabs(
        ["Bühne", "Live", "Inhalte", "Medien", "Stil", "Szenen", "Backup"]
    )

    with tab_buehne:
        with st.expander("Sichtbarkeit", expanded=True):
            render_toggle_panel()
        with st.expander("Position & Größe", expanded=False):
            render_position_panel()
        with st.expander("Thema & Highlight", expanded=True):
            render_topic_panel()
            render_highlight_panel()

    with tab_live:
        with st.expander("Verbindung", expanded=True):
            render_section_note("Nur hier startest oder stoppst du den TikTok-Live-Chat. Auf der Bühne erscheinen keine Usernamen oder Einzelkommentare.")
            render_connection_panel()
        with st.expander("Safety", expanded=False):
            render_safety_panel()

    with tab_inhalte:
        with st.expander("Countdown & Uhr", expanded=True):
            render_countdown_panel()
        with st.expander("KI-Check", expanded=False):
            render_ai_panel()

    with tab_medien:
        with st.expander("Bilder", expanded=True):
            render_section_note("Ausblenden hält das aktive Bild bereit. Löschen entfernt es aus der Bildbibliothek.")
            render_image_panel()
        with st.expander("Video / Website / PDF", expanded=False):
            render_section_note("Externe Seiten: Auto-Modus versucht erst iframe, schaltet bei Blockern auf Live-Screenshot um.")
            render_media_panel()

    with tab_stil:
        with st.expander("Layouts", expanded=True):
            render_section_note("Ein Layout setzt Farbwelt, Typografie und Standard-Cloud. Cloud-Lock fixiert deine manuellen Cloud-Einstellungen.")
            render_layout_panel()
        with st.expander("Cloud / Position", expanded=False):
            render_section_note("Hier verschiebst du die Tag-Cloud frei. X/Y wirken live; oder ziehe sie direkt auf der Bühne im Edit-Modus.")
            render_faders()
        with st.expander("Bewegung / Heatmap", expanded=False):
            render_section_note("Transparente Motion-Layer laufen über dem Hintergrund, damit TikTok eine dezente Bewegung erkennt.")
            render_motion_panel()
        with st.expander("Typografie", expanded=False):
            render_typography_panel()

    with tab_szenen:
        render_section_note("Szenen speichern den kompletten visuellen Zustand. Nutze sie live wie Regie-Cues.")
        render_scene_panel()

    with tab_backup:
        render_persistence_panel()


# ---------------------------------------------------------------------------
# App-Start
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="TikTok Live Regiepult", page_icon="●", layout="wide", initial_sidebar_state="collapsed")
    init_state()
    overlay_mode = st.query_params.get("overlay", "0") == "1"
    if overlay_mode:
        # Alte URLs auf stage.html umleiten — die Streamlit-Seite hostet kein
        # eigenes Overlay-DOM mehr.
        st.markdown(css_for_overlay_mode(), unsafe_allow_html=True)
        render_static_overlay_redirect()
        return

    load_persisted_state_once()
    st.markdown(css_for_streamlit(), unsafe_allow_html=True)
    # Auto-refresh: nur dann nötig, wenn der Live-Chat tickt (neue Keywords)
    # ODER ein Countdown läuft. Beim reinen Style-/Layout-Editieren wäre ein
    # 4s-Refresh schädlich — er triggert Re-Renders der Sidebar und damit
    # potenziell auch des Bühnen-iFrames. Die Bühne selbst pollt eigenständig
    # alle 2s, dafür braucht das Regiepult kein Auto-Refresh.
    rt = live_runtime()
    live_active = bool(rt.thread and rt.thread.is_alive() and rt.status in {"connected", "connecting"})
    countdown_active = bool(st.session_state.get("countdown_running"))
    has_pending_gist = bool(st.session_state.get("gist_pending"))
    if live_active or countdown_active:
        # Live-Betrieb: 5s reichen für Chat-Drain & Countdown-Tick.
        st_autorefresh(interval=5000, key="refresh")
    elif has_pending_gist:
        # Idle, aber ein Gist-Push ist gequeued (Throttle griff). Kurzer
        # Refresh, damit der pending-State noch in den Gist landet —
        # andernfalls verschluckt das Throttle-Fenster Layout-Änderungen,
        # die direkt nach einem OK-Push reinkommen.
        st_autorefresh(interval=2500, key="refresh_gist_drain", limit=2)
    update_countdown()

    drain_live_comments()
    compute_keywords()
    persist_overlay_state()

    left, right = st.columns([0.30, 0.70], gap="medium")
    with left:
        with st.container(key="control_panel_scroll"):
            render_control_panel()
    with right:
        with st.container(key="stage_panel_fixed"):
            top_cols = st.columns([0.70, 0.30])
            with top_cols[0]:
                st.markdown("### Bühne")
            with top_cols[1]:
                st.selectbox("Format", ["9:16", "16:9"], key="aspect", label_visibility="collapsed")
            render_stage(current_overlay_state(), height=900)
    save_persisted_state("auto")


if __name__ == "__main__":
    main()
