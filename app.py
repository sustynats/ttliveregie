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
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import regex
import streamlit as st
from streamlit_autorefresh import st_autorefresh

try:
    from streamlit_js_eval import get_local_storage, streamlit_js_eval
except Exception:
    get_local_storage = None
    streamlit_js_eval = None

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
SERVER_STATE_FILE = APP_DIR / ".ttliveregie_state.json"
LOCAL_STORAGE_KEY = "ttliveregie_state_v2"
COMMENT_WINDOW_SECONDS = 4 * 60
KEYWORD_REFRESH_SECONDS = 20
MAX_KEYWORDS = 32
MIN_WORD_LENGTH = 3
DEFAULT_ASPECT = "9:16"

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
        "cloud_x": 42,
        "cloud_y": 54,
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
        "cloud_y": 52,
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
        "cloud_y": 57,
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
        "cloud_x": 52,
        "cloud_y": 55,
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
        "cloud_x": 45,
        "cloud_y": 57,
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
        "cloud_x": 49,
        "cloud_y": 52,
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
        "cloud_y": 55,
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
        "cloud_x": 54,
        "cloud_y": 55,
    },
}

LEGACY_LAYOUT_MAP = {
    "Neon Pulse": "Neon Pop",
    "Clean Studio": "Bauhaus Clean",
    "Feminist Soft Power": "Soft Power",
}

PRESET_SCENES = ["Intro", "Diskussion", "Q&A", "Deep Dive", "Fazit"]


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
    defaults = {
        "target_input": "",
        "topic": "Worueber sprechen wir gerade?",
        "topic_draft": "Worueber sprechen wir gerade?",
        "highlight_word": "",
        "highlight_draft": "",
        "auto_highlight": True,
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
        "layout": "Editorial Dark",
        "cloud_style": "Magazine Cloud",
        "cloud_style_locked": False,
        "aspect": DEFAULT_ASPECT,
        "show_topic": True,
        "show_cloud": True,
        "show_highlight": True,
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
        "bg_dim": 35,
        "bg_blur": 0,
        "bg_brightness": 100,
        "keyword_size": 100,
        "keyword_density": 80,
        "animation_intensity": 55,
        "cloud_pos_x": 45,
        "cloud_pos_y": 55,
        "cloud_width": 68,
        "cloud_height": 66,
        "cloud_tilt": 0,
        "topic_text_size": 100,
        "highlight_text_size": 100,
        "countdown_text_size": 100,
        "clock_text_size": 100,
        "topic_font_family": "Playfair Display",
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.layout in LEGACY_LAYOUT_MAP:
        st.session_state.layout = LEGACY_LAYOUT_MAP[st.session_state.layout]
    if "bg_brightness" not in st.session_state:
        st.session_state.bg_brightness = max(20, 120 - st.session_state.get("bg_dim", 35))
    if not st.session_state.scenes:
        st.session_state.scenes = build_default_scenes()


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
        "Diskussion": {**base, "layout": "Bauhaus Clean", "cloud_style": "Classic Word Cloud", "topic": "Diskussion", "cloud_width": 62, "keyword_density": 70},
        "Q&A": {**base, "layout": "Neon Pop", "cloud_style": "Color Burst", "topic": "Q&A", "show_countdown": True, "animation_intensity": 68},
        "Deep Dive": {**base, "layout": "System Map", "cloud_style": "Network Cloud", "topic": "Deep Dive", "focus_mode": False, "cloud_width": 74},
        "Fazit": {**base, "layout": "Soft Power", "cloud_style": "Minimal Cloud", "topic": "Fazit", "focus_mode": True, "keyword_density": 45},
    }


