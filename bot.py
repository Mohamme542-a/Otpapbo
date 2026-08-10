# ═══════════════════════════════════════════════════════════════
# 🗂 ARCHIVE BOT — بوت أرشيف مؤسسة العقاب إعلامية (Telegram)
#   pip install python-telegram-bot==21.6
#   python archive_bot.py
#
#   ✦ أقسام قابلة للتعديل بالكامل من لوحة الأدمن (إضافة/تسمية/حذف/ترتيب)
#   ✦ رفع أي محتوى: فيديو • صوت • صورة • ملف • بصمة صوتية • GIF • نص • رابط
#   ✦ تعديل نصوص البوت والأزرار من داخل البوت بدون لمس الكود
# ═══════════════════════════════════════════════════════════════
import json, logging, os, time
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

# ══════════════════ CONFIG (املأ هنا) ══════════════════
BOT_TOKEN = "8589967320:AAG_nrroMIc3dl2v4G339gSJPBqzmrpTMcY"          # ← ضع توكن البوت هنا
ADMIN_IDS = [8747566796]          # ← ضع ايدي الأدمن هنا مثال: [123456789]

DATA_FILE  = "archive.json"
USERS_FILE = "users.json"
PAGE_SIZE  = 8          # عدد العناصر في الصفحة الواحدة

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger("archive")

# ══════════════════ TEXT BOLD HELPER (ألوان/خط عريض) ══════════════════
def make_bold_unicode(text):
    out = []
    for char in str(text):
        c = ord(char)
        if 65 <= c <= 90:      out.append(chr(c - 65 + 0x1D5D4))   # A-Z
        elif 97 <= c <= 122:   out.append(chr(c - 97 + 0x1D5EE))   # a-z
        elif 48 <= c <= 57:    out.append(chr(c - 48 + 0x1D7EC))   # 0-9
        else:                  out.append(char)
    return "".join(out)

LINE = "━━━━━━━━━━━━━━━━━━━━━"

def _kb_btn(text, style=None):
    """KeyboardButton مع style (يعمل في الفورك)، آمن لو المكتبة لا تدعم style."""
    try:
        return KeyboardButton(text, style=style) if style else KeyboardButton(text)
    except TypeError:
        return KeyboardButton(text)

def IB(text, style=None, **kw):
    """InlineKeyboardButton مع style ملوّن، آمن لو المكتبة لا تدعمه."""
    try:
        return InlineKeyboardButton(text, style=style, **kw) if style else InlineKeyboardButton(text, **kw)
    except TypeError:
        return InlineKeyboardButton(text, **kw)

# ══════════════════ STORAGE ══════════════════
DEFAULT_DATA = {
    "brand": "المؤسسة الإعلامية",
    "flag": "🏴",
    "welcome": "أهلاً بك في أرشيف المؤسسة الإعلامية\nاختر القسم الذي تريده من الأزرار بالأسفل.",
    "about": "أرشيف رقمي يضم الإصدارات والأناشيد والكتب والإنفوغرافيك.",
    "contact": "للتواصل: @username",
    "labels": {
        "sections": "📚 الأقسام",
        "about": "ℹ️ حول",
        "contact": "📞 تواصل",
        "search": "🔎 بحث",
        "admin": "🛠️ لوحة الأدمن",
        "back": "🔙 رجوع",
    },
    "sections": [
        {"id": "s1", "title": "🎬 إصدارات",   "desc": "", "items": []},
        {"id": "s2", "title": "🎙 أناشيد",    "desc": "", "items": []},
        {"id": "s3", "title": "📚 كتب",       "desc": "", "items": []},
        {"id": "s4", "title": "📊 إنفوغرافيك", "desc": "", "items": []},
    ],
    "seq": 100,
}

def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(default, dict):
            for k, v in default.items():
                d.setdefault(k, v)
            for k, v in default.get("labels", {}).items():
                d["labels"].setdefault(k, v)
        return d
    except Exception:
        return json.loads(json.dumps(default))

DATA  = _load(DATA_FILE, DEFAULT_DATA)
USERS = _load(USERS_FILE, {})

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)

