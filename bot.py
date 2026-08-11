# ═══════════════════════════════════════════════════════════════
# 🗂 ARCHIVE BOT v2 — بوت أرشيف مؤسسة إعلامية (Telegram)
#   pip install "python-telegram-bot[job-queue]==21.6"
#   python archive_bot_v2.py
#
#   ✦ أقسام قابلة للتعديل بالكامل من لوحة الأدمن
#   ✦ رفع أي محتوى + قوائم متعددة الملفات (جودات) مع غلاف
#   ✦ 🆕 شريط متحرك (Marquee) للعناوين الطويلة
#   ✦ 🆕 نسخ احتياطي دائم واستعادة تلقائية (يحل مشكلة Render)
# ✦ 🆕 15 ميزة إضافية (مفضلة، مشاهدات، روابط مشاركة، اشتراك إلزامي…)
═ ...
استيراد json، وlogging، وos، وtime، وrandom، وhtml، وio
من تيليجرام استورد  (
    زر لوحة المفاتيح المضمن، ترميز لوحة المفاتيح المضمن،
    زر لوحة المفاتيح، الرد على لوحة المفاتيح، التحديث، ملف الإدخال،
)
من telegram.constants قم باستيراد ParseMode
من مكتبة telegram.ext استورد  (
    التطبيق، معالج استعلام رد الاتصال، معالج الأوامر،
    أنواع السياق، معالج الرسائل، المرشحات،
)

# فطري .
BOT_TOKEN = "8589967320:AAG_nrroMIc3dl2v4G339gSJPBqzmrpTMcY"           # ← ضع توكن البوت هنا
ADMIN_IDS = [ 8747566796 ]           # ← ضع ايدي الأدمن هنا مثال: [123456789]

# قناة/مجموعة خاصة تُحفظ فيها النسخ الاحتياطية (اجعل البوت أدمن فيها)
BACKUP_CHAT_ID = ""      # ← مثال: -1001234567890 (اتركه بالكامل لتعطيل النسخ التلقائي)

# مجلد التخزين: على Render أنشئ Persistent Disk وضع مساره هنا مثل /var/data
DATA_DIR = os.environ.get ( " DATA_DIR" , " . " )

BOT_USERNAME = "@Shhsb77_bot"        # ← اسم البوت بدون @ (لروابط المشاركة) اختياري

os.makedirs ( DATA_DIR , exist_ok= True )
DATA_FILE = os.path.join ( DATA_DIR , " archive.json " )
USERS_FILE = os.path.join ( DATA_DIR , " users.json " )
PAGE_SIZE = 8           # عدد العناصر في صفحة التنزيل

# إعدادات شريط المتحرك للإناوين
MARQUEE_WIDTH = 10      # عدد المشاهير
MARQUEE_EVERY = 1.4     # سرعة الحركة بالثواني
MARQUEE_TICKS = 45      # عدد التوجهات التي قبلها (توفير الموارد)

AUTO_BACKUP_MIN = 20     # كل كم دقيقة تُرسل نسخة بيعية

logging.basicConfig ( format= "%(asctime)s - %(name)s - %(levelname)s - %(message)s" , level= logging.INFO )
log = logging.getLogger ( " archive" )

# ══════════════════ مساعد تنسيق النص بخط عريض ══════════════════
دالة  make_bold_unicode ( نص ) :
    الناتج = [ ]
    for char in  str ( text ) :
        ج = ترتيب ( حرف )
        إذا كان  65 ≤ c ≤ 90 : out.append ( chr ( c - 65 + 0x1D5D4 ) ) # AZ   
        elif  97 <= c <= 122 : out.append ( chr ( c - 97 + 0x1D5EE ) ) # az   
        elif  48 <= c <= 57 : out.append ( chr ( c - 48 + 0x1D7EC ) )    # 0-9
        وإلا : أضف الحرف إلى الناتج .
    return  "" . join ( out )

LINE = "━━━━━━━━━━━━━━━━━━━━"

def  _kb_btn ( text, style= None ) :
    يحاول :
        أعد  زر لوحة المفاتيح ( النص، النمط=النمط )  إذا كان النمط موجودًا، وإلا فأعد  زر لوحة المفاتيح ( النص ).
    باستثناء خطأ النوع:
        أعد  زر لوحة المفاتيح ( النص )