def snapshot_scene() -> dict[str, Any]:
    keys = [
        "layout", "cloud_style", "cloud_style_locked", "active_image_id", "show_topic", "show_cloud", "show_highlight", "show_countdown",
        "show_clock", "show_background", "show_animations", "show_safe_zones", "show_overlay_frame",
        "show_live_since",
        "minimal_mode", "topic", "highlight_word", "manual_cloud_words_text", "manual_word_size",
        "manual_words_emphasis", "countdown_title", "countdown_total",
        "countdown_remaining", "countdown_running", "bg_dim", "bg_blur", "bg_brightness", "bg_opacity", "bg_zoom",
        "bg_pos_x", "bg_pos_y", "bg_fit", "keyword_size", "keyword_density", "animation_intensity",
        "cloud_pos_x", "cloud_pos_y", "cloud_width", "cloud_height", "cloud_tilt", "topic_text_size",
        "highlight_text_size", "countdown_text_size", "clock_text_size", "topic_font_family", "topic_font_weight",
        "topic_letter_spacing", "topic_text_transform", "keyword_font_family", "keyword_font_weight",
        "keyword_random_weight", "highlight_font_family", "highlight_font_weight", "highlight_letter_spacing",
        "countdown_font_family", "countdown_font_weight", "overlay_opacity", "transition_speed",
        "focus_mode", "clear_overlay",
    ]
    return {key: st.session_state.get(key) for key in keys}


def apply_scene(scene: dict[str, Any]) -> None:
    for key, value in scene.items():
        if key in st.session_state:
            st.session_state[key] = value
    if st.session_state.layout in LEGACY_LAYOUT_MAP:
        st.session_state.layout = LEGACY_LAYOUT_MAP[st.session_state.layout]
    st.session_state.topic_draft = st.session_state.topic
    st.session_state.highlight_draft = st.session_state.highlight_word


def persistent_payload() -> dict[str, Any]:
    payload = snapshot_scene()
    payload.update(
        {
            "version": 2,
            "browser_id": st.session_state.browser_id or str(uuid.uuid4()),
            "images": st.session_state.images,
            "active_image_id": st.session_state.active_image_id,
            "scenes": st.session_state.scenes,
            "custom_blacklist_text": st.session_state.custom_blacklist_text,
            "custom_whitelist_text": st.session_state.custom_whitelist_text,
            "last_active_scene": st.session_state.last_active_scene,
        }
    )
    return payload


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
    }
    for key, value in payload.items():
        if key in allowed:
            st.session_state[key] = value
    if st.session_state.layout in LEGACY_LAYOUT_MAP:
        st.session_state.layout = LEGACY_LAYOUT_MAP[st.session_state.layout]
    st.session_state.topic_draft = st.session_state.topic
    st.session_state.highlight_draft = st.session_state.highlight_word


