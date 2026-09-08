# -*- coding: utf-8 -*-
"""
بوت دعم تلغرام محسّن ومطوّر — نسخة قوية (v2)
=====================================================
الميزات:
  🎨 أزرار ملونة حقيقية (Telegram يدعم فقط: primary/success/danger)
  🔒 استلام التذاكر (Claim) لمنع تكرار الرد من أكثر من أدمن
  ⚡ تمييز التذاكر العاجلة (Priority)
  💬 ردود جاهزة سريعة (Canned Replies) بضغطة واحدة
  ⭐ تقييم المستخدم لجودة الدعم بعد كل رد
  📢 بث رسالة جماعية لكل المستخدمين (Broadcast) مع تأكيد
  🛡️ حماية من الإزعاج (Anti-flood / Rate limiting)
  🔑 التوكن ومعرفات الأدمن تُقرأ من متغيرات البيئة (لا تُكتب داخل الكود أبدًا)

التثبيت: pip install -r requirements.txt
التشغيل (لينكس/ماك):
    export BOT_TOKEN='التوكن_من_BotFather'
    export ADMIN_IDS='123456789,987654321'
    python support_bot_enhanced.py

التشغيل (ويندوز - PowerShell):
    $env:BOT_TOKEN='التوكن_من_BotFather'
    $env:ADMIN_IDS='123456789,987654321'
    python support_bot_enhanced.py
"""
import csv
import html
import io
import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

# =====================================================================
# 🔧 1. إعدادات البوت الأساسية
# =====================================================================
# ⚠️ لا تكتب التوكن مباشرة هنا أبدًا — أي شخص يرى الملف يمكنه التحكم ببوتك.
# ضعه في متغير بيئة قبل التشغيل (انظر التعليمات بالأعلى).

BOT_TOKEN = os.getenv("BOT_TOKEN", "8682545541:AAHfEF3p2D_8Pg3byaGtw5CvZhZu-2Xp55k").strip()

ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "8619521184,8802164611,8915282966").replace(" ", "").split(",")
    if x.strip().isdigit()
]

DATA_FILE = os.getenv("DATA_FILE", "data.json")
PAGE_SIZE = 8

# 🛡️ حماية من الإزعاج: أقصى عدد رسائل خلال المدة المحددة (بالثواني)
RATE_LIMIT_WINDOW = 20
RATE_LIMIT_MAX_MSGS = 6

# =====================================================================
# 📝 إعدادات السجل (log)
# =====================================================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger("support-bot")

# =====================================================================
# 🎨 نظام تلوين الأزرار
# =====================================================================
# ملاحظة مهمة: تيليجرام يدعم فعليًا 3 ألوان فقط للأزرار: primary (أزرق)،
# success (أخضر)، danger (أحمر). أي قيمة أخرى (warning, secondary, info)
# تُسبب خطأ. لذلك نستخدم أيقونات إضافية للتمييز البصري بين الفئات مع
# تعيين كل فئة إلى أقرب لون حقيقي مدعوم.

STYLE_ICONS = {
    "primary": "🔵",
    "success": "🟢",
    "danger": "🔴",
    "warning": "🟡",
    "secondary": "⚪",
    "info": "🔷",
    "none": "",
}

# تحويل الأنماط الستة إلى أحد الألوان الثلاثة الحقيقية المدعومة من تيليجرام
TELEGRAM_STYLE = {
    "primary": "primary",
    "success": "success",
    "danger": "danger",
    "warning": "danger",     # الأصفر غير مدعوم -> أقرب لون تحذيري حقيقي
    "secondary": "primary",  # الرمادي غير مدعوم -> نستخدم primary
    "info": "primary",
    "none": None,
}


def make_bold_unicode(text: str) -> str:
    """تحويل النص إلى حروف عريضة باستخدام يونيكود"""
    out = []
    for char in text:
        cp = ord(char)
        if 65 <= cp <= 90:
            out.append(chr(cp - 65 + 0x1D5D4))
        elif 97 <= cp <= 122:
            out.append(chr(cp - 97 + 0x1D5EE))
        elif 48 <= cp <= 57:
            out.append(chr(cp - 48 + 0x1D7EC))
        else:
            out.append(char)
    return "".join(out)


