from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import math
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
from urllib.parse import urlparse

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
LOCAL_STORAGE_KEY = "ttliveregie_state_v2"
LOCAL_BROWSER_ID_KEY = "ttliveregie_browser_id_v1"
COMMENT_WINDOW_SECONDS = 4 * 60
KEYWORD_REFRESH_SECONDS = 20
MAX_KEYWORDS = 32
MIN_WORD_LENGTH = 3
DEFAULT_ASPECT = "9:16"
DEFAULTS_VERSION = 3
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
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-generate-001",
    "imagen-3.0-generate-002",
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-preview-image-generation",
]
IMAGE_MODEL_LABELS = {
    "imagen-4.0-fast-generate-001": "Imagen 4 Fast",
    "imagen-4.0-generate-001": "Imagen 4 Standard",
    "imagen-3.0-generate-002": "Imagen 3",
    "gemini-2.5-flash-image": "Gemini 2.5 Flash Image",
    "gemini-2.0-flash-preview-image-generation": "Gemini 2.0 Flash Image Preview",
}
MOTION_EFFECTS = ["Nebel", "Lagerfeuer", "Lichtstaub", "Scanlines", "Regen", "Funkeln", "Wellen"]
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
        async def main() -> None:
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

            try:
                task = await client.start(fetch_room_info=True)
                while not rt.stop_event.is_set():
                    await asyncio.sleep(0.25)
                await client.disconnect()
                if task:
                    task.cancel()
                rt.set_status("stopped", "Gestoppt")
            except Exception as exc:
                rt.set_status("error", f"Verbindung fehlgeschlagen: {exc}")

        asyncio.run(main())

    rt.thread = threading.Thread(target=runner, daemon=True)
    rt.thread.start()


def stop_live_connection() -> None:
    rt = live_runtime()
    rt.stop_event.set()
    rt.set_status("stopped", "Stop angefordert")


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

    st.session_state.keywords = next_keywords
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
        "show_overlay_frame": True,
        "minimal_mode": False,
        "freeze_keywords": False,
        "focus_mode": False,
        "clear_overlay": False,
        "bg_dim": 25,
        "bg_blur": 0,
        "bg_brightness": 115,
        "keyword_size": 55,
        "keyword_density": 45,
        "animation_intensity": 55,
        "show_motion_layers": True,
        "motion_effects": ["Nebel", "Lichtstaub"],
        "motion_opacity": 42,
        "motion_speed": 55,
        "show_heatmap": False,
        "heatmap_opacity": 28,
        "cloud_pos_x": 50,
        "cloud_pos_y": 50,
        "cloud_width": 58,
        "cloud_height": 58,
        "cloud_tilt": 0,
        "topic_text_size": 100,
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
        "highlight_font_family": "Playfair Display",
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
        "website_preview_error": "",
        "website_x": 50,
        "website_y": 54,
        "website_width": 76,
        "website_height": 58,
        "show_ai_card": False,
        "ai_prompt": "",
        "ai_response": "",
        "ai_error": "",
        "ai_model": "gemini-2.5-flash",
        "ai_max_chars": 1200,
        "image_prompt": "",
        "image_model": "imagen-4.0-fast-generate-001",
        "image_prompt_use_chat": True,
        "image_generation_error": "",
        "overlay_room_id": "",
        "chat_window": deque(maxlen=5000),
        "keywords": [],
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
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
        "cloud_pos_x", "cloud_pos_y", "cloud_width", "cloud_height", "cloud_tilt", "topic_text_size",
        "highlight_text_size", "countdown_text_size", "clock_text_size", "topic_font_family", "topic_font_weight",
        "topic_letter_spacing", "topic_text_transform", "keyword_font_family", "keyword_font_weight",
        "keyword_random_weight", "highlight_font_family", "highlight_font_weight", "highlight_letter_spacing",
        "countdown_font_family", "countdown_font_weight", "overlay_opacity", "transition_speed",
        "focus_mode", "clear_overlay", "user_adjusted_cloud_position", "user_adjusted_image_look",
        "show_video", "video_url", "video_show_background", "video_x", "video_y", "video_width", "video_height",
        "video_opacity", "video_fit", "video_muted", "show_website", "website_url", "website_mode",
        "website_preview_title", "website_preview_text", "website_preview_error", "website_x", "website_y",
        "website_width", "website_height", "show_ai_card", "ai_prompt", "ai_response", "ai_error", "ai_model", "overlay_room_id",
        "ai_max_chars", "image_prompt", "image_model", "image_prompt_use_chat", "image_generation_error",
    ]
    return {key: st.session_state.get(key) for key in keys}


def apply_visual_defaults_v3() -> None:
    st.session_state.layout = "Neon Pop"
    st.session_state.cloud_style = "Color Burst"
    st.session_state.show_highlight = False
    st.session_state.auto_highlight = False
    st.session_state.keyword_size = min(int(st.session_state.get("keyword_size", 55) or 55), 55)
    st.session_state.keyword_density = min(int(st.session_state.get("keyword_density", 45) or 45), 45)
    st.session_state.cloud_pos_x = 50
    st.session_state.cloud_pos_y = 50
    st.session_state.cloud_width = min(int(st.session_state.get("cloud_width", 58) or 58), 58)
    st.session_state.cloud_height = min(int(st.session_state.get("cloud_height", 58) or 58), 58)
    st.session_state.topic_font_family = "Poppins"
    st.session_state.defaults_version = DEFAULTS_VERSION


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