def  IB ( text, style= None , ** kw ) :
    يحاول :
        أعد  InlineKeyboardButton ( text, style=style, ** kw )  إذا كان style موجودًا، وإلا  InlineKeyboardButton ( text, ** kw )
    باستثناء خطأ النوع:
        return  InlineKeyboardButton ( text, ** kw )

# للتواصل:
الفجوة = " • ""   •   "

دالة التمرير (نص، إزاحة=0، عرض=عرض_التمرير): scroll(text, offset=0, width=MARQUEE_WIDTH):
    """يعيد جزءً من النص كالشريط إن كان مجسمًا لتصميم التصميم.""""""يعيد جزءاً من النص يتحرك كالشريط إن كان أطول من العرض المسموح."""
    t = str(text).replace("\n", " ").strip()str(text).replace("\n", " ").strip()
    إذا كان طول (t) أقل من أو يساوي العرض:if len(t) <= width:
        أعد treturn t
    s = t + GAP
    off = offset % len(s)len(s)
    return (s + s)[off:off + width]return (s + s)[off:off + width]

دالة is_long(text, width=MARQUEE_WIDTH): is_long(text, width=MARQUEE_WIDTH):
    return len(str(text).replace("\n", " ").strip()) > widthreturn len(str(text).replace("\n", " ").strip()) > width

# مخزن الشرائط العضوية: (chat_id, message_id) -> {"build":fn, "off":int}
MARQ = {}{}

async def _marq_tick(ctx: ContextTypes.DEFAULT_TYPE): def _marq_tick(ctx: ContextTypes.DEFAULT_TYPE):
    key = ctx.job.data["key"]job.data["key"]
    st = MARQ.get(key)get(key)
    وإلا:if not st:
        ctx.job.schedule_removal(); returnjob.schedule_removal(); return
    st["off"] += 1["off"] += 1
    إذا كان st["off"] > MARQUEE_TICKS:if st["off"] > MARQUEE_TICKS:
        MARQ.pop(key, None); ctx.job.schedule_removal(); returnpop(key, None); ctx.job.schedule_removal(); return
    يحاول:try:
        await ctx.bot.edit_message_reply_markup(await ctx.bot.edit_message_reply_markup(
            chat_id=key[0], message_id=key[1], reply_markup=st["build"](st["off"]))[0], message_id=key[1], reply_markup=st["build"](st["off"]))
    باستثناء الاستثناء:except Exception:
        MARQ.pop(key, None); ctx.job.schedule_removal()pop(key, None); ctx.job.schedule_removal()

دالة بدء العرض المتحرك (ctx، الرسالة، البناء، النصوص): start_marquee(ctx, message, build, texts):
    """يشغّل حركة النص إذا كان هناك عنوان طويل في القائمة.""""""يشغّل حركة النص إذا كان هناك عنوان طويل في القائمة."""
    يحاول:try:
        if not message or not any(is_long(t) for t in texts):
            return
        jq = getattr(ctx, "job_queue", None)
        if jq is None:
            return
        key = (message.chat_id, message.message_id)
        for j in jq.jobs():
            if getattr(j, "data", None) and j.data.get("key") == key:
                j.schedule_removal()
        MARQ[key] = {"build": build, "off": 0}
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
    },
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
    row = [
        _kb_btn(make_bold_unicode(L("about")), style="primary"),
        _kb_btn(make_bold_unicode(L("contact")), style="primary"),
    ]
    if is_admin(uid):
        row.append(_kb_btn(make_bold_unicode(L("admin")), style="danger"))
    rows.append(row)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def sections_kb(off=0):
    rows = []
    for s in DATA["sections"]:
        label = f"{s['title']}  •  {len(s['items'])}"
        rows.append([IB(make_bold_unicode(scroll(label, off)),
                        callback_data=f"sec:{s['id']}:0", style="primary")])
    if not rows:
        rows.append([IB(make_bold_unicode("لا توجد أقسام بعد"), callback_data="noop")])
    return InlineKeyboardMarkup(rows)

def item_label(it):
    extra = f"  •  {len(it.get('files', []))} ملفات" if it["type"] == "pack" else ""
    pin = "📌 " if it.get("pin") else ""
    return f"{pin}{TYPE_EMOJI.get(it['type'],'📎')} {it['title']}{extra}"

def sorted_items(sec):
    return sorted(sec["items"], key=lambda i: (0 if i.get("pin") else 1, -int(i.get("ts", 0))))