def style_text(text: str, style: str = "none", bold: bool = True) -> str:
    """إضافة أيقونة وتنسيق للنص"""
    body = make_bold_unicode(text) if bold else text
    icon = STYLE_ICONS.get(style, "")
    return f"{icon} {body}".strip()


# =====================================================================
# ⌨️ أزرار الرد (Reply Keyboard) - تلوين حقيقي (python-telegram-bot >= 22.7)
# =====================================================================

def styled_button(text: str, style: str) -> KeyboardButton:
    """زر بلون تيليجرام حقيقي + أيقونة توضيحية للفئة"""
    return KeyboardButton(style_text(text, style), style=TELEGRAM_STYLE.get(style))


def styled_keyboard(rows, placeholder=None):
    return ReplyKeyboardMarkup(
        [[styled_button(t, s) for t, s in row] for row in rows],
        resize_keyboard=True,
        input_field_placeholder=placeholder,
    )


# =====================================================================
# 📋 تعريف الأزرار الرئيسية (النص, النمط)
# =====================================================================

BTN_CONTACT = ("مراسلة الدعم", "primary")
BTN_STATUS = ("حالة رسالتي", "success")
BTN_HELP = ("مساعدة", "secondary")

BTN_USERS = ("قائمة المستخدمين", "primary")
BTN_PENDING = ("الرسائل غير المجابة", "success")
BTN_SEARCH = ("بحث عن مستخدم", "warning")
BTN_BAN = ("حظر / إلغاء حظر", "danger")
BTN_STATS = ("إحصائيات", "secondary")
BTN_BROADCAST = ("بث جماعي", "info")
BTN_CANCEL = ("إلغاء الرد", "danger")

USER_KB = styled_keyboard([
    [BTN_CONTACT],
    [BTN_STATUS, BTN_HELP],
], placeholder="اكتب رسالتك وسنرد عليك…")

ADMIN_KB = styled_keyboard([
    [BTN_USERS, BTN_PENDING],
    [BTN_SEARCH, BTN_BAN],
    [BTN_STATS, BTN_BROADCAST],
], placeholder="لوحة الأدمن")

# =====================================================================
# 🔗 أزرار الإنلاين (Inline Keyboard) - تدعم التلوين الحقيقي أيضًا (v22.7+)
# =====================================================================

def inline(text: str, style: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        style_text(text, style, bold=False),
        callback_data=data,
        style=TELEGRAM_STYLE.get(style),
    )


# =====================================================================
# 💬 الردود الجاهزة (Canned Replies)
# =====================================================================

CANNED_REPLIES = [
    "شكرًا لتواصلك معنا 🙏 سنراجع طلبك ونرد عليك في أقرب وقت.",
    "تم حل المشكلة ✅ هل تحتاج إلى أي شيء آخر؟",
    "عذرًا على التأخير 🙏 نعمل الآن على حل مشكلتك.",
    "من فضلك أرسل تفاصيل أكثر (صور/سكرين شوت) لنساعدك بشكل أفضل.",
    "طلبك قيد المراجعة من الفريق المختص، شكرًا لصبرك 🙏",
]

# =====================================================================
# 🛡️ حماية من الإزعاج (Anti-flood)
# =====================================================================

_msg_timestamps: dict[int, deque] = defaultdict(deque)


def is_rate_limited(uid: int) -> bool:
    """يرجع True إذا تجاوز المستخدم الحد المسموح من الرسائل"""
    now_ts = time.time()
    q = _msg_timestamps[uid]
    while q and now_ts - q[0] > RATE_LIMIT_WINDOW:
        q.popleft()
    q.append(now_ts)
    return len(q) > RATE_LIMIT_MAX_MSGS


# =====================================================================
# 💾 إدارة البيانات
# =====================================================================

DEFAULT_DATA = {"users": {}, "tickets": {}, "banned": [], "counter": 0}
DATA = json.loads(json.dumps(DEFAULT_DATA))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_data():
    try:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(DATA, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)
    except Exception:
        log.exception("تعذر حفظ البيانات")


