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
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import regex
import streamlit as st
from streamlit_autorefresh import st_autorefresh

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
COMMENT_WINDOW_SECONDS = 4 * 60
KEYWORD_REFRESH_SECONDS = 20
MAX_KEYWORDS = 32
MIN_WORD_LENGTH = 3
DEFAULT_ASPECT = "9:16"

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
    },
    "Neon Pulse": {
        "key": "neon",
        "bg": "#090b13",
        "panel": "rgba(13, 16, 30, .76)",
        "text": "#f4f7ff",
        "muted": "#adb8da",
        "accent": "#33f3ff",
        "accent2": "#ff4fd8",
        "glow": "rgba(51,243,255,.32)",
    },
    "Clean Studio": {
        "key": "clean",
        "bg": "#f3f3ef",
        "panel": "rgba(255,255,255,.82)",
        "text": "#1c2023",
        "muted": "#5e666f",
        "accent": "#315f72",
        "accent2": "#b88a4b",
        "glow": "rgba(49,95,114,.18)",
    },
    "System Map": {
        "key": "map",
        "bg": "#101415",
        "panel": "rgba(17, 23, 24, .72)",
        "text": "#eaf1ed",
        "muted": "#9fb0a8",
        "accent": "#7bd7a8",
        "accent2": "#7aa4ff",
        "glow": "rgba(123,215,168,.24)",
    },
    "Feminist Soft Power": {
        "key": "soft",
        "bg": "#eaded5",
        "panel": "rgba(255, 247, 241, .76)",
        "text": "#2f2928",
        "muted": "#776a67",
        "accent": "#b04e6f",
        "accent2": "#383130",
        "glow": "rgba(176,78,111,.20)",
    },
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
        "layout": "Editorial Dark",
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
        "bg_dim": 45,
        "bg_blur": 3,
        "keyword_size": 100,
        "keyword_density": 80,
        "animation_intensity": 55,
        "cloud_width": 68,
        "cloud_height": 66,
        "topic_text_size": 100,
        "highlight_text_size": 100,
        "countdown_text_size": 100,
        "clock_text_size": 100,
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if not st.session_state.scenes:
        st.session_state.scenes = build_default_scenes()


def build_default_scenes() -> dict[str, dict[str, Any]]:
    base = {
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
        "focus_mode": False,
        "clear_overlay": False,
    }
    return {
        "Intro": {**base, "layout": "Editorial Dark", "topic": "Willkommen im Live", "show_countdown": True, "animation_intensity": 35},
        "Diskussion": {**base, "layout": "Clean Studio", "topic": "Diskussion", "cloud_width": 62, "keyword_density": 70},
        "Q&A": {**base, "layout": "Neon Pulse", "topic": "Q&A", "show_countdown": True, "animation_intensity": 68},
        "Deep Dive": {**base, "layout": "System Map", "topic": "Deep Dive", "focus_mode": False, "cloud_width": 74},
        "Fazit": {**base, "layout": "Feminist Soft Power", "topic": "Fazit", "focus_mode": True, "keyword_density": 45},
    }


def snapshot_scene() -> dict[str, Any]:
    keys = [
        "layout", "active_image_id", "show_topic", "show_cloud", "show_highlight", "show_countdown",
        "show_clock", "show_background", "show_animations", "show_safe_zones", "show_overlay_frame",
        "minimal_mode", "topic", "highlight_word", "manual_cloud_words_text", "manual_word_size",
        "manual_words_emphasis", "countdown_title", "countdown_total",
        "countdown_remaining", "countdown_running", "bg_dim", "bg_blur", "bg_opacity", "bg_zoom",
        "bg_pos_x", "bg_pos_y", "bg_fit", "keyword_size", "keyword_density", "animation_intensity",
        "cloud_width", "cloud_height", "topic_text_size", "highlight_text_size", "countdown_text_size",
        "clock_text_size", "overlay_opacity", "transition_speed",
        "focus_mode", "clear_overlay",
    ]
    return {key: st.session_state.get(key) for key in keys}


def apply_scene(scene: dict[str, Any]) -> None:
    for key, value in scene.items():
        if key in st.session_state:
            st.session_state[key] = value
    st.session_state.topic_draft = st.session_state.topic
    st.session_state.highlight_draft = st.session_state.highlight_word


