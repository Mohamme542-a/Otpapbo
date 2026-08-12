# ═══════════════════════════════════════════════════════════════
# 🗂 ARCHIVE BOT v3 — بوت أرشيف مؤسسة إعلامية (Telegram)
#   pip install "python-telegram-bot[job-queue]==21.6"
#   python archive_bot_v3.py
#
#   ✦ أقسام قابلة للتعديل بالكامل من لوحة الأدمن
#   ✦ رفع أي محتوى + قوائم متعددة الملفات (جودات) مع غلاف
#   ✦ 🆕 شريط متحرك (Marquee) للعناوين الطويلة
#   ✦ 🆕 نسخ احتياطي دائم واستعادة تلقائية (يحل مشكلة Render)
#   ✦ 🆕 15 ميزة إضافية (مفضلة، مشاهدات، روابط مشاركة، اشتراك إجباري…)
# ═══════════════════════════════════════════════════════════════
import json, logging, os, time, random, html, io
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, Update, InputFile,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

# ══════════════════ CONFIG (املأ هنا) ══════════════════
BOT_TOKEN = "8589967320:AAG_nrroMIc3dl2v4G339gSJPBqzmrpTMcY"          # ← ضع توكن البوت هنا
ADMIN_IDS = [8747566796]          # ← ضع ايدي الأدمن هنا مثال: [123456789]

# قناة/مجموعة خاصة تُحفظ فيها النسخ الاحتياطية تلقائياً (اجعل البوت أدمن فيها)
BACKUP_CHAT_ID = ""     # ← مثال: -1001234567890   (اتركه فارغاً لتعطيل النسخ التلقائي)

# مجلد التخزين: على Render أنشئ Persistent Disk وضع مساره هنا مثل /var/data
DATA_DIR = os.environ.get("DATA_DIR", ".")

BOT_USERNAME = ""       # ← اسم البوت بدون @ (لروابط المشاركة) اختياري

os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE  = os.path.join(DATA_DIR, "archive.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PAGE_SIZE  = 8          # عدد العناصر في الصفحة الواحدة

# إعدادات الشريط المتحرك للعناوين الطويلة
MARQUEE_WIDTH  = 100     # عدد الأحرف الظاهرة
MARQUEE_EVERY  = 1.4    # سرعة الحركة بالثواني
MARQUEE_TICKS  = 45
WRAP_MAX_LINES = 3      # أقصى عدد أسطر في وضع «النص الكامل»     # عدد الحركات قبل التوقف (توفير موارد)

AUTO_BACKUP_MIN = 20    # كل كم دقيقة تُرسل نسخة احتياطية

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger("archive")

# ══════════════════ TEXT BOLD HELPER ══════════════════
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
    try:
        return KeyboardButton(text, style=style) if style else KeyboardButton(text)
    except TypeError:
        return KeyboardButton(text)

def IB(text, style=None, **kw):
    try:
        return InlineKeyboardButton(text, style=style, **kw) if style else InlineKeyboardButton(text, **kw)
    except TypeError:
        return InlineKeyboardButton(text, **kw)

# ══════════════════ MARQUEE (شريط متحرك للنص الطويل) ══════════════════
GAP = "   •   "

# مخزن الشرائط النشطة: (chat_id, message_id) -> {"build":fn, "off":int, "tok":int}
MARQ = {}
VIEW_TOK = {}      # chat_id -> رقم العرض الحالي (لإبطال الشرائط القديمة)

def marquee_mode():
    m = S("marquee", "scroll")
    return m if m in ("scroll", "wrap", "off") else "scroll"

def new_view(chat_id):
    """يفتح عرضاً جديداً في المحادثة ويبطل كل الشرائط السابقة (يمنع الجليتش)."""
    VIEW_TOK[chat_id] = VIEW_TOK.get(chat_id, 0) + 1
    return VIEW_TOK[chat_id]

def stop_marquee(ctx, chat_id, message_id=None):
    """يوقف شرائط المحادثة (أو رسالة محددة) فوراً."""
    try:
        for key in list(MARQ.keys()):
            if key[0] == chat_id and (message_id is None or key[1] == message_id):
                MARQ.pop(key, None)
        jq = getattr(ctx, "job_queue", None)
        if jq is None:
            return
        for j in jq.jobs():
            d = getattr(j, "data", None) or {}
            k = d.get("key")
            if k and k[0] == chat_id and (message_id is None or k[1] == message_id):
                j.schedule_removal()
    except Exception as e:
        log.debug("stop_marquee: %s", e)

def wrap_label(text, width=MARQUEE_WIDTH):
    """يعرض النص كاملاً: السطر الأول عريض والبقية أسطر صغيرة تحته."""
    t = str(text).replace("\n", " ").strip()
    words, lines, cur = t.split(), [], ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur); cur = w
        while len(cur) > width:
            lines.append(cur[:width]); cur = cur[width:]
    if cur:
        lines.append(cur)
    lines = lines[:WRAP_MAX_LINES] or [t[:width]]
    head = make_bold_unicode(lines[0])
    rest = "\n".join(lines[1:])
    return head + ("\n" + rest if rest else "")

def scroll(text, offset=0, width=MARQUEE_WIDTH):
    """يعيد جزءاً من النص يتحرك كالشريط إن كان أطول من العرض المسموح."""
    t = str(text).replace("\n", " ").strip()
    if len(t) <= width:
        return t
    s2 = t + GAP
    off = offset % len(s2)
    return (s2 + s2)[off:off + width]

def btn(text, off=0, width=MARQUEE_WIDTH):
    """نص الزر النهائي حسب وضع العرض الذي اختاره الأدمن."""
    t = str(text).replace("\n", " ").strip()
    mode = marquee_mode()
    if len(t) <= width:
        return make_bold_unicode(t)
    if mode == "wrap":
        return wrap_label(t, width)
    if mode == "off":
        return make_bold_unicode(t[:width - 1] + "…")
    return make_bold_unicode(scroll(t, off, width))

def is_long(text, width=MARQUEE_WIDTH):
    return len(str(text).replace("\n", " ").strip()) > width

async def _marq_tick(ctx: ContextTypes.DEFAULT_TYPE):
    key = ctx.job.data["key"]
    st = MARQ.get(key)
    if not st:
        ctx.job.schedule_removal(); return
    # إبطال إن كان المستخدم انتقل لعرض آخر (سبب الجليتش سابقاً)
    if st.get("tok") != VIEW_TOK.get(key[0]):
        MARQ.pop(key, None); ctx.job.schedule_removal(); return
    if marquee_mode() != "scroll":
        MARQ.pop(key, None); ctx.job.schedule_removal(); return
    st["off"] += 1
    if st["off"] > MARQUEE_TICKS:
        MARQ.pop(key, None); ctx.job.schedule_removal(); return
    try:
        await ctx.bot.edit_message_reply_markup(
            chat_id=key[0], message_id=key[1], reply_markup=st["build"](st["off"]))
    except Exception:
        MARQ.pop(key, None); ctx.job.schedule_removal()

def start_marquee(ctx, message, build, texts):
    """يشغّل حركة النص إذا كان الوضع «شريط متحرك» وهناك عنوان طويل."""
    try:
        if not message or marquee_mode() != "scroll":
            return
        if not any(is_long(t) for t in texts):
            return
        jq = getattr(ctx, "job_queue", None)
        if jq is None:
            return
        chat_id = message.chat_id
        stop_marquee(ctx, chat_id)                 # شريط واحد فقط لكل محادثة
        tok = VIEW_TOK.get(chat_id) or new_view(chat_id)
        key = (chat_id, message.message_id)
        MARQ[key] = {"build": build, "off": 0, "tok": tok}
        jq.run_repeating(_marq_tick, interval=MARQUEE_EVERY, first=MARQUEE_EVERY,
                         data={"key": key}, name=f"marq:{key[0]}:{key[1]}")
    except Exception as e:
        log.debug("marquee skip: %s", e)

