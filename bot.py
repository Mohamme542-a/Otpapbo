"""
Telegram PDF/Image OCR & Dictionary Translation Bot - Single File / Pydroid Edition

هذا الملف مستقل من ناحية الكود: لا يحتاج إلى ملف .env أو config خارجي.
عدّل BOT_TOKEN و ADMIN_ID_TEXT في قسم الإعدادات أسفل الاستيرادات مباشرة.

للتثبيت داخل Pydroid استخدم Pip من القائمة أو نفّذ:
python-telegram-bot==22.5
PyMuPDF==1.26.4
Pillow==11.3.0
pytesseract==0.3.13
langdetect==1.0.9

ملاحظة: pytesseract هو واجهة بايثون، ويحتاج وجود برنامج Tesseract نفسه.
إذا لم يكن Tesseract مثبتاً في جهاز Pydroid فسيعمل البوت في استقبال الملفات،
لكن OCR لن يعمل حتى تثبّت محرك Tesseract وتضع مساره في TESSERACT_CMD.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import re
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF
import pytesseract
from langdetect import LangDetectException, detect
from PIL import Image, ImageOps
from telegram import BotCommand, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ========================= إعدادات البوت =========================
# ضع التوكن بين علامتي الاقتباس، مثال: BOT_TOKEN = "123456:ABC..."
# اتركه فارغاً أثناء التجربة ثم عدّله بنفسك.
BOT_TOKEN = "8893399262:AAE7_7dHce4j4_Zp710opf0-qLjTIN0CDuc"

# ضع رقم حساب الأدمن هنا، مثال: ADMIN_ID_TEXT = "123456789"
# اتركه فارغاً إذا لم ترد تفعيل أوامر الإدارة.
ADMIN_ID_TEXT = "8877567829"
ADMIN_ID = int(ADMIN_ID_TEXT) if ADMIN_ID_TEXT.strip().isdigit() else 0

# يحفظ البرنامج قاعدة البيانات والنتائج بجوار ملف bot.py، وهذا مناسب لـ Pydroid.
DATA_DIR = Path(__file__).resolve().parent / "bot_data"
DB_PATH = DATA_DIR / "bot.db"

# إعدادات اختيارية يمكن تعديلها من هنا.
MAX_FILE_MB = 20
MAX_SEND_IMAGES = 500
OCR_TIMEOUT_SECONDS = 120

# إذا كان ملف tesseract موجوداً في مسار خاص على هاتفك، ضعه هنا، مثال:
# TESSERACT_CMD = "/data/data/ru.iiec.pydroid3/files/usr/bin/tesseract"
TESSERACT_CMD = ""
if TESSERACT_CMD.strip():
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD.strip()

LANGUAGE_ALIASES = {
    "ar": "ara",
    "arabic": "ara",
    "العربية": "ara",
    "en": "eng",
    "english": "eng",
    "الانجليزية": "eng",
    "fr": "fra",
    "french": "fra",
    "de": "deu",
    "german": "deu",
    "es": "spa",
    "spanish": "spa",
    "ru": "rus",
    "russian": "rus",
    "it": "ita",
    "italian": "ita",
    "pt": "por",
    "tr": "tur",
}
SUPPORTED_OCR_CODES = {"ara", "eng", "fra", "deu", "spa", "rus", "ita", "por", "tur"}
SUPPORTED_TRANSLATION_CODES = {"ar", "en", "fr", "de", "es", "ru", "it", "pt", "tr", "auto"}

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger("pdf_ocr_bot")
PROCESS_SEMAPHORE = asyncio.Semaphore(2)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for directory in (DATA_DIR, DATA_DIR / "downloads", DATA_DIR / "results"):
        directory.mkdir(parents=True, exist_ok=True)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def safe_filename(name: str, fallback: str = "file") -> str:
    name = Path(name or fallback).name
    name = re.sub(r"[^\w.\- ]+", "_", name, flags=re.UNICODE).strip()
    return name[:120] or fallback


def user_label(update: Update) -> str:
    user = update.effective_user
    return f"{user.full_name} ({user.id})" if user else "unknown"


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self.connect() as con:
            con.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT DEFAULT '',
                    first_name TEXT DEFAULT '',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    is_banned INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS settings (
                    user_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    PRIMARY KEY (user_id, key)
                );
                CREATE TABLE IF NOT EXISTS dictionary_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    target_text TEXT NOT NULL,
                    source_normalized TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(source_lang, target_lang, source_normalized)
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
                """
            )

    def touch_user(self, user_id: int, username: str = "", first_name: str = "") -> None:
        now = utc_now()
        with self.connect() as con:
            con.execute(
                """INSERT INTO users(user_id, username, first_name, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                   username=excluded.username, first_name=excluded.first_name, last_seen=excluded.last_seen""",
                (user_id, username, first_name, now, now),
            )

    def log(self, user_id: int, action: str, details: str = "") -> None:
        with self.connect() as con:
            con.execute(
                "INSERT INTO usage_logs(user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
                (user_id, action, details[:500], utc_now()),
            )

    def get_setting(self, user_id: int, key: str, default: str = "") -> str:
        with self.connect() as con:
            row = con.execute(
                "SELECT value FROM settings WHERE user_id=? AND key=?", (user_id, key)
            ).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, user_id: int, key: str, value: str) -> None:
        with self.connect() as con:
            con.execute(
                """INSERT INTO settings(user_id, key, value) VALUES (?, ?, ?)
                   ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value""",
                (user_id, key, value),
            )

    def get_settings(self, user_id: int) -> dict[str, str]:
        defaults = {"ocr_lang": "ara+eng", "source_lang": "auto", "target_lang": "ar", "mode": "both"}
        with self.connect() as con:
            rows = con.execute("SELECT key, value FROM settings WHERE user_id=?", (user_id,)).fetchall()
        result = defaults.copy()
        result.update({row["key"]: row["value"] for row in rows})
        return result

    def is_banned(self, user_id: int) -> bool:
        with self.connect() as con:
            row = con.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["is_banned"])

    def set_banned(self, user_id: int, value: bool) -> None:
        with self.connect() as con:
            con.execute("UPDATE users SET is_banned=? WHERE user_id=?", (int(value), user_id))

    def add_dictionary_entry(self, source_lang: str, target_lang: str, source: str, target: str, created_by: int) -> None:
        source = source.strip()
        target = target.strip()
        if not source or not target:
            raise ValueError("لا يمكن حفظ زوج ترجمة فارغ")
        with self.connect() as con:
            con.execute(
                """INSERT INTO dictionary_entries
                   (source_lang, target_lang, source_text, target_text, source_normalized, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(source_lang, target_lang, source_normalized) DO UPDATE SET
                   source_text=excluded.source_text, target_text=excluded.target_text,
                   created_by=excluded.created_by, created_at=excluded.created_at""",
                (source_lang, target_lang, source, target, normalize_text(source), created_by, utc_now()),
            )

    def delete_dictionary_entry(self, source_lang: str, target_lang: str, source: str) -> bool:
        with self.connect() as con:
            cursor = con.execute(
                "DELETE FROM dictionary_entries WHERE source_lang=? AND target_lang=? AND source_normalized=?",
                (source_lang, target_lang, normalize_text(source)),
            )
        return cursor.rowcount > 0

    def dictionary_entries(self, source_lang: str, target_lang: str) -> list[sqlite3.Row]:
        with self.connect() as con:
            if source_lang == "auto":
                return con.execute(
                    """SELECT source_text, target_text, source_normalized, source_lang
                       FROM dictionary_entries WHERE target_lang=? ORDER BY LENGTH(source_text) DESC""",
                    (target_lang,),
                ).fetchall()
            return con.execute(
                """SELECT source_text, target_text, source_normalized, source_lang
                   FROM dictionary_entries WHERE source_lang=? AND target_lang=?
                   ORDER BY LENGTH(source_text) DESC""",
                (source_lang, target_lang),
            ).fetchall()

    def dictionary_count(self, source_lang: str = "", target_lang: str = "") -> int:
        query = "SELECT COUNT(*) AS n FROM dictionary_entries WHERE 1=1"
        args: list[str] = []
        if source_lang:
            query += " AND source_lang=?"
            args.append(source_lang)
        if target_lang:
            query += " AND target_lang=?"
            args.append(target_lang)
        with self.connect() as con:
            return int(con.execute(query, args).fetchone()["n"])

    def export_dictionary(self, source_lang: str, target_lang: str) -> list[sqlite3.Row]:
        with self.connect() as con:
            return con.execute(
                """SELECT source_lang, target_lang, source_text, target_text
                   FROM dictionary_entries WHERE source_lang=? AND target_lang=?
                   ORDER BY source_text COLLATE NOCASE""",
                (source_lang, target_lang),
            ).fetchall()

    def add_feedback(self, user_id: int, message: str) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT INTO feedback(user_id, message, created_at) VALUES (?, ?, ?)",
                (user_id, message[:4000], utc_now()),
            )

    def user_ids(self) -> list[int]:
        with self.connect() as con:
            return [int(row["user_id"]) for row in con.execute("SELECT user_id FROM users WHERE is_banned=0")]

    def overall_stats(self) -> dict[str, int]:
        with self.connect() as con:
            users = con.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            active = con.execute("SELECT COUNT(*) AS n FROM users WHERE is_banned=0").fetchone()["n"]
            logs = con.execute("SELECT COUNT(*) AS n FROM usage_logs").fetchone()["n"]
            feedback = con.execute("SELECT COUNT(*) AS n FROM feedback").fetchone()["n"]
            entries = con.execute("SELECT COUNT(*) AS n FROM dictionary_entries").fetchone()["n"]
        return {"users": int(users), "active": int(active), "logs": int(logs), "feedback": int(feedback), "entries": int(entries)}