def load_persisted_state_once() -> None:
    if st.session_state.persist_loaded:
        return
    loaded = None
    if get_local_storage is not None:
        try:
            raw = get_local_storage(LOCAL_STORAGE_KEY, component_key="persist_load")
            if raw is None and not SERVER_STATE_FILE.exists():
                if not st.session_state.browser_id:
                    st.session_state.browser_id = str(uuid.uuid4())
                return
            if raw:
                loaded = json.loads(raw)
        except Exception:
            loaded = None
    if loaded is None and SERVER_STATE_FILE.exists():
        try:
            loaded = json.loads(SERVER_STATE_FILE.read_text(encoding="utf-8"))
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
        SERVER_STATE_FILE.write_text(data, encoding="utf-8")
    except Exception:
        pass
    if streamlit_js_eval is not None:
        digest = hashlib.sha1(data.encode("utf-8")).hexdigest()[:12]
        js = f"localStorage.setItem({json.dumps(LOCAL_STORAGE_KEY)}, {json.dumps(data)})"
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
        SERVER_STATE_FILE.unlink(missing_ok=True)
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
    .stApp { background: #0d0f12; color: #f7f2ea; height: 100vh; overflow: hidden; }
    html, body, [data-testid="stAppViewContainer"], .main {
        height: 100vh;
        overflow: hidden;
    }
    [data-testid="stHeader"] { background: transparent; height: 0; min-height: 0; }
    [data-testid="stSidebar"] { display: none; }
    .block-container {
        max-width: 100%;
        height: 100vh;
        max-height: 100vh;
        padding: 1rem;
        overflow: hidden;
    }
    .block-container div[data-testid="stHorizontalBlock"]:has(.st-key-control_panel_scroll) {
        height: calc(100vh - 2rem);
        max-height: calc(100vh - 2rem);
        min-height: 0;
        align-items: flex-start;
    }
    .st-key-control_panel_scroll {
        background: #12161a;
        border: 1px solid rgba(255,255,255,.16);
        border-radius: 8px;
        padding: .8rem .75rem;
        height: calc(100vh - 2rem);
        max-height: calc(100vh - 2rem);
        overflow-y: auto !important;
        overflow-x: hidden !important;
        color: #f7f2ea;
    }
    .st-key-control_panel_scroll > div,
    .st-key-control_panel_scroll [data-testid="stVerticalBlock"] {
        min-height: 0 !important;
        max-height: none !important;
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
        height: calc(100vh - 2rem);
        max-height: calc(100vh - 2rem);
        align-self: flex-start;
        overflow: hidden;
    }
    .st-key-stage_panel_fixed iframe {
        max-height: calc(100vh - 5.5rem);
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
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: #8f98a4 !important;
    }
    .stTabs [data-baseweb="tab-list"] { gap: .25rem; }
    .stTabs [data-baseweb="tab"] { height: 2.2rem; padding: 0 .55rem; }
    .regie-title { font-size: 1.05rem; font-weight: 800; margin: .15rem 0 .65rem; }
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
    clock = time.strftime("%H:%M")
    remaining = int(state.get("countdown_remaining") or 0)
    total = max(1, int(state.get("countdown_total") or 1))
    countdown_pct = max(0, min(100, remaining / total * 100))
    mins, secs = divmod(remaining, 60)
    safe_zones = state.get("show_safe_zones")
    bg_url = state.get("active_image_data") if state.get("show_background") else ""
    aspect = "9 / 16" if state.get("aspect", DEFAULT_ASPECT) == "9:16" else "16 / 9"
    stage_width = "min(74vh, 100%)" if state.get("aspect", DEFAULT_ASPECT) == "9:16" else "100%"
    animation_scale = state.get("animation_intensity", 55) / 100
    anim_enabled = state.get("show_animations", True)
    overlay_opacity = state.get("overlay_opacity", 100) / 100
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
    if state.get("show_live_since") and state.get("live_started_at"):
        live_since = f'<span>seit {time.strftime("%H:%M:%S", time.localtime(state.get("live_started_at")))}</span>'
    clock_html = "" if hidden or not state.get("show_clock") else f'<div class="live-clock"><b>LIVE {clock}</b>{live_since}</div>'
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
    .stage.framed {{ outline:1px solid color-mix(in srgb, var(--accent) 42%, transparent); }}
    .bg-image {{ position:absolute; inset:-5%; background-repeat:no-repeat; z-index:-4; {bg_style} }}
    .readability {{
      position:absolute; inset:0; z-index:-3;
      background:
        radial-gradient(circle at 24% 28%, color-mix(in srgb, var(--accent) 18%, transparent), transparent 30%),
        linear-gradient(90deg, rgba(0,0,0,.62), rgba(0,0,0,.20) 50%, rgba(0,0,0,.08)),
        linear-gradient(180deg, rgba(0,0,0,.12), rgba(0,0,0,.42));
    }}
    .layout-clean .readability {{ background:linear-gradient(90deg, rgba(255,255,255,.68), rgba(255,255,255,.24) 65%, rgba(255,255,255,.06)); }}
    .layout-soft .readability {{ background:radial-gradient(circle at 18% 26%, rgba(176,78,111,.16), transparent 28%), linear-gradient(90deg, rgba(255,246,239,.72), rgba(255,246,239,.2) 62%, rgba(255,246,239,.05)); }}
    .grain {{ position:absolute; inset:0; z-index:-2; background-image:linear-gradient(115deg, transparent, rgba(255,255,255,.035), transparent); opacity:.55; }}
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
      white-space:nowrap; font-size:clamp(18px, 3.2vw, 34px);
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
    .live-clock span {{ font-size:.76em; color:var(--muted); }}
    .safe {{ position:absolute; display:grid; place-items:center; color:rgba(255,255,255,.72); border:1px dashed rgba(255,255,255,.38); background:rgba(255,255,255,.06); font-size:13px; font-weight:800; text-transform:uppercase; }}
    .safe.guest {{ top:0; right:0; width:28%; height:100%; }}
    .safe.chat {{ left:0; right:0; bottom:0; height:18%; }}
    @keyframes floaty {{
      0%,100% {{ transform:translate(-50%,-50%) rotate(var(--r)) scale(var(--s)); opacity:.82; }}
      50% {{ transform:translate(calc(-50% + 6px), calc(-50% - 9px)) rotate(var(--r)) scale(calc(var(--s) * 1.025)); opacity:1; }}
    }}
    @media (max-width: 740px) {{
      .stage-wrap {{ padding:4px; }}
      .topic {{ width:74%; font-size:calc(clamp(30px, 12vw, 58px) * var(--topicSize)); }}
      .highlight {{ font-size:calc(clamp(38px, 13vw, 74px) * var(--highlightSize)); }}
      .kw {{ font-size:clamp(16px, 6vw, 28px); }}
    }}
    </style>
    </head>
    <body>
      <div class="stage-wrap">
        <main class="stage {frame_cls} {anim_cls} layout-{theme["key"]}">
          <div class="bg-image"></div>
          <div class="readability"></div>
          <div class="grain"></div>
          {clock_html}
          {topic_html}
          {highlight_html}
          {cloud_html}
          {countdown_html}
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
        }
    )
    if st.session_state.auto_highlight and not st.session_state.highlight_word and st.session_state.keywords:
        state["highlight_word"] = st.session_state.keywords[0]["word"]
    return state