def save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(USERS, f, ensure_ascii=False, indent=2)

def next_id(prefix):
    DATA["seq"] = int(DATA.get("seq", 100)) + 1
    save_data()
    return f"{prefix}{DATA['seq']}"

def L(key):
    return DATA["labels"].get(key, key)

def is_admin(uid):
    return uid in ADMIN_IDS

def note_user(tgu):
    u = USERS.get(str(tgu.id))
    if not u:
        u = {"id": tgu.id, "name": tgu.first_name or "", "username": tgu.username or "",
             "banned": False, "joined": int(time.time())}
        USERS[str(tgu.id)] = u
        save_users()
    return u

def get_section(sid):
    for s in DATA["sections"]:
        if s["id"] == sid:
            return s
    return None

def get_item(sec, iid):
    for it in sec["items"]:
        if it["id"] == iid:
            return it
    return None

# ══════════════════ TYPES ══════════════════
TYPE_EMOJI = {
    "video": "🎬", "audio": "🎧", "voice": "🎙", "photo": "🖼",
    "document": "📄", "animation": "🎞", "text": "📝",
}

def detect_media(msg):
    """يستخرج نوع المحتوى و file_id من أي رسالة."""
    if msg.video:     return "video", msg.video.file_id, msg.caption or (msg.video.file_name or "فيديو")
    if msg.audio:     return "audio", msg.audio.file_id, msg.caption or (msg.audio.title or msg.audio.file_name or "ملف صوتي")
    if msg.voice:     return "voice", msg.voice.file_id, msg.caption or "بصمة صوتية"
    if msg.photo:     return "photo", msg.photo[-1].file_id, msg.caption or "صورة"
    if msg.animation: return "animation", msg.animation.file_id, msg.caption or "صورة متحركة"
    if msg.document:  return "document", msg.document.file_id, msg.caption or (msg.document.file_name or "ملف")
    if msg.text:      return "text", None, msg.text
    return None, None, None