ensure_dirs()
DB = Database(DB_PATH)


@dataclass
class ProcessingResult:
    source_type: str
    source_name: str
    page_images: list[Path]
    embedded_images: list[Path]
    text: str
    page_count: int = 0
    embedded_count: int = 0


def normalized_ocr_lang(value: str) -> str:
    value = value.strip().lower()
    if value in {"auto", "default"}:
        return "ara+eng"
    pieces = re.split(r"[+,\s]+", value)
    codes: list[str] = []
    for piece in pieces:
        code = LANGUAGE_ALIASES.get(piece, piece)
        if code in SUPPORTED_OCR_CODES and code not in codes:
            codes.append(code)
    return "+".join(codes) if codes else "ara+eng"


def valid_translation_code(value: str) -> bool:
    return value.strip().lower() in SUPPORTED_TRANSLATION_CODES


def detect_language(text: str) -> str:
    if len(re.sub(r"\s+", "", text)) < 20:
        return "غير كافٍ للكشف"
    try:
        return detect(text)
    except LangDetectException:
        return "غير معروف"


def ocr_image(path: Path, lang: str) -> str:
    lang = normalized_ocr_lang(lang)
    with Image.open(path) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        max_side = max(image.size)
        if max_side > 3200:
            scale = 3200 / max_side
            image = image.resize((int(image.width * scale), int(image.height * scale)))
        try:
            return pytesseract.image_to_string(
                image,
                lang=lang,
                config="--oem 3 --psm 3",
                timeout=OCR_TIMEOUT_SECONDS,
            ).strip()
        except (pytesseract.TesseractError, RuntimeError) as exc:
            LOGGER.warning("OCR failed for %s: %s", path, exc)
            return ""