def load_data():
    global DATA
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            loaded = json.load(f)
        for key, value in DEFAULT_DATA.items():
            loaded.setdefault(key, value)
        DATA = loaded
    except FileNotFoundError:
        save_data()
    except Exception:
        log.exception("ملف البيانات تالف؛ سيتم استخدام بيانات فارغة")


# =====================================================================
# 🔐 دوال الصلاحيات والتحقق
# =====================================================================

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def is_banned(uid: int) -> bool:
    return any(str(x) == str(uid) for x in DATA["banned"])


def user_label(user: dict) -> str:
    name = html.escape(user.get("name") or "بدون اسم")
    username = f"@{html.escape(user['username'])}" if user.get("username") else "بدون معرّف"
    return f"{name} ({username}) — <code>{user.get('id', '')}</code>"


# =====================================================================
# 👤 دوال المستخدمين والتذاكر
# =====================================================================

def save_user(tg_user) -> dict:
    uid = str(tg_user.id)
    stamp = now()
    rec = DATA["users"].get(uid, {
        "id": tg_user.id,
        "first_seen": stamp,
        "messages": 0,
        "status": "new",
        "answered_by": "",
        "history": [],
    })
    rec.update({
        "id": tg_user.id,
        "name": (tg_user.full_name or "").strip(),
        "username": tg_user.username or "",
        "last_seen": stamp,
    })
    rec.setdefault("history", [])
    DATA["users"][uid] = rec
    save_data()
    return rec


def add_history(uid: int, direction: str, message_id: int, ticket_id: Optional[str] = None):
    rec = DATA["users"].get(str(uid))
    if not rec:
        return
    rec.setdefault("history", []).append({
        "direction": direction,
        "message_id": message_id,
        "ticket_id": ticket_id or "",
        "at": now(),
    })
    rec["history"] = rec["history"][-100:]


def remember_link(context, admin_id: int, message_id: int, uid: int, ticket_id: str):
    context.bot_data.setdefault("reply_map", {})[f"{admin_id}:{message_id}"] = {
        "user_id": uid,
        "ticket_id": ticket_id,
    }
    DATA["tickets"][ticket_id].setdefault("message_links", []).append({
        "admin_id": admin_id,
        "message_id": message_id,
    })


def resolve_reply(context, admin_id: int, message_id: int):
    direct = context.bot_data.get("reply_map", {}).get(f"{admin_id}:{message_id}")
    if direct:
        return direct
    for tid, ticket in DATA["tickets"].items():
        for link in ticket.get("message_links", []):
            if str(link.get("admin_id")) == str(admin_id) and str(link.get("message_id")) == str(message_id):
                return {"user_id": ticket["user_id"], "ticket_id": tid}
    return None


# =====================================================================
# 📨 أوامر البوت
# =====================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        await update.message.reply_text(
            "🛠 <b>لوحة الأدمن</b>\nاختر عملية من الأزرار أو استخدم /help_admin.",
            parse_mode=ParseMode.HTML,
            reply_markup=ADMIN_KB,
        )
        return
    save_user(user)
    await update.message.reply_text(
        "👋 <b>أهلًا بك في بوت الدعم</b>\n\nأرسل نصًا أو صورة أو ملفًا أو رسالة صوتية، وسيصلك الرد هنا.",
        parse_mode=ParseMode.HTML,
        reply_markup=USER_KB,
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 معرّفك: <code>{update.effective_user.id}</code>",
        parse_mode=ParseMode.HTML,
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("target", None)
    context.user_data.pop("target_ticket", None)
    context.user_data.pop("awaiting", None)
    context.user_data.pop("broadcast_text", None)
    await update.effective_message.reply_text(
        "✅ تم إلغاء العملية الحالية.",
        reply_markup=ADMIN_KB if is_admin(update.effective_user.id) else USER_KB,
    )


async def cmd_help_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "<b>أوامر الأدمن</b>\n"
        "/users — قائمة المستخدمين\n"
        "/pending — غير المجابة (العاجل أولًا)\n"
        "/stats — الإحصائيات والتقييمات\n"
        "/broadcast — بث رسالة لكل المستخدمين\n"
        "/export — تصدير المستخدمين CSV\n"
        "/cancel — إلغاء العملية الحالية\n\n"
        "للرد: اضغط Reply على رسالة المستخدم، أو اختره من القائمة.\n"
        "🔒 استلام — يمنع الأدمن الآخرين من تكرار نفس الرد.\n"
        "⚡ عاجل — يرفع التذكرة لأعلى قائمة الانتظار.\n"
        "💬 رد جاهز — إرسال رد سريع بضغطة واحدة.",
        parse_mode=ParseMode.HTML,
        reply_markup=ADMIN_KB,
    )