def update_countdown() -> None:
    if st.session_state.countdown_running and st.session_state.countdown_started_at:
        elapsed = time.time() - st.session_state.countdown_started_at
        st.session_state.countdown_remaining = max(0, int(st.session_state.countdown_total - elapsed))
        if st.session_state.countdown_remaining <= 0:
            st.session_state.countdown_running = False


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return "00:00"
    seconds = int(max(0, seconds))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}" if seconds >= 3600 else f"{seconds // 60:02d}:{seconds % 60:02d}"


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
    .stApp { background: #0d0f12; color: #f5f5f2; }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { display: none; }
    .block-container { max-width: 100%; padding: 1rem 1rem 1.4rem; }
    div[data-testid="column"]:first-child {
        background: #14171b;
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 8px;
        padding: .8rem .75rem;
        max-height: calc(100vh - 2rem);
        overflow-y: auto;
    }
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,.16);
        background: #20252b;
        color: #f6f2e9;
        min-height: 2.4rem;
        font-weight: 650;
    }
    div.stButton > button:hover { border-color: #d6b15e; color: #fff; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        background: #0e1115;
        color: #f8f5ee;
        border-radius: 8px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: .25rem; }
    .stTabs [data-baseweb="tab"] { height: 2.2rem; padding: 0 .55rem; }
    .regie-title { font-size: 1.05rem; font-weight: 800; margin: .15rem 0 .65rem; }
    .status-pill {
        padding: .45rem .6rem;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,.12);
        background: rgba(255,255,255,.05);
        font-size: .84rem;
    }
    .layout-grid { display: grid; grid-template-columns: 1fr; gap: .35rem; }
    </style>
    """


def render_overlay_html(state: dict[str, Any]) -> str:
    layout = state.get("layout", "Editorial Dark")
    theme = THEMES.get(layout, THEMES["Editorial Dark"])
    keywords = state.get("keywords", [])
    if state.get("minimal_mode"):
        keywords = keywords[:0]
    if state.get("focus_mode"):
        keywords = keywords[:3]
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
    topic_size = state.get("topic_text_size", 100) / 100
    highlight_size = state.get("highlight_text_size", 100) / 100
    countdown_size = state.get("countdown_text_size", 100) / 100
    clock_size = state.get("clock_text_size", 100) / 100
    keyword_size = state.get("keyword_size", 100) / 100
    manual_size = state.get("manual_word_size", 130) / 100

    keyword_nodes = []
    manual_set = set(manual_words)
    manual_nodes = []
    for i, word in enumerate(manual_words):
        x, y = keyword_position(f"manual-{word}", i + 100)
        size = (1.45 - min(i, 5) * 0.08) * manual_size
        delay = (i % 5) * -0.9
        emph = " manual-emphasis" if state.get("manual_words_emphasis", True) else ""
        manual_nodes.append(
            f'<span class="kw manual{emph}" style="--x:{x}%;--y:{y}%;--s:{size:.2f};--d:10.5s;--delay:{delay:.2f}s">{html.escape(word)}</span>'
        )
    for i, item in enumerate(keywords):
        if item["word"] in manual_set:
            continue
        word = html.escape(item["word"])
        size = item.get("size", 1) * keyword_size
        x = min(80, max(5, item.get("x", 20) * cloud_w / 76))
        y = min(76, max(18, item.get("y", 40) * cloud_h / 72))
        fresh = " fresh" if item.get("fresh") else ""
        delay = (i % 8) * -0.7
        duration = 9 + (i % 5) * 1.7 / max(0.4, animation_scale)
        keyword_nodes.append(
            f'<span class="kw{fresh}" style="--x:{x}%;--y:{y}%;--s:{size:.2f};--d:{duration:.2f}s;--delay:{delay:.2f}s">{word}</span>'
        )

    map_lines = ""
    if theme["key"] == "map" and keywords:
        points = [(item.get("x", 20), item.get("y", 40)) for item in keywords[:12]]
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
            f"filter:blur({state.get('bg_blur',3)}px) brightness({max(20, 120 - state.get('bg_dim',45))}%);"
            f"opacity:{state.get('bg_opacity',100)/100:.2f};"
        )

    hidden = state.get("clear_overlay")
    topic_html = "" if hidden or not state.get("show_topic") else f'<div class="topic">{topic}</div>'
    highlight_html = "" if hidden or not state.get("show_highlight") or not highlight else f'<div class="highlight">{highlight}</div>'
    cloud_html = "" if hidden or not state.get("show_cloud") else f'<div class="cloud">{map_lines}{"".join(keyword_nodes)}{"".join(manual_nodes)}</div>'
    clock_html = "" if hidden or not state.get("show_clock") else f'<div class="live-clock">LIVE {clock}</div>'
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
      font-size:calc(clamp(36px, 7.4vw, 74px) * var(--topicSize)); letter-spacing:0;
      text-wrap:balance; text-shadow:0 8px 28px rgba(0,0,0,.38);
    }}
    .topic::after {{ content:""; display:block; width:72px; height:3px; margin-top:18px; background:var(--accent); border-radius:3px; box-shadow:0 0 24px var(--glow); }}
    .highlight {{
      position:absolute; left:8%; top:36%; max-width:62%; padding:.18em .32em .26em;
      font-size:calc(clamp(42px, 9vw, 96px) * var(--highlightSize)); font-weight:900; line-height:.9; color:var(--text);
      background:linear-gradient(90deg, color-mix(in srgb, var(--accent) 22%, transparent), transparent);
      border-left:4px solid var(--accent); text-shadow:0 0 30px var(--glow), 0 12px 28px rgba(0,0,0,.32);
    }}
    .cloud {{ position:absolute; inset:18% 25% 12% 5%; }}
    .kw {{
      position:absolute; left:var(--x); top:var(--y); transform:translate(-50%,-50%) scale(var(--s));
      font-weight:760; line-height:1; padding:.18rem .38rem; border-radius:7px;
      color:var(--text); background:color-mix(in srgb, var(--panel) 80%, transparent);
      border:1px solid color-mix(in srgb, var(--accent) 22%, transparent);
      box-shadow:0 10px 26px rgba(0,0,0,.18), 0 0 24px var(--glow);
      white-space:nowrap; font-size:clamp(18px, 3.2vw, 34px);
    }}
    .animated .kw {{ animation: floaty var(--d) ease-in-out infinite; animation-delay:var(--delay); }}
    .kw.fresh {{ color:var(--accent); box-shadow:0 0 38px var(--glow), 0 12px 30px rgba(0,0,0,.24); }}
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
    .countdown b {{ display:block; font-size:calc(14px * var(--countdownSize)); color:var(--muted); margin-bottom:2px; }}
    .countdown span {{ display:block; font-size:calc(32px * var(--countdownSize)); font-weight:850; line-height:1; }}
    .ring {{
      width:54px; height:54px; border-radius:50%;
      background:conic-gradient(var(--accent) calc(var(--pct) * 1%), rgba(255,255,255,.13) 0);
      position:relative;
    }}
    .ring::after {{ content:""; position:absolute; inset:7px; border-radius:50%; background:var(--bg); }}
    .live-clock {{
      position:absolute; top:7%; right:8%; padding:9px 12px; border-radius:999px;
      font-weight:800; font-size:calc(14px * var(--clockSize)); color:var(--text); background:var(--panel); border:1px solid rgba(255,255,255,.13);
    }}
    .safe {{ position:absolute; display:grid; place-items:center; color:rgba(255,255,255,.72); border:1px dashed rgba(255,255,255,.38); background:rgba(255,255,255,.06); font-size:13px; font-weight:800; text-transform:uppercase; }}
    .safe.guest {{ top:0; right:0; width:28%; height:100%; }}
    .safe.chat {{ left:0; right:0; bottom:0; height:18%; }}
    @keyframes floaty {{
      0%,100% {{ transform:translate(-50%,-50%) scale(var(--s)); opacity:.82; }}
      50% {{ transform:translate(calc(-50% + 6px), calc(-50% - 9px)) scale(calc(var(--s) * 1.025)); opacity:1; }}
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
    state.update(
        {
            "keywords": st.session_state.keywords,
            "manual_cloud_words": parse_manual_cloud_words(st.session_state.manual_cloud_words_text),
            "active_image_data": active_image_data(),
            "active_image_name": active_image_name(),
            "aspect": st.session_state.aspect,
            "filtered_total": st.session_state.filtered_total,
            "filtered_top": st.session_state.filtered_top,
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
    live_for = format_duration(time.time() - started_at) if started_at and status == "connected" else "00:00"
    st.markdown(f'<div class="status-pill"><b>Status:</b> {html.escape(status)}<br>{html.escape(detail)}<br><b>Live seit:</b> {live_for}</div>', unsafe_allow_html=True)


def render_toggle_panel() -> None:
    section("Sichtbarkeit")
    toggles = [
        ("show_topic", "Thema anzeigen"),
        ("show_cloud", "Keyword-Cloud anzeigen"),
        ("show_highlight", "Highlight-Wort anzeigen"),
        ("show_countdown", "Countdown anzeigen"),
        ("show_clock", "Live-Uhr anzeigen"),
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


def render_image_panel() -> None:
    section("Bild-Manager")
    uploads = st.file_uploader("Hintergrundbilder", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
    if uploads:
        known = {item["id"] for item in st.session_state.images}
        for up in uploads:
            image_id = hashlib.sha1(up.getvalue()).hexdigest()[:12]
            if image_id not in known:
                st.session_state.images.append({"id": image_id, "name": up.name, "data_url": image_to_data_url(up)})
                known.add(image_id)
                if not st.session_state.active_image_id:
                    st.session_state.active_image_id = image_id

    if st.session_state.images:
        for item in list(st.session_state.images):
            cols = st.columns([1, 1, 1])
            cols[0].image(item["data_url"], use_container_width=True)
            if cols[1].button(("Aktiv" if item["id"] == st.session_state.active_image_id else "Aktivieren"), key=f"img_on_{item['id']}", use_container_width=True):
                st.session_state.active_image_id = item["id"]
            if cols[2].button("Löschen", key=f"img_del_{item['id']}", use_container_width=True):
                st.session_state.images = [img for img in st.session_state.images if img["id"] != item["id"]]
                if st.session_state.active_image_id == item["id"]:
                    st.session_state.active_image_id = st.session_state.images[0]["id"] if st.session_state.images else None
    c1, c2 = st.columns(2)
    if c1.button("Bild entfernen", key="image_remove", use_container_width=True):
        st.session_state.active_image_id = None
    if c2.button("Layout automatisch optimieren", key="image_auto_optimize", use_container_width=True):
        st.session_state.bg_dim = 58
        st.session_state.bg_blur = 5
        st.session_state.bg_opacity = 88
        st.session_state.cloud_width = 62
    st.selectbox("Bild-Fit", ["cover", "contain"], key="bg_fit")
    brightness = st.slider("Helligkeit", 20, 120, value=120 - st.session_state.bg_dim, key="image_brightness")
    st.session_state.bg_dim = 120 - brightness
    st.session_state.bg_blur = st.slider("Bild-Blur", 0, 18, value=st.session_state.bg_blur, key="image_bg_blur")
    st.session_state.bg_dim = st.slider("Overlay-Dunkelung Bild", 0, 90, value=st.session_state.bg_dim, key="image_bg_dim")
    st.session_state.bg_opacity = st.slider("Bild-Transparenz", 0, 100, value=st.session_state.bg_opacity, key="image_bg_opacity")
    st.session_state.bg_zoom = st.slider("Bild-Zoom", 80, 150, value=st.session_state.bg_zoom, key="image_bg_zoom")
    st.session_state.bg_pos_x = st.slider("Bild-Position X", 0, 100, value=st.session_state.bg_pos_x, key="image_bg_pos_x")
    st.session_state.bg_pos_y = st.slider("Bild-Position Y", 0, 100, value=st.session_state.bg_pos_y, key="image_bg_pos_y")


def render_scene_panel() -> None:
    section("Szenen")
    name = st.text_input("Neue Szene", value="Meine Szene")
    if st.button("Aktuelle Einstellungen als Szene speichern", key="scene_save", use_container_width=True):
        if name.strip():
            st.session_state.scenes[name.strip()] = snapshot_scene()
    for scene_name, scene in st.session_state.scenes.items():
        if st.button(scene_name, key=f"scene_{scene_name}", use_container_width=True):
            apply_scene(scene)


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
    section("Visual Mixing")
    st.slider("Hintergrund-Dunkelung", 0, 90, key="bg_dim")
    st.slider("Blur", 0, 18, key="bg_blur")
    st.slider("Keyword-Größe", 55, 160, key="keyword_size")
    st.slider("Keyword-Dichte", 10, 100, key="keyword_density")
    st.slider("Animationsintensität", 0, 100, key="animation_intensity")
    st.slider("Cloud-Breite", 35, 90, key="cloud_width")
    st.slider("Cloud-Höhe", 35, 90, key="cloud_height")
    st.slider("Textgröße Thema", 65, 145, key="topic_text_size")
    st.slider("Textgröße Highlight", 60, 160, key="highlight_text_size")
    st.slider("Textgröße Manuelle Wörter", 80, 210, key="manual_word_size")
    st.slider("Textgröße Countdown", 70, 150, key="countdown_text_size")
    st.slider("Textgröße Live-Uhr", 70, 150, key="clock_text_size")
    st.slider("Overlay-Transparenz", 20, 100, key="overlay_opacity")
    st.slider("Übergangsgeschwindigkeit", 10, 100, key="transition_speed")


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


def render_control_panel() -> None:
    st.markdown('<div class="regie-title">Live-Regiepult</div>', unsafe_allow_html=True)
    tabs = st.tabs(["Live", "Look", "Szenen", "Safety"])
    with tabs[0]:
        render_connection_panel()
        render_toggle_panel()
        render_topic_panel()
        render_highlight_panel()
        render_countdown_panel()
        render_quick_actions()
    with tabs[1]:
        render_layout_panel()
        render_image_panel()
        render_faders()
    with tabs[2]:
        render_scene_panel()
    with tabs[3]:
        render_safety_panel()


# ---------------------------------------------------------------------------
# App-Start
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="TikTok Live Regiepult", page_icon="●", layout="wide", initial_sidebar_state="collapsed")
    init_state()
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
        render_control_panel()
    with right:
        top_cols = st.columns([1, 0.22])
        with top_cols[0]:
            st.markdown("### Bühne / Overlay-Fläche")
        with top_cols[1]:
            st.selectbox("Format", ["9:16", "16:9"], key="aspect", label_visibility="collapsed")
        render_stage(current_overlay_state(), height=900)


if __name__ == "__main__":
    main()