def process_image_file(input_path: Path, output_dir: Path, ocr_lang: str) -> ProcessingResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    copy_path = output_dir / f"image_{safe_filename(input_path.name, 'image')}"
    shutil.copy2(input_path, copy_path)
    text = ocr_image(copy_path, ocr_lang)
    return ProcessingResult(
        source_type="image",
        source_name=input_path.name,
        page_images=[copy_path],
        embedded_images=[],
        text=text,
        page_count=1,
        embedded_count=0,
    )


def process_pdf_file(input_path: Path, output_dir: Path, ocr_lang: str) -> ProcessingResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    page_images: list[Path] = []
    embedded_images: list[Path] = []
    ocr_sections: list[str] = []
    native_sections: list[str] = []

    with fitz.open(input_path) as document:
        for page_index, page in enumerate(document, start=1):
            native_text = page.get_text("text").strip()
            if native_text:
                native_sections.append(f"--- النص الأصلي من الصفحة {page_index} ---\n{native_text}")

            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            page_path = output_dir / f"page_{page_index:04d}.png"
            pixmap.save(str(page_path))
            page_images.append(page_path)
            page_text = ocr_image(page_path, ocr_lang)
            if page_text:
                ocr_sections.append(f"--- OCR الصفحة {page_index} ---\n{page_text}")

            seen_xrefs: set[int] = set()
            for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                xref = int(image_info[0])
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    extracted = document.extract_image(xref)
                    extension = extracted.get("ext", "png")
                    image_path = output_dir / f"page_{page_index:04d}_embedded_{image_index:03d}.{extension}"
                    image_path.write_bytes(extracted["image"])
                    embedded_images.append(image_path)
                    embedded_text = ocr_image(image_path, ocr_lang)
                    if embedded_text:
                        ocr_sections.append(
                            f"--- OCR الصورة المضمنة {page_index}/{image_index} ---\\n{embedded_text}"
                        )
                except Exception as exc:
                    LOGGER.warning("Could not extract PDF image xref=%s: %s", xref, exc)

    sections = []
    if native_sections:
        sections.append("\n\n".join(native_sections))
    if ocr_sections:
        sections.append("\n\n".join(ocr_sections))
    combined = "\n\n".join(sections).strip()
    return ProcessingResult(
        source_type="pdf",
        source_name=input_path.name,
        page_images=page_images,
        embedded_images=embedded_images,
        text=combined or "لم يتم العثور على نص قابل للاستخراج.",
        page_count=len(page_images),
        embedded_count=len(embedded_images),
    )