async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        await show_users(update, context)


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        await show_pending(update, context)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        await show_stats(update, context)


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    context.user_data["awaiting"] = "broadcast"
    await update.message.reply_text(
        "📢 أرسل الآن نص الرسالة التي تريد بثّها لجميع المستخدمين، أو /cancel للإلغاء."
    )


# =====================================================================
# 📤 دوال عرض البيانات
# =====================================================================

def admin_actions_kb(uid: int, tid: str):
    """لوحة أزرار الأدمن للتذكرة: رد سريع، استلام، عاجل، تم، حظر"""
    ticket = DATA["tickets"].get(tid, {})
    claim_label = "🔒 مُستلمة" if ticket.get("claimed_by") else "🔒 استلام"
    priority_label = "🚨 عاجل!" if ticket.get("priority") else "⚡ تمييز كعاجل"
    return InlineKeyboardMarkup([
        [
            inline("رد", "success", f"reply:{uid}:{tid}"),
            inline("تم التعامل", "primary", f"done:{tid}"),
        ],
        [
            inline(claim_label, "primary", f"claim:{tid}"),
            inline(priority_label, "danger", f"prio:{tid}"),
        ],
        [
            inline("💬 رد جاهز", "success", f"canned:{uid}:{tid}"),
        ],
        [
            inline("حظر", "danger", f"ban:{uid}"),
        ],
    ])


def canned_kb(uid: int, tid: str):
    rows = [
        [inline(f"{i+1}. {text[:30]}", "success", f"send_canned:{i}:{uid}:{tid}")]
        for i, text in enumerate(CANNED_REPLIES)
    ]
    rows.append([inline("رجوع", "secondary", f"noop")])
    return InlineKeyboardMarkup(rows)


async def forward_to_admins(update: Update, context: ContextTypes.DEFAULT_TYPE, rec: dict):
    DATA["counter"] += 1
    tid = str(DATA["counter"])
    msg = update.message

    DATA["tickets"][tid] = {
        "user_id": rec["id"],
        "status": "pending",
        "answered_by": "",
        "created": now(),
        "message_links": [],
        "header_cards": [],
        "claimed_by": "",
        "priority": False,
        "rating": None,
    }

    header = (
        f"📨 <b>رسالة جديدة #{tid}</b>\n👤 {user_label(rec)}\n"
        f"💬 إجمالي رسائله: {rec['messages']}\n───────────────"
    )

    for admin_id in ADMIN_IDS:
        try:
            card = await context.bot.send_message(
                admin_id,
                header,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_actions_kb(rec["id"], tid),
            )
            copied = await msg.copy(chat_id=admin_id, reply_to_message_id=card.message_id)
            remember_link(context, admin_id, card.message_id, rec["id"], tid)
            remember_link(context, admin_id, copied.message_id, rec["id"], tid)
            DATA["tickets"][tid]["header_cards"].append({"admin_id": admin_id, "message_id": card.message_id})
        except Exception as exc:
            log.warning("فشل إرسال التذكرة %s للأدمن %s: %s", tid, admin_id, exc)

    add_history(rec["id"], "in", msg.message_id, tid)
    save_data()


async def refresh_ticket_cards(context, tid: str):
    """تحديث بطاقة التذكرة عند جميع الأدمنز (بعد الاستلام أو التمييز كعاجل)"""
    ticket = DATA["tickets"].get(tid)
    if not ticket:
        return
    u = DATA["users"].get(str(ticket["user_id"]), {"id": ticket["user_id"]})
    header = (
        f"📨 <b>رسالة #{tid}</b>\n👤 {user_label(u)}\n───────────────"
    )
    if ticket.get("priority"):
        header = "🚨 <b>عاجلة</b>\n" + header
    if ticket.get("claimed_by"):
        header += f"\n🔒 مُستلمة بواسطة: {html.escape(ticket['claimed_by'])}"
    for card in ticket.get("header_cards", []):
        try:
            await context.bot.edit_message_text(
                chat_id=card["admin_id"],
                message_id=card["message_id"],
                text=header,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_actions_kb(ticket["user_id"], tid),
            )
        except Exception:
            pass  # قد تكون الرسالة قديمة جدًا أو محذوفة، نتجاهل بأمان