def persist_overlay_state() -> None:
    data = current_overlay_state()
    safe = json.dumps(data, ensure_ascii=False)
    RUNTIME_STATE_FILE.write_text(safe, encoding="utf-8")


def load_overlay_state() -> dict[str, Any]:
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
    st.markdown(f'<div class="status-pill"><b>Status:</b> {html.escape(status)}<br>{html.escape(detail)}<br><b>Laufzeit:</b> {live_for}<br><b>Live seit:</b> {live_clock_since}</div>', unsafe_allow_html=True)


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
    for name, theme in THEMES.items():
        active = "✓ " if st.session_state.layout == name else ""
        if st.button(f"{active}{name}", key=f"layout_{theme['key']}", use_container_width=True):
            st.session_state.layout = name
            st.session_state.topic_font_family = theme.get("font", st.session_state.topic_font_family)
            st.session_state.highlight_font_family = theme.get("font", st.session_state.highlight_font_family)
            if not st.session_state.cloud_style_locked:
                st.session_state.cloud_style = theme.get("cloud_style", st.session_state.cloud_style)
                st.session_state.cloud_pos_x = theme.get("cloud_x", st.session_state.cloud_pos_x)
                st.session_state.cloud_pos_y = theme.get("cloud_y", st.session_state.cloud_pos_y)