def parse_dictionary_lines(raw_text: str) -> list[tuple[str, str]]:
    raw_text = raw_text.lstrip("\ufeff")
    try:
        payload = json.loads(raw_text)
        pairs: list[tuple[str, str]] = []
        if isinstance(payload, dict):
            pairs = [(str(key), str(value)) for key, value in payload.items()]
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and "source" in item and "target" in item:
                    pairs.append((str(item["source"]), str(item["target"])))
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    pairs.append((str(item[0]), str(item[1])))
        if pairs:
            return [(a.strip(), b.strip()) for a, b in pairs if a.strip() and b.strip()]
    except json.JSONDecodeError:
        pass

    pairs = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        separator = None
        for candidate in ("\t", "=>", "→", "|", "\u2192"):
            if candidate in line:
                separator = candidate
                break
        if separator:
            left, right = line.split(separator, 1)
        elif line.count(",") == 1:
            left, right = line.split(",", 1)
        elif ":" in line and line.count(":") == 1:
            left, right = line.split(":", 1)
        else:
            continue
        left, right = left.strip(), right.strip()
        if left and right:
            pairs.append((left, right))
    return pairs


def parse_language_pair_and_text(argument: str, default_source: str, default_target: str) -> tuple[str, str, str]:
    parts = argument.strip().split(maxsplit=2)
    source, target, text = default_source, default_target, argument.strip()
    if len(parts) >= 3 and valid_translation_code(parts[0]) and valid_translation_code(parts[1]):
        source, target, text = parts[0].lower(), parts[1].lower(), parts[2]
    return source, target, text.strip()


def dictionary_translate(text: str, source_lang: str, target_lang: str) -> tuple[str, int]:
    entries = DB.dictionary_entries(source_lang, target_lang)
    if not entries:
        return text, 0
    result = text
    replacements = 0
    for entry in entries:
        source = str(entry["source_text"])
        target = str(entry["target_text"])
        if not source:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)", re.IGNORECASE | re.UNICODE)
        result, count = pattern.subn(lambda _match: target, result)
        if count == 0 and normalize_text(result) == normalize_text(source):
            result = target
            count = 1
        replacements += count
    return result, replacements