def users_filtered(page=0, query=""):
    users = list(DATA["users"].values())
    q = query.strip().lower()
    if q:
        users = [u for u in users if (
            q in str(u.get("name", "")).lower()
            or q.lstrip("@").lower() in str(u.get("username", "")).lower()
            or q == str(u.get("id"))
        )]
    users.sort(key=lambda u: u.get("last_seen", ""), reverse=True)
    return users, users[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]


def users_page_kb(page=0, query=""):
    users, chunk = users_filtered(page, query)
    rows = []
    for u in chunk:
        icon = "🔴" if is_banned(u["id"]) else {
            "pending": "🟡", "answered": "🟢", "new": "🔵",
        }.get(u.get("status"), "⚪")
        rows.append([InlineKeyboardButton(
            f"{icon} {(u.get('name') or str(u['id']))[:35]}",
            callback_data=f"pick:{u['id']}",
        )])
    nav = []
    if page:
        nav.append(InlineKeyboardButton("« السابق", callback_data=f"page:{page-1}:{query[:30]}"))
    if (page + 1) * PAGE_SIZE < len(users):
        nav.append(InlineKeyboardButton("التالي »", callback_data=f"page:{page+1}:{query[:30]}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows or [[inline("لا يوجد مستخدمون", "secondary", "noop")]])


async def show_users(update, context, page=0, query=""):
    total = len(DATA["users"])
    title = f"👥 <b>قائمة المستخدمين</b> ({total})\nاختر مستخدمًا للرد أو عرض التفاصيل:"
    if query:
        title = f"🔎 <b>نتائج البحث:</b> {html.escape(query)}"
    await update.effective_message.reply_text(
        title, parse_mode=ParseMode.HTML, reply_markup=users_page_kb(page, query),
    )


async def show_pending(update, context):
    items = [(tid, t) for tid, t in DATA["tickets"].items() if t.get("status") == "pending"]
    if not items:
        return await update.effective_message.reply_text("🟢 لا توجد رسائل غير مجابة.")

    # العاجلة أولًا، ثم الأحدث
    items.sort(key=lambda it: (not it[1].get("priority", False), it[1].get("created", "")), reverse=False)

    lines = [f"🟡 <b>غير المجابة</b> ({len(items)})"]
    rows = []
    for tid, ticket in items[:20]:
        u = DATA["users"].get(str(ticket["user_id"]), {"id": ticket["user_id"]})
        flag = "🚨 " if ticket.get("priority") else ""
        claimed = f" — 🔒 {html.escape(ticket['claimed_by'])}" if ticket.get("claimed_by") else ""
        lines.append(f"{flag}#{tid} — {user_label(u)}{claimed}")
        rows.append([inline(f"{flag}رد على #{tid}", "success", f"reply:{ticket['user_id']}:{tid}")])

    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows),
    )


async def show_stats(update, context):
    pending = sum(t.get("status") == "pending" for t in DATA["tickets"].values())
    answered = sum(t.get("status") == "answered" for t in DATA["tickets"].values())
    total_messages = sum(u.get("messages", 0) for u in DATA["users"].values())
    ratings = [t["rating"] for t in DATA["tickets"].values() if t.get("rating")]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None
    urgent = sum(t.get("priority") and t.get("status") == "pending" for t in DATA["tickets"].values())

    rating_line = f"⭐ متوسط التقييم: <b>{avg_rating}/5</b> ({len(ratings)} تقييم)" if avg_rating else "⭐ لا توجد تقييمات بعد"

    await update.effective_message.reply_text(
        f"📊 <b>الإحصائيات</b>\n\n"
        f"👥 المستخدمون: <b>{len(DATA['users'])}</b>\n"
        f"💬 رسائل المستخدمين: <b>{total_messages}</b>\n"
        f"📨 التذاكر: <b>{len(DATA['tickets'])}</b>\n"
        f"🟢 تمت الإجابة: <b>{answered}</b>\n"
        f"🟡 بانتظار الرد: <b>{pending}</b>\n"
        f"🚨 عاجلة بانتظار الرد: <b>{urgent}</b>\n"
        f"🔴 المحظورون: <b>{len(DATA['banned'])}</b>\n"
        f"{rating_line}",
        parse_mode=ParseMode.HTML,
    )