def apply_persistent_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    allowed = set(snapshot_scene()) | {
        "browser_id",
        "images",
        "active_image_id",
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
    if is_ai_error_text(st.session_state.get("ai_response", "")):
        st.session_state.ai_error = st.session_state.ai_response
        st.session_state.ai_response = ""
        st.session_state.show_ai_card = False
    if not payload.get("user_adjusted_cloud_position"):
        st.session_state.cloud_pos_x = 50
        st.session_state.cloud_pos_y = 50
    if not payload.get("user_adjusted_image_look") and st.session_state.get("bg_dim", 25) > 45:
        st.session_state.bg_dim = 25
        st.session_state.bg_brightness = max(115, st.session_state.get("bg_brightness", 115))
    st.session_state.topic_draft = st.session_state.topic
    st.session_state.highlight_draft = st.session_state.highlight_word


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


def youtube_embed_url(value: str) -> str:
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
    return f"https://www.youtube.com/embed/{html.escape(video_id)}?controls=1&rel=0&playsinline=1&enablejsapi=1"


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


def brighten_stage() -> None:
    st.session_state.bg_dim = 18
    st.session_state.bg_blur = 0
    st.session_state.bg_brightness = 125
    st.session_state.bg_opacity = 100
    st.session_state.overlay_opacity = 100
    st.session_state.clear_overlay = False
    st.session_state.show_background = True
    st.session_state.user_adjusted_image_look = True


def google_api_key() -> str:
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
        return False, "Kein GOOGLE_API_KEY oder GEMINI_API_KEY in Streamlit Secrets gefunden."
    model = st.session_state.get("image_model", "gemini-2.5-flash-image")
    if model not in IMAGE_MODELS:
        model = "imagen-4.0-fast-generate-001"
    visual_prompt = (
        "Create a high-quality vertical 9:16 abstract livestream overlay background. "
        "No text, no logos, no readable words, no people. Leave calm negative space on the right and bottom. "
        "Professional, subtle, readable behind typography. "
        f"Prompt: {prompt}"
    )
    try:
        client = genai.Client(api_key=api_key)
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
                    encoded = data if isinstance(data, str) else base64.b64encode(data).decode("ascii")
                    data_url = f"data:image/png;base64,{encoded}"
                    image_id = hashlib.sha1(data_url.encode("utf-8")).hexdigest()[:12]
                    title = f"KI-Bild {time.strftime('%H:%M:%S')}"
                    st.session_state.images.append({"id": image_id, "name": title, "title": title, "data_url": data_url})
                    st.session_state.active_image_id = image_id
                    st.session_state.show_background = True
                    st.session_state.bg_brightness = 118
                    st.session_state.bg_dim = 24
                    st.session_state.image_generation_error = ""
                    return True, f"Hintergrundbild mit {IMAGE_MODEL_LABELS.get(model, model)} generiert und aktiviert."
        else:
            kwargs: dict[str, Any] = {"model": model, "contents": [visual_prompt]}
            if model == "gemini-2.0-flash-preview-image-generation" and genai_types is not None:
                kwargs["config"] = genai_types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
            response = client.models.generate_content(**kwargs)
            parts = getattr(response, "parts", None)
            if parts is None and getattr(response, "candidates", None):
                parts = response.candidates[0].content.parts
            for part in parts or []:
                inline_data = getattr(part, "inline_data", None)
                if inline_data is not None:
                    data = getattr(inline_data, "data", b"")
                    mime_type = getattr(inline_data, "mime_type", "image/png") or "image/png"
                    encoded = data if isinstance(data, str) else base64.b64encode(data).decode("ascii")
                    data_url = f"data:{mime_type};base64,{encoded}"
                    image_id = hashlib.sha1(data_url.encode("utf-8")).hexdigest()[:12]
                    title = f"KI-Bild {time.strftime('%H:%M:%S')}"
                    st.session_state.images.append({"id": image_id, "name": title, "title": title, "data_url": data_url})
                    st.session_state.active_image_id = image_id
                    st.session_state.show_background = True
                    st.session_state.bg_brightness = 118
                    st.session_state.bg_dim = 24
                    st.session_state.image_generation_error = ""
                    return True, f"Hintergrundbild mit {IMAGE_MODEL_LABELS.get(model, model)} generiert und aktiviert."
        return False, "Google hat kein Bild zurückgegeben. Bitte Prompt oder Modell wechseln."
    except Exception as exc:
        return False, friendly_ai_error(exc)


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


# ---------------------------------------------------------------------------
# Overlay-Rendering
# ---------------------------------------------------------------------------

def css_for_streamlit() -> str:
    return """
    <style>
    .stApp { background: #0d0f12; color: #f7f2ea; }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { display: none; }
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


def render_overlay_html(state: dict[str, Any]) -> str:
    layout = state.get("layout", "Editorial Dark")
    layout = LEGACY_LAYOUT_MAP.get(layout, layout)
    theme = THEMES.get(layout, THEMES["Editorial Dark"])
    cloud_style = state.get("cloud_style") or theme.get("cloud_style", "Classic Word Cloud")
    cloud_slug = {
        "Bubble Cloud": "bubble",
        "Magazine Cloud": "magazine",
        "Network Cloud": "network",
        "Color Burst": "color",
        "Minimal Cloud": "minimal",
        "Orbital Cloud": "orbital",
        "Vertical Cloud": "vertical",
    }.get(cloud_style, "classic")
    keywords = state.get("keywords", [])
    if state.get("minimal_mode"):
        keywords = keywords[:0]
    if state.get("focus_mode"):
        keywords = keywords[:3]
    if cloud_style == "Minimal Cloud":
        keywords = keywords[:10]
    density = max(4, min(len(keywords), int(MAX_KEYWORDS * state.get("keyword_density", 80) / 100)))
    keywords = keywords[:density]
    manual_words = [] if state.get("minimal_mode") else state.get("manual_cloud_words", [])
    topic = html.escape(state.get("topic") or "")
    highlight = html.escape(state.get("highlight_word") or "")
    live_duration_text = html.escape(state.get("live_duration") or "00:00:00")
    live_started_at = state.get("live_started_at")
    live_since_time = time.strftime("%H:%M:%S", time.localtime(live_started_at)) if live_started_at else "--:--:--"
    remaining = int(state.get("countdown_remaining") or 0)
    total = max(1, int(state.get("countdown_total") or 1))
    countdown_pct = max(0, min(100, remaining / total * 100))
    mins, secs = divmod(remaining, 60)
    safe_zones = state.get("show_safe_zones")
    show_video = bool(state.get("show_video") and state.get("video_url"))
    bg_visible_behind_video = state.get("video_show_background", True)
    bg_url = state.get("active_image_data") if state.get("show_background") and (not show_video or bg_visible_behind_video) else ""
    aspect = "9 / 16" if state.get("aspect", DEFAULT_ASPECT) == "9:16" else "16 / 9"
    stage_width = "min(74vh, 100%)" if state.get("aspect", DEFAULT_ASPECT) == "9:16" else "100%"
    animation_scale = state.get("animation_intensity", 55) / 100
    anim_enabled = state.get("show_animations", True)
    overlay_opacity = state.get("overlay_opacity", 100) / 100
    dim_alpha = max(0, min(0.5, state.get("bg_dim", 25) / 100))
    motion_opacity = max(0, min(0.8, state.get("motion_opacity", 22) / 100))
    heat = state.get("sentiment", {"score": 0, "label": "neutral", "intensity": 0.18})
    heat_score = float(heat.get("score", 0))
    heat_intensity = float(heat.get("intensity", 0.18))
    heat_opacity = max(0, min(0.75, state.get("heatmap_opacity", 28) / 100))
    cloud_w = state.get("cloud_width", 68)
    cloud_h = state.get("cloud_height", 66)
    cloud_x = state.get("cloud_pos_x", theme.get("cloud_x", 45))
    cloud_y = state.get("cloud_pos_y", theme.get("cloud_y", 55))
    cloud_tilt = state.get("cloud_tilt", 0)
    topic_size = state.get("topic_text_size", 100) / 100
    highlight_size = state.get("highlight_text_size", 100) / 100
    countdown_size = state.get("countdown_text_size", 100) / 100
    clock_size = state.get("clock_text_size", 100) / 100
    keyword_size = state.get("keyword_size", 100) / 100
    manual_size = state.get("manual_word_size", 130) / 100
    topic_font = font_stack(state.get("topic_font_family", theme.get("font", "Inter")))
    keyword_font = font_stack(state.get("keyword_font_family", "Inter"))
    highlight_font = font_stack(state.get("highlight_font_family", theme.get("font", "Inter")))
    countdown_font = font_stack(state.get("countdown_font_family", "Inter"))
    topic_weight = int(state.get("topic_font_weight", 850))
    keyword_weight = int(state.get("keyword_font_weight", 760))
    highlight_weight = int(state.get("highlight_font_weight", 900))
    countdown_weight = int(state.get("countdown_font_weight", 850))
    topic_spacing = state.get("topic_letter_spacing", 0) / 100
    highlight_spacing = state.get("highlight_letter_spacing", 0) / 100
    topic_transform = state.get("topic_text_transform", "normal")

    keyword_nodes = []
    manual_set = set(manual_words)
    manual_nodes = []
    for i, word in enumerate(manual_words):
        x, y, rotation = cloud_style_position(cloud_style, f"manual-{word}", i + 100, max(1, len(manual_words) + len(keywords)))
        size = (1.45 - min(i, 5) * 0.08) * manual_size
        delay = (i % 5) * -0.9
        emph = " manual-emphasis" if state.get("manual_words_emphasis", True) else ""
        manual_nodes.append(
            f'<span class="kw manual{emph}" style="--x:{x}%;--y:{y}%;--s:{size:.2f};--r:{rotation:.1f}deg;--d:10.5s;--delay:{delay:.2f}s">{html.escape(word)}</span>'
        )
    for i, item in enumerate(keywords):
        if item["word"] in manual_set:
            continue
        word = html.escape(item["word"])
        size = item.get("size", 1) * keyword_size
        x, y, rotation = cloud_style_position(cloud_style, item["word"], i, len(keywords))
        fresh = " fresh" if item.get("fresh") else ""
        color_class = f" c{i % 6}"
        weight = keyword_weight + ((i % 3) * 80 if state.get("keyword_random_weight") else 0)
        delay = (i % 8) * -0.7
        duration = 9 + (i % 5) * 1.7 / max(0.4, animation_scale)
        keyword_nodes.append(
            f'<span class="kw{fresh}{color_class}" style="--x:{x}%;--y:{y}%;--s:{size:.2f};--r:{rotation:.1f}deg;--w:{weight};--d:{duration:.2f}s;--delay:{delay:.2f}s">{word}</span>'
        )

    map_lines = ""
    if cloud_style == "Network Cloud" or theme["key"] == "map":
        points = [cloud_style_position(cloud_style, item["word"], idx, len(keywords))[:2] for idx, item in enumerate(keywords[:14])]
        line_nodes = []
        for idx, (x, y) in enumerate(points):
            if idx % 2 == 0:
                line_nodes.append(f'<line x1="48" y1="40" x2="{x}" y2="{y}" />')
        map_lines = f'<svg class="map-lines" viewBox="0 0 100 100" preserveAspectRatio="none">{"".join(line_nodes)}</svg>'

    bg_style = ""
    if bg_url:
        bg_style = (
            f"background-image:url('{bg_url}');"
            f"background-size:{state.get('bg_fit','cover')};"
            f"background-position:{state.get('bg_pos_x',50)}% {state.get('bg_pos_y',50)}%;"
            f"transform:scale({state.get('bg_zoom',100)/100:.3f});"
            f"filter:blur({state.get('bg_blur',0)}px) brightness({state.get('bg_brightness',100)}%);"
            f"opacity:{state.get('bg_opacity',100)/100:.2f};"
        )

    hidden = state.get("clear_overlay")
    topic_html = "" if hidden or not state.get("show_topic") else f'<div class="topic">{topic}</div>'
    highlight_html = "" if hidden or not state.get("show_highlight") or not highlight else f'<div class="highlight">{highlight}</div>'
    cloud_html = "" if hidden or not state.get("show_cloud") else f'<div class="cloud cloud-{cloud_slug}">{map_lines}{"".join(keyword_nodes)}{"".join(manual_nodes)}</div>'
    live_since = ""
    if state.get("show_live_since"):
        live_since = f'<span>Live seit {live_since_time}</span>'
    clock_html = "" if hidden or not state.get("show_clock") else f'<div class="live-clock"><b>LIVE {live_duration_text}</b>{live_since}</div>'
    countdown_html = ""
    if not hidden and state.get("show_countdown"):
        countdown_html = (
            f'<div class="countdown">'
            f'<div class="ring" style="--pct:{countdown_pct:.1f}"></div>'
            f'<div><b>{html.escape(state.get("countdown_title") or "")}</b><span>{mins:02d}:{secs:02d}</span></div>'
            f'</div>'
        )

    safe_html = ""
    if safe_zones and not hidden:
        safe_html = '<div class="safe guest">Gäste-Zone</div><div class="safe chat">TikTok Chat-Zone</div>'
    motion_html = ""
    if not hidden and anim_enabled and state.get("show_motion_layers", True) and state.get("motion_effects"):
        effect_nodes = []
        for effect in state.get("motion_effects", []):
            slug = effect.lower()
            if slug == "lagerfeuer":
                effect_nodes.append(
                    '<div class="fireplace">'
                    '<div class="fire-glow"></div>'
                    '<i class="flame f1"></i><i class="flame f2"></i><i class="flame f3"></i><i class="flame f4"></i><i class="flame f5"></i>'
                    '<i class="ember e1"></i><i class="ember e2"></i><i class="ember e3"></i><i class="ember e4"></i>'
                    '<div class="logs"><span></span><span></span></div>'
                    '</div>'
                )
            else:
                effect_nodes.append(f'<i class="fx fx-{html.escape(slug)}"></i>')
        effect_nodes = "".join(effect_nodes)
        motion_html = f'<div class="motion-layer">{effect_nodes}</div>'
    heatmap_html = ""
    if not hidden and state.get("show_heatmap"):
        heat_cls = "positive" if heat_score > 0.18 else "negative" if heat_score < -0.18 else "neutral"
        heatmap_html = f'<div class="heatmap {heat_cls}"><span>Stimmung: {html.escape(str(heat.get("label", "neutral")))}</span></div>'
    video_html = ""
    if not hidden and show_video:
        video_url = readable_url(state.get("video_url", ""))
        youtube_url = youtube_embed_url(video_url)
        if youtube_url:
            video_html = (
                f'<iframe class="stage-video video-embed" src="{youtube_url}" '
                f'style="--vx:{state.get("video_x",50)}%;--vy:{state.get("video_y",54)}%;--vw:{state.get("video_width",70)}%;--vh:{state.get("video_height",40)}%;--vo:{state.get("video_opacity",100)/100:.2f};" '
                f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>'
            )
        else:
            video_html = (
                f'<video class="stage-video" src="{html.escape(video_url)}" '
                f'id="stageVideo" '
                f'controls playsinline {"muted" if state.get("video_muted") else ""} '
                f'style="--vx:{state.get("video_x",50)}%;--vy:{state.get("video_y",54)}%;--vw:{state.get("video_width",70)}%;--vh:{state.get("video_height",40)}%;--vo:{state.get("video_opacity",100)/100:.2f};object-fit:{html.escape(state.get("video_fit","contain"))};"></video>'
                f'<div class="video-controls"><button onclick="stageVideo.currentTime=Math.max(0,stageVideo.currentTime-10)">-10</button><button onclick="stageVideo.paused?stageVideo.play():stageVideo.pause()">Play/Pause</button><button onclick="stageVideo.currentTime=stageVideo.currentTime+10">+10</button></div>'
            )
    website_html = ""
    if not hidden and state.get("show_website") and state.get("website_url"):
        website_url = readable_url(state.get("website_url", ""))
        website_mode = state.get("website_mode", "Auto")
        has_preview = bool(state.get("website_preview_text"))
        use_reader = website_mode == "Website-Vorschau" or (website_mode == "Auto" and has_preview)
        use_link_card = website_mode == "Link-Karte" or website_mode == "Auto"
        host = html.escape(url_host(website_url) or website_url)
        if use_reader:
            website_html = (
                f'<div class="stage-web-card reader" style="--wx:{state.get("website_x",50)}%;--wy:{state.get("website_y",54)}%;--ww:{state.get("website_width",76)}%;--wh:{state.get("website_height",58)}%;">'
                f'<span>Website-Vorschau · {host}</span><b>{html.escape(state.get("website_preview_title") or host)}</b>'
                f'<p>{html.escape(state.get("website_preview_text", ""))}</p><small>{html.escape(website_url)}</small></div>'
            )
        elif use_link_card:
            website_html = (
                f'<div class="stage-web-card" style="--wx:{state.get("website_x",50)}%;--wy:{state.get("website_y",54)}%;--ww:{state.get("website_width",76)}%;--wh:{state.get("website_height",58)}%;">'
                f'<span>Website</span><b>{host}</b><p>Viele normale Websites blockieren Browser-Einbettung. Lade eine Website-Vorschau oder nutze eine offizielle Embed-/Video-URL.</p>'
                f'<small>{html.escape(website_url)}</small></div>'
            )
        else:
            website_html = (
                f'<iframe class="stage-web" src="{html.escape(website_url)}" '
                f'style="--wx:{state.get("website_x",50)}%;--wy:{state.get("website_y",54)}%;--ww:{state.get("website_width",76)}%;--wh:{state.get("website_height",58)}%;" '
                f'allow="clipboard-read; clipboard-write; fullscreen; autoplay" referrerpolicy="no-referrer-when-downgrade"></iframe>'
            )
    ai_html = ""
    if not hidden and state.get("show_ai_card") and state.get("ai_response"):
        ai_text = state.get("ai_response", "")
        if not is_ai_error_text(ai_text):
            ai_html = f'<div class="ai-card"><b>KI-Check</b><p>{html.escape(ai_text)}</p></div>'

    frame_cls = " framed" if state.get("show_overlay_frame", True) else ""
    anim_cls = " animated" if anim_enabled else ""

    return f"""
    <!doctype html>
    <html>
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    :root {{
      --bg:{theme["bg"]}; --panel:{theme["panel"]}; --text:{theme["text"]}; --muted:{theme["muted"]};
      --accent:{theme["accent"]}; --accent2:{theme["accent2"]}; --glow:{theme["glow"]};
      --opacity:{overlay_opacity}; --topicSize:{topic_size:.2f}; --highlightSize:{highlight_size:.2f};
      --countdownSize:{countdown_size:.2f}; --clockSize:{clock_size:.2f};
      --accent3:{theme.get("accent3", theme["accent"])}; --cloudX:{cloud_x}%; --cloudY:{cloud_y}%;
      --cloudW:{cloud_w}%; --cloudH:{cloud_h}%; --cloudTilt:{cloud_tilt}deg;
      --topicFont:{topic_font}; --keywordFont:{keyword_font}; --highlightFont:{highlight_font}; --countdownFont:{countdown_font};
      --topicWeight:{topic_weight}; --keywordWeight:{keyword_weight}; --highlightWeight:{highlight_weight}; --countdownWeight:{countdown_weight};
      --topicSpacing:{topic_spacing:.2f}em; --highlightSpacing:{highlight_spacing:.2f}em; --topicTransform:{topic_transform};
      --dim:{dim_alpha:.2f};
      --motionOpacity:{motion_opacity:.2f}; --motionSpeed:{max(.4, state.get("motion_speed", 55) / 55):.2f};
      --heatOpacity:{heat_opacity:.2f}; --heatIntensity:{heat_intensity:.2f};
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; min-height:100vh; display:grid; place-items:center; background:#050608;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--text); overflow:hidden;
    }}
    .stage-wrap {{ width:{stage_width}; height:100vh; display:grid; place-items:center; padding:12px; }}
    .stage {{
      position:relative; width:100%; max-width:100%; max-height:100%; aspect-ratio:{aspect}; overflow:hidden;
      background: var(--bg); opacity:var(--opacity); border-radius:4px; isolation:isolate;
      box-shadow:0 24px 70px rgba(0,0,0,.42);
    }}
    .stage::before {{
      content:""; position:absolute; inset:0; z-index:-3; pointer-events:none;
      background: transparent;
    }}
    .layout-neon::before {{ background:radial-gradient(circle at 72% 22%, color-mix(in srgb, var(--accent) 28%, transparent), transparent 26%), radial-gradient(circle at 15% 78%, color-mix(in srgb, var(--accent2) 22%, transparent), transparent 30%); }}
    .layout-candy::before {{ background:linear-gradient(135deg, #ff8cc6 0%, #ffb347 35%, #fff176 62%, #55e6d6 100%); opacity:.86; }}
    .layout-bauhaus::before {{ background:linear-gradient(90deg, transparent 0 62%, color-mix(in srgb, var(--accent2) 18%, transparent) 62%), radial-gradient(circle at 84% 18%, var(--accent3) 0 8%, transparent 8%), linear-gradient(135deg, transparent 0 72%, var(--accent) 72%); opacity:.55; }}
    .layout-print::before {{ background:repeating-linear-gradient(0deg, rgba(0,0,0,.025) 0 1px, transparent 1px 7px); }}
    .layout-festival::before {{ background:radial-gradient(circle at 18% 18%, var(--accent) 0 8%, transparent 8%), radial-gradient(circle at 78% 22%, var(--accent2) 0 12%, transparent 12%), radial-gradient(circle at 84% 76%, var(--accent3) 0 10%, transparent 10%); opacity:.32; }}
    .layout-cyber::before {{ background:linear-gradient(120deg, rgba(0,245,255,.16), transparent 35%), repeating-linear-gradient(90deg, rgba(255,255,255,.05) 0 1px, transparent 1px 44px); }}
    .layout-aurora::before {{ background:radial-gradient(ellipse at 20% 25%, rgba(112,255,202,.35), transparent 34%), radial-gradient(ellipse at 85% 35%, rgba(154,140,255,.32), transparent 36%); }}
    .layout-poster::before {{ background:linear-gradient(135deg, rgba(255,42,42,.20) 0 22%, transparent 22% 70%, rgba(255,212,0,.28) 70%), repeating-linear-gradient(0deg, rgba(0,0,0,.035) 0 2px, transparent 2px 8px); }}
    .layout-bloom::before {{ background:radial-gradient(circle at 28% 34%, rgba(124,255,107,.28), transparent 22%), radial-gradient(circle at 72% 58%, rgba(107,214,255,.24), transparent 28%); }}
    .layout-velvet::before {{ background:radial-gradient(circle at 24% 22%, rgba(255,93,168,.32), transparent 28%), radial-gradient(circle at 80% 78%, rgba(255,207,112,.20), transparent 32%); }}
    .stage.framed {{ outline:1px solid color-mix(in srgb, var(--accent) 42%, transparent); }}
    .bg-image {{ position:absolute; inset:-5%; background-repeat:no-repeat; z-index:-4; {bg_style} }}
    .readability {{
      position:absolute; inset:0; z-index:-3;
      background:
        radial-gradient(circle at 24% 28%, color-mix(in srgb, var(--accent) 18%, transparent), transparent 30%),
        linear-gradient(90deg, rgba(0,0,0,var(--dim)), rgba(0,0,0,calc(var(--dim) * .38)) 50%, rgba(0,0,0,calc(var(--dim) * .18))),
        linear-gradient(180deg, rgba(0,0,0,calc(var(--dim) * .2)), rgba(0,0,0,var(--dim)));
    }}
    .layout-clean .readability {{ background:linear-gradient(90deg, rgba(255,255,255,.68), rgba(255,255,255,.24) 65%, rgba(255,255,255,.06)); }}
    .layout-soft .readability {{ background:radial-gradient(circle at 18% 26%, rgba(176,78,111,.16), transparent 28%), linear-gradient(90deg, rgba(255,246,239,.72), rgba(255,246,239,.2) 62%, rgba(255,246,239,.05)); }}
    .grain {{ position:absolute; inset:0; z-index:-2; background-image:linear-gradient(115deg, transparent, rgba(255,255,255,.035), transparent); opacity:.55; }}
    .motion-layer {{ position:absolute; inset:0; z-index:3; opacity:var(--motionOpacity); pointer-events:none; overflow:hidden; mix-blend-mode:screen; }}
    .fx {{ position:absolute; inset:-18%; display:block; }}
    .fx-nebel {{ background:radial-gradient(circle at 18% 42%, rgba(255,255,255,.28), transparent 26%), radial-gradient(circle at 82% 62%, rgba(255,255,255,.18), transparent 32%); filter:blur(18px); animation: drift calc(20s / var(--motionSpeed)) linear infinite; }}
    .fireplace {{ position:absolute; left:50%; bottom:4%; width:62%; height:30%; transform:translateX(-50%); filter:saturate(1.15); }}
    .fire-glow {{ position:absolute; left:50%; bottom:2%; width:86%; height:86%; transform:translateX(-50%); background:radial-gradient(ellipse at 50% 80%, rgba(255,132,28,.75), rgba(255,58,18,.34) 30%, rgba(255,160,50,.12) 52%, transparent 74%); filter:blur(20px); animation:flicker calc(2.6s / var(--motionSpeed)) ease-in-out infinite; }}
    .flame {{ position:absolute; bottom:18%; left:50%; width:16%; height:62%; border-radius:48% 48% 52% 52%; transform-origin:50% 100%; background:linear-gradient(180deg, rgba(255,250,180,.95) 0%, rgba(255,175,38,.95) 36%, rgba(255,69,18,.72) 76%, transparent 100%); filter:blur(.4px); mix-blend-mode:screen; animation: flameDance calc(1.7s / var(--motionSpeed)) ease-in-out infinite; }}
    .flame.f1 {{ left:40%; height:54%; width:15%; animation-delay:-.1s; }}
    .flame.f2 {{ left:49%; height:76%; width:18%; animation-delay:-.45s; }}
    .flame.f3 {{ left:58%; height:48%; width:14%; animation-delay:-.8s; }}
    .flame.f4 {{ left:45%; height:38%; width:11%; background:linear-gradient(180deg, rgba(255,255,220,.9), rgba(255,214,62,.9) 42%, transparent); animation-delay:-1.1s; }}
    .flame.f5 {{ left:54%; height:44%; width:12%; background:linear-gradient(180deg, rgba(255,245,190,.86), rgba(255,109,22,.82) 58%, transparent); animation-delay:-1.35s; }}
    .logs {{ position:absolute; left:50%; bottom:10%; width:44%; height:16%; transform:translateX(-50%); }}
    .logs span {{ position:absolute; left:8%; right:8%; top:36%; height:38%; border-radius:999px; background:linear-gradient(90deg, #32170c, #8b4520 28%, #2a1208 72%, #7a3618); box-shadow:0 0 18px rgba(255,90,22,.38); }}
    .logs span:first-child {{ transform:rotate(11deg); }}
    .logs span:last-child {{ transform:rotate(-10deg); top:42%; }}
    .ember {{ position:absolute; bottom:30%; width:5px; height:5px; border-radius:50%; background:#ffd36c; box-shadow:0 0 14px #ff8b22; animation: emberRise calc(4.8s / var(--motionSpeed)) linear infinite; }}
    .ember.e1 {{ left:42%; animation-delay:-.3s; }} .ember.e2 {{ left:50%; animation-delay:-1.4s; }} .ember.e3 {{ left:58%; animation-delay:-2.6s; }} .ember.e4 {{ left:46%; animation-delay:-3.4s; }}
    .fx-lichtstaub {{ background-image:radial-gradient(circle, rgba(255,255,255,.75) 0 1px, transparent 2px); background-size:72px 72px; animation: drift calc(30s / var(--motionSpeed)) linear infinite reverse; }}
    .fx-scanlines {{ background:repeating-linear-gradient(180deg, rgba(255,255,255,.10) 0 1px, transparent 1px 8px); animation: scan calc(8s / var(--motionSpeed)) linear infinite; }}
    .fx-regen {{ background:repeating-linear-gradient(110deg, transparent 0 16px, rgba(160,200,255,.18) 17px 19px, transparent 20px 34px); animation: rain calc(5s / var(--motionSpeed)) linear infinite; }}
    .fx-funkeln {{ background:radial-gradient(circle at 20% 20%, rgba(255,255,255,.75), transparent 1.5%), radial-gradient(circle at 70% 36%, rgba(255,255,255,.55), transparent 1.2%), radial-gradient(circle at 52% 80%, rgba(255,255,255,.45), transparent 1.4%); animation:flicker calc(4s / var(--motionSpeed)) ease-in-out infinite alternate; }}
    .fx-wellen {{ background:repeating-radial-gradient(ellipse at 50% 60%, transparent 0 8%, rgba(255,255,255,.12) 9%, transparent 10%); animation:pulse calc(10s / var(--motionSpeed)) ease-in-out infinite; }}
    .heatmap {{ position:absolute; inset:0; z-index:2; pointer-events:none; opacity:calc(var(--heatOpacity) * var(--heatIntensity)); mix-blend-mode:screen; }}
    .heatmap.positive {{ background:radial-gradient(circle at 28% 28%, rgba(57,255,146,.55), transparent 32%), radial-gradient(circle at 70% 62%, rgba(80,180,255,.22), transparent 30%); }}
    .heatmap.negative {{ background:radial-gradient(circle at 30% 30%, rgba(255,57,86,.55), transparent 34%), radial-gradient(circle at 65% 68%, rgba(255,176,58,.28), transparent 32%); }}
    .heatmap.neutral {{ background:radial-gradient(circle at 38% 38%, rgba(255,255,255,.20), transparent 34%), radial-gradient(circle at 74% 58%, rgba(120,160,255,.18), transparent 32%); }}
    .heatmap span {{ position:absolute; left:7%; bottom:14%; font-size:12px; font-weight:900; text-transform:uppercase; color:rgba(255,255,255,.72); }}
    .topic {{
      position:absolute; top:7%; left:7%; width:68%; font-weight:850; line-height:.98;
      font-family:var(--topicFont); font-weight:var(--topicWeight);
      font-size:calc(clamp(36px, 7.4vw, 74px) * var(--topicSize)); letter-spacing:var(--topicSpacing); text-transform:var(--topicTransform);
      text-wrap:balance; text-shadow:0 8px 28px rgba(0,0,0,.38);
    }}
    .topic::after {{ content:""; display:block; width:72px; height:3px; margin-top:18px; background:var(--accent); border-radius:3px; box-shadow:0 0 24px var(--glow); }}
    .highlight {{
      position:absolute; left:8%; top:36%; max-width:62%; padding:.18em .32em .26em;
      font-family:var(--highlightFont); font-size:calc(clamp(42px, 9vw, 96px) * var(--highlightSize)); font-weight:var(--highlightWeight); letter-spacing:var(--highlightSpacing); line-height:.9; color:var(--text);
      background:linear-gradient(90deg, color-mix(in srgb, var(--accent) 22%, transparent), transparent);
      border-left:4px solid var(--accent); text-shadow:0 0 30px var(--glow), 0 12px 28px rgba(0,0,0,.32);
    }}
    .cloud {{
      position:absolute; left:var(--cloudX); top:var(--cloudY); width:var(--cloudW); height:var(--cloudH);
      transform:translate(-50%,-50%) rotate(var(--cloudTilt)); transform-origin:center; z-index:2;
    }}
    .kw {{
      position:absolute; left:var(--x); top:var(--y); transform:translate(-50%,-50%) rotate(var(--r)) scale(var(--s));
      font-family:var(--keywordFont); font-weight:var(--w, var(--keywordWeight)); line-height:1; padding:.18rem .38rem; border-radius:7px;
      color:var(--text); background:color-mix(in srgb, var(--panel) 80%, transparent);
      border:1px solid color-mix(in srgb, var(--accent) 22%, transparent);
      box-shadow:0 10px 26px rgba(0,0,0,.18), 0 0 24px var(--glow);
      white-space:nowrap; font-size:clamp(12px, 2.1vw, 24px);
    }}
    .animated .kw {{ animation: floaty var(--d) ease-in-out infinite; animation-delay:var(--delay); }}
    .kw.fresh {{ color:var(--accent); box-shadow:0 0 38px var(--glow), 0 12px 30px rgba(0,0,0,.24); }}
    .cloud-bubble .kw, .cloud-Bubble .kw {{ border-radius:999px; padding:.38rem .62rem; background:color-mix(in srgb, var(--panel) 70%, transparent); backdrop-filter:blur(8px); }}
    .cloud-magazine .kw {{ background:transparent; border-color:transparent; box-shadow:none; font-family:var(--topicFont); }}
    .cloud-network .kw {{ border-radius:999px; background:rgba(13,20,20,.68); }}
    .cloud-color .kw.c0 {{ color:var(--accent); }} .cloud-color .kw.c1 {{ color:var(--accent2); }} .cloud-color .kw.c2 {{ color:var(--accent3); }} .cloud-color .kw.c3 {{ color:#ffffff; }} .cloud-color .kw.c4 {{ color:#ffd166; }} .cloud-color .kw.c5 {{ color:#2dfcff; }}
    .cloud-minimal .kw {{ background:transparent; border:0; box-shadow:none; }}
    .kw.manual {{
      z-index:4; color:var(--accent); background:linear-gradient(90deg, color-mix(in srgb, var(--accent) 24%, var(--panel)), color-mix(in srgb, var(--accent2) 18%, var(--panel)));
      border-color:color-mix(in srgb, var(--accent) 58%, transparent); text-transform:uppercase; letter-spacing:0;
    }}
    .kw.manual-emphasis {{ box-shadow:0 0 46px var(--glow), 0 14px 34px rgba(0,0,0,.32); }}
    .layout-map .kw {{ border-radius:999px; background:rgba(13,20,20,.68); }}
    .map-lines {{ position:absolute; inset:0; opacity:.42; }}
    .map-lines line {{ stroke:var(--accent); stroke-width:.22; vector-effect:non-scaling-stroke; }}
    .countdown {{
      position:absolute; left:7%; bottom:18%; min-width:220px; display:flex; align-items:center; gap:14px;
      padding:14px 16px; border:1px solid color-mix(in srgb, var(--accent) 32%, transparent);
      background:var(--panel); backdrop-filter:blur(14px); border-radius:8px;
    }}
    .countdown b {{ display:block; font-family:var(--countdownFont); font-size:calc(14px * var(--countdownSize)); color:var(--muted); margin-bottom:2px; }}
    .countdown span {{ display:block; font-family:var(--countdownFont); font-size:calc(32px * var(--countdownSize)); font-weight:var(--countdownWeight); line-height:1; }}
    .ring {{
      width:54px; height:54px; border-radius:50%;
      background:conic-gradient(var(--accent) calc(var(--pct) * 1%), rgba(255,255,255,.13) 0);
      position:relative;
    }}
    .ring::after {{ content:""; position:absolute; inset:7px; border-radius:50%; background:var(--bg); }}
    .live-clock {{
      position:absolute; top:7%; right:8%; padding:9px 12px; border-radius:999px;
      display:flex; flex-direction:column; gap:1px; font-family:var(--countdownFont); font-weight:800; font-size:calc(14px * var(--clockSize)); color:var(--text); background:var(--panel); border:1px solid rgba(255,255,255,.13);
    }}
    .live-clock span, .live-clock small {{ font-size:.76em; color:var(--muted); line-height:1.08; }}
    .safe {{ position:absolute; display:grid; place-items:center; color:rgba(255,255,255,.72); border:1px dashed rgba(255,255,255,.38); background:rgba(255,255,255,.06); font-size:13px; font-weight:800; text-transform:uppercase; }}
    .safe.guest {{ top:0; right:0; width:28%; height:100%; }}
    .safe.chat {{ left:0; right:0; bottom:0; height:18%; }}
    .stage-video, .stage-web, .stage-web-card {{
      position:absolute; left:var(--vx, var(--wx)); top:var(--vy, var(--wy));
      width:var(--vw, var(--ww)); height:var(--vh, var(--wh));
      transform:translate(-50%,-50%); z-index:5; border-radius:8px;
      border:1px solid color-mix(in srgb, var(--accent) 38%, transparent);
      box-shadow:0 18px 48px rgba(0,0,0,.42); background:#050608;
    }}
    .stage-video {{ opacity:var(--vo); }}
    .video-controls {{ position:absolute; left:var(--vx,50%); top:calc(var(--vy,54%) + var(--vh,40%) / 2 + 18px); transform:translateX(-50%); z-index:7; display:flex; gap:8px; }}
    .video-controls button {{ border:1px solid color-mix(in srgb, var(--accent) 36%, transparent); background:rgba(0,0,0,.58); color:#fff; border-radius:999px; padding:8px 12px; font-weight:900; cursor:pointer; }}
    .stage-web {{ z-index:4; }}
    .stage-web-card {{
      z-index:4; display:flex; flex-direction:column; justify-content:center; padding:28px;
      background:linear-gradient(135deg, color-mix(in srgb, var(--panel) 92%, #0b0e12), rgba(0,0,0,.72));
      color:var(--text); backdrop-filter:blur(14px);
    }}
    .stage-web-card span {{ color:var(--accent); font-size:13px; font-weight:900; text-transform:uppercase; letter-spacing:.08em; }}
    .stage-web-card b {{ margin-top:10px; font-size:clamp(30px, 5.6vw, 62px); line-height:.98; font-family:var(--topicFont); }}
    .stage-web-card p {{ max-width:88%; color:var(--muted); font-size:clamp(16px, 2.3vw, 24px); line-height:1.25; }}
    .stage-web-card small {{ color:color-mix(in srgb, var(--muted) 76%, transparent); word-break:break-all; font-size:13px; }}
    .stage-web-card.reader {{ justify-content:flex-start; overflow:hidden; }}
    .stage-web-card.reader b {{ font-size:clamp(24px, 3.7vw, 46px); }}
    .stage-web-card.reader p {{ max-width:96%; font-size:clamp(15px, 1.8vw, 21px); line-height:1.38; overflow:hidden; }}
    .ai-card {{
      position:absolute; left:7%; right:34%; bottom:20%; z-index:6; padding:18px 20px;
      border-radius:8px; background:var(--panel); border:1px solid color-mix(in srgb, var(--accent) 34%, transparent);
      backdrop-filter:blur(16px); box-shadow:0 18px 48px rgba(0,0,0,.34);
    }}
    .ai-card b {{ display:block; font-family:var(--countdownFont); color:var(--accent); margin-bottom:8px; }}
    .ai-card p {{ margin:0; white-space:pre-wrap; font-size:clamp(11px, 1.22vw, 18px); line-height:1.24; }}
    @keyframes floaty {{
      0%,100% {{ transform:translate(-50%,-50%) rotate(var(--r)) scale(var(--s)); opacity:.82; }}
      50% {{ transform:translate(calc(-50% + 6px), calc(-50% - 9px)) rotate(var(--r)) scale(calc(var(--s) * 1.025)); opacity:1; }}
    }}
    @keyframes drift {{ from {{ transform:translate3d(-4%,0,0); }} to {{ transform:translate3d(6%,-4%,0); }} }}
    @keyframes flicker {{ 0%,100% {{ opacity:.55; transform:scale(1); }} 50% {{ opacity:1; transform:scale(1.04); }} }}
    @keyframes flameDance {{ 0%,100% {{ transform:translateX(-50%) rotate(-3deg) scaleY(.95); opacity:.82; }} 35% {{ transform:translateX(calc(-50% - 5px)) rotate(4deg) scaleY(1.08); opacity:1; }} 70% {{ transform:translateX(calc(-50% + 4px)) rotate(-6deg) scaleY(.9); opacity:.9; }} }}
    @keyframes emberRise {{ 0% {{ transform:translate3d(0, 0, 0) scale(.7); opacity:0; }} 18% {{ opacity:1; }} 100% {{ transform:translate3d(18px, -180px, 0) scale(.15); opacity:0; }} }}
    @keyframes scan {{ from {{ transform:translateY(-8%); }} to {{ transform:translateY(8%); }} }}
    @keyframes rain {{ from {{ transform:translate3d(-6%,-10%,0); }} to {{ transform:translate3d(6%,10%,0); }} }}
    @keyframes pulse {{ 0%,100% {{ transform:scale(.96); opacity:.5; }} 50% {{ transform:scale(1.05); opacity:1; }} }}
    @media (max-width: 740px) {{
      .stage-wrap {{ padding:4px; }}
      .topic {{ width:74%; font-size:calc(clamp(30px, 12vw, 58px) * var(--topicSize)); }}
      .highlight {{ font-size:calc(clamp(38px, 13vw, 74px) * var(--highlightSize)); }}
      .kw {{ font-size:clamp(11px, 4.2vw, 20px); }}
    }}
    </style>
    </head>
    <body>
      <div class="stage-wrap">
        <main class="stage {frame_cls} {anim_cls} layout-{theme["key"]}">
          <div class="bg-image"></div>
          <div class="readability"></div>
          <div class="grain"></div>
          {heatmap_html}
          {motion_html}
          {clock_html}
          {topic_html}
          {highlight_html}
          {website_html}
          {video_html}
          {cloud_html}
          {countdown_html}
          {ai_html}
          {safe_html}
        </main>
      </div>
    </body>
    </html>
    """


def current_overlay_state() -> dict[str, Any]:
    state = snapshot_scene()
    rt = live_runtime()
    with rt.lock:
        live_started_at = rt.started_at
    live_duration = format_duration(time.time() - live_started_at) if live_started_at else "00:00:00"
    state.update(
        {
            "keywords": st.session_state.keywords,
            "manual_cloud_words": parse_manual_cloud_words(st.session_state.manual_cloud_words_text),
            "active_image_data": active_image_data(),
            "active_image_name": active_image_name(),
            "aspect": st.session_state.aspect,
            "filtered_total": st.session_state.filtered_total,
            "filtered_top": st.session_state.filtered_top,
            "live_started_at": live_started_at,
            "live_duration": live_duration,
            "sentiment": chat_sentiment_state(),
        }
    )
    if st.session_state.auto_highlight and not st.session_state.highlight_word and st.session_state.keywords:
        state["highlight_word"] = st.session_state.keywords[0]["word"]
    return state


def persist_overlay_state() -> None:
    data = current_overlay_state()
    safe = json.dumps(data, ensure_ascii=False)
    RUNTIME_STATE_FILE.write_text(safe, encoding="utf-8")
    try:
        room_state_file(st.session_state.overlay_room_id).write_text(safe, encoding="utf-8")
    except Exception:
        pass


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
    st.components.v1.html(render_overlay_html(state), height=height, scrolling=False)


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
    toggles = [
        ("show_topic", "Thema anzeigen"),
        ("show_cloud", "Keyword-Cloud anzeigen"),
        ("show_highlight", "Highlight-Wort anzeigen"),
        ("show_countdown", "Countdown anzeigen"),
        ("show_clock", "Live-Uhr anzeigen"),
        ("show_live_since", "Live seit Uhrzeit anzeigen"),
        ("show_background", "Hintergrundbild anzeigen"),
        ("show_animations", "Animationen anzeigen"),
        ("show_motion_layers", "Bewegung anzeigen"),
        ("show_heatmap", "Heatmap anzeigen"),
        ("show_safe_zones", "Safe-Zones anzeigen"),
        ("show_overlay_frame", "Overlay-Frame anzeigen"),
        ("minimal_mode", "Minimal Mode"),
    ]
    for key, label in toggles:
        st.toggle(label, key=key)


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
            st.session_state.topic_font_family = theme.get("font", st.session_state.topic_font_family)
            st.session_state.highlight_font_family = theme.get("font", st.session_state.highlight_font_family)
            if not st.session_state.cloud_style_locked:
                st.session_state.cloud_style = theme.get("cloud_style", st.session_state.cloud_style)
                if not st.session_state.user_adjusted_cloud_position:
                    st.session_state.cloud_pos_x = 50
                    st.session_state.cloud_pos_y = 50


def render_image_panel() -> None:
    section("Bild-Manager")
    st.session_state.image_prompt = st.text_area(
        "KI-Hintergrund-Prompt",
        value=st.session_state.image_prompt,
        height=90,
        placeholder="z. B. ruhige abstrakte Studiobühne, goldene Akzente, viel Platz rechts",
    )
    st.toggle("Chat der letzten 5 Minuten in Bildprompt einbeziehen", key="image_prompt_use_chat")
    if st.session_state.get("image_model") not in IMAGE_MODELS:
        st.session_state.image_model = "imagen-4.0-fast-generate-001"
    st.selectbox("Bildmodell", IMAGE_MODELS, key="image_model", format_func=lambda value: IMAGE_MODEL_LABELS.get(value, value))
    st.caption("Imagen-Modelle nutzen `generate_images` und sind laut Google teils Paid-Tier-abhaengig. Falls eins nicht verfuegbar ist, anderes Modell testen.")
    if st.button("KI-Hintergrund erstellen", key="image_generate_ai", use_container_width=True):
        ok, message = generate_background_image(st.session_state.image_prompt, st.session_state.image_prompt_use_chat)
        if ok:
            st.success(message)
        else:
            st.session_state.image_generation_error = message
            st.error(message)
    if st.session_state.image_generation_error:
        st.caption(st.session_state.image_generation_error)
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
        for item in list(st.session_state.images):
            cols = st.columns([1, 1, 1])
            cols[0].image(item["data_url"], use_container_width=True)
            new_title = cols[0].text_input("Titel", value=item.get("title", item.get("name", "Bild")), key=f"img_title_{item['id']}", label_visibility="collapsed")
            item["title"] = new_title
            if cols[1].button(("Aktiv" if item["id"] == st.session_state.active_image_id else "Aktivieren"), key=f"img_on_{item['id']}", use_container_width=True):
                st.session_state.active_image_id = item["id"]
                st.session_state.show_background = True
            if cols[2].button("Löschen", key=f"img_del_{item['id']}", use_container_width=True):
                st.session_state.images = [img for img in st.session_state.images if img["id"] != item["id"]]
                if st.session_state.active_image_id == item["id"]:
                    st.session_state.active_image_id = None
    st.caption("Ausblenden behaelt das aktive Bild in der Galerie. Abwaehlen entfernt nur die aktive Auswahl. Loeschen entfernt ein Bild aus der Session-Galerie.")
    c1, c2, c3 = st.columns(3)
    hide_label = "Bild einblenden" if not st.session_state.show_background else "Bild ausblenden"
    if c1.button(hide_label, key="image_toggle_visibility", use_container_width=True):
        st.session_state.show_background = not st.session_state.show_background
    if c2.button("Aktives Bild abwählen", key="image_remove", use_container_width=True):
        st.session_state.active_image_id = None
    if c3.button("Look optimieren", key="image_auto_optimize", use_container_width=True):
        st.session_state.bg_dim = 34
        st.session_state.bg_blur = 2
        st.session_state.bg_brightness = 112
        st.session_state.bg_opacity = 96
        st.session_state.user_adjusted_image_look = True
        st.session_state.cloud_width = 62
        st.session_state.show_background = True
    if st.button("Bühne aufhellen", key="image_brighten_stage", use_container_width=True):
        brighten_stage()
    st.selectbox("Bild-Fit", ["cover", "contain"], key="bg_fit")
    st.slider("Helligkeit", 20, 140, key="bg_brightness")
    st.session_state.bg_blur = st.slider("Bild-Blur", 0, 18, value=st.session_state.bg_blur, key="image_bg_blur")
    st.session_state.bg_dim = st.slider("Overlay-Dunkelung Bild", 0, 90, value=st.session_state.bg_dim, key="image_bg_dim")
    st.session_state.bg_opacity = st.slider("Bild-Transparenz", 0, 100, value=st.session_state.bg_opacity, key="image_bg_opacity")
    st.session_state.bg_zoom = st.slider("Bild-Zoom", 80, 150, value=st.session_state.bg_zoom, key="image_bg_zoom")
    st.session_state.bg_pos_x = st.slider("Bild-Position X", 0, 100, value=st.session_state.bg_pos_x, key="image_bg_pos_x")
    st.session_state.bg_pos_y = st.slider("Bild-Position Y", 0, 100, value=st.session_state.bg_pos_y, key="image_bg_pos_y")
    st.session_state.user_adjusted_image_look = True


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
        st.session_state.filtered_top = []
        st.session_state.filtered_total = 0
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
        for key in ["show_topic", "show_cloud", "show_highlight", "show_countdown", "show_clock", "show_background"]:
            st.session_state[key] = True
        st.session_state.clear_overlay = False
        st.session_state.minimal_mode = False
    elif action == "hide_all":
        for key in ["show_topic", "show_cloud", "show_highlight", "show_countdown", "show_clock"]:
            st.session_state[key] = False


def render_faders() -> None:
    section("Cloud / Visual Mixing")
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


def render_media_panel() -> None:
    section("Video")
    st.session_state.video_url = st.text_input(
        "Video-URL",
        value=st.session_state.video_url,
        placeholder="https://.../video.mp4 oder direkte WebM/HLS-URL",
    )
    st.caption("Direkte MP4/WebM/HLS-Links laufen im Videoplayer. YouTube-Links werden automatisch als YouTube-Embed eingebettet.")
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
    st.caption("Normale Websites blockieren haeufig iframe-Einbettung. Auto zeigt deshalb stabil eine Vorschau oder Link-Karte; Interaktiver Browser funktioniert nur mit embed-freundlichen Seiten.")
    st.toggle("Website anzeigen", key="show_website")
    if st.session_state.website_url:
        st.session_state.website_url = readable_url(st.session_state.website_url)
    st.selectbox("Website Darstellung", ["Auto", "Interaktiver Browser", "Website-Vorschau", "Link-Karte"], key="website_mode")
    if st.session_state.website_url and is_known_iframe_blocked(st.session_state.website_url):
        st.warning("Diese Domain blockiert sehr wahrscheinlich iframe-Einbettung. Nutze Website-Vorschau, Link-Karte oder eine offizielle Embed-/Video-URL.")
    c1, c2 = st.columns(2)
    if c1.button("Website-Vorschau laden", key="website_preview_load", use_container_width=True):
        ok, title, text = fetch_website_preview(st.session_state.website_url)
        if ok:
            st.session_state.website_preview_title = title
            st.session_state.website_preview_text = text
            st.session_state.website_preview_error = ""
            st.session_state.website_mode = "Website-Vorschau"
            st.session_state.show_website = True
            st.success("Vorschau geladen.")
        else:
            st.session_state.website_preview_error = text
            st.error(text)
    if c2.button("Website-Vorschau löschen", key="website_preview_clear", use_container_width=True):
        st.session_state.website_preview_title = ""
        st.session_state.website_preview_text = ""
        st.session_state.website_preview_error = ""
    if st.session_state.website_preview_error:
        st.caption(st.session_state.website_preview_error)
    if st.session_state.website_preview_text:
        st.text_area("Geladene Vorschau", value=st.session_state.website_preview_text, height=110, disabled=True)
    st.slider("Website Position X", 0, 100, key="website_x")
    st.slider("Website Position Y", 0, 100, key="website_y")
    st.slider("Website Breite", 20, 100, key="website_width")
    st.slider("Website Höhe", 15, 90, key="website_height")


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
    st.selectbox("Thema Font", fonts, key="topic_font_family")
    st.markdown(
        f'<div class="font-preview" style="font-family:{font_stack(st.session_state.topic_font_family)}">Thema Vorschau: Worueber sprechen wir gerade?</div>',
        unsafe_allow_html=True,
    )
    st.slider("Thema Größe", 65, 180, key="topic_text_size")
    st.slider("Thema Gewicht", 300, 950, key="topic_font_weight", step=50)
    st.slider("Thema Letter Spacing", -8, 18, key="topic_letter_spacing")
    st.selectbox("Thema Text Transform", transforms, key="topic_text_transform")
    st.selectbox("Keyword Font", fonts, key="keyword_font_family")
    st.markdown(
        f'<div class="font-preview compact" style="font-family:{font_stack(st.session_state.keyword_font_family)}">Keyword Vorschau: demokratie dialog fakten live</div>',
        unsafe_allow_html=True,
    )
    st.slider("Keyword Basisgröße", 55, 180, key="keyword_size")
    st.slider("Keyword Gewicht", 300, 950, key="keyword_font_weight", step=50)
    st.toggle("Zufällige Keyword-Gewichtung", key="keyword_random_weight")
    st.selectbox("Highlight Font", fonts, key="highlight_font_family")
    st.markdown(
        f'<div class="font-preview" style="font-family:{font_stack(st.session_state.highlight_font_family)}">Highlight Vorschau</div>',
        unsafe_allow_html=True,
    )
    st.slider("Highlight Größe", 60, 190, key="highlight_text_size")
    st.slider("Highlight Gewicht", 300, 950, key="highlight_font_weight", step=50)
    st.slider("Highlight Letter Spacing", -8, 18, key="highlight_letter_spacing")
    st.selectbox("Countdown / Uhr Font", fonts, key="countdown_font_family")
    st.markdown(
        f'<div class="font-preview compact" style="font-family:{font_stack(st.session_state.countdown_font_family)}">LIVE 12:34 · seit 00:12:08</div>',
        unsafe_allow_html=True,
    )
    st.slider("Countdown Größe", 70, 160, key="countdown_text_size")
    st.slider("Live-Uhr Größe", 70, 160, key="clock_text_size")
    st.slider("Countdown / Uhr Gewicht", 300, 950, key="countdown_font_weight", step=50)


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


def render_persistence_panel() -> None:
    section("Persistenz / Backup")
    st.caption("Settings, Szenen und Bildbibliothek werden im Browser localStorage gesichert. Zusaetzlich wird lokal eine JSON-Datei als Fallback geschrieben.")
    st.session_state.overlay_room_id = safe_profile_id(
        st.text_input("Geheime Host-Overlay-ID", value=st.session_state.overlay_room_id, help="Diese ID verbindet Regiepult und Browserquelle. Sie ist nicht an den TikTok-Usernamen gebunden.")
    )
    cloud_url = f"https://ttliveregie.streamlit.app/?overlay=1&room={st.session_state.overlay_room_id}"
    local_url = f"http://localhost:8501/?overlay=1&room={st.session_state.overlay_room_id}"
    render_copyable_url("Streamlit-Cloud Browserquelle", cloud_url, "cloud_overlay")
    render_copyable_url("Lokale Browserquelle", local_url, "local_overlay")
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


def render_control_panel() -> None:
    render_director_header()
    render_quick_actions()
    if st.button("Save Scene", key="quick_save_scene_top", use_container_width=True):
        scene_name = st.session_state.last_active_scene or f"Szene {len(st.session_state.scenes) + 1}"
        st.session_state.scenes[scene_name] = snapshot_scene()
        st.session_state.last_active_scene = scene_name
    with st.expander("1. Verbindung", expanded=True):
        render_section_note("Nur hier startest oder stoppst du den TikTok-Live-Chat. Im Overlay erscheinen keine Usernamen oder Einzelkommentare.")
        render_connection_panel()
    with st.expander("2. Szenen", expanded=False):
        render_section_note("Szenen speichern den kompletten visuellen Zustand. Nutze sie live wie Regie-Cues.")
        render_scene_panel()
    with st.expander("3. Sichtbarkeit", expanded=False):
        render_toggle_panel()
    with st.expander("4. Thema & Highlight", expanded=True):
        render_topic_panel()
        render_highlight_panel()
    with st.expander("5. Countdown & Uhr", expanded=False):
        render_countdown_panel()
    with st.expander("6. Layouts", expanded=False):
        render_section_note("Ein Layout setzt Farbwelt, typografische Grundstimmung und Standard-Cloud. Manuelle Cloud-Einstellungen bleiben fixiert, wenn der Cloud-Lock aktiv ist.")
        render_layout_panel()
    with st.expander("7. Cloud", expanded=False):
        render_section_note("Hier verschiebst du die Tag-Cloud frei auf der Bühne. X/Y reagieren live.")
        render_faders()
    with st.expander("8. Medien / Web", expanded=False):
        render_section_note("Video und Website liegen direkt auf der Bühne. Die eingebetteten Controls sind in der Bühnenfläche klickbar.")
        render_media_panel()
    with st.expander("9. Bewegung / Heatmap", expanded=False):
        render_section_note("Transparente Motion-Layer laufen über dem Hintergrund, damit TikTok eine dezente Bewegung erkennt.")
        render_motion_panel()
    with st.expander("10. Bilder", expanded=False):
        render_section_note("Ausblenden hält das aktive Bild bereit. Löschen entfernt es aus der lokalen Bildbibliothek.")
        render_image_panel()
    with st.expander("11. KI-Check", expanded=False):
        render_ai_panel()
    with st.expander("12. Typografie", expanded=False):
        render_typography_panel()
    with st.expander("13. Safety", expanded=False):
        render_safety_panel()
    with st.expander("14. Persistenz / Backup", expanded=False):
        render_persistence_panel()


# ---------------------------------------------------------------------------
# App-Start
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="TikTok Live Regiepult", page_icon="●", layout="wide", initial_sidebar_state="collapsed")
    init_state()
    load_persisted_state_once()
    st.markdown(css_for_streamlit(), unsafe_allow_html=True)
    overlay_mode = st.query_params.get("overlay", "0") == "1"
    st_autorefresh(interval=2500 if overlay_mode else 4000, key="refresh")
    update_countdown()

    if overlay_mode:
        state = load_overlay_state()
        st.components.v1.html(render_overlay_html(state), height=980, scrolling=False)
        return

    drain_live_comments()
    compute_keywords()
    persist_overlay_state()

    left, right = st.columns([0.28, 0.72], gap="medium")
    with left:
        with st.container(key="control_panel_scroll"):
            render_control_panel()
    with right:
        with st.container(key="stage_panel_fixed"):
            top_cols = st.columns([1, 0.22])
            with top_cols[0]:
                st.markdown("### Bühne / Overlay-Fläche")
            with top_cols[1]:
                st.selectbox("Format", ["9:16", "16:9"], key="aspect", label_visibility="collapsed")
            render_stage(current_overlay_state(), height=900)
    save_persisted_state("auto")


if __name__ == "__main__":
    main()