async def send_item(bot, chat_id, item, reply_markup=None):
    t, fid = item["type"], item.get("file_id")
    cap = f"{TYPE_EMOJI.get(t,'📎')} <b>{make_bold_unicode(item.get('title',''))}</b>"
    if item.get("caption"):
        cap += f"\n{LINE}\n{item['caption']}"
    kw = dict(caption=cap, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    if   t == "video":     await bot.send_video(chat_id, fid, **kw)
    elif t == "audio":     await bot.send_audio(chat_id, fid, **kw)
    elif t == "voice":     await bot.send_voice(chat_id, fid, **kw)
    elif t == "photo":     await bot.send_photo(chat_id, fid, **kw)
    elif t == "animation": await bot.send_animation(chat_id, fid, **kw)
    elif t == "document":  await bot.send_document(chat_id, fid, **kw)
    else:
        await bot.send_message(chat_id, cap, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

# ══════════════════ KEYBOARDS ══════════════════
def main_kb(uid):
    rows = [[_kb_btn(make_bold_unicode(L("sections")), style="danger")]]
    rows.append([
        _kb_btn(make_bold_unicode(L("about")), style="primary"),
        _kb_btn(make_bold_unicode(L("contact")), style="primary"),
    ])
    row3 = [_kb_btn(make_bold_unicode(L("search")), style="success")]
    if is_admin(uid):
        row3.append(_kb_btn(make_bold_unicode(L("admin")), style="success"))
    rows.append(row3)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def sections_kb():
    rows = []
    for s in DATA["sections"]:
        rows.append([IB(make_bold_unicode(f"{s['title']}  •  {len(s['items'])}"),
                        callback_data=f"sec:{s['id']}:0", style="primary")])
    if not rows:
        rows.append([IB(make_bold_unicode("لا توجد أقسام بعد"), callback_data="noop")])
    return InlineKeyboardMarkup(rows)

def items_kb(sec, page):
    items = sec["items"]
    pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    rows = []
    for it in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        rows.append([IB(make_bold_unicode(f"{TYPE_EMOJI.get(it['type'],'📎')} {it['title'][:45]}"),
                        callback_data=f"itm:{sec['id']}:{it['id']}:{page}", style="primary")])
    nav = []
    if page > 0:            nav.append(IB("◀️", callback_data=f"sec:{sec['id']}:{page-1}", style="primary"))
    nav.append(IB(f"{page+1}/{pages}", callback_data="noop"))
    if page < pages - 1:    nav.append(IB("▶️", callback_data=f"sec:{sec['id']}:{page+1}", style="primary"))
    if len(nav) > 1: rows.append(nav)
    rows.append([IB(make_bold_unicode(L("back")), callback_data="sections", style="danger")])
    return InlineKeyboardMarkup(rows)

def item_kb(sid, page, uid, iid):
    rows = [[IB(make_bold_unicode(L("back")), callback_data=f"sec:{sid}:{page}", style="danger")]]
    if is_admin(uid):
        rows.insert(0, [IB(make_bold_unicode("🗑 حذف هذا العنصر"), callback_data=f"adm:delitem:{sid}:{iid}", style="danger")])
    return InlineKeyboardMarkup(rows)

def admin_kb():
    rows = [
        [IB(make_bold_unicode("📤 رفع محتوى لقسم"), callback_data="adm:upload", style="success")],
        [IB(make_bold_unicode("➕ إضافة قسم"), callback_data="adm:addsec", style="success"),
         IB(make_bold_unicode("✏️ تسمية قسم"), callback_data="adm:rensec", style="primary")],
        [IB(make_bold_unicode("🗑 حذف قسم"), callback_data="adm:delsec", style="danger"),
         IB(make_bold_unicode("↕️ ترتيب الأقسام"), callback_data="adm:order", style="primary")],
        [IB(make_bold_unicode("🧹 إدارة محتوى قسم"), callback_data="adm:manage", style="primary")],
        [IB(make_bold_unicode("🏷 تعديل أسماء الأزرار"), callback_data="adm:labels", style="primary")],
        [IB(make_bold_unicode("📝 نص الترحيب"), callback_data="adm:txt:welcome", style="primary"),
         IB(make_bold_unicode("ℹ️ نص حول"), callback_data="adm:txt:about", style="primary")],
        [IB(make_bold_unicode("📞 نص التواصل"), callback_data="adm:txt:contact", style="primary"),
         IB(make_bold_unicode("🏴 اسم المؤسسة"), callback_data="adm:txt:brand", style="primary")],
        [IB(make_bold_unicode("📣 إعلان للجميع"), callback_data="adm:bc", style="primary"),
         IB(make_bold_unicode("👥 المستخدمون"), callback_data="adm:users", style="primary")],
        [IB(make_bold_unicode("🚫 حظر / فك حظر"), callback_data="adm:ban", style="danger"),
         IB(make_bold_unicode("📊 إحصائيات"), callback_data="adm:stats", style="primary")],
    ]
    return InlineKeyboardMarkup(rows)

def pick_section_kb(action):
    rows = [[IB(make_bold_unicode(s["title"]), callback_data=f"pick:{action}:{s['id']}", style="primary")]
            for s in DATA["sections"]]
    rows.append([IB(make_bold_unicode(L("back")), callback_data="adm:panel", style="danger")])
    return InlineKeyboardMarkup(rows)

def labels_kb():
    rows = [[IB(make_bold_unicode(f"{k} : {v}"), callback_data=f"lbl:{k}", style="primary")]
            for k, v in DATA["labels"].items()]
    rows.append([IB(make_bold_unicode(L("back")), callback_data="adm:panel", style="danger")])
    return InlineKeyboardMarkup(rows)

def order_kb():
    rows = []
    for i, s in enumerate(DATA["sections"]):
        rows.append([
            IB("🔼", callback_data=f"mv:up:{s['id']}", style="success"),
            IB(make_bold_unicode(s["title"]), callback_data="noop"),
            IB("🔽", callback_data=f"mv:dn:{s['id']}", style="danger"),
        ])
    rows.append([IB(make_bold_unicode(L("back")), callback_data="adm:panel", style="danger")])
    return InlineKeyboardMarkup(rows)

def manage_items_kb(sec, page=0):
    items = sec["items"]
    pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    rows = []
    for it in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        rows.append([
            IB(make_bold_unicode(f"{TYPE_EMOJI.get(it['type'],'📎')} {it['title'][:32]}"), callback_data="noop"),
            IB("✏️", callback_data=f"ren:{sec['id']}:{it['id']}", style="primary"),
            IB("🗑", callback_data=f"adm:delitem:{sec['id']}:{it['id']}", style="danger"),
        ])
    nav = []
    if page > 0:         nav.append(IB("◀️", callback_data=f"mng:{sec['id']}:{page-1}", style="primary"))
    nav.append(IB(f"{page+1}/{pages}", callback_data="noop"))
    if page < pages - 1: nav.append(IB("▶️", callback_data=f"mng:{sec['id']}:{page+1}", style="primary"))
    if len(nav) > 1: rows.append(nav)
    rows.append([IB(make_bold_unicode(L("back")), callback_data="adm:panel", style="danger")])
    return InlineKeyboardMarkup(rows)

# ══════════════════ HEADERS ══════════════════
def welcome_text():
    return (f"{DATA.get('flag','🏴')} <b>{make_bold_unicode(DATA['brand'])}</b> {DATA.get('flag','🏴')}\n"
            f"{LINE}\n"
            f"{DATA['welcome']}\n"
            f"{LINE}")

def sections_header():
    total = sum(len(s["items"]) for s in DATA["sections"])
    return (f"📚 <b>{make_bold_unicode('أقسام الأرشيف')}</b>\n{LINE}\n"
            f"🗂 الأقسام: <b>{len(DATA['sections'])}</b> • 📦 المواد: <b>{total}</b>\n{LINE}")

# ══════════════════ COMMANDS ══════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = note_user(update.effective_user)
    if u.get("banned"):
        return
    uid = update.effective_user.id
    who = ("@" + update.effective_user.username) if update.effective_user.username else (update.effective_user.first_name or "زائرنا")
    await update.message.reply_text(
        f"{welcome_text()}\n\n👋 أهلاً <b>{make_bold_unicode(who)}</b>",
        parse_mode=ParseMode.HTML, reply_markup=main_kb(uid))

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(f"🛠 <b>{make_bold_unicode('لوحة الأدمن')}</b>\n{LINE}",
                                    parse_mode=ParseMode.HTML, reply_markup=admin_kb())

async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 <code>{update.effective_user.id}</code>", parse_mode=ParseMode.HTML)

# ══════════════════ CALLBACKS ══════════════════
async def on_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    data = q.data or ""
    await q.answer()

    if data == "noop":
        return

    # ── القوائم العامة ──
    if data == "sections":
        await q.edit_message_text(sections_header(), parse_mode=ParseMode.HTML, reply_markup=sections_kb())
        return

    if data.startswith("sec:"):
        _, sid, page = data.split(":")
        sec = get_section(sid)
        if not sec:
            await q.edit_message_text("⚠️ القسم غير موجود."); return
        head = (f"{sec['title']}\n{LINE}\n"
                f"{sec.get('desc') or 'اختر المادة التي تريدها 👇'}\n"
                f"📦 العدد: <b>{len(sec['items'])}</b>\n{LINE}")
        await q.edit_message_text(head, parse_mode=ParseMode.HTML, reply_markup=items_kb(sec, int(page)))
        return

    if data.startswith("itm:"):
        _, sid, iid, page = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        if not it:
            await q.answer("⚠️ العنصر محذوف", show_alert=True); return
        await send_item(ctx.bot, q.message.chat_id, it, item_kb(sid, int(page), uid, iid))
        return

    # ── من هنا فصاعداً أوامر الأدمن ──
    if not is_admin(uid):
        await q.answer("🚫 غير مصرح", show_alert=True); return

    if data == "adm:panel":
        await q.edit_message_text(f"🛠 <b>{make_bold_unicode('لوحة الأدمن')}</b>\n{LINE}",
                                  parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

    if data == "adm:upload":
        await q.edit_message_text("📤 اختر القسم الذي تريد الرفع إليه:", reply_markup=pick_section_kb("upload")); return

    if data == "adm:rensec":
        await q.edit_message_text("✏️ اختر القسم لتغيير اسمه:", reply_markup=pick_section_kb("rensec")); return

    if data == "adm:delsec":
        await q.edit_message_text("🗑 اختر القسم لحذفه (سيُحذف محتواه):", reply_markup=pick_section_kb("delsec")); return

    if data == "adm:manage":
        await q.edit_message_text("🧹 اختر القسم لإدارة محتواه:", reply_markup=pick_section_kb("manage")); return

    if data == "adm:order":
        await q.edit_message_text("↕️ رتّب الأقسام:", reply_markup=order_kb()); return

    if data == "adm:labels":
        await q.edit_message_text("🏷 اضغط على الزر الذي تريد تغيير اسمه:", reply_markup=labels_kb()); return

    if data == "adm:addsec":
        ctx.user_data["await"] = ("addsec", None)
        await q.edit_message_text("➕ أرسل اسم القسم الجديد (يمكنك وضع إيموجي في البداية):"); return

    if data.startswith("adm:txt:"):
        key = data.split(":")[2]
        ctx.user_data["await"] = ("txt", key)
        cur = DATA.get(key, "")
        await q.edit_message_text(f"📝 أرسل النص الجديد.\n{LINE}\nالحالي:\n<code>{cur}</code>", parse_mode=ParseMode.HTML); return

    if data == "adm:bc":
        ctx.user_data["await"] = ("bc", None)
        await q.edit_message_text("📣 أرسل الرسالة (نص أو وسائط) وسأبثّها لكل المستخدمين:"); return

    if data == "adm:ban":
        ctx.user_data["await"] = ("ban", None)
        await q.edit_message_text("🚫 أرسل ايدي المستخدم لحظره أو فك حظره:"); return

    if data == "adm:users":
        lines = [f"👥 <b>{make_bold_unicode('المستخدمون')}</b>\n{LINE}"]
        for u in list(USERS.values())[-30:]:
            mark = "🚫" if u.get("banned") else "✅"
            lines.append(f"{mark} <code>{u['id']}</code> — {u.get('username') or u.get('name') or '—'}")
        lines.append(LINE)
        await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

    if data == "adm:stats":
        total = sum(len(s["items"]) for s in DATA["sections"])
        by = {}
        for s in DATA["sections"]:
            for it in s["items"]:
                by[it["type"]] = by.get(it["type"], 0) + 1
        det = "\n".join(f"{TYPE_EMOJI.get(k,'📎')} {k}: <b>{v}</b>" for k, v in by.items()) or "—"
        txt = (f"📊 <b>{make_bold_unicode('إحصائيات الأرشيف')}</b>\n{LINE}\n"
               f"👥 المستخدمون: <b>{len(USERS)}</b>\n"
               f"🗂 الأقسام: <b>{len(DATA['sections'])}</b>\n"
               f"📦 إجمالي المواد: <b>{total}</b>\n{LINE}\n{det}\n{LINE}")
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

    if data.startswith("adm:delitem:"):
        _, _, sid, iid = data.split(":")
        sec = get_section(sid)
        if sec:
            sec["items"] = [i for i in sec["items"] if i["id"] != iid]
            save_data()
        await q.answer("🗑 تم الحذف", show_alert=True)
        try:
            await q.edit_message_reply_markup(reply_markup=manage_items_kb(sec))
        except Exception:
            pass
        return

    if data.startswith("mng:"):
        _, sid, page = data.split(":")
        sec = get_section(sid)
        await q.edit_message_text(f"🧹 إدارة: {sec['title']}\n{LINE}", reply_markup=manage_items_kb(sec, int(page))); return

    if data.startswith("ren:"):
        _, sid, iid = data.split(":")
        ctx.user_data["await"] = ("renitem", (sid, iid))
        await q.edit_message_text("✏️ أرسل العنوان الجديد لهذه المادة:"); return

    if data.startswith("mv:"):
        _, direction, sid = data.split(":")
        idx = next((i for i, s in enumerate(DATA["sections"]) if s["id"] == sid), None)
        if idx is not None:
            new = idx - 1 if direction == "up" else idx + 1
            if 0 <= new < len(DATA["sections"]):
                DATA["sections"][idx], DATA["sections"][new] = DATA["sections"][new], DATA["sections"][idx]
                save_data()
        await q.edit_message_reply_markup(reply_markup=order_kb()); return

    if data.startswith("lbl:"):
        key = data.split(":")[1]
        ctx.user_data["await"] = ("label", key)
        await q.edit_message_text(f"🏷 أرسل الاسم الجديد للزر <code>{key}</code>\nالحالي: <b>{L(key)}</b>",
                                  parse_mode=ParseMode.HTML); return

    if data.startswith("pick:"):
        _, action, sid = data.split(":")
        sec = get_section(sid)
        if not sec:
            await q.edit_message_text("⚠️ القسم غير موجود."); return

        if action == "upload":
            ctx.user_data["await"] = ("upload", sid)
            await q.edit_message_text(
                f"📤 أرسل الآن المحتوى إلى قسم <b>{sec['title']}</b>\n{LINE}\n"
                "🎬 فيديو • 🎧 صوت • 🖼 صورة • 📄 ملف • 🎙 بصمة • 🎞 GIF • 📝 نص\n"
                "يمكنك إرسال عدة عناصر متتالية، وعند الانتهاء أرسل /done",
                parse_mode=ParseMode.HTML)
        elif action == "rensec":
            ctx.user_data["await"] = ("rensec", sid)
            await q.edit_message_text(f"✏️ أرسل الاسم الجديد للقسم <b>{sec['title']}</b>", parse_mode=ParseMode.HTML)
        elif action == "delsec":
            DATA["sections"] = [s for s in DATA["sections"] if s["id"] != sid]
            save_data()
            await q.edit_message_text(f"🗑 تم حذف القسم.\n{LINE}", reply_markup=admin_kb())
        elif action == "manage":
            await q.edit_message_text(f"🧹 إدارة: {sec['title']}\n{LINE}", reply_markup=manage_items_kb(sec, 0))
        return

# ══════════════════ MESSAGES ══════════════════
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    u = note_user(update.effective_user)
    if u.get("banned"):
        return
    uid = update.effective_user.id
    text = (msg.text or "").strip()

    # ── حالات انتظار الأدمن ──
    waiting = ctx.user_data.get("await")
    if waiting and is_admin(uid):
        kind, payload = waiting

        if text == "/done":
            ctx.user_data.pop("await", None)
            await msg.reply_text(f"✅ تم الإنهاء.\n{LINE}", reply_markup=admin_kb()); return

        if kind == "upload":
            sec = get_section(payload)
            if not sec:
                ctx.user_data.pop("await", None)
                await msg.reply_text("⚠️ القسم غير موجود."); return
            t, fid, cap = detect_media(msg)
            if not t:
                await msg.reply_text("⚠️ نوع غير مدعوم."); return
            title = (cap or "بدون عنوان").split("\n")[0][:60]
            sec["items"].append({
                "id": next_id("i"), "type": t, "file_id": fid,
                "title": title, "caption": cap if t != "text" else "",
                "ts": int(time.time()),
            })
            save_data()
            await msg.reply_text(
                make_bold_unicode(f"✅ أُضيفت المادة إلى {sec['title']} ({len(sec['items'])})") +
                "\nأرسل التالي أو /done للإنهاء")
            return

        if kind == "addsec":
            DATA["sections"].append({"id": next_id("s"), "title": text or "قسم جديد", "desc": "", "items": []})
            save_data(); ctx.user_data.pop("await", None)
            await msg.reply_text(f"✅ تمت إضافة القسم: <b>{text}</b>", parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

        if kind == "rensec":
            sec = get_section(payload)
            if sec:
                sec["title"] = text or sec["title"]; save_data()
            ctx.user_data.pop("await", None)
            await msg.reply_text(f"✅ تم تغيير الاسم إلى: <b>{text}</b>", parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

        if kind == "renitem":
            sid, iid = payload
            sec = get_section(sid); it = get_item(sec, iid) if sec else None
            if it:
                it["title"] = text[:60]; save_data()
            ctx.user_data.pop("await", None)
            await msg.reply_text("✅ تم تعديل العنوان.", reply_markup=admin_kb()); return

        if kind == "txt":
            DATA[payload] = text; save_data(); ctx.user_data.pop("await", None)
            await msg.reply_text("✅ تم تحديث النص.", reply_markup=admin_kb()); return

        if kind == "label":
            DATA["labels"][payload] = text; save_data(); ctx.user_data.pop("await", None)
            await msg.reply_text("✅ تم تحديث اسم الزر.", reply_markup=main_kb(uid)); return

        if kind == "ban":
            tid = text.strip()
            tu = USERS.get(tid)
            if not tu:
                await msg.reply_text("⚠️ لم أجد هذا المستخدم."); return
            tu["banned"] = not tu.get("banned"); save_users(); ctx.user_data.pop("await", None)
            await msg.reply_text(f"{'🚫 تم الحظر' if tu['banned'] else '✅ تم فك الحظر'} — <code>{tid}</code>",
                                 parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

        if kind == "bc":
            ctx.user_data.pop("await", None)
            ok = fail = 0
            for key in list(USERS.keys()):
                try:
                    await ctx.bot.copy_message(int(key), msg.chat_id, msg.message_id)
                    ok += 1
                except Exception:
                    fail += 1
            await msg.reply_text(f"📣 تم البث\n{LINE}\n✅ {ok} • ❌ {fail}", reply_markup=admin_kb()); return

    # ── بحث ──
    if ctx.user_data.get("search"):
        ctx.user_data.pop("search", None)
        res = []
        for s in DATA["sections"]:
            for it in s["items"]:
                if text and text.lower() in (it["title"] + " " + (it.get("caption") or "")).lower():
                    res.append((s, it))
        if not res:
            await msg.reply_text(f"🔎 لا توجد نتائج لـ <b>{text}</b>", parse_mode=ParseMode.HTML); return
        rows = [[IB(make_bold_unicode(f"{TYPE_EMOJI.get(it['type'],'📎')} {it['title'][:40]} • {s['title']}"),
                    callback_data=f"itm:{s['id']}:{it['id']}:0", style="primary")] for s, it in res[:20]]
        await msg.reply_text(f"🔎 <b>نتائج البحث</b> ({len(res)})\n{LINE}", parse_mode=ParseMode.HTML,
                             reply_markup=InlineKeyboardMarkup(rows)); return

    # ── أزرار الكيبورد الرئيسية (تقارن بعد إزالة التنسيق) ──
    plain = text
    def eq(label):
        return plain in (label, make_bold_unicode(label))

    if eq(L("sections")):
        await msg.reply_text(sections_header(), parse_mode=ParseMode.HTML, reply_markup=sections_kb()); return
    if eq(L("about")):
        await msg.reply_text(f"ℹ️ <b>{make_bold_unicode('حول')}</b>\n{LINE}\n{DATA['about']}\n{LINE}",
                             parse_mode=ParseMode.HTML); return
    if eq(L("contact")):
        await msg.reply_text(f"📞 <b>{make_bold_unicode('تواصل')}</b>\n{LINE}\n{DATA['contact']}\n{LINE}",
                             parse_mode=ParseMode.HTML); return
    if eq(L("search")):
        ctx.user_data["search"] = True
        await msg.reply_text("🔎 أرسل كلمة البحث:"); return
    if eq(L("admin")) and is_admin(uid):
        await msg.reply_text(f"🛠 <b>{make_bold_unicode('لوحة الأدمن')}</b>\n{LINE}",
                             parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

    await msg.reply_text(welcome_text(), parse_mode=ParseMode.HTML, reply_markup=main_kb(uid))

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

# ══════════════════ MAIN ══════════════════
def main():
    if not BOT_TOKEN:
        raise SystemExit("⚠️ ضع BOT_TOKEN في أعلى الملف.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, on_message))
    log.info("Archive bot started ✅")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