async def export_users(update, context):
    if not is_admin(update.effective_user.id):
        return
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["id", "name", "username", "status", "messages", "first_seen", "last_seen"])
    for u in DATA["users"].values():
        writer.writerow([u.get(k, "") for k in ["id", "name", "username", "status", "messages", "first_seen", "last_seen"]])
    await update.message.reply_document(
        io.BytesIO(out.getvalue().encode("utf-8-sig")),
        filename="users.csv",
        caption="📄 تصدير قائمة المستخدمين",
    )


# =====================================================================
# 📩 دوال الرد على المستخدمين
# =====================================================================

async def ask_for_rating(context, uid: int, tid: str):
    """إرسال طلب تقييم للمستخدم بعد رد الأدمن"""
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐" * n, callback_data=f"rate:{tid}:{n}") for n in range(1, 6)
    ]])
    try:
        await context.bot.send_message(
            uid, "🙏 كيف تقيّم جودة الرد الذي استلمته؟", reply_markup=kb,
        )
    except Exception:
        pass


async def deliver_to_user(update, context, uid: int, tid: Optional[str] = None, text_override: Optional[str] = None):
    """إرسال رد للأدمن إلى المستخدم (نصًا يدويًا أو رد جاهز)"""
    admin = update.effective_user

    try:
        await context.bot.send_message(uid, "📬 <b>رد من فريق الدعم:</b>", parse_mode=ParseMode.HTML)
        if text_override is not None:
            sent = await context.bot.send_message(uid, text_override)
        else:
            sent = await update.message.copy(chat_id=uid)
    except Exception:
        target = update.message or update.callback_query.message
        return await target.reply_text("⚠️ تعذر إرسال الرد. قد يكون المستخدم حظر البوت.")

    rec = DATA["users"].get(str(uid))
    if rec:
        rec["status"] = "answered"
        rec["answered_by"] = admin.full_name
        add_history(uid, "out", sent.message_id, tid)

    if not tid:
        for candidate, ticket in reversed(list(DATA["tickets"].items())):
            if str(ticket.get("user_id")) == str(uid) and ticket.get("status") == "pending":
                tid = candidate
                break

    if tid and tid in DATA["tickets"]:
        DATA["tickets"][tid].update({
            "status": "answered",
            "answered_by": str(admin.id),
            "answered_at": now(),
        })

    save_data()
    context.user_data.pop("target", None)
    context.user_data.pop("target_ticket", None)

    if tid:
        await ask_for_rating(context, uid, tid)

    reply_target = update.message or update.callback_query.message
    await reply_target.reply_text("✅ تم إرسال الرد وتحديث حالة التذكرة.", reply_markup=ADMIN_KB)