def items_kb(sec, page, off=0):
    items = sorted_items(sec)
    pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    rows = []
    for it in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        rows.append([IB(make_bold_unicode(scroll(item_label(it), off)),
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
    items = sorted_items(sec)
    return [item_label(it) for it in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]]

def item_kb(sid, page, uid, iid):
    fav = iid in USERS.get(str(uid), {}).get("fav", [])
    rows = [[
        IB(make_bold_unicode("💔 إزالة من المفضلة" if fav else "⭐ أضف للمفضلة"),
           callback_data=f"fav:{iid}", style="success"),
    ]]
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
        rows.append([IB(make_bold_unicode(scroll(lbl, off)),
                        callback_data=f"pf:{sec['id']}:{item['id']}:{idx}:{page}", style="primary")])
    if not rows:
        rows.append([IB(make_bold_unicode("لا توجد ملفات في هذه القائمة"), callback_data="noop")])
    else:
        rows.append([IB(make_bold_unicode("📥 إرسال كل الملفات"),
                        callback_data=f"pall:{sec['id']}:{item['id']}:{page}", style="success")])
    fav = item["id"] in USERS.get(str(uid), {}).get("fav", [])
    rows.append([IB(make_bold_unicode("💔 إزالة من المفضلة" if fav else "⭐ أضف للمفضلة"),
                    callback_data=f"fav:{item['id']}", style="success")])
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
    nav = []
    if page > 0:         nav.append(IB("◀️", callback_data=f"mng:{sec['id']}:{page-1}", style="primary"))
    nav.append(IB(f"{page+1}/{pages}", callback_data="noop"))
    if page < pages - 1: nav.append(IB("▶️", callback_data=f"mng:{sec['id']}:{page+1}", style="primary"))
    if len(nav) > 1: rows.append(nav)
    rows.append([IB(make_bold_unicode(L("back")), callback_data="adm:panel", style="danger")])
    return InlineKeyboardMarkup(rows)

def results_kb(pairs, off=0, back="sections"):
    rows = [[IB(make_bold_unicode(scroll(f"{TYPE_EMOJI.get(it['type'],'📎')} {it['title']} • {s['title']}", off)),
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
    return (f"📚 <b>{make_bold_unicode('أقسام الأرشيف')}</b>\n{LINE}\n"
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
        msg = await safe_edit(q, sections_header(), reply_markup=sections_kb(0))
        start_marquee(ctx, msg, lambda off=0: sections_kb(off),
                      [f"{s['title']} • {len(s['items'])}" for s in DATA["sections"]])
        return

    if data.startswith("sec:"):
        _, sid, page = data.split(":")
        sec = get_section(sid)
        if not sec:
            await safe_edit(q, "⚠️ القسم غير موجود."); return
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
        if it["type"] == "pack":
            await show_pack(ctx, q, sec, it, int(page), uid)
            return
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
        await send_pack_file(ctx.bot, q.message.chat_id, it, files[int(idx)])
        return

    if data.startswith("pall:"):
        _, sid, iid, page = data.split(":")
        sec = get_section(sid); it = get_item(sec, iid) if sec else None
        files = it.get("files", []) if it else []
        if not files:
            await q.answer("⚠️ لا توجد ملفات", show_alert=True); return
        for f in files:
            try:
                await send_pack_file(ctx.bot, q.message.chat_id, it, f)
            except Exception as e:
                log.warning("send pack file failed: %s", e)
        return

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
            sec["items"] = [i for i in sec["items"] if i["id"] != iid]
            save_data(); add_log(f"حذف مادة {iid} من {sec['title']}")
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

    # ── اشتراك إجباري للمستخدم العادي ──
    if not is_admin(uid) and not await sub_ok(ctx.bot, uid):
        await msg.reply_text("📢 يرجى الاشتراك في القناة أولاً:", reply_markup=sub_kb()); return

    # ── بحث ──
    if ctx.user_data.get("search"):
        scope = ctx.user_data.pop("search")
        pool = all_items() if scope is True else [(get_section(scope), it) for it in (get_section(scope) or {"items": []})["items"]]
        res = [(s, it) for s, it in pool
               if s and text and text.lower() in (it["title"] + " " + (it.get("caption") or "")).lower()]
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
    plain = text
    def eq(label):
        return plain in (label, make_bold_unicode(label))

    if eq(L("sections")):
        m = await msg.reply_text(sections_header(), parse_mode=ParseMode.HTML, reply_markup=sections_kb(0))
        start_marquee(ctx, m, lambda off=0: sections_kb(off),
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