def render_image_panel() -> None:
    section("Bild-Manager")
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
        st.session_state.bg_dim = 58
        st.session_state.bg_blur = 5
        st.session_state.bg_brightness = 100
        st.session_state.bg_opacity = 88
        st.session_state.cloud_width = 62
        st.session_state.show_background = True
    st.selectbox("Bild-Fit", ["cover", "contain"], key="bg_fit")
    st.slider("Helligkeit", 20, 140, key="bg_brightness")
    st.session_state.bg_blur = st.slider("Bild-Blur", 0, 18, value=st.session_state.bg_blur, key="image_bg_blur")
    st.session_state.bg_dim = st.slider("Overlay-Dunkelung Bild", 0, 90, value=st.session_state.bg_dim, key="image_bg_dim")
    st.session_state.bg_opacity = st.slider("Bild-Transparenz", 0, 100, value=st.session_state.bg_opacity, key="image_bg_opacity")
    st.session_state.bg_zoom = st.slider("Bild-Zoom", 80, 150, value=st.session_state.bg_zoom, key="image_bg_zoom")
    st.session_state.bg_pos_x = st.slider("Bild-Position X", 0, 100, value=st.session_state.bg_pos_x, key="image_bg_pos_x")
    st.session_state.bg_pos_y = st.slider("Bild-Position Y", 0, 100, value=st.session_state.bg_pos_y, key="image_bg_pos_y")


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
    section("Quick Actions")
    actions = [
        ("Freeze Keywords", "freeze"),
        ("Reset Keywords", "reset"),
        ("Auto-Highlight", "auto_highlight_action"),
        ("Focus Mode", "focus"),
        ("Minimal Mode", "minimal"),
        ("Clear Overlay", "clear"),
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
    st.slider("Cloud-Breite", 35, 90, key="cloud_width")
    st.slider("Cloud-Höhe", 35, 90, key="cloud_height")
    st.slider("Cloud Rotation / Tilt", -10, 10, key="cloud_tilt")
    st.slider("Overlay-Transparenz", 20, 100, key="overlay_opacity")
    st.slider("Übergangsgeschwindigkeit", 10, 100, key="transition_speed")


def render_typography_panel() -> None:
    section("Typografie")
    fonts = list(FONT_PRESETS)
    transforms = ["normal", "uppercase"]
    st.selectbox("Thema Font", fonts, key="topic_font_family")
    st.slider("Thema Größe", 65, 180, key="topic_text_size")
    st.slider("Thema Gewicht", 300, 950, key="topic_font_weight", step=50)
    st.slider("Thema Letter Spacing", -8, 18, key="topic_letter_spacing")
    st.selectbox("Thema Text Transform", transforms, key="topic_text_transform")
    st.selectbox("Keyword Font", fonts, key="keyword_font_family")
    st.slider("Keyword Basisgröße", 55, 180, key="keyword_size")
    st.slider("Keyword Gewicht", 300, 950, key="keyword_font_weight", step=50)
    st.toggle("Zufällige Keyword-Gewichtung", key="keyword_random_weight")
    st.selectbox("Highlight Font", fonts, key="highlight_font_family")
    st.slider("Highlight Größe", 60, 190, key="highlight_text_size")
    st.slider("Highlight Gewicht", 300, 950, key="highlight_font_weight", step=50)
    st.slider("Highlight Letter Spacing", -8, 18, key="highlight_letter_spacing")
    st.selectbox("Countdown / Uhr Font", fonts, key="countdown_font_family")
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
    st.markdown('<div class="regie-title">Live-Regiepult</div>', unsafe_allow_html=True)
    render_quick_actions()
    if st.button("Save Scene", key="quick_save_scene_top", use_container_width=True):
        scene_name = st.session_state.last_active_scene or f"Szene {len(st.session_state.scenes) + 1}"
        st.session_state.scenes[scene_name] = snapshot_scene()
        st.session_state.last_active_scene = scene_name
    tabs = st.tabs(["Live", "Szenen", "Look", "Cloud", "Text", "Bilder", "Safety", "Backup"])
    with tabs[0]:
        render_connection_panel()
        render_toggle_panel()
        render_topic_panel()
        render_highlight_panel()
        render_countdown_panel()
    with tabs[1]:
        render_scene_panel()
    with tabs[2]:
        render_layout_panel()
    with tabs[3]:
        render_faders()
    with tabs[4]:
        render_typography_panel()
    with tabs[5]:
        render_image_panel()
    with tabs[6]:
        render_safety_panel()
    with tabs[7]:
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
        with st.container(height=820, key="control_panel_scroll"):
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