# ══════════════════ STORAGE ══════════════════
DEFAULT_DATA = {
    "brand": "المؤسسة الإعلامية",
    "flag": "🏴",
    "welcome": "السلام عليكم ورحمة الله وبركاته\nحيّاكم الله في أرشيف المؤسسة الإعلامية\nاختر القسم الذي تريده من الأزرار بالأسفل.",
    "about": "أرشيف رقمي يضم الإصدارات والأناشيد والكتب والإنفوغرافيك.",
    "contact": "للتواصل: @username",
    "labels": {
        "sections": "📚 الأقسام",
        "about": "ℹ️ حول",
        "contact": "📞 تواصل",
        "search": "🔎 بحث",
        "admin": "🛠️ لوحة الأدمن",
        "back": "🔙 رجوع",
        "fav": "⭐ المفضلة",
        "new": "🆕 الأحدث",
        "top": "🔥 الأكثر طلباً",
        "random": "🎲 عشوائي",
        "cart": "🧺 السلة",
        "tags": "🏷 الوسوم",
        "adv": "🔍 بحث متقدم",
        "leader": "🎖 المتصدرون",
        "hist": "🕓 آخر ما شاهدت",
        "feedback": "✉️ مراسلة الإدارة",
        "dltop": "🏆 الأكثر تحميلاً",
    },
    "sections": [
        {"id": "s1", "title": "🎬 إصدارات",   "desc": "", "items": []},
        {"id": "s2", "title": "🎙 أناشيد",    "desc": "", "items": []},
        {"id": "s3", "title": "📚 كتب",       "desc": "", "items": []},
        {"id": "s4", "title": "📊 إنفوغرافيك", "desc": "", "items": []},
    ],
    "admins": [],                 # أدمن إضافيون يُضافون من داخل البوت
    "settings": {
        "maintenance": False,     # وضع الصيانة
        "force_sub": "",          # @channel للاشتراك الإجباري
        "protect": False,         # منع إعادة التوجيه/الحفظ للمحتوى
        "marquee": "scroll",      # scroll | wrap | off  (وضع عرض العناوين الطويلة)
        "notify_new": False,      # إشعار المستخدمين بالجديد تلقائياً
        "daily_limit": 0,         # حد التنزيل اليومي لكل مستخدم (0 = بلا حد)
        "banner": "",             # شريط إعلان أعلى القوائم
    },
    "trash": [],                  # سلة المحذوفات
    "logs": [],                   # سجل نشاط
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
            for k, v in default.get("settings", {}).items():
                d["settings"].setdefault(k, v)
        return d
    except Exception:
        return json.loads(json.dumps(default))

DATA  = _load(DATA_FILE, DEFAULT_DATA)
USERS = _load(USERS_FILE, {})

def _atomic_write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

DIRTY = {"data": False, "users": False}

def save_data():
    _atomic_write(DATA_FILE, DATA)
    DIRTY["data"] = True          # ليُرسل في النسخة الاحتياطية القادمة

def save_users():
    _atomic_write(USERS_FILE, USERS)
    DIRTY["users"] = True

def add_log(txt):
    DATA.setdefault("logs", []).append({"t": int(time.time()), "x": txt[:200]})
    DATA["logs"] = DATA["logs"][-300:]
    save_data()

def next_id(prefix):
    DATA["seq"] = int(DATA.get("seq", 100)) + 1
    save_data()
    return f"{prefix}{DATA['seq']}"

def L(key):
    return DATA["labels"].get(key, key)

def is_admin(uid):
    return uid in ADMIN_IDS or uid in DATA.get("admins", [])

def S(key, default=None):
    return DATA.get("settings", {}).get(key, default)

def note_user(tgu):
    u = USERS.get(str(tgu.id))
    if not u:
        u = {"id": tgu.id, "name": tgu.first_name or "", "username": tgu.username or "",
             "banned": False, "joined": int(time.time()), "fav": [], "hits": 0}
        USERS[str(tgu.id)] = u
        save_users()
    u.setdefault("fav", []); u.setdefault("hits", 0)
    u["last"] = int(time.time())
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

def find_item(iid):
    for s in DATA["sections"]:
        for it in s["items"]:
            if it["id"] == iid:
                return s, it
    return None, None

def all_items():
    return [(s, it) for s in DATA["sections"] for it in s["items"]]

# ══════════════════ NAV / ANTI-SPAM ══════════════════
LAST_ACT = {}
def rate_ok(uid, gap=0.5):
    now = time.time()
    if now - LAST_ACT.get(uid, 0) < gap:
        return False
    LAST_ACT[uid] = now
    return True

# ══════════════════ TYPES ══════════════════
TYPE_EMOJI = {
    "video": "🎬", "audio": "🎧", "voice": "🎙", "photo": "🖼",
    "document": "📄", "animation": "🎞", "text": "📝", "pack": "🗂",
}

def detect_media(msg):
    if msg.video:     return "video", msg.video.file_id, msg.caption or (msg.video.file_name or "فيديو")
    if msg.audio:     return "audio", msg.audio.file_id, msg.caption or (msg.audio.title or msg.audio.file_name or "ملف صوتي")
    if msg.voice:     return "voice", msg.voice.file_id, msg.caption or "بصمة صوتية"
    if msg.photo:     return "photo", msg.photo[-1].file_id, msg.caption or "صورة"
    if msg.animation: return "animation", msg.animation.file_id, msg.caption or "صورة متحركة"
    if msg.document:  return "document", msg.document.file_id, msg.caption or (msg.document.file_name or "ملف")
    if msg.text:      return "text", None, msg.text
    return None, None, None

async def send_media(bot, chat_id, t, fid, cap, reply_markup=None):
    kw = dict(caption=cap, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    if S("protect"):
        kw["protect_content"] = True
    if   t == "video":     await bot.send_video(chat_id, fid, **kw)
    elif t == "audio":     await bot.send_audio(chat_id, fid, **kw)
    elif t == "voice":     await bot.send_voice(chat_id, fid, **kw)
    elif t == "photo":     await bot.send_photo(chat_id, fid, **kw)
    elif t == "animation": await bot.send_animation(chat_id, fid, **kw)
    elif t == "document":  await bot.send_document(chat_id, fid, **kw)
    else:
        await bot.send_message(chat_id, cap, parse_mode=ParseMode.HTML, reply_markup=reply_markup,
                               protect_content=bool(S("protect")))

def share_link(iid):
    return f"https://t.me/{BOT_USERNAME}?start=it_{iid}" if BOT_USERNAME else ""

async def send_item(bot, chat_id, item, reply_markup=None):
    t, fid = item["type"], item.get("file_id")
    cap = f"{TYPE_EMOJI.get(t,'📎')} <b>{make_bold_unicode(item.get('title',''))}</b>"
    if item.get("caption"):
        cap += f"\n{LINE}\n{item['caption']}"
    lnk = share_link(item["id"])
    if lnk:
        cap += f"\n{LINE}\n🔗 {lnk}"
    item["views"] = int(item.get("views", 0)) + 1
    save_data()
    await send_media(bot, chat_id, t, fid, cap, reply_markup)

async def send_pack_file(bot, chat_id, item, f, reply_markup=None):
    cap = (f"{TYPE_EMOJI.get(f.get('type'),'📎')} <b>{make_bold_unicode(f.get('label',''))}</b>\n"
           f"{LINE}\n🗂 {make_bold_unicode(item.get('title',''))}")
    item["views"] = int(item.get("views", 0)) + 1
    save_data()
    await send_media(bot, chat_id, f.get("type"), f.get("file_id"), cap, reply_markup)

def _has_media(m):
    return bool(m and (m.photo or m.video or m.document or m.audio or m.animation or m.voice))

async def safe_edit(q, text, parse_mode=ParseMode.HTML, reply_markup=None):
    """تعديل آمن يعمل مع النصوص والوسائط — يعيد الرسالة الناتجة."""
    m = q.message
    if m is not None and not _has_media(m):
        try:
            await q.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            return m
        except Exception as e:
            log.debug("safe_edit fallback: %s", e)
    try:
        await m.delete()
    except Exception:
        pass
    try:
        return await q.get_bot().send_message(m.chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        log.warning("safe_edit send failed: %s", e)
        return None

# ══════════════════ KEYBOARDS ══════════════════
def main_kb(uid):
    rows = [[_kb_btn(make_bold_unicode(L("sections")), style="danger")]]
    rows.append([
        _kb_btn(make_bold_unicode(L("new")), style="primary"),
        _kb_btn(make_bold_unicode(L("top")), style="primary"),
        _kb_btn(make_bold_unicode(L("random")), style="primary"),
    ])
    rows.append([
        _kb_btn(make_bold_unicode(L("fav")), style="success"),
        _kb_btn(make_bold_unicode(L("search")), style="success"),
    ])
    rows.append([
        _kb_btn(make_bold_unicode(L("cart")), style="primary"),
        _kb_btn(make_bold_unicode(L("tags")), style="primary"),
        _kb_btn(make_bold_unicode(L("adv")), style="primary"),
    ])
    rows.append([
        _kb_btn(make_bold_unicode(L("dltop")), style="success"),
        _kb_btn(make_bold_unicode(L("leader")), style="success"),
        _kb_btn(make_bold_unicode(L("hist")), style="success"),
    ])
    rows.append([_kb_btn(make_bold_unicode(L("feedback")), style="primary")])
    row = [
        _kb_btn(make_bold_unicode(L("about")), style="primary"),
        _kb_btn(make_bold_unicode(L("contact")), style="primary"),
    ]
    if is_admin(uid):
        row.append(_kb_btn(make_bold_unicode(L("admin")), style="danger"))
    rows.append(row)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def sections_kb(off=0, uid=None):
    rows = []
    for s in visible_sections(uid):
        n = len(pub_items(s)) if not is_admin(uid or 0) else len(s["items"])
        label = f"{s['title']}  •  {n}" + ("  🔐" if s.get("pw") else "") + ("  🙈" if s.get("hidden") else "")
        rows.append([IB(btn(label, off), callback_data=f"sec:{s['id']}:0", style="primary")])
    if not rows:
        rows.append([IB(make_bold_unicode("لا توجد أقسام بعد"), callback_data="noop")])
    return InlineKeyboardMarkup(rows)

def item_label(it):
    extra = f"  •  {len(it.get('files', []))} ملفات" if it["type"] == "pack" else ""
    pin = "📌 " if it.get("pin") else ""
    return f"{pin}{TYPE_EMOJI.get(it['type'],'📎')} {it['title']}{extra}"

def visible_sections(uid=None):
    if uid is not None and is_admin(uid):
        return DATA["sections"]
    return [s for s in DATA["sections"] if not s.get("hidden")]

def pub_items(sec):
    """المواد الظاهرة للمستخدم: غير مخفية وحان وقت نشرها."""
    now = int(time.time())
    return [it for it in sorted_items(sec)
            if not it.get("hidden") and int(it.get("publish_at") or 0) <= now]

def item_rating(it):
    r = it.get("rate") or {}
    if not r:
        return 0.0, 0
    vals = [int(v) for v in r.values()]
    return round(sum(vals) / len(vals), 1), len(vals)

def note_dl(it):
    it["dl"] = int(it.get("dl", 0)) + 1
    it["dlog"] = ([*(it.get("dlog") or []), int(time.time())])[-300:]
    save_data()

def dl_week(it):
    wk = int(time.time()) - 7 * 86400
    return sum(1 for t in (it.get("dlog") or []) if t > wk)

def dl_ok(uid):
    lim = int(S("daily_limit", 0) or 0)
    if lim <= 0 or is_admin(uid):
        return True
    u = USERS.get(str(uid)) or {}
    today = time.strftime("%Y-%m-%d")
    if u.get("dl_day") != today:
        u["dl_day"], u["dl_cnt"] = today, 0
    if int(u.get("dl_cnt", 0)) >= lim:
        return False
    u["dl_cnt"] = int(u.get("dl_cnt", 0)) + 1
    save_users()
    return True

def award(uid, pts=1):
    u = USERS.get(str(uid))
    if not u:
        return
    u["points"] = int(u.get("points", 0)) + pts
    save_users()

def level_of(points):
    for i, need in enumerate([0, 10, 30, 60, 120, 250, 500], start=1):
        if points < need:
            return max(1, i - 1)
    return 7

def note_hist(uid, iid):
    u = USERS.get(str(uid))
    if not u:
        return
    h = [x for x in (u.get("hist") or []) if x != iid]
    h.insert(0, iid)
    u["hist"] = h[:15]
    save_users()

def all_tags():
    tags = {}
    for s, it in all_items():
        for t in (it.get("tags") or []):
            tags[t] = tags.get(t, 0) + 1
    return dict(sorted(tags.items(), key=lambda kv: -kv[1]))

def sorted_items(sec):
    return sorted(sec["items"], key=lambda i: (0 if i.get("pin") else 1, -int(i.get("ts", 0))))

def items_kb(sec, page, off=0):
    items = pub_items(sec)
    pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    rows = []
    for it in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        rows.append([IB(btn(item_label(it), off),
                        callback_data=f"itm:{sec['id']}:{it['id']}:{page}", style="primary")])
    nav = []
    if page > 0:            nav.append(IB("◀️", callback_data=f"sec:{sec['id']}:{page-1}", style="primary"))
    nav.append(IB(f"{page+1}/{pages}", callback_data="noop"))
    if page < pages - 1:    nav.append(IB("▶️", callback_data=f"sec:{sec['id']}:{page+1}", style="primary"))
    if len(nav) > 1: rows.append(nav)
    rows.append([IB(make_bold_unicode("🔎 بحث داخل القسم"), callback_data=f"ssrch:{sec['id']}", style="success")])
    rows.append([IB(make_bold_unicode(L("back")), callback_data="sections", style="danger")])
    return InlineKeyboardMarkup(rows)

def items_texts(sec, page):
    items = pub_items(sec)
    return [item_label(it) for it in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]]

def item_kb(sid, page, uid, iid):
    fav = iid in USERS.get(str(uid), {}).get("fav", [])
    incart = iid in (USERS.get(str(uid), {}).get("cart") or [])
    _s, _it = find_item(iid)
    avg, cnt = item_rating(_it) if _it else (0, 0)
    rows = [[
        IB(make_bold_unicode("💔 إزالة من المفضلة" if fav else "⭐ أضف للمفضلة"),
           callback_data=f"fav:{iid}", style="success"),
        IB(make_bold_unicode("🧺 إزالة من السلة" if incart else "🧺 أضف للسلة"),
           callback_data=f"cart:{iid}", style="primary"),
    ]]
    rows.append([IB(make_bold_unicode(f"⭐ التقييم {avg}/5 ({cnt})"), callback_data="noop", style="primary")])
    rows.append([IB(str(n) + "⭐", callback_data=f"rate:{iid}:{n}", style="success") for n in range(1, 6)])
    rows.append([IB(make_bold_unicode("🔁 مواد مشابهة"), callback_data=f"sim:{sid}:{iid}", style="primary"),
                 IB(make_bold_unicode("🔗 مشاركة"), callback_data=f"shr:{iid}", style="primary")])
    if is_admin(uid):
        rows.append([
            IB(make_bold_unicode("📌 تثبيت/إلغاء"), callback_data=f"pin:{sid}:{iid}", style="primary"),
            IB(make_bold_unicode("🗑 حذف"), callback_data=f"adm:delitem:{sid}:{iid}", style="danger"),
        ])
    rows.append([IB(make_bold_unicode(L("back")), callback_data=f"sec:{sid}:{page}", style="danger")])
    return InlineKeyboardMarkup(rows)

def pack_kb(sec, item, page, uid, off=0):
    rows = []
    for idx, f in enumerate(item.get("files", [])):
        lbl = f"{TYPE_EMOJI.get(f.get('type'),'📎')} {f.get('label','')}"
        rows.append([IB(btn(lbl, off),
                        callback_data=f"pf:{sec['id']}:{item['id']}:{idx}:{page}", style="primary")])
    if not rows:
        rows.append([IB(make_bold_unicode("لا توجد ملفات في هذه القائمة"), callback_data="noop")])
    else:
        rows.append([IB(make_bold_unicode("📥 إرسال كل الملفات"),
                        callback_data=f"pall:{sec['id']}:{item['id']}:{page}", style="success")])
    fav = item["id"] in USERS.get(str(uid), {}).get("fav", [])
    incart = item["id"] in (USERS.get(str(uid), {}).get("cart") or [])
    rows.append([IB(make_bold_unicode("💔 إزالة من المفضلة" if fav else "⭐ أضف للمفضلة"),
                    callback_data=f"fav:{item['id']}", style="success"),
                 IB(make_bold_unicode("🧺 إزالة من السلة" if incart else "🧺 أضف للسلة"),
                    callback_data=f"cart:{item['id']}", style="primary")])
    if is_admin(uid):
        rows.append([IB(make_bold_unicode("➕ إضافة ملفات"), callback_data=f"padd:{sec['id']}:{item['id']}", style="success"),
                     IB(make_bold_unicode("🧹 إدارة الملفات"), callback_data=f"pmng:{sec['id']}:{item['id']}", style="primary")])
        rows.append([IB(make_bold_unicode("🖼 تعيين / تغيير الغلاف"), callback_data=f"pcov:{sec['id']}:{item['id']}", style="primary"),
                     IB(make_bold_unicode("📌 تثبيت/إلغاء"), callback_data=f"pin:{sec['id']}:{item['id']}", style="primary")])
    rows.append([IB(make_bold_unicode(L("back")), callback_data=f"sec:{sec['id']}:{page}", style="danger")])
    return InlineKeyboardMarkup(rows)

def pack_files_admin_kb(sec, item):
    rows = []
    for idx, f in enumerate(item.get("files", [])):
        rows.append([
            IB(make_bold_unicode(f"{TYPE_EMOJI.get(f.get('type'),'📎')} {str(f.get('label',''))[:28]}"), callback_data="noop"),
            IB("🔼", callback_data=f"pmv:{sec['id']}:{item['id']}:{idx}:up", style="success"),
            IB("🔽", callback_data=f"pmv:{sec['id']}:{item['id']}:{idx}:dn", style="primary"),
            IB("✏️", callback_data=f"pren:{sec['id']}:{item['id']}:{idx}", style="primary"),
            IB("🗑", callback_data=f"pdel:{sec['id']}:{item['id']}:{idx}", style="danger"),
        ])
    rows.append([IB(make_bold_unicode("➕ إضافة ملفات"), callback_data=f"padd:{sec['id']}:{item['id']}", style="success")])
    rows.append([IB(make_bold_unicode(L("back")), callback_data=f"itm:{sec['id']}:{item['id']}:0", style="danger")])
    return InlineKeyboardMarkup(rows)

def pack_header(sec, item):
    lnk = share_link(item["id"])
    return (f"🗂 <b>{make_bold_unicode(item.get('title',''))}</b>\n{LINE}\n"
            f"{item.get('caption') or 'اختر الجودة التي تريدها 👇'}\n"
            f"📦 عدد الملفات: <b>{len(item.get('files', []))}</b> • 👁 <b>{item.get('views',0)}</b>\n"
            + (f"🔗 {lnk}\n" if lnk else "") + LINE)

async def show_pack(ctx, q, sec, it, page, uid):
    head = pack_header(sec, it)
    build = lambda off=0: pack_kb(sec, it, page, uid, off)
    texts = [f.get("label", "") for f in it.get("files", [])]
    cover = it.get("cover")
    m = q.message
    if cover:
        try:
            await m.delete()
        except Exception:
            pass
        msg = await q.get_bot().send_photo(m.chat_id, cover, caption=head,
                                           parse_mode=ParseMode.HTML, reply_markup=build(0))
    else:
        msg = await safe_edit(q, head, reply_markup=build(0))
    start_marquee(ctx, msg, build, texts)

def admin_kb():
    st = DATA.get("settings", {})
    rows = [
        [IB(make_bold_unicode("📤 رفع محتوى لقسم"), callback_data="adm:upload", style="success")],
        [IB(make_bold_unicode("🗂 إنشاء قائمة متعددة الملفات"), callback_data="adm:pack", style="success")],
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
        [IB(make_bold_unicode("💾 نسخة احتياطية الآن"), callback_data="adm:backup", style="success"),
         IB(make_bold_unicode("♻️ استعادة نسخة"), callback_data="adm:restore", style="danger")],
        [IB(make_bold_unicode("👑 إضافة أدمن"), callback_data="adm:addadmin", style="primary"),
         IB(make_bold_unicode("🗒 سجل النشاط"), callback_data="adm:logs", style="primary")],
        [IB(make_bold_unicode(("🔧 الصيانة: تعمل" if st.get("maintenance") else "🔧 الصيانة: متوقفة")),
            callback_data="adm:tg:maintenance", style="danger"),
         IB(make_bold_unicode(("🔒 الحماية: مفعّلة" if st.get("protect") else "🔓 الحماية: متوقفة")),
            callback_data="adm:tg:protect", style="primary")],
        [IB(make_bold_unicode("📢 الاشتراك الإجباري"), callback_data="adm:forcesub", style="primary")],
        [IB(make_bold_unicode({"scroll": "🎞 العناوين: شريط متحرك", "wrap": "📃 العناوين: نص كامل",
                               "off": "⏹ العناوين: بلا حركة"}[(st.get("marquee") or "scroll")]),
            callback_data="adm:marq", style="success")],
        [IB(make_bold_unicode("🔔 إشعار الجديد: يعمل" if st.get("notify_new") else "🔕 إشعار الجديد: متوقف"),
            callback_data="adm:tg:notify_new", style="primary"),
         IB(make_bold_unicode(f"🚦 حد التنزيل: {st.get('daily_limit', 0) or 'بلا حد'}"),
            callback_data="adm:limit", style="primary")],
        [IB(make_bold_unicode("📌 شريط الإعلان"), callback_data="adm:banner", style="primary"),
         IB(make_bold_unicode("⚡ رفع مجمّع سريع"), callback_data="adm:bulk", style="success")],
        [IB(make_bold_unicode("♻️ سلة المحذوفات"), callback_data="adm:trash", style="danger"),
         IB(make_bold_unicode("🎖 المتصدرون"), callback_data="adm:leader", style="primary")],
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
    for s in DATA["sections"]:
        rows.append([
            IB("🔼", callback_data=f"mv:up:{s['id']}", style="success"),
            IB(make_bold_unicode(s["title"]), callback_data="noop"),
            IB("🔽", callback_data=f"mv:dn:{s['id']}", style="danger"),
        ])
    rows.append([IB(make_bold_unicode(L("back")), callback_data="adm:panel", style="danger")])
    return InlineKeyboardMarkup(rows)

def manage_items_kb(sec, page=0):
    items = sorted_items(sec)
    pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    rows = []
    for it in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        rows.append([
            IB(make_bold_unicode(f"{TYPE_EMOJI.get(it['type'],'📎')} {it['title'][:28]}"), callback_data="noop"),
            IB("📌", callback_data=f"pin:{sec['id']}:{it['id']}", style="success"),
            IB("✏️", callback_data=f"ren:{sec['id']}:{it['id']}", style="primary"),
            IB("↔️", callback_data=f"mvitem:{sec['id']}:{it['id']}", style="primary"),
            IB("🗑", callback_data=f"adm:delitem:{sec['id']}:{it['id']}", style="danger"),
        ])
        rows.append([
            IB("🏷 وسوم", callback_data=f"tag:{sec['id']}:{it['id']}", style="primary"),
            IB("🙈 إظهار" if it.get("hidden") else "🙈 إخفاء", callback_data=f"hid:{sec['id']}:{it['id']}", style="primary"),
            IB("⏰ جدولة", callback_data=f"sch:{sec['id']}:{it['id']}", style="primary"),
            IB("📑 نسخ", callback_data=f"cpitem:{sec['id']}:{it['id']}", style="success"),
        ])
    nav = []
    if page > 0:         nav.append(IB("◀️", callback_data=f"mng:{sec['id']}:{page-1}", style="primary"))
    nav.append(IB(f"{page+1}/{pages}", callback_data="noop"))
    if page < pages - 1: nav.append(IB("▶️", callback_data=f"mng:{sec['id']}:{page+1}", style="primary"))
    if len(nav) > 1: rows.append(nav)
    rows.append([IB(make_bold_unicode("📄 تصدير قائمة القسم"), callback_data=f"mngexp:{sec['id']}", style="success"),
                 IB(make_bold_unicode("📊 إحصائيات القسم"), callback_data=f"secst:{sec['id']}", style="primary")])
    rows.append([IB(make_bold_unicode("🔐 قفل/فتح القسم"), callback_data=f"secpw:{sec['id']}", style="danger"),
                 IB(make_bold_unicode("🙈 إخفاء/إظهار القسم"), callback_data=f"sechid:{sec['id']}", style="primary")])
    rows.append([IB(make_bold_unicode(L("back")), callback_data="adm:panel", style="danger")])
    return InlineKeyboardMarkup(rows)

def results_kb(pairs, off=0, back="sections"):
    rows = [[IB(btn(f"{TYPE_EMOJI.get(it['type'],'📎')} {it['title']} • {s['title']}", off),
                callback_data=f"itm:{s['id']}:{it['id']}:0", style="primary")] for s, it in pairs]
    if not rows:
        rows.append([IB(make_bold_unicode("لا توجد نتائج"), callback_data="noop")])
    rows.append([IB(make_bold_unicode(L("back")), callback_data=back, style="danger")])
    return InlineKeyboardMarkup(rows)

# ══════════════════ HEADERS ══════════════════
def welcome_text():
    return (f"{DATA.get('flag','🏴')} <b>{make_bold_unicode(DATA['brand'])}</b> {DATA.get('flag','🏴')}\n"
            f"{LINE}\n{DATA['welcome']}\n{LINE}")

def sections_header():
    total = sum(len(s["items"]) for s in DATA["sections"])
    ban = (S("banner") or "").strip()
    top = (f"📌 <b>{html.escape(ban)}</b>\n{LINE}\n" if ban else "")
    return (top + f"📚 <b>{make_bold_unicode('أقسام الأرشيف')}</b>\n{LINE}\n"
            f"🗂 الأقسام: <b>{len(DATA['sections'])}</b> • 📦 المواد: <b>{total}</b>\n{LINE}")

# ══════════════════ BACKUP / RESTORE ══════════════════
async def do_backup(bot, chat_id=None, force=False):
    target = chat_id or BACKUP_CHAT_ID
    if not target:
        return False
    if not force and not (DIRTY["data"] or DIRTY["users"]):
        return False
    try:
        stamp = time.strftime("%Y-%m-%d %H:%M")
        for path, name in ((DATA_FILE, "archive.json"), (USERS_FILE, "users.json")):
            if not os.path.exists(path):
                continue
            with open(path, "rb") as f:
                await bot.send_document(target, InputFile(f, filename=name),
                                        caption=f"💾 نسخة احتياطية • {stamp}")
        DIRTY["data"] = DIRTY["users"] = False
        return True
    except Exception as e:
        log.warning("backup failed: %s", e)
        return False

async def job_backup(ctx: ContextTypes.DEFAULT_TYPE):
    await do_backup(ctx.bot)

def apply_restore(payload, kind):
    global DATA, USERS
    if kind == "data":
        DATA.clear(); DATA.update(_load_obj(payload, DEFAULT_DATA)); save_data()
    else:
        USERS.clear(); USERS.update(payload); save_users()

def _load_obj(d, default):
    for k, v in default.items():
        d.setdefault(k, v)
    for k, v in default.get("labels", {}).items():
        d["labels"].setdefault(k, v)
    for k, v in default.get("settings", {}).items():
        d["settings"].setdefault(k, v)
    return d

async def notify_new(bot, sec, it):
    """إشعار المستخدمين بالمادة الجديدة إن كان الإشعار مفعّلاً."""
    if not S("notify_new"):
        return
    txt = (f"🆕 <b>{make_bold_unicode('جديد في الأرشيف')}</b>\n{LINE}\n"
           f"{TYPE_EMOJI.get(it['type'],'📎')} <b>{html.escape(it.get('title',''))}</b>\n"
           f"🗂 {html.escape(sec['title'])}\n{LINE}")
    kb = InlineKeyboardMarkup([[IB(make_bold_unicode("📂 اذهب للمادة"),
                                   callback_data=f"itm:{sec['id']}:{it['id']}:0", style="success")]])
    for key, u in list(USERS.items()):
        if u.get("banned") or u.get("mute_new"):
            continue
        try:
            await bot.send_message(int(key), txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception:
            pass

# ══════════════════ FORCE SUBSCRIBE ══════════════════
async def sub_ok(bot, uid):
    ch = (S("force_sub") or "").strip()
    if not ch:
        return True
    if not ch.startswith("@") and not ch.startswith("-100"):
        ch = "@" + ch
    try:
        m = await bot.get_chat_member(ch, uid)
        return m.status in ("member", "administrator", "creator", "owner")
    except Exception:
        return True

def sub_kb():
    ch = (S("force_sub") or "").lstrip("@")
    return InlineKeyboardMarkup([
        [IB(make_bold_unicode("📢 اشترك في القناة"), url=f"https://t.me/{ch}", style="primary")],
        [IB(make_bold_unicode("✅ تحققت، تابع"), callback_data="checksub", style="success")],
    ])

# ══════════════════ COMMANDS ══════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = note_user(update.effective_user)
    if u.get("banned"):
        return
    uid = update.effective_user.id
    if S("maintenance") and not is_admin(uid):
        await update.message.reply_text("🔧 البوت في وضع الصيانة مؤقتاً، جزاكم الله خيراً على صبركم.")
        return
    if not await sub_ok(ctx.bot, uid):
        await update.message.reply_text("📢 للاستفادة من الأرشيف يرجى الاشتراك في القناة أولاً:",
                                        reply_markup=sub_kb()); return
    # رابط مشاركة عميق: /start it_i123
    args = ctx.args or []
    if args and args[0].startswith("it_"):
        iid = args[0][3:]
        s, it = find_item(iid)
        if it:
            if it["type"] == "pack":
                head = pack_header(s, it)
                kb = pack_kb(s, it, 0, uid)
                if it.get("cover"):
                    await ctx.bot.send_photo(update.effective_chat.id, it["cover"], caption=head,
                                             parse_mode=ParseMode.HTML, reply_markup=kb)
                else:
                    await update.message.reply_text(head, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await send_item(ctx.bot, update.effective_chat.id, it, item_kb(s["id"], 0, uid, iid))
            return
    if args and args[0].startswith("sec_"):
        sec = get_section(args[0][4:])
        if sec and not sec.get("hidden"):
            head = f"{sec['title']}\n{LINE}\n{sec.get('desc') or 'اختر المادة التي تريدها 👇'}\n{LINE}"
            m = await update.message.reply_text(head, parse_mode=ParseMode.HTML, reply_markup=items_kb(sec, 0, 0))
            start_marquee(ctx, m, lambda off=0: items_kb(sec, 0, off), items_texts(sec, 0))
            return
    who = ("@" + update.effective_user.username) if update.effective_user.username else (update.effective_user.first_name or "زائرنا")
    await update.message.reply_text(
        f"{welcome_text()}\n\n🌿 <b>{make_bold_unicode('السلام عليكم ورحمة الله وبركاته')}</b>\n<b>{make_bold_unicode(who)}</b>",
        parse_mode=ParseMode.HTML, reply_markup=main_kb(uid))

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(f"🛠 <b>{make_bold_unicode('لوحة الأدمن')}</b>\n{LINE}",
                                    parse_mode=ParseMode.HTML, reply_markup=admin_kb())

async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 <code>{update.effective_user.id}</code>", parse_mode=ParseMode.HTML)

async def cmd_backup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    ok = await do_backup(ctx.bot, chat_id=update.effective_chat.id, force=True)
    if BACKUP_CHAT_ID:
        await do_backup(ctx.bot, force=True)
    await update.message.reply_text("💾 تم إرسال النسخة الاحتياطية." if ok else "⚠️ تعذّر إنشاء النسخة.")

async def cmd_restore(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    ctx.user_data["await"] = ("restore", None)
    await update.message.reply_text(
        f"♻️ أرسل الآن ملف <b>archive.json</b> (أو users.json) لاستعادته.\n{LINE}\n"
        "يمكنك إعادة توجيه الملف من قناة النسخ الاحتياطي مباشرة.", parse_mode=ParseMode.HTML)

# ══════════════════ CALLBACKS ══════════════════
async def on_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    data = q.data or ""
    await q.answer()

    if data == "noop":
        return
    # إبطال أي شريط متحرك قديم قبل أي انتقال (إصلاح جليتش الرجوع)
    try:
        if q.message:
            stop_marquee(ctx, q.message.chat_id)
            new_view(q.message.chat_id)
    except Exception:
        pass
    if not rate_ok(uid, 0.3):
        return
    if S("maintenance") and not is_admin(uid):
        await q.answer("🔧 البوت في وضع الصيانة", show_alert=True); return

    if data == "checksub":
        if await sub_ok(ctx.bot, uid):
            await safe_edit(q, "✅ جزاك الله خيراً، يمكنك الآن استخدام الأرشيف.")
            await ctx.bot.send_message(q.message.chat_id, welcome_text(), parse_mode=ParseMode.HTML,
                                       reply_markup=main_kb(uid))
        else:
            await q.answer("⚠️ لم أجد اشتراكك بعد", show_alert=True)
        return
    if not await sub_ok(ctx.bot, uid):
        await safe_edit(q, "📢 يرجى الاشتراك في القناة أولاً:", reply_markup=sub_kb()); return

    # ── القوائم العامة ──
    if data == "sections":
        msg = await safe_edit(q, sections_header(), reply_markup=sections_kb(0, uid))
        start_marquee(ctx, msg, lambda off=0: sections_kb(off, uid),
                      [f"{s['title']} • {len(s['items'])}" for s in DATA["sections"]])
        return

    if data.startswith("sec:"):
        _, sid, page = data.split(":")
        sec = get_section(sid)
        if not sec:
            await safe_edit(q, "⚠️ القسم غير موجود."); return
        if sec.get("hidden") and not is_admin(uid):
            await q.answer("🙈 هذا القسم غير متاح حالياً", show_alert=True); return
        if sec.get("pw") and not is_admin(uid) and sid not in (ctx.user_data.get("unlocked") or []):
            ctx.user_data["unlock"] = sid
            await safe_edit(q, f"🔐 <b>{make_bold_unicode('قسم مقفل')}</b>\n{LINE}\nأرسل كلمة المرور للدخول:"); return
        page = int(page)
        head = (f"{sec['title']}\n{LINE}\n"
                f"{sec.get('desc') or 'اختر المادة التي تريدها 👇'}\n"
                f"📦 العدد: <b>{len(sec['items'])}</b>\n{LINE}")
        msg = await safe_edit(q, head, reply_markup=items_kb(sec, page, 0))
        start_marquee(ctx, msg, lambda off=0: items_kb(sec, page, off), items_texts(sec, page))
        return

    if data.startswith("ssrch:"):
        sid = data.split(":")[1]
        ctx.user_data["search"] = sid
        await safe_edit(q, "🔎 أرسل كلمة البحث داخل هذا القسم:"); return

    if data.startswith("itm:"):
        _, sid, iid, page = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        if not it:
            await q.answer("⚠️ العنصر محذوف", show_alert=True); return
        if it.get("hidden") and not is_admin(uid):
            await q.answer("🙈 هذه المادة غير متاحة", show_alert=True); return
        if int(it.get("publish_at") or 0) > int(time.time()) and not is_admin(uid):
            await q.answer("⏰ سيُنشر قريباً إن شاء الله", show_alert=True); return
        if it["type"] == "pack":
            note_hist(uid, iid)
            await show_pack(ctx, q, sec, it, int(page), uid)
            return
        if not dl_ok(uid):
            await q.answer("🚦 بلغت حدّك اليومي، عد غداً بإذن الله", show_alert=True); return
        note_hist(uid, iid); note_dl(it); award(uid, 1)
        await send_item(ctx.bot, q.message.chat_id, it, item_kb(sid, int(page), uid, iid))
        return

    if data.startswith("fav:"):
        iid = data.split(":")[1]
        u = USERS.get(str(uid))
        if not u:
            return
        fav = u.setdefault("fav", [])
        if iid in fav:
            fav.remove(iid); await q.answer("💔 أُزيلت من المفضلة", show_alert=False)
        else:
            fav.append(iid); await q.answer("⭐ أُضيفت للمفضلة", show_alert=False)
        save_users(); return

    if data.startswith("pf:"):
        _, sid, iid, idx, page = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        files = it.get("files", []) if it else []
        if not files or int(idx) >= len(files):
            await q.answer("⚠️ الملف غير موجود", show_alert=True); return
        if not dl_ok(uid):
            await q.answer("🚦 بلغت حدّك اليومي، عد غداً بإذن الله", show_alert=True); return
        note_dl(it); award(uid, 1)
        await send_pack_file(ctx.bot, q.message.chat_id, it, files[int(idx)])
        return

    if data.startswith("pall:"):
        _, sid, iid, page = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        files = it.get("files", []) if it else []
        if not files:
            await q.answer("⚠️ لا توجد ملفات", show_alert=True); return
        if not dl_ok(uid):
            await q.answer("🚦 بلغت حدّك اليومي، عد غداً بإذن الله", show_alert=True); return
        note_dl(it); award(uid, 2)
        for f in files:
            try:
                await send_pack_file(ctx.bot, q.message.chat_id, it, f)
            except Exception as e:
                log.warning("send pack file failed: %s", e)
        return

    if data.startswith("cart:"):
        iid = data.split(":")[1]
        u = USERS.get(str(uid))
        if not u:
            return
        c = u.setdefault("cart", [])
        if iid in c:
            c.remove(iid); await q.answer("🧺 أُزيلت من السلة")
        else:
            c.append(iid); await q.answer("🧺 أُضيفت للسلة")
        save_users(); return

    if data == "cart:send":
        u = USERS.get(str(uid)) or {}
        ids = list(u.get("cart") or [])
        if not ids:
            await q.answer("🧺 السلة فارغة", show_alert=True); return
        if not dl_ok(uid):
            await q.answer("🚦 بلغت حدّك اليومي", show_alert=True); return
        for iid in ids:
            s2, it2 = find_item(iid)
            if not it2:
                continue
            try:
                if it2["type"] == "pack":
                    for f in it2.get("files", []):
                        await send_pack_file(ctx.bot, q.message.chat_id, it2, f)
                else:
                    await send_item(ctx.bot, q.message.chat_id, it2)
                note_dl(it2)
            except Exception as e:
                log.warning("cart send: %s", e)
        award(uid, len(ids))
        await q.answer("📥 تم إرسال محتويات السلة"); return

    if data == "cart:clear":
        u = USERS.get(str(uid))
        if u:
            u["cart"] = []; save_users()
        await safe_edit(q, "🧺 تم تفريغ السلة."); return

    if data.startswith("rate:"):
        _, iid, n = data.split(":")
        s2, it2 = find_item(iid)
        if not it2:
            return
        it2.setdefault("rate", {})[str(uid)] = int(n)
        save_data(); award(uid, 1)
        avg, cnt = item_rating(it2)
        await q.answer(f"⭐ شكراً لك — المعدل الآن {avg}/5 من {cnt} تقييم", show_alert=True); return

    if data.startswith("shr:"):
        iid = data.split(":")[1]
        lnk = share_link(iid)
        await q.answer(lnk or "⚠️ ضع BOT_USERNAME في الكود لتفعيل الروابط", show_alert=True); return

    if data.startswith("sim:"):
        _, sid, iid = data.split(":")
        s2, it2 = find_item(iid)
        pool = []
        tags = set((it2.get("tags") or []) if it2 else [])
        for ss, ii in all_items():
            if ii["id"] == iid or ii.get("hidden"):
                continue
            score = (2 if ss["id"] == sid else 0) + len(tags & set(ii.get("tags") or []))
            if score:
                pool.append((score, ss, ii))
        pool.sort(key=lambda x: -x[0])
        pairs = [(ss, ii) for _, ss, ii in pool[:10]]
        m = await ctx.bot.send_message(q.message.chat_id, f"🔁 <b>{make_bold_unicode('مواد مشابهة')}</b>\n{LINE}",
                                       parse_mode=ParseMode.HTML, reply_markup=results_kb(pairs, 0))
        start_marquee(ctx, m, lambda off=0: results_kb(pairs, off), [f"{i['title']}" for _, i in pairs]); return

    if data.startswith("tagq:"):
        tg = data.split(":", 1)[1]
        pairs = [(s2, it2) for s2, it2 in all_items() if tg in (it2.get("tags") or []) and not it2.get("hidden")][:20]
        msg2 = await safe_edit(q, f"🏷 <b>{html.escape(tg)}</b>\n{LINE}", reply_markup=results_kb(pairs, 0, back="tags:list"))
        start_marquee(ctx, msg2, lambda off=0: results_kb(pairs, off, back="tags:list"),
                      [f"{i['title']}" for _, i in pairs]); return

    if data == "tags:list":
        tags = all_tags()
        rows = [[IB(make_bold_unicode(f"🏷 {t} ({n})"), callback_data=f"tagq:{t}", style="primary")] for t, n in list(tags.items())[:20]]
        rows = rows or [[IB(make_bold_unicode("لا توجد وسوم بعد"), callback_data="noop")]]
        await safe_edit(q, f"🏷 <b>{make_bold_unicode('الوسوم')}</b>\n{LINE}", reply_markup=InlineKeyboardMarkup(rows)); return

    if data.startswith("advt:"):
        t = data.split(":")[1]
        ctx.user_data["adv_type"] = None if t == "all" else t
        ctx.user_data["search"] = True
        await safe_edit(q, f"🔍 أرسل كلمة البحث ({'كل الأنواع' if t == 'all' else TYPE_EMOJI.get(t,'') + ' ' + t}):"); return

    # ── من هنا فصاعداً أوامر الأدمن ──
    if not is_admin(uid):
        await q.answer("🚫 غير مصرح", show_alert=True); return

    if data.startswith("pin:"):
        _, sid, iid = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        if it:
            it["pin"] = not it.get("pin"); save_data()
            await q.answer("📌 تم التثبيت" if it["pin"] else "تم إلغاء التثبيت", show_alert=True)
        return

    if data.startswith("padd:"):
        _, sid, iid = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        if not it:
            await q.answer("⚠️ القائمة غير موجودة", show_alert=True); return
        ctx.user_data["await"] = ("packfiles", (sid, iid))
        await safe_edit(q,
            f"📤 أرسل الآن ملفات القائمة <b>{html.escape(it['title'])}</b> واحداً بعد الآخر\n{LINE}\n"
            "🔸 يمكنك كتابة اسم الملف في التعليق (مثل: جودة عالية 1080p)\n"
            "🔸 وإن لم تكتب شيئاً سأسميه تلقائياً (النسخة 1، النسخة 2 …)\n"
            "🔸 عند الانتهاء أرسل /done")
        return

    if data.startswith("pmng:"):
        _, sid, iid = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        if not it:
            await q.answer("⚠️ القائمة غير موجودة", show_alert=True); return
        await safe_edit(q, f"🧹 إدارة ملفات: <b>{html.escape(it['title'])}</b>\n{LINE}",
                        reply_markup=pack_files_admin_kb(sec, it)); return

    if data.startswith("pmv:"):
        _, sid, iid, idx, d = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        i = int(idx)
        if it:
            fs = it.get("files", [])
            j = i - 1 if d == "up" else i + 1
            if 0 <= j < len(fs):
                fs[i], fs[j] = fs[j], fs[i]; save_data()
        try:
            await q.edit_message_reply_markup(reply_markup=pack_files_admin_kb(sec, it))
        except Exception:
            pass
        return

    if data.startswith("pcov:"):
        _, sid, iid = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        if not it:
            await q.answer("⚠️ القائمة غير موجودة", show_alert=True); return
        ctx.user_data["await"] = ("packcover", (sid, iid))
        await safe_edit(q, f"🖼 أرسل الآن صورة الغلاف للقائمة <b>{html.escape(it['title'])}</b>\n{LINE}\n"
                           "🔸 أرسل /skip لحذف الغلاف الحالي أو تجاوز الخطوة")
        return

    if data.startswith("pren:"):
        _, sid, iid, idx = data.split(":")
        ctx.user_data["await"] = ("packren", (sid, iid, int(idx)))
        await safe_edit(q, "✏️ أرسل الاسم الجديد لهذا الملف:"); return

    if data.startswith("pdel:"):
        _, sid, iid, idx = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        if it and 0 <= int(idx) < len(it.get("files", [])):
            it["files"].pop(int(idx)); save_data()
        await q.answer("🗑 تم حذف الملف", show_alert=True)
        try:
            await q.edit_message_reply_markup(reply_markup=pack_files_admin_kb(sec, it))
        except Exception:
            pass
        return

    if data == "adm:pack":
        await safe_edit(q, "🗂 اختر القسم الذي ستوضع فيه القائمة:", reply_markup=pick_section_kb("pack")); return

    if data == "adm:panel":
        await safe_edit(q, f"🛠 <b>{make_bold_unicode('لوحة الأدمن')}</b>\n{LINE}",
                        reply_markup=admin_kb()); return

    if data == "adm:upload":
        await safe_edit(q, "📤 اختر القسم الذي تريد الرفع إليه:", reply_markup=pick_section_kb("upload")); return

    if data == "adm:rensec":
        await safe_edit(q, "✏️ اختر القسم لتغيير اسمه:", reply_markup=pick_section_kb("rensec")); return

    if data == "adm:delsec":
        await safe_edit(q, "🗑 اختر القسم لحذفه (سيُحذف محتواه):", reply_markup=pick_section_kb("delsec")); return

    if data == "adm:manage":
        await safe_edit(q, "🧹 اختر القسم لإدارة محتواه:", reply_markup=pick_section_kb("manage")); return

    if data == "adm:order":
        await safe_edit(q, "↕️ رتّب الأقسام:", reply_markup=order_kb()); return

    if data == "adm:labels":
        await safe_edit(q, "🏷 اضغط على الزر الذي تريد تغيير اسمه:", reply_markup=labels_kb()); return

    if data == "adm:addsec":
        ctx.user_data["await"] = ("addsec", None)
        await safe_edit(q, "➕ أرسل اسم القسم الجديد (يمكنك وضع إيموجي في البداية):"); return

    if data == "adm:backup":
        await do_backup(ctx.bot, chat_id=q.message.chat_id, force=True)
        if BACKUP_CHAT_ID:
            await do_backup(ctx.bot, force=True)
        await q.answer("💾 تم إرسال النسخة", show_alert=True); return

    if data == "adm:restore":
        ctx.user_data["await"] = ("restore", None)
        await safe_edit(q, f"♻️ أرسل ملف <b>archive.json</b> (أو users.json) لاستعادته.\n{LINE}\n"
                           "يمكنك إعادة توجيهه من قناة النسخ الاحتياطي."); return

    if data == "adm:addadmin":
        ctx.user_data["await"] = ("addadmin", None)
        await safe_edit(q, "👑 أرسل ايدي المستخدم لإضافته/إزالته كأدمن:"); return

    if data == "adm:forcesub":
        ctx.user_data["await"] = ("forcesub", None)
        await safe_edit(q, f"📢 أرسل معرّف القناة للاشتراك الإجباري (مثال: @mychannel)\n{LINE}\n"
                           f"الحالي: <b>{S('force_sub') or '—'}</b>\nأرسل /off للتعطيل"); return

    if data.startswith("adm:tg:"):
        key = data.split(":")[2]
        DATA["settings"][key] = not DATA["settings"].get(key)
        save_data()
        await q.edit_message_reply_markup(reply_markup=admin_kb()); return

    if data == "adm:logs":
        logs = DATA.get("logs", [])[-25:]
        txt = "\n".join(f"• {time.strftime('%m-%d %H:%M', time.localtime(l['t']))} — {html.escape(l['x'])}"
                        for l in reversed(logs)) or "—"
        await safe_edit(q, f"🗒 <b>{make_bold_unicode('سجل النشاط')}</b>\n{LINE}\n{txt}\n{LINE}",
                        reply_markup=admin_kb()); return

    if data.startswith("adm:txt:"):
        key = data.split(":")[2]
        ctx.user_data["await"] = ("txt", key)
        cur = DATA.get(key, "")
        await safe_edit(q, f"📝 أرسل النص الجديد.\n{LINE}\nالحالي:\n<code>{html.escape(str(cur))}</code>"); return

    if data == "adm:bc":
        ctx.user_data["await"] = ("bc", None)
        await safe_edit(q, "📣 أرسل الرسالة (نص أو وسائط) وسأبثّها لكل المستخدمين:"); return

    if data == "adm:ban":
        ctx.user_data["await"] = ("ban", None)
        await safe_edit(q, "🚫 أرسل ايدي المستخدم لحظره أو فك حظره:"); return

    if data == "adm:marq":
        order = ["scroll", "wrap", "off"]
        cur = S("marquee", "scroll")
        DATA["settings"]["marquee"] = order[(order.index(cur) + 1) % 3] if cur in order else "scroll"
        save_data()
        names = {"scroll": "🎞 شريط متحرك", "wrap": "📃 نص كامل بأسطر صغيرة", "off": "⏹ بلا حركة (اقتصار بنقاط)"}
        await q.answer("تم: " + names[DATA["settings"]["marquee"]], show_alert=True)
        await safe_edit(q, f"🛠 <b>{make_bold_unicode('لوحة الأدمن')}</b>\n{LINE}", reply_markup=admin_kb()); return

    if data == "adm:limit":
        ctx.user_data["await"] = ("limit", None)
        await safe_edit(q, "🚦 أرسل عدد التنزيلات اليومية المسموحة لكل مستخدم (0 = بلا حد):"); return

    if data == "adm:banner":
        ctx.user_data["await"] = ("banner", None)
        await safe_edit(q, "📌 أرسل نص شريط الإعلان الذي يظهر أعلى القوائم (أو /off لإلغائه):"); return

    if data == "adm:bulk":
        await safe_edit(q, "⚡ اختر القسم للرفع المجمّع السريع:", reply_markup=pick_section_kb("bulk")); return

    if data == "adm:trash":
        tr = DATA.get("trash", [])[-15:]
        rows = [[IB(make_bold_unicode(f"♻️ {x['item'].get('title','')[:26]}"), callback_data=f"untrash:{x['item']['id']}", style="success")] for x in tr]
        rows.append([IB(make_bold_unicode("🧨 تفريغ السلة نهائياً"), callback_data="trash:clear", style="danger")])
        rows.append([IB(make_bold_unicode(L("back")), callback_data="adm:panel", style="primary")])
        await safe_edit(q, f"♻️ <b>{make_bold_unicode('سلة المحذوفات')}</b>\n{LINE}\nالعدد: <b>{len(DATA.get('trash', []))}</b>",
                        reply_markup=InlineKeyboardMarkup(rows)); return

    if data.startswith("untrash:"):
        iid = data.split(":")[1]
        tr = DATA.get("trash", [])
        rec = next((x for x in tr if x["item"]["id"] == iid), None)
        if rec:
            sec = get_section(rec.get("sid")) or (DATA["sections"][0] if DATA["sections"] else None)
            if sec:
                sec["items"].append(rec["item"])
            tr.remove(rec); save_data()
        await q.answer("♻️ تمت الاستعادة", show_alert=True)
        await safe_edit(q, "♻️ تمت استعادة المادة.", reply_markup=admin_kb()); return

    if data == "trash:clear":
        DATA["trash"] = []; save_data()
        await safe_edit(q, "🧨 تم تفريغ سلة المحذوفات.", reply_markup=admin_kb()); return

    if data == "adm:leader":
        top = sorted(USERS.values(), key=lambda u: -int(u.get("points", 0)))[:15]
        lines = [f"🎖 <b>{make_bold_unicode('المتصدرون')}</b>\n{LINE}"]
        for i, u in enumerate(top, 1):
            lines.append(f"{i}. {html.escape(str(u.get('username') or u.get('name') or u['id']))} — <b>{u.get('points',0)}</b> نقطة (مستوى {level_of(int(u.get('points',0)))})")
        await safe_edit(q, "\n".join(lines) + f"\n{LINE}", reply_markup=admin_kb()); return

    if data.startswith("tag:"):
        _, sid, iid = data.split(":")
        ctx.user_data["await"] = ("tags", (sid, iid))
        await safe_edit(q, "🏷 أرسل الوسوم مفصولة بفاصلة (مثال: إصدار, جهاد, 1446) أو /off لحذفها:"); return

    if data.startswith("hid:"):
        _, sid, iid = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        if it:
            it["hidden"] = not it.get("hidden"); save_data()
            await q.answer("🙈 أُخفيت المادة" if it["hidden"] else "👁 أصبحت ظاهرة", show_alert=True)
        try:
            await q.edit_message_reply_markup(reply_markup=manage_items_kb(sec))
        except Exception:
            pass
        return

    if data.startswith("sch:"):
        _, sid, iid = data.split(":")
        ctx.user_data["await"] = ("sched", (sid, iid))
        await safe_edit(q, "⏰ أرسل وقت النشر بعد كم ساعة (مثال: 5) أو /off للنشر فوراً:"); return

    if data.startswith("cpitem:"):
        _, sid, iid = data.split(":")
        ctx.user_data["copying"] = (sid, iid)
        await safe_edit(q, "📑 اختر القسم الذي تريد نسخ المادة إليه:", reply_markup=pick_section_kb("copyto")); return

    if data.startswith("mngexp:"):
        sid = data.split(":")[1]
        sec = get_section(sid)
        if not sec:
            return
        body = [f"# {sec['title']}", LINE]
        for i, it in enumerate(sorted_items(sec), 1):
            body.append(f"{i}. [{it['type']}] {it['title']} — 👁{it.get('views',0)} 📥{it.get('dl',0)}")
        buf = io.BytesIO("\n".join(body).encode("utf-8"))
        buf.name = f"{sid}_list.txt"
        await ctx.bot.send_document(q.message.chat_id, document=buf, filename=buf.name,
                                    caption=f"📄 قائمة {sec['title']}")
        return

    if data.startswith("secst:"):
        sid = data.split(":")[1]
        sec = get_section(sid)
        if not sec:
            return
        items = sec["items"]
        top = sorted(items, key=lambda i: -int(i.get("dl", 0)))[:10]
        det = "\n".join(f"{n}. {html.escape(i['title'][:30])} — 📥{i.get('dl',0)} 👁{i.get('views',0)}" for n, i in enumerate(top, 1)) or "—"
        await safe_edit(q, f"📊 <b>{html.escape(sec['title'])}</b>\n{LINE}\n"
                           f"📦 المواد: <b>{len(items)}</b> • 🙈 مخفية: <b>{sum(1 for i in items if i.get('hidden'))}</b>\n"
                           f"📥 تنزيلات: <b>{sum(int(i.get('dl',0)) for i in items)}</b>\n{LINE}\n{det}",
                        reply_markup=admin_kb()); return

    if data.startswith("secpw:"):
        sid = data.split(":")[1]
        ctx.user_data["await"] = ("secpw", sid)
        await safe_edit(q, "🔐 أرسل كلمة المرور لهذا القسم (أو /off لإزالة القفل):"); return

    if data.startswith("sechid:"):
        sid = data.split(":")[1]
        sec = get_section(sid)
        if sec:
            sec["hidden"] = not sec.get("hidden"); save_data()
            await q.answer("🙈 أُخفي القسم" if sec["hidden"] else "👁 أصبح ظاهراً", show_alert=True)
        await safe_edit(q, f"🧹 إدارة: {sec['title']}\n{LINE}", reply_markup=manage_items_kb(sec, 0)); return

    if data == "adm:users":
        lines = [f"👥 <b>{make_bold_unicode('المستخدمون')}</b>\n{LINE}"]
        for u in list(USERS.values())[-30:]:
            mark = "🚫" if u.get("banned") else "✅"
            lines.append(f"{mark} <code>{u['id']}</code> — {html.escape(str(u.get('username') or u.get('name') or '—'))}")
        lines.append(LINE)
        await safe_edit(q, "\n".join(lines), reply_markup=admin_kb()); return

    if data == "adm:stats":
        total = sum(len(s["items"]) for s in DATA["sections"])
        by = {}
        views = 0
        for s in DATA["sections"]:
            for it in s["items"]:
                by[it["type"]] = by.get(it["type"], 0) + 1
                views += int(it.get("views", 0))
        det = "\n".join(f"{TYPE_EMOJI.get(k,'📎')} {k}: <b>{v}</b>" for k, v in by.items()) or "—"
        day = int(time.time()) - 86400
        active = sum(1 for u in USERS.values() if u.get("last", 0) > day)
        txt = (f"📊 <b>{make_bold_unicode('إحصائيات الأرشيف')}</b>\n{LINE}\n"
               f"👥 المستخدمون: <b>{len(USERS)}</b> • نشط اليوم: <b>{active}</b>\n"
               f"🗂 الأقسام: <b>{len(DATA['sections'])}</b>\n"
               f"📦 إجمالي المواد: <b>{total}</b> • 👁 المشاهدات: <b>{views}</b>\n{LINE}\n{det}\n{LINE}")
        await safe_edit(q, txt, reply_markup=admin_kb()); return

    if data.startswith("adm:delitem:"):
        _, _, sid, iid = data.split(":")
        sec = get_section(sid)
        if sec:
            gone = get_item(sec, iid)
            if gone:
                DATA.setdefault("trash", []).append({"sid": sid, "t": int(time.time()), "item": gone})
                DATA["trash"] = DATA["trash"][-50:]
            sec["items"] = [i for i in sec["items"] if i["id"] != iid]
            save_data(); add_log(f"حذف مادة {iid} من {sec['title']} (إلى سلة المحذوفات)")
        await q.answer("🗑 تم الحذف", show_alert=True)
        try:
            await q.edit_message_reply_markup(reply_markup=manage_items_kb(sec))
        except Exception:
            pass
        return

    if data.startswith("mng:"):
        _, sid, page = data.split(":")
        sec = get_section(sid)
        await safe_edit(q, f"🧹 إدارة: {sec['title']}\n{LINE}", reply_markup=manage_items_kb(sec, int(page))); return

    if data.startswith("ren:"):
        _, sid, iid = data.split(":")
        ctx.user_data["await"] = ("renitem", (sid, iid))
        await safe_edit(q, "✏️ أرسل العنوان الجديد لهذه المادة:"); return

    if data.startswith("mvitem:"):
        _, sid, iid = data.split(":")
        ctx.user_data["moving"] = (sid, iid)
        await safe_edit(q, "↔️ اختر القسم الذي تريد نقل المادة إليه:", reply_markup=pick_section_kb("moveto")); return

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
        await safe_edit(q, f"🏷 أرسل الاسم الجديد للزر <code>{key}</code>\nالحالي: <b>{html.escape(L(key))}</b>"); return

    if data.startswith("pick:"):
        _, action, sid = data.split(":")
        sec = get_section(sid)
        if not sec:
            await safe_edit(q, "⚠️ القسم غير موجود."); return

        if action == "upload":
            ctx.user_data["await"] = ("upload", sid)
            await safe_edit(q,
                f"📤 أرسل الآن المحتوى إلى قسم <b>{html.escape(sec['title'])}</b>\n{LINE}\n"
                "🎬 فيديو • 🎧 صوت • 🖼 صورة • 📄 ملف • 🎙 بصمة • 🎞 GIF • 📝 نص\n"
                "يمكنك إرسال عدة عناصر متتالية، وعند الانتهاء أرسل /done")
        elif action == "pack":
            ctx.user_data["await"] = ("packname", sid)
            await safe_edit(q,
                f"🗂 أرسل اسم القائمة التي ستظهر في قسم <b>{html.escape(sec['title'])}</b>\n{LINE}\n"
                "مثال: إصدار «الفتح المبين» — عدة جودات")
        elif action == "bulk":
            ctx.user_data["await"] = ("bulk", sid)
            ctx.user_data["bulkn"] = 0
            await safe_edit(q,
                f"⚡ الرفع المجمّع إلى <b>{html.escape(sec['title'])}</b>\n{LINE}\n"
                "أرسل الملفات تتابعاً بسرعة — تُسمّى تلقائياً إن لم تكتب تعليقاً.\nوعند الانتهاء /done")
        elif action == "copyto":
            src = ctx.user_data.pop("copying", None)
            if src:
                osid, iid = src
                osec = get_section(osid); it = get_item(osec, iid) if osec else None
                if it:
                    cp = json.loads(json.dumps(it)); cp["id"] = next_id("i"); cp["ts"] = int(time.time())
                    sec["items"].append(cp); save_data(); add_log(f"نسخ مادة إلى {sec['title']}")
            await safe_edit(q, "✅ تم نسخ المادة.", reply_markup=admin_kb())
        elif action == "rensec":
            ctx.user_data["await"] = ("rensec", sid)
            await safe_edit(q, f"✏️ أرسل الاسم الجديد للقسم <b>{html.escape(sec['title'])}</b>")
        elif action == "delsec":
            DATA["sections"] = [s for s in DATA["sections"] if s["id"] != sid]
            save_data(); add_log("حذف قسم")
            await safe_edit(q, f"🗑 تم حذف القسم.\n{LINE}", reply_markup=admin_kb())
        elif action == "manage":
            await safe_edit(q, f"🧹 إدارة: {sec['title']}\n{LINE}", reply_markup=manage_items_kb(sec, 0))
        elif action == "moveto":
            src = ctx.user_data.pop("moving", None)
            if src:
                osid, iid = src
                osec = get_section(osid); it = get_item(osec, iid) if osec else None
                if it:
                    osec["items"] = [i for i in osec["items"] if i["id"] != iid]
                    sec["items"].append(it); save_data()
                    add_log(f"نقل مادة إلى {sec['title']}")
            await safe_edit(q, "✅ تم نقل المادة.", reply_markup=admin_kb())
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
    if S("maintenance") and not is_admin(uid):
        await msg.reply_text("🔧 البوت في وضع الصيانة مؤقتاً."); return

    # ── حالات انتظار الأدمن ──
    waiting = ctx.user_data.get("await")
    if waiting and is_admin(uid):
        kind, payload = waiting

        if text == "/done":
            ctx.user_data.pop("await", None)
            if BACKUP_CHAT_ID:
                await do_backup(ctx.bot, force=True)
            await msg.reply_text(f"✅ تم الإنهاء (وتم حفظ نسخة احتياطية).\n{LINE}", reply_markup=admin_kb()); return

        if kind == "limit":
            try:
                DATA["settings"]["daily_limit"] = max(0, int(text))
            except ValueError:
                await msg.reply_text("⚠️ أرسل رقماً."); return
            save_data(); ctx.user_data.pop("await", None)
            await msg.reply_text("✅ تم تحديث حد التنزيل اليومي.", reply_markup=admin_kb()); return

        if kind == "banner":
            DATA["settings"]["banner"] = "" if text == "/off" else text
            save_data(); ctx.user_data.pop("await", None)
            await msg.reply_text("✅ تم تحديث شريط الإعلان.", reply_markup=admin_kb()); return

        if kind == "tags":
            sid, iid = payload
            sec = get_section(sid); it = get_item(sec, iid) if sec else None
            if it:
                it["tags"] = [] if text == "/off" else [t.strip() for t in text.replace("،", ",").split(",") if t.strip()][:8]
                save_data()
            ctx.user_data.pop("await", None)
            await msg.reply_text("🏷 تم تحديث الوسوم.", reply_markup=admin_kb()); return

        if kind == "sched":
            sid, iid = payload
            sec = get_section(sid); it = get_item(sec, iid) if sec else None
            if it:
                if text == "/off":
                    it["publish_at"] = 0
                else:
                    try:
                        it["publish_at"] = int(time.time()) + int(float(text) * 3600)
                    except ValueError:
                        await msg.reply_text("⚠️ أرسل عدد الساعات (مثال: 3)."); return
                save_data()
            ctx.user_data.pop("await", None)
            await msg.reply_text("⏰ تم ضبط وقت النشر.", reply_markup=admin_kb()); return

        if kind == "secpw":
            sec = get_section(payload)
            if sec:
                sec["pw"] = "" if text == "/off" else text.strip()
                save_data()
            ctx.user_data.pop("await", None)
            await msg.reply_text("🔐 تم تحديث قفل القسم.", reply_markup=admin_kb()); return

        if kind == "bulk":
            sec = get_section(payload)
            if not sec:
                ctx.user_data.pop("await", None)
                await msg.reply_text("⚠️ القسم غير موجود."); return
            t, fid, cap = detect_media(msg)
            if not t:
                await msg.reply_text("⚠️ نوع غير مدعوم."); return
            ctx.user_data["bulkn"] = int(ctx.user_data.get("bulkn", 0)) + 1
            title = ((cap or "").split("\n")[0][:120] or f"{sec['title']} — {ctx.user_data['bulkn']}")
            it = {"id": next_id("i"), "type": t, "file_id": fid, "title": title,
                  "caption": cap if t != "text" else "", "ts": int(time.time()),
                  "views": 0, "dl": 0, "pin": False, "tags": [], "hidden": False, "publish_at": 0}
            sec["items"].append(it); save_data()
            await notify_new(ctx.bot, sec, it)
            await msg.reply_text(make_bold_unicode(f"⚡ {ctx.user_data['bulkn']} — {title}"))
            return

        if kind == "restore":
            doc = msg.document
            if not doc:
                await msg.reply_text("⚠️ أرسل ملف JSON."); return
            try:
                f = await doc.get_file()
                raw = await f.download_as_bytearray()
                payload_obj = json.loads(bytes(raw).decode("utf-8"))
            except Exception as e:
                await msg.reply_text(f"⚠️ ملف غير صالح: {e}"); return
            if isinstance(payload_obj, dict) and "sections" in payload_obj:
                apply_restore(payload_obj, "data")
                await msg.reply_text("♻️ تمت استعادة الأرشيف بنجاح ✅", reply_markup=admin_kb())
            elif isinstance(payload_obj, dict):
                apply_restore(payload_obj, "users")
                await msg.reply_text("♻️ تمت استعادة المستخدمين ✅", reply_markup=admin_kb())
            else:
                await msg.reply_text("⚠️ صيغة غير معروفة.")
            ctx.user_data.pop("await", None)
            add_log("استعادة نسخة احتياطية")
            return

        if kind == "upload":
            sec = get_section(payload)
            if not sec:
                ctx.user_data.pop("await", None)
                await msg.reply_text("⚠️ القسم غير موجود."); return
            t, fid, cap = detect_media(msg)
            if not t:
                await msg.reply_text("⚠️ نوع غير مدعوم."); return
            title = (cap or "بدون عنوان").split("\n")[0][:120]
            sec["items"].append({
                "id": next_id("i"), "type": t, "file_id": fid,
                "title": title, "caption": cap if t != "text" else "",
                "ts": int(time.time()), "views": 0, "pin": False,
            })
            save_data(); add_log(f"رفع مادة إلى {sec['title']}")
            await notify_new(ctx.bot, sec, sec["items"][-1])
            await msg.reply_text(
                make_bold_unicode(f"✅ أُضيفت المادة إلى {sec['title']} ({len(sec['items'])})") +
                "\nأرسل التالي أو /done للإنهاء")
            return

        if kind == "packname":
            sec = get_section(payload)
            if not sec:
                ctx.user_data.pop("await", None)
                await msg.reply_text("⚠️ القسم غير موجود."); return
            iid = next_id("i")
            sec["items"].append({
                "id": iid, "type": "pack", "file_id": None, "cover": None,
                "title": (text or "قائمة جديدة")[:120], "caption": "",
                "files": [], "ts": int(time.time()), "views": 0, "pin": False,
            })
            save_data()
            ctx.user_data["await"] = ("packcover", (payload, iid))
            await msg.reply_text(
                f"✅ تم إنشاء القائمة: <b>{html.escape(text)}</b>\n{LINE}\n"
                "🖼 أرسل الآن <b>صورة الغلاف</b> التي ستظهر مع الاسم قبل الجودات\n"
                "🔸 أو أرسل /skip للتجاوز بدون غلاف",
                parse_mode=ParseMode.HTML)
            return

        if kind == "packcover":
            sid, iid = payload
            sec = get_section(sid); it = get_item(sec, iid) if sec else None
            if not it:
                ctx.user_data.pop("await", None)
                await msg.reply_text("⚠️ القائمة غير موجودة."); return
            if text == "/skip":
                it["cover"] = None; save_data()
            elif msg.photo:
                it["cover"] = msg.photo[-1].file_id; save_data()
            elif msg.video and msg.video.thumbnail:
                it["cover"] = msg.video.thumbnail.file_id; save_data()
            else:
                await msg.reply_text("⚠️ أرسل صورة للغلاف أو /skip للتجاوز."); return
            ctx.user_data["await"] = ("packfiles", (sid, iid))
            await msg.reply_text(
                f"{'✅ تم حفظ الغلاف' if it.get('cover') else '⏭ بدون غلاف'}\n{LINE}\n"
                "📤 أرسل الآن ملفات القائمة واحداً بعد الآخر (فيديو بجودات مختلفة مثلاً)\n"
                "🔸 اكتب اسم/الجودة في التعليق (مثل: جودة 1080p) أو اتركه فأسميه تلقائياً\n"
                "🔸 عند الانتهاء أرسل /done",
                parse_mode=ParseMode.HTML)
            return

        if kind == "packfiles":
            sid, iid = payload
            sec = get_section(sid); it = get_item(sec, iid) if sec else None
            if not it:
                ctx.user_data.pop("await", None)
                await msg.reply_text("⚠️ القائمة غير موجودة."); return
            t, fid, cap = detect_media(msg)
            if not t or t == "text":
                await msg.reply_text("⚠️ أرسل ملفاً (فيديو/صوت/صورة/ملف)."); return
            it.setdefault("files", [])
            label = (msg.caption or "").split("\n")[0].strip()[:80] or f"النسخة {len(it['files']) + 1}"
            it["files"].append({"type": t, "file_id": fid, "label": label, "ts": int(time.time())})
            save_data()
            await msg.reply_text(
                make_bold_unicode(f"✅ أُضيف «{label}» إلى القائمة {it['title']} ({len(it['files'])})") +
                "\nأرسل الملف التالي أو /done للإنهاء")
            return

        if kind == "packren":
            sid, iid, idx = payload
            sec = get_section(sid); it = get_item(sec, iid) if sec else None
            if it and 0 <= idx < len(it.get("files", [])):
                it["files"][idx]["label"] = (text or it["files"][idx]["label"])[:80]
                save_data()
            ctx.user_data.pop("await", None)
            await msg.reply_text("✅ تم تعديل اسم الملف.", reply_markup=admin_kb()); return

        if kind == "addsec":
            DATA["sections"].append({"id": next_id("s"), "title": text or "قسم جديد", "desc": "", "items": []})
            save_data(); ctx.user_data.pop("await", None); add_log("إضافة قسم")
            await msg.reply_text(f"✅ تمت إضافة القسم: <b>{html.escape(text)}</b>",
                                 parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

        if kind == "rensec":
            sec = get_section(payload)
            if sec:
                sec["title"] = text or sec["title"]; save_data()
            ctx.user_data.pop("await", None)
            await msg.reply_text(f"✅ تم تغيير الاسم إلى: <b>{html.escape(text)}</b>",
                                 parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

        if kind == "renitem":
            sid, iid = payload
            sec = get_section(sid); it = get_item(sec, iid) if sec else None
            if it:
                it["title"] = text[:120]; save_data()
            ctx.user_data.pop("await", None)
            await msg.reply_text("✅ تم تعديل العنوان.", reply_markup=admin_kb()); return

        if kind == "txt":
            DATA[payload] = text; save_data(); ctx.user_data.pop("await", None)
            await msg.reply_text("✅ تم تحديث النص.", reply_markup=admin_kb()); return

        if kind == "label":
            DATA["labels"][payload] = text; save_data(); ctx.user_data.pop("await", None)
            await msg.reply_text("✅ تم تحديث اسم الزر.", reply_markup=main_kb(uid)); return

        if kind == "forcesub":
            DATA["settings"]["force_sub"] = "" if text == "/off" else text.strip()
            save_data(); ctx.user_data.pop("await", None)
            await msg.reply_text("✅ تم تحديث الاشتراك الإجباري.", reply_markup=admin_kb()); return

        if kind == "addadmin":
            try:
                tid = int(text.strip())
            except ValueError:
                await msg.reply_text("⚠️ أرسل رقم ايدي صحيح."); return
            adm = DATA.setdefault("admins", [])
            if tid in adm:
                adm.remove(tid); out = "تمت إزالة الأدمن"
            else:
                adm.append(tid); out = "تمت إضافة الأدمن"
            save_data(); ctx.user_data.pop("await", None)
            await msg.reply_text(f"👑 {out}: <code>{tid}</code>", parse_mode=ParseMode.HTML,
                                 reply_markup=admin_kb()); return

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
                if USERS[key].get("banned"):
                    continue
                try:
                    await ctx.bot.copy_message(int(key), msg.chat_id, msg.message_id)
                    ok += 1
                except Exception:
                    fail += 1
            add_log(f"بث رسالة ({ok} نجاح / {fail} فشل)")
            await msg.reply_text(f"📣 تم البث\n{LINE}\n✅ {ok} • ❌ {fail}", reply_markup=admin_kb()); return

    # ── فتح قسم مقفل ──
    if ctx.user_data.get("unlock"):
        sid = ctx.user_data["unlock"]
        sec = get_section(sid)
        if sec and text and text.strip() == (sec.get("pw") or ""):
            ctx.user_data.pop("unlock", None)
            ok = ctx.user_data.setdefault("unlocked", [])
            if sid not in ok:
                ok.append(sid)
            head = f"{sec['title']}\n{LINE}\n🔓 تم الفتح، بارك الله فيك.\n{LINE}"
            m = await msg.reply_text(head, parse_mode=ParseMode.HTML, reply_markup=items_kb(sec, 0, 0))
            start_marquee(ctx, m, lambda off=0: items_kb(sec, 0, off), items_texts(sec, 0))
        else:
            await msg.reply_text("🔐 كلمة المرور غير صحيحة، حاول مرة أخرى أو اضغط الأقسام.")
        return

    # ── مراسلة الإدارة ──
    if ctx.user_data.pop("fb", None):
        who = f"@{update.effective_user.username}" if update.effective_user.username else str(uid)
        for a in set(list(ADMIN_IDS) + list(DATA.get("admins", []))):
            try:
                await ctx.bot.send_message(a, f"✉️ <b>رسالة من مستخدم</b>\n{LINE}\n👤 {html.escape(who)} — <code>{uid}</code>\n{LINE}\n{html.escape(text or '(وسائط)')}",
                                           parse_mode=ParseMode.HTML)
                if not text:
                    await ctx.bot.copy_message(a, msg.chat_id, msg.message_id)
            except Exception:
                pass
        award(uid, 1)
        await msg.reply_text("✅ وصلت رسالتك للإدارة، جزاك الله خيراً."); return

    # ── اشتراك إجباري للمستخدم العادي ──
    if not is_admin(uid) and not await sub_ok(ctx.bot, uid):
        await msg.reply_text("📢 يرجى الاشتراك في القناة أولاً:", reply_markup=sub_kb()); return

    # ── بحث ──
    if ctx.user_data.get("search"):
        scope = ctx.user_data.pop("search")
        pool = all_items() if scope is True else [(get_section(scope), it) for it in (get_section(scope) or {"items": []})["items"]]
        ftype = ctx.user_data.pop("adv_type", None)
        res = [(s, it) for s, it in pool
               if s and text and text.lower() in (it["title"] + " " + (it.get("caption") or "") + " " + " ".join(it.get("tags") or [])).lower()
               and not it.get("hidden") and (not ftype or it.get("type") == ftype)]
        if not res:
            await msg.reply_text(f"🔎 لا توجد نتائج لـ <b>{html.escape(text)}</b>", parse_mode=ParseMode.HTML); return
        pairs = res[:20]
        m = await msg.reply_text(f"🔎 <b>نتائج البحث</b> ({len(res)})\n{LINE}", parse_mode=ParseMode.HTML,
                                 reply_markup=results_kb(pairs, 0))
        start_marquee(ctx, m, lambda off=0: results_kb(pairs, off),
                      [f"{it['title']} • {s['title']}" for s, it in pairs])
        return

    # ── اقتراح/رسالة للأدمن ──
    if ctx.user_data.pop("tolerate_msg", None):
        pass

    # ── أزرار الكيبورد الرئيسية ──
    try:
        stop_marquee(ctx, msg.chat_id)
        new_view(msg.chat_id)
    except Exception:
        pass

    plain = text
    def eq(label):
        return plain in (label, make_bold_unicode(label))

    if eq(L("cart")):
        ids = list((USERS.get(str(uid)) or {}).get("cart") or [])
        pairs = [(s2, it2) for s2, it2 in ((find_item(i)) for i in ids) if it2]
        rows = [[IB(btn(f"{TYPE_EMOJI.get(it2['type'],'📎')} {it2['title']}", 0),
                    callback_data=f"itm:{s2['id']}:{it2['id']}:0", style="primary")] for s2, it2 in pairs]
        rows = rows or [[IB(make_bold_unicode("🧺 السلة فارغة"), callback_data="noop")]]
        if pairs:
            rows.append([IB(make_bold_unicode("📥 إرسال كل السلة"), callback_data="cart:send", style="success"),
                         IB(make_bold_unicode("🗑 تفريغ"), callback_data="cart:clear", style="danger")])
        await msg.reply_text(f"🧺 <b>{make_bold_unicode('سلة التنزيل')}</b>\n{LINE}\nالعدد: <b>{len(pairs)}</b>",
                             parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows)); return

    if eq(L("tags")):
        tags = all_tags()
        rows = [[IB(make_bold_unicode(f"🏷 {t} ({n})"), callback_data=f"tagq:{t}", style="primary")] for t, n in list(tags.items())[:20]]
        rows = rows or [[IB(make_bold_unicode("لا توجد وسوم بعد"), callback_data="noop")]]
        await msg.reply_text(f"🏷 <b>{make_bold_unicode('الوسوم')}</b>\n{LINE}", parse_mode=ParseMode.HTML,
                             reply_markup=InlineKeyboardMarkup(rows)); return

    if eq(L("adv")):
        rows = [[IB(make_bold_unicode("🔎 كل الأنواع"), callback_data="advt:all", style="success")]]
        row = []
        for t, e in TYPE_EMOJI.items():
            row.append(IB(f"{e} {t}", callback_data=f"advt:{t}", style="primary"))
            if len(row) == 3:
                rows.append(row); row = []
        if row:
            rows.append(row)
        await msg.reply_text(f"🔍 <b>{make_bold_unicode('بحث متقدم')}</b>\n{LINE}\nاختر نوع المحتوى ثم أرسل الكلمة:",
                             parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows)); return

    if eq(L("dltop")):
        pairs = sorted(all_items(), key=lambda p: -dl_week(p[1]))[:15]
        pairs = [(s2, it2) for s2, it2 in pairs if dl_week(it2) > 0] or pairs[:5]
        m = await msg.reply_text(f"🏆 <b>{make_bold_unicode('الأكثر تحميلاً هذا الأسبوع')}</b>\n{LINE}",
                                 parse_mode=ParseMode.HTML, reply_markup=results_kb(pairs, 0))
        start_marquee(ctx, m, lambda off=0: results_kb(pairs, off), [i['title'] for _, i in pairs]); return

    if eq(L("leader")):
        top = sorted(USERS.values(), key=lambda u: -int(u.get("points", 0)))[:10]
        me = USERS.get(str(uid)) or {}
        lines = [f"🎖 <b>{make_bold_unicode('لوحة المتصدرين')}</b>\n{LINE}"]
        for i, u in enumerate(top, 1):
            lines.append(f"{'🥇🥈🥉'[i-1] if i <= 3 else str(i) + '.'} {html.escape(str(u.get('username') or u.get('name') or '—'))} — <b>{u.get('points',0)}</b>")
        lines.append(LINE)
        lines.append(f"👤 نقاطك: <b>{me.get('points',0)}</b> • مستواك: <b>{level_of(int(me.get('points',0)))}</b>")
        await msg.reply_text("\n".join(lines), parse_mode=ParseMode.HTML); return

    if eq(L("hist")):
        ids = list((USERS.get(str(uid)) or {}).get("hist") or [])
        pairs = [(s2, it2) for s2, it2 in ((find_item(i)) for i in ids) if it2]
        m = await msg.reply_text(f"🕓 <b>{make_bold_unicode('آخر ما شاهدت')}</b>\n{LINE}",
                                 parse_mode=ParseMode.HTML, reply_markup=results_kb(pairs, 0))
        start_marquee(ctx, m, lambda off=0: results_kb(pairs, off), [i['title'] for _, i in pairs]); return

    if eq(L("feedback")):
        ctx.user_data["fb"] = True
        await msg.reply_text("✉️ أرسل رسالتك أو اقتراحك الآن وستصل للإدارة بإذن الله."); return

    if eq(L("sections")):
        m = await msg.reply_text(sections_header(), parse_mode=ParseMode.HTML, reply_markup=sections_kb(0, uid))
        start_marquee(ctx, m, lambda off=0: sections_kb(off, uid),
                      [f"{s['title']} • {len(s['items'])}" for s in DATA["sections"]])
        return

    if eq(L("new")):
        pairs = sorted(all_items(), key=lambda p: -int(p[1].get("ts", 0)))[:15]
        m = await msg.reply_text(f"🆕 <b>{make_bold_unicode('أحدث الإضافات')}</b>\n{LINE}",
                                 parse_mode=ParseMode.HTML, reply_markup=results_kb(pairs, 0))
        start_marquee(ctx, m, lambda off=0: results_kb(pairs, off),
                      [f"{it['title']} • {s['title']}" for s, it in pairs]); return

    if eq(L("top")):
        pairs = sorted(all_items(), key=lambda p: -int(p[1].get("views", 0)))[:15]
        m = await msg.reply_text(f"🔥 <b>{make_bold_unicode('الأكثر طلباً')}</b>\n{LINE}",
                                 parse_mode=ParseMode.HTML, reply_markup=results_kb(pairs, 0))
        start_marquee(ctx, m, lambda off=0: results_kb(pairs, off),
                      [f"{it['title']} • {s['title']}" for s, it in pairs]); return

    if eq(L("random")):
        pool = all_items()
        if not pool:
            await msg.reply_text("📦 الأرشيف فارغ حالياً."); return
        s, it = random.choice(pool)
        if it["type"] == "pack":
            head = pack_header(s, it)
            kb = pack_kb(s, it, 0, uid)
            if it.get("cover"):
                await ctx.bot.send_photo(msg.chat_id, it["cover"], caption=head,
                                         parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await msg.reply_text(head, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await send_item(ctx.bot, msg.chat_id, it, item_kb(s["id"], 0, uid, it["id"]))
        return

    if eq(L("fav")):
        favs = USERS.get(str(uid), {}).get("fav", [])
        pairs = [(s, it) for s, it in all_items() if it["id"] in favs]
        m = await msg.reply_text(f"⭐ <b>{make_bold_unicode('مفضلتك')}</b> ({len(pairs)})\n{LINE}",
                                 parse_mode=ParseMode.HTML, reply_markup=results_kb(pairs, 0))
        start_marquee(ctx, m, lambda off=0: results_kb(pairs, off),
                      [f"{it['title']} • {s['title']}" for s, it in pairs]); return

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

    # ── رسالة عادية من مستخدم: تُحوَّل للأدمن ──
    if text and not text.startswith("/") and not is_admin(uid):
        for a in set(ADMIN_IDS) | set(DATA.get("admins", [])):
            try:
                await ctx.bot.send_message(
                    a, f"✉️ <b>رسالة من مستخدم</b>\n{LINE}\n🆔 <code>{uid}</code>\n"
                       f"{html.escape(text[:500])}", parse_mode=ParseMode.HTML)
            except Exception:
                pass
        await msg.reply_text("✅ وصلت رسالتك للإدارة، جزاك الله خيراً.", reply_markup=main_kb(uid)); return

    await msg.reply_text(welcome_text(), parse_mode=ParseMode.HTML, reply_markup=main_kb(uid))

# ══════════════════ MAIN ══════════════════
async def on_startup(app: Application):
    if BACKUP_CHAT_ID:
        try:
            await app.bot.send_message(BACKUP_CHAT_ID,
                f"♻️ <b>تم تشغيل البوت</b>\n{LINE}\n"
                f"📦 المواد: <b>{sum(len(s['items']) for s in DATA['sections'])}</b>\n"
                f"👥 المستخدمون: <b>{len(USERS)}</b>\n{LINE}\n"
                "إن كان الأرشيف فارغاً بعد إعادة التشغيل، أرسل /restore ثم أعد توجيه آخر ملف archive.json.",
                parse_mode=ParseMode.HTML)
        except Exception as e:
            log.warning("startup notice failed: %s", e)
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
def main():
    if not BOT_TOKEN:
        raise SystemExit("⚠️ ضع BOT_TOKEN في أعلى الملف.")
    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(CommandHandler("restore", cmd_restore))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, on_message))
    if app.job_queue and BACKUP_CHAT_ID:
        app.job_queue.run_repeating(job_backup, interval=AUTO_BACKUP_MIN * 60, first=120)
    log.info("Archive bot v2 started ✅")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