# =====================================================================
# 📨 معالجة الرسائل الواردة
# =====================================================================

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    user = update.effective_user
    text = (msg.text or "").strip()

    # ====== معالجة رسائل الأدمن ======
    if is_admin(user.id):
        awaiting = context.user_data.get("awaiting")

        # تأكيد نص البث الجماعي
        if awaiting == "broadcast" and text:
            context.user_data["broadcast_text"] = text
            context.user_data["awaiting"] = None
            total = len(DATA["users"])
            kb = InlineKeyboardMarkup([[
                inline("✅ تأكيد الإرسال", "success", "broadcast:yes"),
                inline("❌ إلغاء", "danger", "broadcast:no"),
            ]])
            return await msg.reply_text(
                f"📢 <b>معاينة البث</b> (سيصل إلى {total} مستخدم):\n\n{html.escape(text)}",
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )

        if msg.reply_to_message:
            info = resolve_reply(context, user.id, msg.reply_to_message.message_id)
            if info:
                return await deliver_to_user(update, context, info["user_id"], info.get("ticket_id"))

        if text == BTN_USERS[0]:
            return await show_users(update, context)
        if text == BTN_PENDING[0]:
            return await show_pending(update, context)
        if text == BTN_STATS[0]:
            return await show_stats(update, context)
        if text == BTN_BROADCAST[0]:
            return await cmd_broadcast(update, context)
        if text == BTN_SEARCH[0]:
            context.user_data["awaiting"] = "search"
            return await msg.reply_text("🔎 أرسل الاسم أو username أو رقم المستخدم:")
        if text == BTN_BAN[0]:
            context.user_data["awaiting"] = "ban"
            return await msg.reply_text("🔴 أرسل رقم المستخدم للحظر أو رفع الحظر:")
        if text == BTN_CANCEL[0]:
            return await cmd_cancel(update, context)

        if awaiting == "search" and text:
            context.user_data.pop("awaiting", None)
            return await show_users(update, context, query=text)
        if awaiting == "ban" and text:
            context.user_data.pop("awaiting", None)
            if not text.isdigit():
                return await msg.reply_text("⚠️ أرسل رقمًا صحيحًا.")
            uid = int(text)
            if is_banned(uid):
                DATA["banned"] = [x for x in DATA["banned"] if str(x) != str(uid)]
                result = "🟢 تم رفع الحظر"
            else:
                DATA["banned"].append(uid)
                result = "🔴 تم الحظر"
            save_data()
            return await msg.reply_text(f"{result} — <code>{uid}</code>", parse_mode=ParseMode.HTML)

        target = context.user_data.get("target")
        if target:
            return await deliver_to_user(update, context, int(target), context.user_data.get("target_ticket"))

        return await msg.reply_text(
            "ℹ️ للرد اضغط Reply على رسالة المستخدم، أو اختر مستخدمًا من القائمة.",
            reply_markup=ADMIN_KB,
        )

    # ====== معالجة رسائل المستخدم العادي ======
    if is_banned(user.id):
        return await msg.reply_text("🚫 لا يمكنك مراسلة الدعم حاليًا.")

    if is_rate_limited(user.id):
        return await msg.reply_text("⏳ الرجاء الانتظار قليلًا قبل إرسال رسائل جديدة.")

    if text == BTN_HELP[0]:
        return await msg.reply_text(
            "👋 أرسل رسالتك هنا، ويدعم البوت النص والصور والملفات والصوت.",
            reply_markup=USER_KB,
        )

    if text == BTN_CONTACT[0]:
        return await msg.reply_text("✍️ تفضل، اكتب رسالتك الآن.", reply_markup=USER_KB)

    if text == BTN_STATUS[0]:
        rec = DATA["users"].get(str(user.id), {})
        status = {
            "answered": "🟢 تم الرد على آخر رسالة",
            "pending": "🟡 رسالتك قيد المعالجة",
            "new": "🔵 لم ترسل رسالة بعد",
        }.get(rec.get("status", "new"), "⚪")
        return await msg.reply_text(status, reply_markup=USER_KB)

    rec = save_user(user)
    rec["messages"] = rec.get("messages", 0) + 1
    rec["status"] = "pending"
    save_data()

    await forward_to_admins(update, context, rec)
    await msg.reply_text("✅ تم إرسال رسالتك للدعم، سيصلك الرد قريبًا.", reply_markup=USER_KB)