def split_text(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n", 0, limit)
        if cut < 500:
            cut = remaining.rfind(" ", 0, limit)
        if cut < 500:
            cut = limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    return chunks


async def reply_chunks(update: Update, text: str) -> None:
    message = update.effective_message
    if not message:
        return
    for chunk in split_text(text):
        await message.reply_text(chunk)


async def send_media(update: Update, path: Path, caption: str = "") -> None:
    message = update.effective_message
    if not message:
        return
    size_mb = path.stat().st_size / (1024 * 1024)
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and size_mb <= 9.5:
        with path.open("rb") as handle:
            await message.reply_photo(photo=handle, caption=caption[:1024] if caption else None)
    else:
        with path.open("rb") as handle:
            await message.reply_document(document=handle, caption=caption[:1024] if caption else None)


def last_result_path(user_id: int) -> Path | None:
    value = DB.get_setting(user_id, "last_result_path", "")
    path = Path(value) if value else None
    return path if path and path.exists() else None


def save_last_result(user_id: int, text: str, source_name: str) -> Path:
    filename = f"{user_id}_{int(time.time())}_{safe_filename(source_name, 'result')}.txt"
    path = DATA_DIR / "results" / filename
    path.write_text(text, encoding="utf-8")
    DB.set_setting(user_id, "last_result_path", str(path))
    return path


def get_last_text(user_id: int) -> str:
    path = last_result_path(user_id)
    return path.read_text(encoding="utf-8") if path else ""


def is_admin(update: Update) -> bool:
    return bool(ADMIN_ID and update.effective_user and update.effective_user.id == ADMIN_ID)


def ensure_user(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    DB.touch_user(user.id, user.username or "", user.first_name or "")
    if DB.is_banned(user.id) and not is_admin(update):
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    await update.effective_message.reply_text(
        "أهلاً بك في بوت PDF OCR.\n\n"
        "أرسل ملف PDF أو صورة وسأستخرج الصفحات والصور والنص منها.\n"
        "بعد المعالجة استخدم /translate لترجمة النص بالقاموس الذي يضيفه الأدمن.\n\n"
        "اكتب /help لعرض جميع الوظائف."
    )
    DB.log(update.effective_user.id, "start")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    await update.effective_message.reply_text(
        "الوظائف المتاحة:\n\n"
        "1) إرسال PDF: استخراج كل صفحة كصورة، واستخراج الصور المضمنة، وتشغيل OCR.\n"
        "2) إرسال صورة: استخراج النص منها مباشرة.\n"
        "3) /translate [المصدر] [الهدف] [النص] — ترجمة قاموسية. اكتب last لترجمة آخر نتيجة.\n"
        "4) /setlang ara+eng — لغة OCR؛ المتاح ara, eng, fra, deu, spa, rus, ita, por, tur.\n"
        "5) /settarget ar — اللغة الهدف الافتراضية.\n"
        "6) /mode both|images|text — تحديد ما يرسله البوت.\n"
        "7) /summary — إحصاءات آخر نص.\n"
        "8) /search كلمة — البحث في آخر نص مستخرج.\n"
        "9) /last — إعادة إرسال آخر ملف نصي.\n"
        "10) /settings — عرض إعداداتك.\n"
        "11) /feedback اقتراحك — إرسال ملاحظة للأدمن.\n"
        "12) /privacy — معلومات الخصوصية.\n"
        "13) /id — عرض رقم حسابك.\n\n"
        "أوامر الأدمن بعد ضبط ADMIN_ID:\n"
        "/teach [المصدر] [الهدف] المصدر => الترجمة\n"
        "/delword [المصدر] [الهدف] الكلمة\n"
        "/dictstats و /exportdict [المصدر] [الهدف]\n"
        "رفع ملف TXT/CSV/JSON مع caption مثل: /importdict en ar\n"
        "/stats و /broadcast و /ban و /unban"
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        DB.touch_user(update.effective_user.id, update.effective_user.username or "", update.effective_user.first_name or "")
        await update.effective_message.reply_text(f"معرّف حسابك: {update.effective_user.id}")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    settings = DB.get_settings(update.effective_user.id)
    await update.effective_message.reply_text(
        "إعداداتك الحالية:\n"
        f"OCR: {settings['ocr_lang']}\n"
        f"المصدر: {settings['source_lang']}\n"
        f"الهدف: {settings['target_lang']}\n"
        f"الوضع: {settings['mode']}"
    )


async def setlang_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    value = " ".join(context.args).strip()
    normalized = normalized_ocr_lang(value)
    if not value or normalized == "ara+eng" and value.lower() not in {"ara+eng", "eng+ara", "ar+en", "en+ar", "auto"}:
        await update.effective_message.reply_text("استخدم مثلاً: /setlang ara+eng أو /setlang ara")
        return
    DB.set_setting(update.effective_user.id, "ocr_lang", normalized)
    await update.effective_message.reply_text(f"تم ضبط لغة OCR إلى: {normalized}")


async def settarget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    value = " ".join(context.args).strip().lower()
    if not valid_translation_code(value) or value == "auto":
        await update.effective_message.reply_text("استخدم رمزاً مثل ar أو en أو fr أو de أو es")
        return
    DB.set_setting(update.effective_user.id, "target_lang", value)
    await update.effective_message.reply_text(f"تم ضبط اللغة الهدف إلى: {value}")


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    value = (context.args[0].lower() if context.args else "").strip()
    if value not in {"both", "images", "text"}:
        await update.effective_message.reply_text("الاستخدام: /mode both أو /mode images أو /mode text")
        return
    DB.set_setting(update.effective_user.id, "mode", value)
    await update.effective_message.reply_text(f"تم ضبط الوضع إلى: {value}")


async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    user_id = update.effective_user.id
    settings = DB.get_settings(user_id)
    argument = " ".join(context.args).strip()
    if argument.lower() == "last":
        text = get_last_text(user_id)
        source, target = settings["source_lang"], settings["target_lang"]
    else:
        source, target, text = parse_language_pair_and_text(argument, settings["source_lang"], settings["target_lang"])
    if not text:
        await update.effective_message.reply_text("استخدم: /translate en ar Hello world أو /translate last")
        return
    if not valid_translation_code(source) or not valid_translation_code(target) or target == "auto":
        await update.effective_message.reply_text("رموز اللغات غير صحيحة. مثال: /translate en ar النص")
        return
    translated, replacements = dictionary_translate(text, source, target)
    await reply_chunks(update, f"الترجمة القاموسية ({source} → {target}):\n{translated}\n\nعدد المطابقات: {replacements}")
    DB.log(user_id, "translate", f"{source}->{target}")


async def teach_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("هذا الأمر متاح للأدمن فقط.")
        return
    argument = " ".join(context.args).strip()
    parts = argument.split(maxsplit=2)
    source_lang, target_lang = "en", "ar"
    pair_text = argument
    if len(parts) >= 3 and valid_translation_code(parts[0]) and valid_translation_code(parts[1]):
        source_lang, target_lang, pair_text = parts[0].lower(), parts[1].lower(), parts[2]
    pair = re.split(r"\s*(?:=>|→|\|)\s*", pair_text, maxsplit=1)
    if len(pair) != 2:
        await update.effective_message.reply_text("الصيغة: /teach en ar hello => مرحباً")
        return
    DB.add_dictionary_entry(source_lang, target_lang, pair[0], pair[1], update.effective_user.id)
    await update.effective_message.reply_text(f"تم تعليم البوت: {pair[0].strip()} → {pair[1].strip()}")


async def delword_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("هذا الأمر متاح للأدمن فقط.")
        return
    parts = " ".join(context.args).strip().split(maxsplit=2)
    if len(parts) != 3 or not valid_translation_code(parts[0]) or not valid_translation_code(parts[1]):
        await update.effective_message.reply_text("الصيغة: /delword en ar hello")
        return
    deleted = DB.delete_dictionary_entry(parts[0].lower(), parts[1].lower(), parts[2])
    await update.effective_message.reply_text("تم الحذف." if deleted else "لم أجد هذه الكلمة.")


async def dictstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("هذا الأمر متاح للأدمن فقط.")
        return
    count = DB.dictionary_count()
    await update.effective_message.reply_text(f"عدد أزواج الترجمة المحفوظة: {count}")


async def importdict_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("هذا الأمر متاح للأدمن فقط.")
        return
    await update.effective_message.reply_text(
        "ارفع ملف TXT أو CSV أو JSON مع كتابة caption بالشكل:\n"
        "/importdict en ar\n\n"
        "كل سطر في TXT يكون: source<TAB>target أو source => target.\n"
        "ويمكن أن يكون JSON كقاموس {\"hello\": \"مرحباً\"} أو قائمة source/target."
    )


async def import_dictionary_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("هذا الملف مخصص لاستيراد قاموس الأدمن فقط.")
        return
    document = update.effective_message.document
    caption = (update.effective_message.caption or "").strip()
    match = re.search(r"/importdict(?:@\w+)?\s+(\w+)\s+(\w+)", caption, flags=re.IGNORECASE)
    if not match:
        await update.effective_message.reply_text("أرفق caption مثل: /importdict en ar")
        return
    source_lang, target_lang = match.group(1).lower(), match.group(2).lower()
    if not valid_translation_code(source_lang) or not valid_translation_code(target_lang) or source_lang == "auto" or target_lang == "auto":
        await update.effective_message.reply_text("رموز اللغات غير صحيحة.")
        return
    if document.file_size and document.file_size > MAX_FILE_MB * 1024 * 1024:
        await update.effective_message.reply_text(f"الملف أكبر من الحد المسموح {MAX_FILE_MB} MB.")
        return
    temporary = Path(tempfile.mkdtemp(prefix="dict_"))
    try:
        input_path = temporary / safe_filename(document.file_name or "dictionary.txt")
        tg_file = await context.bot.get_file(document.file_id)
        await tg_file.download_to_drive(custom_path=str(input_path))
        raw = input_path.read_text(encoding="utf-8-sig", errors="replace")
        pairs = parse_dictionary_lines(raw)
        for source, target in pairs:
            DB.add_dictionary_entry(source_lang, target_lang, source, target, update.effective_user.id)
        await update.effective_message.reply_text(
            f"تم استيراد {len(pairs)} زوج ترجمة إلى {source_lang} → {target_lang}."
        )
        DB.log(update.effective_user.id, "import_dictionary", f"{source_lang}->{target_lang}:{len(pairs)}")
    except Exception as exc:
        LOGGER.exception("Dictionary import failed")
        await update.effective_message.reply_text(f"تعذر استيراد القاموس: {exc}")
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


async def exportdict_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("هذا الأمر متاح للأدمن فقط.")
        return
    parts = " ".join(context.args).strip().split()
    if len(parts) != 2 or not valid_translation_code(parts[0]) or not valid_translation_code(parts[1]):
        await update.effective_message.reply_text("الصيغة: /exportdict en ar")
        return
    rows = DB.export_dictionary(parts[0].lower(), parts[1].lower())
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(["source", "target"])
    for row in rows:
        writer.writerow([row["source_text"], row["target_text"]])
    data = io.BytesIO(output.getvalue().encode("utf-8"))
    data.name = f"dictionary_{parts[0]}_{parts[1]}.tsv"
    await update.effective_message.reply_document(document=data, caption=f"عدد السجلات: {len(rows)}")


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    text = get_last_text(update.effective_user.id)
    if not text:
        await update.effective_message.reply_text("لا توجد نتيجة محفوظة بعد.")
        return
    words = re.findall(r"\b\w+\b", text, flags=re.UNICODE)
    unique = len({normalize_text(word) for word in words})
    await update.effective_message.reply_text(
        f"ملخص آخر نتيجة:\nالأحرف: {len(text)}\nالكلمات: {len(words)}\nالكلمات المختلفة: {unique}\n"
        f"الأسطر: {text.count(chr(10)) + 1}\nاللغة المتوقعة: {detect_language(text)}"
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    query = " ".join(context.args).strip()
    text = get_last_text(update.effective_user.id)
    if not query or not text:
        await update.effective_message.reply_text("استخدم /search كلمة بعد استخراج ملف.")
        return
    matches = [line for line in text.splitlines() if query.casefold() in line.casefold()]
    if matches:
        await reply_chunks(update, "الأسطر المطابقة:\n" + "\n".join(matches[:100]))
    else:
        await update.effective_message.reply_text("لم أجد تطابقاً في آخر نتيجة.")


async def last_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    path = last_result_path(update.effective_user.id)
    if not path:
        await update.effective_message.reply_text("لا توجد نتيجة محفوظة بعد.")
        return
    with path.open("rb") as handle:
        await update.effective_message.reply_document(document=handle, caption="آخر نتيجة OCR محفوظة")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    path = last_result_path(update.effective_user.id)
    if path:
        path.unlink(missing_ok=True)
    DB.set_setting(update.effective_user.id, "last_result_path", "")
    await update.effective_message.reply_text("تم حذف آخر نتيجة محفوظة من مساحة البوت.")


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    message = " ".join(context.args).strip()
    if not message:
        await update.effective_message.reply_text("استخدم /feedback ثم اكتب اقتراحك أو مشكلتك.")
        return
    DB.add_feedback(update.effective_user.id, message)
    await update.effective_message.reply_text("تم تسجيل ملاحظتك، شكراً لك.")
    if ADMIN_ID:
        try:
            await context.bot.send_message(ADMIN_ID, f"ملاحظة من {user_label(update)}:\n{message}")
        except Exception:
            LOGGER.exception("Could not forward feedback")


async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    await update.effective_message.reply_text(
        "تُعالج الملفات مؤقتاً لاستخراج الصور والنص. تُحفظ آخر نتيجة نصية فقط لتفعيل /last و /translate last، "
        "وتُحفظ إعداداتك والقاموس في قاعدة بيانات البوت. استخدم /clear لحذف آخر نتيجة. "
        "لا تضع مستندات حساسة إذا لم تكن قد أعددت تخزيناً خاصاً وآمناً على الخادم."
    )


async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("هذا الأمر متاح للأدمن فقط.")
        return
    stats = DB.overall_stats()
    await update.effective_message.reply_text(
        "إحصاءات البوت:\n"
        f"المستخدمون: {stats['users']}\nالمستخدمون غير المحظورين: {stats['active']}\n"
        f"سجلات الاستخدام: {stats['logs']}\nملاحظات المستخدمين: {stats['feedback']}\n"
        f"أزواج القاموس: {stats['entries']}"
    )


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("هذا الأمر متاح للأدمن فقط.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("الصيغة: /ban user_id")
        return
    DB.set_banned(int(context.args[0]), True)
    await update.effective_message.reply_text("تم الحظر.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("هذا الأمر متاح للأدمن فقط.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("الصيغة: /unban user_id")
        return
    DB.set_banned(int(context.args[0]), False)
    await update.effective_message.reply_text("تم إلغاء الحظر.")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("هذا الأمر متاح للأدمن فقط.")
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("الصيغة: /broadcast نص الرسالة")
        return
    sent = 0
    failed = 0
    for user_id in DB.user_ids():
        try:
            await context.bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await update.effective_message.reply_text(f"اكتمل الإرسال. نجح: {sent}، فشل: {failed}.")


async def process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, input_path: Path, is_pdf: bool) -> None:
    user_id = update.effective_user.id
    settings = DB.get_settings(user_id)
    temporary = Path(tempfile.mkdtemp(prefix="ocr_"))
    status = await update.effective_message.reply_text("بدأت المعالجة. قد يستغرق OCR وقتاً حسب عدد الصفحات.")
    try:
        async with PROCESS_SEMAPHORE:
            if is_pdf:
                result = await asyncio.to_thread(process_pdf_file, input_path, temporary, settings["ocr_lang"])
            else:
                result = await asyncio.to_thread(process_image_file, input_path, temporary, settings["ocr_lang"])

        text_path = save_last_result(user_id, result.text, result.source_name)
        DB.log(user_id, "process_pdf" if is_pdf else "process_image", result.source_name)
        try:
            await status.edit_text(
                f"اكتملت المعالجة. الصفحات: {result.page_count}، الصور المضمنة: {result.embedded_count}."
            )
        except Exception:
            pass

        mode = settings["mode"]
        if mode in {"both", "images"}:
            all_images = result.page_images + result.embedded_images
            if len(all_images) > MAX_SEND_IMAGES:
                await update.effective_message.reply_text(
                    f"عدد الصور {len(all_images)}، وسيتم إرسال أول {MAX_SEND_IMAGES}. "
                    "يمكن رفع MAX_SEND_IMAGES في إعدادات الاستضافة لإرسال عدد أكبر."
                )
            for index, image_path in enumerate(all_images[:MAX_SEND_IMAGES], start=1):
                caption = f"الصورة {index} من {min(len(all_images), MAX_SEND_IMAGES)}"
                await send_media(update, image_path, caption)

        if mode in {"both", "text"}:
            await reply_chunks(update, "النص المستخرج:\n\n" + result.text)
            with text_path.open("rb") as handle:
                await update.effective_message.reply_document(document=handle, caption="ملف النص المستخرج")

        await update.effective_message.reply_text(
            "لترجمة النص المحفوظ بالقاموس استخدم: /translate last\n"
            "ولتغيير ما يرسل البوت استخدم: /mode both أو /mode images أو /mode text"
        )
    except Exception as exc:
        LOGGER.exception("File processing failed for %s", input_path)
        try:
            await status.edit_text(f"حدث خطأ أثناء المعالجة: {exc}")
        except Exception:
            await update.effective_message.reply_text(f"حدث خطأ أثناء المعالجة: {exc}")
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    document = update.effective_message.document
    caption = (update.effective_message.caption or "").strip()
    if is_admin(update) and caption.lower().startswith("/importdict"):
        await import_dictionary_document(update, context)
        return
    file_name = document.file_name or "uploaded_file"
    suffix = Path(file_name).suffix.lower()
    mime = (document.mime_type or "").lower()
    is_pdf = suffix == ".pdf" or mime == "application/pdf"
    is_image = suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"} or mime.startswith("image/")
    if not (is_pdf or is_image):
        await update.effective_message.reply_text("أرسل PDF أو صورة بصيغة JPG/PNG/WEBP/TIFF.")
        return
    if document.file_size and document.file_size > MAX_FILE_MB * 1024 * 1024:
        await update.effective_message.reply_text(f"الحد الأقصى للملف هو {MAX_FILE_MB} MB.")
        return
    temporary = Path(tempfile.mkdtemp(prefix="download_"))
    try:
        input_path = temporary / safe_filename(file_name)
        tg_file = await context.bot.get_file(document.file_id)
        await tg_file.download_to_drive(custom_path=str(input_path))
        await process_and_reply(update, context, input_path, is_pdf)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    photo = update.effective_message.photo[-1]
    temporary = Path(tempfile.mkdtemp(prefix="photo_"))
    try:
        input_path = temporary / "telegram_photo.jpg"
        tg_file = await context.bot.get_file(photo.file_id)
        await tg_file.download_to_drive(custom_path=str(input_path))
        await process_and_reply(update, context, input_path, False)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_user(update):
        return
    await update.effective_message.reply_text(
        "أرسل صورة أو ملف PDF للمعالجة، أو استخدم /translate لترجمة نص بالقاموس. اكتب /help للمساعدة."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception("Unhandled Telegram error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("حدث خطأ غير متوقع. حاول مرة أخرى لاحقاً.")
        except Exception:
            pass


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "بدء الاستخدام"),
            BotCommand("help", "عرض المساعدة"),
            BotCommand("translate", "ترجمة بالنص أو آخر نتيجة"),
            BotCommand("settings", "إعداداتك"),
            BotCommand("summary", "ملخص آخر نص"),
            BotCommand("last", "آخر نتيجة"),
            BotCommand("privacy", "الخصوصية"),
        ]
    )


def build_application() -> Application:
    if not BOT_TOKEN.strip():
        raise RuntimeError("BOT_TOKEN فارغ. افتح الملف وعدّل قيمة BOT_TOKEN في قسم الإعدادات.")
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("setlang", setlang_command))
    application.add_handler(CommandHandler("settarget", settarget_command))
    application.add_handler(CommandHandler("mode", mode_command))
    application.add_handler(CommandHandler(["translate", "tr"], translate_command))
    application.add_handler(CommandHandler("teach", teach_command))
    application.add_handler(CommandHandler("delword", delword_command))
    application.add_handler(CommandHandler("dictstats", dictstats_command))
    application.add_handler(CommandHandler("importdict", importdict_help))
    application.add_handler(CommandHandler("exportdict", exportdict_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("last", last_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(CommandHandler("privacy", privacy_command))
    application.add_handler(CommandHandler("stats", admin_stats_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_error_handler(error_handler)
    return application
from flask import Flask
import threading
import os

web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is Running! 🚀"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()


def main() -> None:
    LOGGER.info("Starting Telegram PDF OCR bot; DB=%s", DB_PATH)
    application = build_application()
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