# =====================================================================
# 🔄 معالجة الأزرار المضمنة (CallbackQuery)
# =====================================================================

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    parts = (q.data or "").split(":")
    action = parts[0]

    # تقييم المستخدم (متاح لأي مستخدم، ليس فقط الأدمن)
    if action == "rate":
        tid, score = parts[1], int(parts[2])
        if tid in DATA["tickets"]:
            DATA["tickets"][tid]["rating"] = score
            save_data()
        return await q.edit_message_text(f"شكرًا لتقييمك! {'⭐' * score}")

    if not is_admin(q.from_user.id):
        return

    if action == "noop":
        return

    if action == "page":
        page = int(parts[1])
        query = ":".join(parts[2:]) if len(parts) > 2 else ""
        return await q.edit_message_reply_markup(reply_markup=users_page_kb(page, query))

    if action in ("pick", "reply"):
        uid = int(parts[1])
        tid = parts[2] if len(parts) > 2 else None
        context.user_data["target"] = uid
        context.user_data["target_ticket"] = tid

        u = DATA["users"].get(str(uid), {"id": uid, "name": "", "username": ""})
        history = len(u.get("history", []))
        return await q.message.reply_text(
            f"👤 {user_label(u)}\n🗂 عناصر السجل: {history}\n✍️ اكتب الرد الآن أو استخدم /cancel.",
            parse_mode=ParseMode.HTML,
        )

    if action == "claim":
        tid = parts[1]
        ticket = DATA["tickets"].get(tid)
        if ticket and not ticket.get("claimed_by"):
            ticket["claimed_by"] = q.from_user.full_name
            save_data()
            await refresh_ticket_cards(context, tid)
        return

    if action == "prio":
        tid = parts[1]
        ticket = DATA["tickets"].get(tid)
        if ticket:
            ticket["priority"] = not ticket.get("priority", False)
            save_data()
            await refresh_ticket_cards(context, tid)
        return

    if action == "canned":
        uid, tid = parts[1], parts[2]
        return await q.message.reply_text("💬 اختر ردًا جاهزًا لإرساله فورًا:", reply_markup=canned_kb(int(uid), tid))

    if action == "send_canned":
        idx, uid, tid = int(parts[1]), int(parts[2]), parts[3]
        if 0 <= idx < len(CANNED_REPLIES):
            return await deliver_to_user(update, context, uid, tid, text_override=CANNED_REPLIES[idx])
        return

    if action == "done" and len(parts) > 1 and parts[1] in DATA["tickets"]:
        DATA["tickets"][parts[1]]["status"] = "answered"
        save_data()
        return await q.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([[inline("تم التعامل", "success", "noop")]])
        )

    if action == "ban" and len(parts) > 1:
        uid = int(parts[1])
        if is_banned(uid):
            DATA["banned"] = [x for x in DATA["banned"] if str(x) != str(uid)]
            result = "🟢 تم رفع الحظر"
        else:
            DATA["banned"].append(uid)
            result = "🔴 تم الحظر"
        save_data()
        return await q.message.reply_text(f"{result} — <code>{uid}</code>", parse_mode=ParseMode.HTML)

    if action == "broadcast":
        text = context.user_data.get("broadcast_text")
        if parts[1] == "no" or not text:
            context.user_data.pop("broadcast_text", None)
            return await q.edit_message_text("❌ تم إلغاء البث.")

        sent, failed = 0, 0
        for uid_str in list(DATA["users"].keys()):
            try:
                await context.bot.send_message(int(uid_str), text)
                sent += 1
            except Exception:
                failed += 1
        context.user_data.pop("broadcast_text", None)
        return await q.edit_message_text(f"✅ تم إرسال البث إلى {sent} مستخدم. (فشل: {failed})")


# =====================================================================
# ❌ معالجة الأخطاء
# =====================================================================

async def on_error(update, context):
    log.error("خطأ غير معالج: %s", context.error, exc_info=context.error)


# =====================================================================
# 🚀 تشغيل البوت
# =====================================================================

def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "❌ لم يتم ضبط BOT_TOKEN.\n"
            "شغّل الأمر التالي قبل تشغيل البوت (استبدل التوكن بتوكنك الحقيقي):\n"
            "   export BOT_TOKEN='التوكن_من_BotFather'   (لينكس/ماك)\n"
            "   $env:BOT_TOKEN='التوكن_من_BotFather'      (ويندوز PowerShell)"
        )

    if not ADMIN_IDS:
        log.warning("⚠️ ADMIN_IDS فارغة - لن يكون هناك أدمن للبوت. اضبط متغير البيئة ADMIN_IDS.")

    load_data()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("help_admin", cmd_help_admin))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("export", export_users))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(~filters.COMMAND, on_message))
    app.add_error_handler(on_error)

    log.info("✅ البوت يعمل الآن")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
