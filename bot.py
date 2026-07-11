# ═══════════════════════════════════════════════════════════════
# 🤖 OTP APP IBRAHIM — Telegram Bot (Zenex + ZYRON + Combos + Mino)
#   pip install python-telegram-bot==21.6 requests
#   python bot.py
# ═══════════════════════════════════════════════════════════════
import asyncio, json, logging, os, re, time
from collections import defaultdict

import requests
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

# ══════════════════ TEXT BOLD HELPER (ألوان) ══════════════════
def make_bold_unicode(text):
    out = []
    for char in text:
        codepoint = ord(char)
        if 65 <= codepoint <= 90:  # A-Z
            out.append(chr(codepoint - 65 + 0x1D5D4))
        elif 97 <= codepoint <= 122:  # a-z
            out.append(chr(codepoint - 97 + 0x1D5EE))
        elif 48 <= codepoint <= 57:  # 0-9
            out.append(chr(codepoint - 48 + 0x1D7EC))
        else:
            out.append(char)
    return "".join(out)

# ══════════════════ STICKERS SECTION (ANIMATED) ══════════════════
# هذه الستيكرات كلها متحركة (Animated) وتم اختبارها
SERVICE_STICKERS = {
    "telegram":  "CAACAgQAAxkBAAMWalE9ysTxPY_EIMEcm0NLLR5TzQsAAoMVAALNcSBQbezxTdykgl48BA",
    "instagram": "CAACAgQAAxkBAAMXalE-o09K3zpAd6TZZ76xX75VMk8AAhsRAALqYClQBW59mi-1AUY8BA",
    "whatsapp":  "CAACAgQAAxkBAAMdalFNLyEkOG2l1Aw2V5PtSdeR7sQAAgMUAALzjSBTFdGk8PyPORM8BA",
    "facebook":  "CAACAgQAAxkBAAMfalFw15F8SBq8Lk-gWb9B_puK_QkAAq4VAAJ-fxFTzOJ3pX02GEM8BA",
    "tiktok":    "CAACAgQAAxkBAAMfalFw6FEoKF7x_xiLxYgFkNGc61gAAq0VAAJ-fxFTbGJtXnFQs8A8BA",
    "imo":       "",  # ← ضع file_id لستيكر imo (أرسل الستيكر للبوت ليعطيك الـ file_id)
    # لإضافة/تحديث: أرسل الستيكر مباشرة للبوت وسيرجع لك الـ file_id لتضعه هنا
}

# ══════════════════ CONFIG (edit here) ══════════════════
BOT_TOKEN = "8907846587:AAGSHZbj0BN2okK0hUqd0lgMQVa789yZQJE"
ADMIN_IDS = [8761832730]

# Zenex — direct credentials
ZENEX_URL   = "https://api.zenexnetwork.com/v1"
ZENEX_TOKEN = "ZNX_KB2H1GOF4PJR4H6FN9GJ1VMX"

# ZYRON — direct credentials (auto-login on start)
ZYRON_HOST = "http://151.80.19.204/ints/login"
ZYRON_USER = "Hama11"                             # ← اسم المستخدم
ZYRON_PASS = "Hama11"                             # ← كلمة السر

# NumberPanel.tech — REST API (المصدر الثالث)
NP_URL   = "https://numberpanel.tech/api"
NP_TOKEN = "np_live_cXAtYgOl0nfrmdktshMoLztN9JEoOe6VUei7Df_d_sE"

# Mino — الموقع الرابع (جديد)
MINO_API_KEY = "mino_live_286408936c463de9e9da08db0255ac1c"
MINO_BASE_URL = "https://mino-sms-panel.xyz"

# OTP group (send masked notice to this group). 0 = disabled.
OTP_GROUP_ID = -1003921031641
OTP_GROUP_LINK = "https://t.me/shHsu77"
OTP_GROUP_TITLE = "🔔 جروب OTP"
MASK_GROUP_CODE = False
BOT_USERNAME = "@Otptestre_bot"

REQUIRED_CHANNELS = [{"id": -1003974736720, "title": "القناة الأولى", "url": "https://t.me/gvbhvc669"}]
FORCE_JOIN_GROUP = True
STATE_FILE = "state.json"
USERS_FILE = "users.json"
COMBO_FILE = "combos.json"

NUMBER_TTL_MIN = 20
POLL_INTERVAL  = 3
POLL_TIMEOUT   = NUMBER_TTL_MIN * 60

SERVICE_MAP = {
    "whatsapp":  {"emoji": "🟢", "keys": ["whatsapp"],  "name": {"ar": "واتساب", "en": "WhatsApp",  "ku": "واتساپ"}},
    "facebook":  {"emoji": "🔵", "keys": ["facebook"],  "name": {"ar": "فيسبوك", "en": "Facebook",  "ku": "فەیسبوک"}},
    "telegram":  {"emoji": "✈️", "keys": ["telegram"],  "name": {"ar": "تيليجرام","en": "Telegram", "ku": "تێلێگرام"}},
    "instagram": {"emoji": "📸", "keys": ["instagram"], "name": {"ar": "إنستجرام","en": "Instagram","ku": "ئینستاگرام"}},
    "tiktok":    {"emoji": "🎵", "keys": ["tiktok"],    "name": {"ar": "تيك توك","en": "TikTok",    "ku": "تیک تۆک"}},
    "imo":       {"emoji": "💬", "keys": ["imo"],       "name": {"ar": "إيمو",   "en": "imo",       "ku": "ئیمۆ"}},
}

# اسم كل دولة بثلاث لغات
ISO_NAMES = {
    "sd":{"ar":"السودان","en":"Sudan","ku":"سوودان"},
    "eg":{"ar":"مصر","en":"Egypt","ku":"میسر"},
    "sa":{"ar":"السعودية","en":"Saudi Arabia","ku":"سعوودیە"},
    "ae":{"ar":"الإمارات","en":"UAE","ku":"ئیمارات"},
    "kw":{"ar":"الكويت","en":"Kuwait","ku":"کوەیت"},
    "qa":{"ar":"قطر","en":"Qatar","ku":"قەتەر"},
    "bh":{"ar":"البحرين","en":"Bahrain","ku":"بەحرەین"},
    "om":{"ar":"عُمان","en":"Oman","ku":"عومان"},
    "ye":{"ar":"اليمن","en":"Yemen","ku":"یەمەن"},
    "iq":{"ar":"العراق","en":"Iraq","ku":"عێراق"},
    "sy":{"ar":"سوريا","en":"Syria","ku":"سووریا"},
    "lb":{"ar":"لبنان","en":"Lebanon","ku":"لوبنان"},
    "jo":{"ar":"الأردن","en":"Jordan","ku":"ئوردن"},
    "ps":{"ar":"فلسطين","en":"Palestine","ku":"فەڵەستین"},
    "il":{"ar":"إسرائيل","en":"Israel","ku":"ئیسرائیل"},
    "tr":{"ar":"تركيا","en":"Turkey","ku":"تورکیا"},
    "ir":{"ar":"إيران","en":"Iran","ku":"ئێران"},
    "af":{"ar":"أفغانستان","en":"Afghanistan","ku":"ئەفغانستان"},
    "pk":{"ar":"باكستان","en":"Pakistan","ku":"پاکستان"},
    "in":{"ar":"الهند","en":"India","ku":"هیندستان"},
    "bd":{"ar":"بنغلاديش","en":"Bangladesh","ku":"بەنگلادێش"},
    "lk":{"ar":"سريلانكا","en":"Sri Lanka","ku":"سریلانکا"},
    "np":{"ar":"نيبال","en":"Nepal","ku":"نیپاڵ"},
    "mm":{"ar":"ميانمار","en":"Myanmar","ku":"میانمار"},
    "th":{"ar":"تايلاند","en":"Thailand","ku":"تایلەند"},
    "vn":{"ar":"فيتنام","en":"Vietnam","ku":"ڤیەتنام"},
    "id":{"ar":"إندونيسيا","en":"Indonesia","ku":"ئەندۆنیسیا"},
    "my":{"ar":"ماليزيا","en":"Malaysia","ku":"مالیزیا"},
    "sg":{"ar":"سنغافورة","en":"Singapore","ku":"سینگاپور"},
    "ph":{"ar":"الفلبين","en":"Philippines","ku":"فلیپین"},
    "cn":{"ar":"الصين","en":"China","ku":"چین"},
    "jp":{"ar":"اليابان","en":"Japan","ku":"یابان"},
    "kr":{"ar":"كوريا الجنوبية","en":"South Korea","ku":"کۆریای باشوور"},
    "kp":{"ar":"كوريا الشمالية","en":"North Korea","ku":"کۆریای باکوور"},
    "kh":{"ar":"كمبوديا","en":"Cambodia","ku":"کەمبۆدیا"},
    "la":{"ar":"لاوس","en":"Laos","ku":"لاوس"},
    "mn":{"ar":"منغوليا","en":"Mongolia","ku":"مەنگۆلیا"},
    "us":{"ar":"الولايات المتحدة","en":"United States","ku":"ئەمریکا"},
    "ca":{"ar":"كندا","en":"Canada","ku":"کەنەدا"},
    "mx":{"ar":"المكسيك","en":"Mexico","ku":"مەکسیک"},
    "br":{"ar":"البرازيل","en":"Brazil","ku":"برازیل"},
    "ar":{"ar":"الأرجنتين","en":"Argentina","ku":"ئەرجەنتین"},
    "cl":{"ar":"تشيلي","en":"Chile","ku":"چیلی"},
    "co":{"ar":"كولومبيا","en":"Colombia","ku":"کۆلۆمبیا"},
    "pe":{"ar":"بيرو","en":"Peru","ku":"پیرو"},
    "ve":{"ar":"فنزويلا","en":"Venezuela","ku":"ڤەنزوێلا"},
    "ec":{"ar":"الإكوادور","en":"Ecuador","ku":"ئیکوادۆر"},
    "bo":{"ar":"بوليفيا","en":"Bolivia","ku":"بۆلیڤیا"},
    "py":{"ar":"باراغواي","en":"Paraguay","ku":"پاراگوای"},
    "uy":{"ar":"أوروغواي","en":"Uruguay","ku":"ئوروگوای"},
    "gy":{"ar":"غيانا","en":"Guyana","ku":"گویانا"},
    "cu":{"ar":"كوبا","en":"Cuba","ku":"کووبا"},
    "ht":{"ar":"هايتي","en":"Haiti","ku":"هایتی"},
    "jm":{"ar":"جامايكا","en":"Jamaica","ku":"جامایکا"},
    "gt":{"ar":"غواتيمالا","en":"Guatemala","ku":"گواتیمالا"},
    "sv":{"ar":"السلفادور","en":"El Salvador","ku":"سالڤادۆر"},
    "hn":{"ar":"هندوراس","en":"Honduras","ku":"هوندۆراس"},
    "cr":{"ar":"كوستاريكا","en":"Costa Rica","ku":"کۆستاریکا"},
    "pa":{"ar":"بنما","en":"Panama","ku":"پەنەما"},
    "bz":{"ar":"بليز","en":"Belize","ku":"بێلیز"},
    "gb":{"ar":"بريطانيا","en":"United Kingdom","ku":"بەریتانیا"},
    "fr":{"ar":"فرنسا","en":"France","ku":"فەڕەنسا"},
    "de":{"ar":"ألمانيا","en":"Germany","ku":"ئەڵمانیا"},
    "it":{"ar":"إيطاليا","en":"Italy","ku":"ئیتاڵیا"},
    "es":{"ar":"إسبانيا","en":"Spain","ku":"ئیسپانیا"},
    "pt":{"ar":"البرتغال","en":"Portugal","ku":"پورتوگاڵ"},
    "nl":{"ar":"هولندا","en":"Netherlands","ku":"هۆڵەندا"},
    "be":{"ar":"بلجيكا","en":"Belgium","ku":"بەلجیکا"},
    "ch":{"ar":"سويسرا","en":"Switzerland","ku":"سویسرا"},
    "at":{"ar":"النمسا","en":"Austria","ku":"نەمسا"},
    "se":{"ar":"السويد","en":"Sweden","ku":"سوید"},
    "no":{"ar":"النرويج","en":"Norway","ku":"نەرویج"},
    "dk":{"ar":"الدنمارك","en":"Denmark","ku":"دانمارک"},
    "fi":{"ar":"فنلندا","en":"Finland","ku":"فینلاندا"},
    "ie":{"ar":"أيرلندا","en":"Ireland","ku":"ئیرلەندا"},
    "hu":{"ar":"المجر","en":"Hungary","ku":"هەنگاریا"},
    "pl":{"ar":"بولندا","en":"Poland","ku":"پۆڵۆنیا"},
    "ua":{"ar":"أوكرانيا","en":"Ukraine","ku":"ئۆکرانیا"},
    "ru":{"ar":"روسيا","en":"Russia","ku":"ڕووسیا"},
    "by":{"ar":"بيلاروسيا","en":"Belarus","ku":"بێلاڕوس"},
    "lt":{"ar":"ليتوانيا","en":"Lithuania","ku":"لیتوانیا"},
    "lv":{"ar":"لاتفيا","en":"Latvia","ku":"لاتڤیا"},
    "ee":{"ar":"إستونيا","en":"Estonia","ku":"ئیستۆنیا"},
    "md":{"ar":"مولدوفا","en":"Moldova","ku":"مۆلدۆڤا"},
    "am":{"ar":"أرمينيا","en":"Armenia","ku":"ئەرمینیا"},
    "az":{"ar":"أذربيجان","en":"Azerbaijan","ku":"ئازەربایجان"},
    "ge":{"ar":"جورجيا","en":"Georgia","ku":"جۆرجیا"},
    "kg":{"ar":"قيرغيزستان","en":"Kyrgyzstan","ku":"قرغیزستان"},
    "tj":{"ar":"طاجيكستان","en":"Tajikistan","ku":"تاجیکستان"},
    "tm":{"ar":"تركمانستان","en":"Turkmenistan","ku":"تورکمانستان"},
    "uz":{"ar":"أوزبكستان","en":"Uzbekistan","ku":"ئوزبەکستان"},
    "ro":{"ar":"رومانيا","en":"Romania","ku":"ڕۆمانیا"},
    "bg":{"ar":"بلغاريا","en":"Bulgaria","ku":"بولگاریا"},
    "rs":{"ar":"صربيا","en":"Serbia","ku":"سربیا"},
    "hr":{"ar":"كرواتيا","en":"Croatia","ku":"کرواتیا"},
    "si":{"ar":"سلوفينيا","en":"Slovenia","ku":"سلۆڤینیا"},
    "sk":{"ar":"سلوفاكيا","en":"Slovakia","ku":"سلۆڤاکیا"},
    "cz":{"ar":"التشيك","en":"Czech Republic","ku":"چیک"},
    "ba":{"ar":"البوسنة","en":"Bosnia","ku":"بۆسنیا"},
    "me":{"ar":"الجبل الأسود","en":"Montenegro","ku":"مۆنتێنیگرۆ"},
    "mk":{"ar":"مقدونيا","en":"North Macedonia","ku":"مەقدۆنیا"},
    "al":{"ar":"ألبانيا","en":"Albania","ku":"ئەڵبانیا"},
    "gr":{"ar":"اليونان","en":"Greece","ku":"یۆنان"},
    "cy":{"ar":"قبرص","en":"Cyprus","ku":"قوبرس"},
    "mt":{"ar":"مالطا","en":"Malta","ku":"ماڵتا"},
    "is":{"ar":"آيسلندا","en":"Iceland","ku":"ئایسلاندا"},
    "lu":{"ar":"لوكسمبورغ","en":"Luxembourg","ku":"لوکسەمبورگ"},
    "mc":{"ar":"موناكو","en":"Monaco","ku":"مۆناکۆ"},
    "ad":{"ar":"أندورا","en":"Andorra","ku":"ئەندۆرا"},
    "gi":{"ar":"جبل طارق","en":"Gibraltar","ku":"جەبەل تارق"},
    "fo":{"ar":"جزر فارو","en":"Faroe Islands","ku":"دوورگەکانی فارۆ"},
    "gl":{"ar":"غرينلاند","en":"Greenland","ku":"گرینلاند"},
    "au":{"ar":"أستراليا","en":"Australia","ku":"ئوسترالیا"},
    "nz":{"ar":"نيوزيلندا","en":"New Zealand","ku":"نیوزیلاند"},
    "fj":{"ar":"فيجي","en":"Fiji","ku":"فیجی"},
    "pg":{"ar":"بابوا غينيا الجديدة","en":"Papua New Guinea","ku":"پاپوا"},
    "ma":{"ar":"المغرب","en":"Morocco","ku":"مەغریب"},
    "dz":{"ar":"الجزائر","en":"Algeria","ku":"جەزائیر"},
    "tn":{"ar":"تونس","en":"Tunisia","ku":"تونس"},
    "ly":{"ar":"ليبيا","en":"Libya","ku":"لیبیا"},
    "et":{"ar":"إثيوبيا","en":"Ethiopia","ku":"ئەتیۆپیا"},
    "so":{"ar":"الصومال","en":"Somalia","ku":"سۆماڵ"},
    "dj":{"ar":"جيبوتي","en":"Djibouti","ku":"جیبووتی"},
    "tz":{"ar":"تنزانيا","en":"Tanzania","ku":"تانزانیا"},
    "ug":{"ar":"أوغندا","en":"Uganda","ku":"ئوگاندا"},
    "bi":{"ar":"بوروندي","en":"Burundi","ku":"بوروندی"},
    "mz":{"ar":"موزمبيق","en":"Mozambique","ku":"مۆزەمبیک"},
    "zm":{"ar":"زامبيا","en":"Zambia","ku":"زامبیا"},
    "zw":{"ar":"زيمبابوي","en":"Zimbabwe","ku":"زیمبابوی"},
    "na":{"ar":"ناميبيا","en":"Namibia","ku":"نامیبیا"},
    "mw":{"ar":"مالاوي","en":"Malawi","ku":"ماڵاوی"},
    "ls":{"ar":"ليسوتو","en":"Lesotho","ku":"لیسۆتۆ"},
    "bw":{"ar":"بوتسوانا","en":"Botswana","ku":"بۆتسوانا"},
    "sz":{"ar":"إسواتيني","en":"Eswatini","ku":"سوازیلاند"},
    "km":{"ar":"جزر القمر","en":"Comoros","ku":"کۆمۆرۆس"},
    "gm":{"ar":"غامبيا","en":"Gambia","ku":"گامبیا"},
    "sn":{"ar":"السنغال","en":"Senegal","ku":"سینیگاڵ"},
    "mr":{"ar":"موريتانيا","en":"Mauritania","ku":"مۆریتانیا"},
    "ml":{"ar":"مالي","en":"Mali","ku":"ماڵی"},
    "gn":{"ar":"غينيا","en":"Guinea","ku":"گینێ"},
    "bf":{"ar":"بوركينا فاسو","en":"Burkina Faso","ku":"بورکینا فاسۆ"},
    "ne":{"ar":"النيجر","en":"Niger","ku":"نیجەر"},
    "tg":{"ar":"توغو","en":"Togo","ku":"تۆگۆ"},
    "bj":{"ar":"بنين","en":"Benin","ku":"بێنین"},
    "mu":{"ar":"موريشيوس","en":"Mauritius","ku":"مۆریشس"},
    "lr":{"ar":"ليبيريا","en":"Liberia","ku":"لیبێریا"},
    "sl":{"ar":"سيراليون","en":"Sierra Leone","ku":"سیرالیۆن"},
    "cm":{"ar":"الكاميرون","en":"Cameroon","ku":"کامیرۆن"},
    "ci":{"ar":"ساحل العاج","en":"Ivory Coast","ku":"کۆتی دیڤوار"},
    "mg":{"ar":"مدغشقر","en":"Madagascar","ku":"مەدەگاسکار"},
    "td":{"ar":"تشاد","en":"Chad","ku":"چاد"},
    "cf":{"ar":"إفريقيا الوسطى","en":"Central African Republic","ku":"ئەفریقای ناوەڕاست"},
    "cv":{"ar":"الرأس الأخضر","en":"Cape Verde","ku":"کاپڤێرد"},
    "st":{"ar":"ساو تومي","en":"Sao Tome","ku":"ساوتۆمێ"},
    "gq":{"ar":"غينيا الاستوائية","en":"Equatorial Guinea","ku":"گینێی ئیستوایی"},
    "ga":{"ar":"الغابون","en":"Gabon","ku":"گابۆن"},
    "cg":{"ar":"الكونغو","en":"Congo","ku":"کۆنگۆ"},
    "cd":{"ar":"جمهورية الكونغو الديمقراطية","en":"DR Congo","ku":"کۆنگۆی د.ک."},
    "ao":{"ar":"أنغولا","en":"Angola","ku":"ئەنگۆلا"},
    "gw":{"ar":"غينيا بيساو","en":"Guinea-Bissau","ku":"گینێ بیساو"},
    "sh":{"ar":"سانت هيلينا","en":"Saint Helena","ku":"سانت هیلینا"},
    "sc":{"ar":"سيشل","en":"Seychelles","ku":"سیشێل"},
    "rw":{"ar":"رواندا","en":"Rwanda","ku":"ڕواندا"},
    "er":{"ar":"إريتريا","en":"Eritrea","ku":"ئێریتریا"},
    "ng":{"ar":"نيجيريا","en":"Nigeria","ku":"نایجیریا"},
    "ke":{"ar":"كينيا","en":"Kenya","ku":"کینیا"},
    "gh":{"ar":"غانا","en":"Ghana","ku":"گانا"},
    "za":{"ar":"جنوب أفريقيا","en":"South Africa","ku":"باشوری ئەفریقا"},
}

CC_TO_ISO = {
    "20":"eg","27":"za","30":"gr","31":"nl","32":"be","33":"fr","34":"es","36":"hu",
    "39":"it","40":"ro","41":"ch","43":"at","44":"gb","45":"dk","46":"se","47":"no",
    "48":"pl","49":"de","51":"pe","52":"mx","53":"cu","54":"ar","55":"br","56":"cl",
    "57":"co","58":"ve","60":"my","61":"au","62":"id","63":"ph","64":"nz","65":"sg",
    "66":"th","81":"jp","82":"kr","84":"vn","86":"cn","90":"tr","91":"in","92":"pk",
    "93":"af","94":"lk","95":"mm","98":"ir","1":"us","7":"ru",
    "212":"ma","213":"dz","216":"tn","218":"ly","220":"gm","221":"sn","222":"mr",
    "223":"ml","224":"gn","225":"ci","226":"bf","227":"ne","228":"tg","229":"bj",
    "230":"mu","231":"lr","232":"sl","233":"gh","234":"ng","235":"td","236":"cf",
    "237":"cm","238":"cv","239":"st","240":"gq","241":"ga","242":"cg","243":"cd",
    "244":"ao","245":"gw","247":"sh","248":"sc","249":"sd","250":"rw","251":"et",
    "252":"so","253":"dj","254":"ke","255":"tz","256":"ug","257":"bi","258":"mz",
    "260":"zm","261":"mg","263":"zw","264":"na","265":"mw","266":"ls","267":"bw",
    "268":"sz","269":"km","290":"sh","291":"er","298":"fo","299":"gl",
    "350":"gi","351":"pt","352":"lu","353":"ie","354":"is","355":"al","356":"mt",
    "357":"cy","358":"fi","359":"bg","370":"lt","371":"lv","372":"ee","373":"md",
    "374":"am","375":"by","376":"ad","377":"mc","380":"ua","381":"rs","382":"me",
    "385":"hr","386":"si","387":"ba","389":"mk","420":"cz","421":"sk",
    "501":"bz","502":"gt","503":"sv","504":"hn","506":"cr","507":"pa","509":"ht",
    "591":"bo","592":"gy","593":"ec","595":"py","598":"uy",
    "670":"tl","675":"pg","679":"fj","850":"kp","852":"hk","853":"mo","855":"kh",
    "856":"la","880":"bd","886":"tw",
    "960":"mv","961":"lb","962":"jo","963":"sy","964":"iq","965":"kw","966":"sa",
    "967":"ye","968":"om","970":"ps","971":"ae","972":"il","973":"bh","974":"qa",
    "975":"bt","976":"mn","977":"np","992":"tj","993":"tm","994":"az","995":"ge",
    "996":"kg","998":"uz",
}

def find_iso_by_name(text):
    """يقبل ISO / اسم دولة (عربي/إن/كردي) / رمز اتصال / رقم كامل."""
    s = str(text or "").strip().lower()
    if not s: return ""
    if s in ISO_NAMES: return s
    if s in CC_TO_ISO: return CC_TO_ISO[s]
    digits = re.sub(r"\D","", s)
    if digits:
        for L in (4,3,2,1):
            if len(digits) >= L and digits[:L] in CC_TO_ISO: return CC_TO_ISO[digits[:L]]
    for iso, d in ISO_NAMES.items():
        for v in d.values():
            if v.lower() == s: return iso
    for iso, d in ISO_NAMES.items():
        for v in d.values():
            if len(s) >= 3 and (s in v.lower() or v.lower() in s): return iso
    return ""

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger("otp")

# ══════════════════ i18n ══════════════════
T = {
    "ar": {"hi":"أهلاً","get_number":"📞 احصل على رقم","language":"🌐 اللغة",
        "admin_panel":"🛠 لوحة الأدمن","pick_service":"📱 اختر الخدمة:","pick_country":"🌍 اختر الدولة:",
        "no_country":"⚠️ لا توجد دول متاحة حالياً.","reserving":"⏳ جاري حجز الرقم...",
        "reserved":"✅ تم حجز الرقم","no_range":"⚠️ لا يوجد رقم متاح لهذه الدولة.",
        "waiting_code":"⏳ بانتظار الكود...","code_arrived":"🔐 وصل الكود!",
        "cancel_number":"❌ إلغاء","change_country":"🌍 تغيير الدولة","new_number":"🔄 رقم جديد",
        "back":"⬅️ رجوع","copy":"📋 نسخ","timeout":"⌛ انتهت المهلة","banned":"⛔ محظور",
        "admin_only":"⛔ للأدمن فقط","choose_lang":"🌐 اختر لغتك:","lang_set":"✅ تم تغيير اللغة",
        "add_range_zenex":"➕ إضافة رينج زينيكس","add_range_mino":"➕ إضافة رينج Mino",
        "code_label":"🔑 الرمز","copy_hint":"(اضغط على الرمز أعلاه لنسخه)",
        "back_ar":"⬅️ رجوع",
        "operator":"📶 المشغل","service":"📱 الخدمة","country":"🌍 الدولة","number":"☎️ الرقم",
        "must_join":"🔒 اشترك أولاً في القنوات/الجروب التالية للاستمرار:",
        "check_sub":"✅ تحققت من الاشتراك","not_subbed":"⚠️ لم تشترك في كل القنوات بعد.",
        "open_bot":"🤖 افتح البوت لرؤية الكود","join_group":"🔔 جروب OTP","goto_group":"🔔 اذهب لجروب OTP",
        "code_hidden":"🔒 الكود مخفي — افتح البوت لعرضه"},
    "en": {"hi":"Hi","get_number":"📞 Get Number","language":"🌐 Language",
        "admin_panel":"🛠 Admin","pick_service":"📱 Choose a service:","pick_country":"🌍 Choose a country:",
        "no_country":"⚠️ No countries available.","reserving":"⏳ Reserving...",
        "reserved":"✅ Number reserved","no_range":"⚠️ No number available.",
        "waiting_code":"⏳ Waiting for code...","code_arrived":"🔐 Code received!",
        "cancel_number":"❌ Cancel","change_country":"🌍 Change Country","new_number":"🔄 New Number",
        "back":"⬅️ Back","copy":"📋 Copy","timeout":"⌛ Timed out","banned":"⛔ Banned",
        "admin_only":"⛔ Admin only","choose_lang":"🌐 Choose language:","lang_set":"✅ Language updated",
        "add_range_zenex":"➕ Add Zenex range","add_range_mino":"➕ Add Mino range",
        "code_label":"🔑 Code","copy_hint":"(Tap the code above to copy)",
        "back_ar":"⬅️ Back",
        "operator":"📶 Operator","service":"📱 Service","country":"🌍 Country","number":"☎️ Number",
        "must_join":"🔒 Join the following channels/group to continue:",
        "check_sub":"✅ I have joined","not_subbed":"⚠️ Not subscribed to all channels.",
        "open_bot":"🤖 Open the bot to see the code","join_group":"🔔 OTP Group","goto_group":"🔔 Go to OTP Group",
        "code_hidden":"🔒 Code hidden — open the bot to view it"},
    "ku": {"hi":"بەخێربێی","get_number":"📞 وەرگرتنی ژمارە","language":"🌐 زمان",
        "admin_panel":"🛠 ئەدمین","pick_service":"📱 خزمەتگوزارییەک هەڵبژێرە:","pick_country":"🌍 وڵاتێک هەڵبژێرە:",
        "no_country":"⚠️ هیچ وڵاتێک بەردەست نییە.","reserving":"⏳ خەریکە ژمارە دەگرێت...",
        "reserved":"✅ ژمارە گیرا","no_range":"⚠️ ژمارە بەردەست نییە.",
        "waiting_code":"⏳ چاوەڕوانی کۆد...","code_arrived":"🔐 کۆد گەیشت!",
        "cancel_number":"❌ هەڵوەشاندنەوە","change_country":"🌍 گۆڕینی وڵات","new_number":"🔄 ژمارەیەکی نوێ",
        "back":"⬅️ گەڕانەوە","copy":"📋 لەبەرگرتنەوە","timeout":"⌛ کاتی تەواو بوو","banned":"⛔ قەدەغەکراوی",
        "admin_only":"⛔ تەنیا بۆ ئەدمین","choose_lang":"🌐 زمانەکەت هەڵبژێرە:","lang_set":"✅ زمان گۆڕدرا",
        "add_range_zenex":"➕ زیادکردنی ڕەنجی Zenex","add_range_mino":"➕ زیادکردنی ڕەنجی Mino",
        "code_label":"🔑 کۆد","copy_hint":"(بکە لە کۆد بۆ کۆپیکردن)",
        "back_ar":"⬅️ گەڕانەوە",
        "operator":"📶 ئۆپەراتۆر","service":"📱 خزمەتگوزاری","country":"🌍 وڵات","number":"☎️ ژمارە",
        "must_join":"🔒 پێویستە لەم کەناڵ/گرووپانە بەشدار بیت:",
        "check_sub":"✅ بەشداربووم","not_subbed":"⚠️ بەشدار نیت لە هەموو کەناڵەکاندا.",
        "open_bot":"🤖 بۆتەکە بکەرەوە بۆ بینینی کۆد","join_group":"🔔 گرووپی OTP","goto_group":"🔔 بڕۆ بۆ گرووپی OTP",
        "code_hidden":"🔒 کۆد شاراوەیە — بۆتەکە بکەرەوە"},
}
def tr(lang, k): return T.get(lang, T["ar"]).get(k, T["ar"].get(k, k))
def svc_name(sid, lang):
    s = SERVICE_MAP.get(sid)
    return s["name"].get(lang, s["name"]["en"]) if s else sid
def iso_name(iso, lang):
    d = ISO_NAMES.get((iso or "").lower())
    return d.get(lang, d.get("en")) if d else (iso or "").upper()

# ══════════════════ Storage ══════════════════
def _load(fp, default):
    if not os.path.exists(fp): _save(fp, default); return default
    try:
        with open(fp, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return default
def _save(fp, data):
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

STATE  = _load(STATE_FILE, {"disabled": [], "custom": {}, "provider": "zenex", "mino_ranges": []})
USERS  = _load(USERS_FILE, {})
COMBOS = _load(COMBO_FILE, {})
STATE.setdefault("provider", "zenex"); STATE.setdefault("custom", {}); STATE.setdefault("disabled", []); STATE.setdefault("mino_ranges", [])

def save_state(): _save(STATE_FILE, STATE)
def save_users(): _save(USERS_FILE, USERS)
def save_combos(): _save(COMBO_FILE, COMBOS)

RESERVATIONS = {}
LAST_OTP = _load("last_otp.json", None)

def save_last_otp(): _save("last_otp.json", LAST_OTP)
def _norm_num(n): return re.sub(r"\D", "", str(n or ""))
def register_reservation(number, uid, sid, iso, svc_name_, country):
    k = _norm_num(number)
    if not k: return
    RESERVATIONS[k] = {"uid": int(uid), "sid": sid, "iso": iso, "svc_name": svc_name_, "country": country, "ts": int(time.time())}
def unregister_reservation(number): RESERVATIONS.pop(_norm_num(number), None)
def find_reserver(number): return RESERVATIONS.get(_norm_num(number))

def set_last_otp(uid, number, code, svc_name_, country, iso):
    global LAST_OTP
    u = USERS.get(str(uid), {}) if uid else {}
    LAST_OTP = {"uid": int(uid) if uid else 0, "name": u.get("name") or "", "username": u.get("username") or "", "number": str(number), "code": str(code), "service": svc_name_, "country": country, "iso": iso, "ts": int(time.time())}
    save_last_otp()

def get_user(uid):
    k = str(uid)
    if k not in USERS:
        USERS[k] = {"lang":"ar","banned":False, "stats":{"numbers":0,"otps":0,"cancels":0}, "history":[], "joined": int(time.time())}
        save_users()
    u = USERS[k]
    u.setdefault("lang","ar"); u.setdefault("stats",{"numbers":0,"otps":0,"cancels":0}); u.setdefault("history",[])
    return u

def note_user(tg_user):
    u = get_user(tg_user.id)
    try:
        u["name"] = tg_user.full_name
        u["username"] = tg_user.username or ""
        u.setdefault("joined", int(time.time()))
        save_users()
    except Exception: pass
    return u

def flag(iso):
    if not iso or len(iso) != 2: return "🌍"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso.upper())
def guess_iso(number):
    d = re.sub(r"\D", "", number or "")
    for L in (3,2,1):
        if len(d) >= L and d[:L] in CC_TO_ISO: return CC_TO_ISO[d[:L]]
    return ""
def mask_number(num):
    d = re.sub(r"\D", "", num or "")
    if len(d) < 6: return "•" * len(d)
    prefix = "+" if str(num).startswith("+") else ""
    return f"{prefix}{d[:3]}{'★'*(len(d)-5)}{d[-2:]}"
def mask_code(code):
    s = str(code or "")
    if len(s) <= 2: return "★" * max(1, len(s))
    return f"{s[0]}{'★'*(len(s)-1)}"

# ══════════════════ Zenex ══════════════════
def zx_headers(): return {"mapikey": ZENEX_TOKEN, "Content-Type":"application/json","Accept":"application/json"}
def zx_active_ranges():
    try:
        r = requests.get(f"{ZENEX_URL}/active-ranges", headers=zx_headers(), timeout=15)
        if not r.ok: return []
        return ((r.json().get("data") or {}).get("active_ranges") or [])
    except Exception: return []
def zx_get_number(rng):
    try:
        r = requests.post(f"{ZENEX_URL}/getnum", headers=zx_headers(), json={"range": rng, "is_national": False, "remove_plus": False}, timeout=20)
        if not r.ok: return None
        d = r.json().get("data") or {}
        num = d.get("number") or d.get("copy") or d.get("full_number")
        if not num: return None
        return {"number": str(num), "country": d.get("country") or "", "iso": (d.get("iso") or "").lower(), "operator": d.get("operator") or ""}
    except Exception: return None
def zx_cancel(number):
    try: requests.post(f"{ZENEX_URL}/cancelnum", headers=zx_headers(), json={"number": number}, timeout=10)
    except Exception: pass
def zx_fetch_otps():
    try:
        r = requests.get(f"{ZENEX_URL}/numsuccess/info", headers=zx_headers(), timeout=15)
        if not r.ok: return []
        return ((r.json().get("data") or {}).get("otps") or [])
    except Exception: return []

# ══════════════════ ZYRON ══════════════════
_ZY_SESS, _ZY_TS = None, 0
def _solve_captcha(html_):
    m = re.search(r"(\d+)\s*([\+\-\*x×])\s*(\d+)\s*=", html_)
    if not m: return "0"
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    return str({"+":a+b,"-":a-b,"*":a*b,"x":a*b,"×":a*b}.get(op, a+b))
def zyron_login():
    global _ZY_SESS, _ZY_TS
    if not (ZYRON_HOST and ZYRON_USER and ZYRON_PASS): return None
    if _ZY_SESS and time.time() - _ZY_TS < 1800: return _ZY_SESS
    s = requests.Session()
    try:
        r = s.get(ZYRON_HOST + "/", timeout=15)
        s.post(ZYRON_HOST + "/signin", data={"username":ZYRON_USER,"password":ZYRON_PASS,"capt":_solve_captcha(r.text)}, timeout=15, allow_redirects=True)
        _ZY_SESS, _ZY_TS = s, time.time()
        log.info("ZYRON login OK")
        return s
    except Exception as e:
        log.warning("ZYRON login failed: %s", e); return None

# ══════════════════ NumberPanel ══════════════════
class NumberPanelSource:
    def __init__(self, base_url, token):
        self.base = base_url.rstrip("/")
        self.token = token
        self._seen_ids = set()

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def _get(self, path, params=None):
        try:
            r = requests.get(f"{self.base}{path}", headers=self._headers(), params=params or {}, timeout=15)
            if r.ok: return r.json()
        except Exception: pass
        return None

    def _post(self, path, payload):
        try:
            r = requests.post(f"{self.base}{path}", headers=self._headers(), json=payload, timeout=15)
            if r.ok: return r.json()
        except Exception: pass
        return None

    def get_my_countries_with_services(self):
        found = []
        try:
            data = self._get("/my_numbers")
            if isinstance(data, dict):
                numbers = data.get("data") or data.get("numbers") or []
                for n in numbers:
                    num = n.get("number") or n.get("phone") or ""
                    service = n.get("service") or "general"
                    if not num: continue
                    clean_num = re.sub(r"\D", "", num)
                    iso = guess_iso(clean_num)
                    if iso:
                        found.append({"iso": iso, "name": iso_name(iso, "en") or iso.upper(), "service": service.lower()})
        except Exception as e: logging.warning(f"NP get_my_countries_with_services error: {e}")
        return found

    def ranges(self):
        out = []
        try:
            pairs = self.get_my_countries_with_services()
            if not pairs: return []
            for p in pairs:
                iso = p["iso"]
                service = p["service"]
                for sid, svc in SERVICE_MAP.items():
                    if service in svc["keys"] or service == sid:
                        out.append({"service": sid, "range": f"np::{sid}::{iso}", "iso": iso, "hits": 1, "country": p["name"]})
        except Exception as e: logging.warning(f"NP ranges error: {e}")
        return out

    def fetch_otps(self):
        new = []
        try:
            data = self._get("/my_otps", {"limit": 50})
            if not isinstance(data, dict) or not data.get("success"): return []
            items = data.get("otps") or []
            for it in items:
                if not isinstance(it, dict): continue
                number = str(it.get("number") or "").strip()
                message = str(it.get("message") or "").strip()
                code = str(it.get("otp_code") or "").strip()
                if not number or not code: continue
                uid = f"np:{number}:{code}"
                if uid in self._seen_ids: continue
                self._seen_ids.add(uid)
                new.append({"id": uid, "number": number, "code": code, "otp": code, "message": message, "date": it.get("timestamp") or "", "service": it.get("service") or "", "country": it.get("country") or ""})
            if len(self._seen_ids) > 10000: self._seen_ids = set(list(self._seen_ids)[-5000:])
        except Exception as e: logging.warning(f"NP fetch_otps error: {e}")
        return new

    def request_number(self, service, country):
        data = self._post("/request_number", {"service": service, "country": country})
        if data:
            number = data.get("number") or data.get("phone")
            if number: return {"number": number}
        return None

    def get_number(self, rng):
        try:
            _, sid, iso = rng.split("::", 2)
            country_name = iso_name(iso, "en")
            res = self.request_number(sid, country_name)
            if res: return {"number": res["number"], "country": country_name, "iso": iso, "operator": "NumberPanel"}
        except Exception: pass
        return None

    def status(self):
        try:
            data = self._get("/otp", {"count": 1})
            return (True, "✅ ناجح (متصل)") if data is not None else (False, "❌ فشل")
        except Exception as e: return False, f"❌ خطأ: {e}"

NP = NumberPanelSource(NP_URL, NP_TOKEN)

# ══════════════════ Mino (الموقع الرابع) ══════════════════
# API الفعلي لموقع mino-sms-panel.xyz (حسب توثيق /docs):
#   POST/GET /getnumber   ?api_key=&rid=&national_format=0/1&remove_plus=0/1
#   GET      /check       ?api_key=&number=
#   GET      /live        ?api_key=
#   GET      /success_otp ?api_key=
#   GET      /console     ?api_key=
# ملاحظة: الرينجات (rid) تُضاف يدوياً من الأدمن (لا يوجد endpoint لسردها).
class MinoSource:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base = base_url.rstrip("/")
        self._seen_ids = set()

    def _get(self, path, params=None):
        try:
            params = dict(params or {})
            params.setdefault("api_key", self.api_key)
            r = requests.get(f"{self.base}{path}", params=params, timeout=15)
            if r.ok:
                try: return r.json()
                except Exception: return {"raw": r.text}
        except Exception as e:
            logging.warning(f"Mino GET {path} error: {e}")
        return None

    def ranges(self):
        """يبني الرينجات من قائمة STATE['mino_ranges'] التي يضيفها الأدمن يدوياً."""
        out = []
        for r in STATE.get("mino_ranges", []):
            rid  = str(r.get("rid") or "").strip()
            sid  = (r.get("sid") or "").lower()
            iso  = (r.get("iso") or "").lower()
            hits = int(r.get("hits") or 1)
            if not rid or not sid or sid not in SERVICE_MAP: continue
            country = r.get("country") or iso_name(iso, "en") or iso.upper()
            out.append({
                "service": sid,
                "range":   f"mino::{rid}::{sid}::{iso}",
                "iso":     iso,
                "hits":    hits,
                "country": country,
            })
        return out

    def get_number(self, rng):
        """rng = mino::<rid>::<sid>::<iso> — يعالج JSON + text (ACCESS_NUMBER:ID:NUMBER) + raw."""
        try:
            parts = rng.split("::")
            if len(parts) < 4: return None
            _, rid, sid, iso = parts[0], parts[1], parts[2], parts[3]
            # نفس صيغة URL في bot.py المرجعي مع fallback params
            url = f"{self.base}/getnumber"
            params = {"api_key": self.api_key, "rid": rid, "range": rid,
                      "target": rid, "national": 1, "remove_plus": 1}
            r = requests.get(url, params=params, timeout=20)
            if not r.ok:
                logging.warning(f"Mino getnumber HTTP {r.status_code}: {r.text[:200]}")
                return None
            raw_text = r.text.strip()
            if not raw_text: return None
            err_keywords = ["NO_NUMBERS","NO_NUMBER","OUT_OF_STOCK","BANNED","LIMIT","ERROR","BALANCE","EMPTY","SQL"]
            if any(err in raw_text.upper() for err in err_keywords):
                logging.info(f"Mino no number for rid={rid}: {raw_text[:100]}")
                return None
            number = None
            # 1) JSON
            try:
                data = r.json()
                if isinstance(data, dict):
                    if str(data.get("status")).lower() in ["error","fail","false"]:
                        return None
                    d = data.get("data") if isinstance(data.get("data"), dict) else data
                    number = (d.get("full_number") or d.get("number") or d.get("phone")
                              or d.get("phoneNumber") or d.get("mobile"))
            except Exception:
                pass
            # 2) split على : أو |
            if not number:
                for part in reversed(re.split(r'[:|]', raw_text)):
                    clean = re.sub(r'\D','', part.strip())
                    if 7 <= len(clean) <= 15:
                        number = clean; break
            # 3) نص خام
            if not number:
                clean_all = re.sub(r'\D','', raw_text)
                if 7 <= len(clean_all) <= 15:
                    number = clean_all
            if not number: return None
            clean_num = re.sub(r'\D','', str(number))
            real_iso = iso or guess_iso(clean_num) or iso
            return {"number": clean_num,
                    "country": iso_name(real_iso, "en") or real_iso.upper(),
                    "iso": real_iso, "operator": "Mino"}
        except Exception as e:
            logging.warning(f"Mino get_number error: {e}")
        return None

    def fetch_otps(self):
        new = []
        try:
            data = self._get("/success_otp")
            if not data: return new
            otps = data.get("otps") or data.get("data") or data.get("results") or []
            if isinstance(otps, dict): otps = otps.get("items") or []
            for otp in otps:
                if not isinstance(otp, dict): continue
                number  = otp.get("number") or otp.get("phone") or ""
                message = otp.get("message") or otp.get("sms") or otp.get("text") or ""
                code    = otp.get("otp_code") or otp.get("otp") or otp.get("code") or ""
                if not (number and code): continue
                uid = f"mino:{number}:{code}:{otp.get('id') or otp.get('timestamp') or ''}"
                if uid in self._seen_ids: continue
                self._seen_ids.add(uid)
                new.append({"id": uid, "number": str(number), "code": str(code),
                            "otp": str(code), "message": message,
                            "date": otp.get("timestamp") or "",
                            "service": otp.get("service") or "",
                            "country": otp.get("country") or ""})
        except Exception as e:
            logging.warning(f"Mino fetch_otps error: {e}")
        return new

    def check(self, number):
        return self._get("/check", {"number": number})

MINO = MinoSource(MINO_API_KEY, MINO_BASE_URL)

# ══════════════════ Login / health status ══════════════════
def zenex_status():
    try:
        r = requests.get(f"{ZENEX_URL}/active-ranges", headers=zx_headers(), timeout=15)
        if r.ok: return True, f"✅ ناجح ({len((r.json().get('data') or {}).get('active_ranges') or [])} رينج نشط)"
        return False, f"❌ فشل (HTTP {r.status_code})"
    except Exception as e: return False, f"❌ خطأ: {e}"

def zyron_status():
    if not (ZYRON_HOST and ZYRON_USER and ZYRON_PASS): return False, "⚪ غير مُعدّ"
    global _ZY_SESS, _ZY_TS
    _ZY_SESS, _ZY_TS = None, 0
    s = zyron_login()
    return (True, "✅ ناجح") if s else (False, "❌ فشل تسجيل الدخول")

def np_status():
    ok, msg = NP.status()
    try: np_ranges = len(NP.ranges())
    except: np_ranges = 0
    return ok, msg, np_ranges

def mino_status():
    try:
        numbers = MINO.ranges()
        return (True, f"✅ ناجح ({len(numbers)} رقم)") if numbers is not None else (False, "❌ فشل")
    except Exception as e: return False, f"❌ خطأ: {e}"

def logins_report():
    zx_ok, zx_msg = zenex_status()
    zy_ok, zy_msg = zyron_status()
    np_ok, np_msg, np_ranges = np_status()
    mino_ok, mino_msg = mino_status()
    return (
        "🔐 <b>حالة الدخول للمواقع</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>Zenex</b>: {zx_msg}\n"
        f"🔵 <b>ZYRON</b>: {zy_msg}\n"
        f"🟣 <b>NumberPanel</b>: {np_msg} ({np_ranges} رينج)\n"
        f"🔴 <b>Mino</b>: {mino_msg}\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )

# ══════════════════ Unified ranges ══════════════════
def all_ranges():
    base = []
    # 1. Zenex
    if STATE.get("provider") == "zenex":
        base.extend(zx_active_ranges())
    # 2. Custom
    for sid, arr in STATE.get("custom", {}).items():
        for r in arr: base.append({**r, "service": sid})
    # 3. NumberPanel
    try:
        base.extend(NP.ranges())
    except Exception: pass
    # 4. Mino
    try:
        base.extend(MINO.ranges())
    except Exception: pass
    return base

def ranges_for_service(sid):
    svc = SERVICE_MAP.get(sid)
    if not svc: return []
    keys = svc["keys"]
    out = []
    for r in all_ranges():
        s = str(r.get("service") or "").lower()
        if any(k in s for k in keys):
            iso = (r.get("iso") or "").lower() or guess_iso(str(r.get("range","")))
            out.append({"range": r["range"], "iso": iso, "hits": int(r.get("hits") or 0)})
    for name, c in COMBOS.get(sid, {}).items():
        remaining = [n for n in c.get("numbers", []) if n not in c.get("used", [])]
        if remaining:
            iso = c.get("iso") or guess_iso(remaining[0])
            out.append({"range": f"combo::{sid}::{name}", "iso": iso, "hits": len(remaining), "combo": name})
    return out

def countries_for_service(sid):
    groups = defaultdict(lambda: {"iso":"","ranges":[],"hits":0})
    for r in ranges_for_service(sid):
        g = groups[r["iso"] or "??"]
        g["iso"] = r["iso"]; g["ranges"].append(r); g["hits"] += r["hits"]
    return sorted(groups.values(), key=lambda x: (-x["hits"], x["iso"]))

def best_range(sid, iso):
    for c in countries_for_service(sid):
        if c["iso"] == iso:
            rs = sorted(c["ranges"], key=lambda r: -r["hits"])
            return rs[0] if rs else None
    return None

def reserve_number(rng):
    if rng.startswith("combo::"):
        _, sid, name = rng.split("::", 2)
        c = COMBOS.get(sid, {}).get(name)
        if not c: return None
        rem = [n for n in c["numbers"] if n not in c.get("used", [])]
        if not rem: return None
        num = rem[0]
        return {"number": num, "country": name, "iso": c.get("iso") or guess_iso(num), "operator": "combo", "combo": (sid, name)}
    if rng.startswith("np::"):
        return NP.get_number(rng)
    if rng.startswith("mino::"):
        return MINO.get_number(rng)
    return zx_get_number(rng)

def cancel_number(number): zx_cancel(number)

def consume_combo(sid, name, number):
    c = COMBOS.get(sid, {}).get(name)
    if not c: return
    c.setdefault("used", []).append(number)
    c["numbers"] = [n for n in c["numbers"] if n != number]
    save_combos()

def find_otp_for(number, seen):
    tail = re.sub(r"\D", "", number)[-9:]
    for msg in zx_fetch_otps():
        mid = str(msg.get("nid") or msg.get("id") or msg.get("created_at") or "")
        if mid in seen: continue
        digits = re.sub(r"\D", "", str(msg.get("number") or ""))
        if not digits.endswith(tail): continue
        raw = str(msg.get("otp") or "")
        m = re.search(r"\b(\d{4,8})\b", raw)
        return {"id": mid, "code": m.group(1) if m else raw, "raw": raw}
    for source, name in [(NP, "NP"), (MINO, "Mino")]:
        try:
            for m in source.fetch_otps():
                if m["id"] in seen: continue
                digits = re.sub(r"\D", "", m["number"])
                if not digits.endswith(tail): continue
                raw = m["otp"]
                mm = re.search(r"\b(\d{3}[-\s]?\d{3,4}|\d{4,8})\b", raw)
                code = re.sub(r"\D", "", mm.group(1)) if mm else raw
                return {"id": m["id"], "code": code, "raw": raw}
        except Exception: pass
    return None

# ══════════════════ Subscription gate ══════════════════
def required_chats():
    chats = list(REQUIRED_CHANNELS)
    if FORCE_JOIN_GROUP and OTP_GROUP_ID:
        chats.append({"id": OTP_GROUP_ID, "title": OTP_GROUP_TITLE, "url": OTP_GROUP_LINK or None, "is_group": True})
    return chats

async def check_subscription(ctx, uid):
    missing = []
    for ch in required_chats():
        try:
            m = await ctx.bot.get_chat_member(ch["id"], uid)
            if m.status in ("left", "kicked"): missing.append(ch)
        except Exception: missing.append(ch)
    return (len(missing) == 0), missing

def _chat_url(ch):
    if ch.get("url"): return ch["url"]
    cid = ch["id"]
    if isinstance(cid, str) and cid.startswith("@"): return f"https://t.me/{cid.lstrip('@')}"
    return None

def sub_kb(missing, lang):
    rows = []
    for ch in missing:
        url = _chat_url(ch)
        icon = "🔔" if ch.get("is_group") else "📢"
        rows.append([InlineKeyboardButton(f"{icon} {ch['title']}", url=url or None, callback_data="noop" if not url else None)])
    rows.append([InlineKeyboardButton(tr(lang, "check_sub"), callback_data="sub:check", style="primary")])
    return InlineKeyboardMarkup(rows)

async def enforce_sub(ctx, chat_id, uid, lang):
    ok, missing = await check_subscription(ctx, uid)
    if ok: return True
    await ctx.bot.send_message(chat_id, tr(lang, "must_join"), reply_markup=sub_kb(missing, lang))
    return False

def bot_url(): return f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else None
def group_url(): return OTP_GROUP_LINK or None

# ══════════════════ Keyboards ══════════════════
def _kb_btn(text, style=None):
    """KeyboardButton مع style (يعمل في الفورك)، آمن لو المكتبة لا تدعم style."""
    try:
        return KeyboardButton(text, style=style) if style else KeyboardButton(text)
    except TypeError:
        return KeyboardButton(text)

def main_kb(lang, is_admin):
    # استخدام KeyboardButton مباشرة مع style
    rows = [
        [KeyboardButton(text=make_bold_unicode(f"📞 {tr(lang, 'get_number')}"), style="primary")]
    ]
    row2 = [
        KeyboardButton(text=make_bold_unicode(f"🌐 {tr(lang, 'language')}"), style="success")
    ]
    if is_admin:
        row2.append(KeyboardButton(text=make_bold_unicode(f"🛠️ {tr(lang, 'admin_panel')}"), style="danger"))
    rows.append(row2)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)
def services_kb(lang):
    rows = []
    for sid, s in SERVICE_MAP.items():
        if sid in STATE.get("disabled", []): continue
        rows.append([InlineKeyboardButton(
            make_bold_unicode(f"{s['emoji']} {svc_name(sid, lang)}"),
            callback_data=f"svc:{sid}",
            style="primary"
        )])
    return InlineKeyboardMarkup(rows)

def countries_kb(sid, lang, page=0):
    countries = countries_for_service(sid)
    if not countries: return None
    per_page = 10
    pages = max(1, (len(countries) + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    sl = countries[page*per_page:(page+1)*per_page]
    rows = []
    for idx, c in enumerate(sl):
        iso = c["iso"]
        country_display_name = ""
        try:
            first_range = c.get("ranges", [{}])[0]
            if first_range: country_display_name = first_range.get("country", "")
        except: pass
        if not country_display_name:
            country_display_name = iso_name(iso, lang)
        if not country_display_name:
            country_display_name = iso.upper() if iso else "Unknown"
        country_display_name = country_display_name.strip()
        rows.append([InlineKeyboardButton(
            make_bold_unicode(f"{flag(iso)} {country_display_name} ✅ {c['hits']}"),
            callback_data=f"co:{sid}:{c['iso']}",
            style="primary"
        )])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("◀️", callback_data=f"cop:{sid}:{page-1}", style="primary"))
    nav.append(InlineKeyboardButton(f"{page+1}/{pages}", callback_data="noop"))
    if page < pages - 1: nav.append(InlineKeyboardButton("▶️", callback_data=f"cop:{sid}:{page+1}", style="primary"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton("🔄", callback_data=f"cop:{sid}:{page}", style="primary"),
                 InlineKeyboardButton(make_bold_unicode(tr(lang, "back")), callback_data="services", style="danger")])
    return InlineKeyboardMarkup(rows)

def number_kb(sid, iso, number, lang):
    rows = [
        [InlineKeyboardButton(make_bold_unicode(tr(lang, "new_number")), callback_data=f"new:{sid}:{iso}", style="success")],
        [InlineKeyboardButton(make_bold_unicode(tr(lang, "change_country")), callback_data=f"svc:{sid}", style="primary"),
         InlineKeyboardButton(make_bold_unicode(tr(lang, "copy")), callback_data=f"cp:{number}", style="primary")],
    ]
    gu = group_url()
    if gu: rows.append([InlineKeyboardButton(make_bold_unicode(tr(lang, "goto_group")), url=gu, style="primary")])
    rows.append([InlineKeyboardButton(make_bold_unicode(tr(lang, "cancel_number")), callback_data=f"cxl:{number}:{sid}:{iso}", style="danger")])
    rows.append([InlineKeyboardButton(make_bold_unicode(tr(lang, "back")), callback_data="services", style="danger")])
    return InlineKeyboardMarkup(rows)

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(make_bold_unicode(f"🔌 Provider: {STATE.get('provider','zenex').upper()}"), callback_data="adm:prov", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("🟢 تفعيل/إيقاف الخدمات"), callback_data="adm:toggle", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("➕ رينج زينيكس"), callback_data="adm:add_zx", style="success"),
         InlineKeyboardButton(make_bold_unicode("➕ رينج Mino"), callback_data="adm:add_mino", style="success")],
        [InlineKeyboardButton(make_bold_unicode("🗑 حذف رينج زينيكس"), callback_data="adm:del", style="danger"),
         InlineKeyboardButton(make_bold_unicode("🗑 حذف رينج Mino"), callback_data="adm:del_mino", style="danger")],
        [InlineKeyboardButton(make_bold_unicode("📤 رفع كومبو"), callback_data="adm:combo_up", style="success"),
         InlineKeyboardButton(make_bold_unicode("📁 كومبوهاتي"), callback_data="adm:combo_list", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("📋 الرينجات المباشرة"), callback_data="adm:list", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("📣 إعلان للجميع"), callback_data="adm:bc", style="primary"),
         InlineKeyboardButton(make_bold_unicode("👥 مستخدمون"), callback_data="adm:users", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("🚫 حظر / فك مستخدم"), callback_data="adm:ban", style="danger")],
        [InlineKeyboardButton(make_bold_unicode("📊 إحصائيات"), callback_data="adm:stats", style="primary"),
         InlineKeyboardButton(make_bold_unicode("🔐 حالة الدخول"), callback_data="adm:logins", style="primary")],
    ])

def lang_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(make_bold_unicode("🇸🇦 العربية"), callback_data="lang:ar", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("🇬🇧 English"), callback_data="lang:en", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("🟨 کوردی"), callback_data="lang:ku", style="primary")],
    ])

# ══════════════════ Session helpers ══════════════════
def cancel_task(ctx, chat_id):
    t = ctx.application.bot_data.get(f"task:{chat_id}")
    if t and not t.done(): t.cancel()
    ctx.application.bot_data.pop(f"task:{chat_id}", None)
def set_task(ctx, chat_id, t):
    cancel_task(ctx, chat_id)
    ctx.application.bot_data[f"task:{chat_id}"] = t

WELCOME = ("⚡ <b>OTP APP IBRAHIM</b> ⚡\n"
           "━━━━━━━━━━━━━━━━━━━━━\n"
           "🟢 <b>Premium</b> • ⚡ <b>Fast</b> • 🔐 <b>Secure</b>\n"
           "━━━━━━━━━━━━━━━━━━━━━")

# ══════════════════ Commands ══════════════════
async def cmd_start(update, ctx):
    u = note_user(update.effective_user)
    if u.get("banned"): return
    lang = u["lang"]; is_admin = update.effective_user.id in ADMIN_IDS
    await update.message.reply_text(f"{WELCOME}\n👋 <b>{tr(lang,'hi')} {update.effective_user.first_name}</b>", parse_mode=ParseMode.HTML, reply_markup=main_kb(lang, is_admin))

async def cmd_admin(update, ctx):
    if update.effective_user.id not in ADMIN_IDS:
        u = get_user(update.effective_user.id)
        await update.message.reply_text(tr(u["lang"], "admin_only")); return
    await update.message.reply_text(make_bold_unicode("🛠 Admin Panel"), parse_mode=ParseMode.HTML, reply_markup=admin_kb())

async def cmd_lang(update, ctx):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(tr(u["lang"], "choose_lang"), reply_markup=lang_kb())

async def cmd_last(update, ctx):
    uid = update.effective_user.id
    is_admin = uid in ADMIN_IDS
    if not LAST_OTP:
        await update.message.reply_text("لا يوجد أي OTP مسجّل بعد."); return
    L = LAST_OTP
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(L.get("ts", 0)))
    if is_admin:
        num = L.get("number") or "—"
        code = L.get("code") or "—"
        user_line = (f"@{L['username']}" if L.get("username") else (L.get("name") or "—")) + f" (<code>{L.get('uid')}</code>)"
    else:
        num = mask_number(L.get("number") or "")
        code = mask_code(L.get("code") or "")
        user_line = L.get("name") or (f"@{L['username']}" if L.get("username") else "—")
    txt = ("📊 <b>آخر OTP</b>\n"
           "━━━━━━━━━━━━━━━━━━━━━\n"
           f"👤 <b>المستخدم:</b> {user_line}\n"
           f"📱 <b>الخدمة:</b> {L.get('service') or '—'}\n"
           f"🌍 <b>الدولة:</b> {flag(L.get('iso') or '')} {L.get('country') or '—'}\n"
           f"☎️ <b>الرقم:</b> <code>{num}</code>\n"
           f"🔑 <b>الكود:</b> <code>{code}</code>\n"
           f"⏰ {ts}")
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

async def cmd_pm(update, ctx):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("⛔ للأدمن فقط."); return
    args = ctx.args or []
    if len(args) < 2:
        await update.message.reply_text("الاستخدام:\n<code>/pm &lt;user_id&gt; نص الرسالة</code>", parse_mode=ParseMode.HTML); return
    tid_raw = args[0]
    text = " ".join(args[1:]).strip()
    tid = re.sub(r"\D", "", tid_raw)
    if not tid or not text:
        await update.message.reply_text("⚠️ ID غير صحيح أو الرسالة فارغة."); return
    try:
        await ctx.bot.send_message(int(tid), f"📩 <b>رسالة من الإدارة:</b>\n━━━━━━━━━━━━━━━━━━━━━\n{text}", parse_mode=ParseMode.HTML)
        await update.message.reply_text(f"✅ أُرسلت إلى <code>{tid}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ فشل الإرسال: {e}")

async def on_text(update, ctx):
    # ====== كود استخراج الستيكر (مدمج) ======
    if update.message.sticker:
        sticker = update.message.sticker
        file_id = sticker.file_id
        file_unique_id = sticker.file_unique_id
        emoji = sticker.emoji or "بدون إيموجي"
        set_name = sticker.set_name or "غير معروف"
        await update.message.reply_text(
            f"✅ <b>تم استلام الستيكر!</b>\n\n"
            f"📁 <b>File ID:</b>\n<code>{file_id}</code>\n\n"
            f"🆔 <b>File Unique ID:</b>\n<code>{file_unique_id}</code>\n\n"
            f"😊 <b>Emoji:</b> {emoji}\n"
            f"📦 <b>Set Name:</b> {set_name}\n\n"
            f"💡 <i>انسخ الـ File ID وضعه في كود البوت.</i>",
            parse_mode=ParseMode.HTML
        )
        return
    # ===========================================

    t = (update.message.text or "").strip()
    uid = update.effective_user.id
    u = note_user(update.effective_user); lang = u["lang"]
    if u.get("banned"): return
    is_admin = uid in ADMIN_IDS

    if is_admin and ctx.user_data.get("await_ban"):
        ctx.user_data.pop("await_ban")
        tid = re.sub(r"\D", "", t)
        if not tid:
            await update.message.reply_text("⚠️ أرسل ID رقمي صحيح."); return
        tu = get_user(int(tid)); tu["banned"] = not tu.get("banned"); save_users()
        state = "⛔ تم الحظر" if tu["banned"] else "✅ تم فك الحظر"
        await update.message.reply_text(f"{state} للمستخدم <code>{tid}</code>", parse_mode=ParseMode.HTML); return

    if is_admin and ctx.user_data.get("await_mino_range_for"):
        sid = ctx.user_data.pop("await_mino_range_for")
        parts = [x.strip() for x in t.split("|")]
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ الصيغة: <code>rid|country</code>\nمثال:\n<code>12345|السودان</code>\n<code>12345|Egypt</code>\n<code>12345|249</code>",
                parse_mode=ParseMode.HTML); return
        rid = parts[0]
        country_hint = parts[1]
        iso = find_iso_by_name(country_hint) or (country_hint.lower() if len(country_hint) == 2 else "")
        if not iso:
            await update.message.reply_text(f"⚠️ لم أتعرف على الدولة: <b>{country_hint}</b>", parse_mode=ParseMode.HTML); return
        country_full = iso_name(iso, "ar") or iso.upper()
        STATE.setdefault("mino_ranges", []).append({"rid": rid, "sid": sid, "iso": iso, "country": country_full, "hits": 1})
        save_state()
        await update.message.reply_text(
            make_bold_unicode(f"✅ أُضيف رينج Mino\n📱 {svc_name(sid,'ar')}\n🌍 {flag(iso)} {country_full}\n🆔 rid={rid}"),
            parse_mode=ParseMode.HTML); return
    if is_admin and ctx.user_data.get("await_range_for"):
        sid = ctx.user_data.pop("await_range_for")
        parts = [x.strip() for x in t.split("|")]
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ الصيغة: <code>code|country</code>\nمثال:\n<code>+9627|الأردن</code>\n<code>+20|Egypt</code>",
                parse_mode=ParseMode.HTML); return
        code = parts[0]
        country_hint = parts[1]
        iso = find_iso_by_name(country_hint) or guess_iso(code)
        if not iso:
            await update.message.reply_text(f"⚠️ لم أتعرف على الدولة: <b>{country_hint}</b>", parse_mode=ParseMode.HTML); return
        country_full = iso_name(iso, "ar") or iso.upper()
        STATE["custom"].setdefault(sid, []).append({"range": code, "country": country_full, "iso": iso, "hits": 0})
        save_state()
        await update.message.reply_text(
            make_bold_unicode(f"✅ أُضيف رينج زينيكس\n📱 {svc_name(sid,'ar')}\n🌍 {flag(iso)} {country_full}\n🔢 {code}"),
            parse_mode=ParseMode.HTML); return
    if is_admin and ctx.user_data.get("await_bc"):
        ctx.user_data.pop("await_bc"); sent = 0
        for k in list(USERS.keys()):
            try: await ctx.bot.send_message(int(k), f"📣 {t}"); sent += 1
            except Exception: pass
        await update.message.reply_text(f"✅ {sent}"); return

    if "📞" in t:
        if not await enforce_sub(ctx, update.effective_chat.id, uid, lang):
            return
    # ====== إعادة تحميل تلقائية ======
    global STATE, USERS, COMBOS
    STATE  = _load(STATE_FILE, {"disabled": [], "custom": {}, "provider": "zenex", "mino_ranges": []})
    USERS  = _load(USERS_FILE, {})
    COMBOS = _load(COMBO_FILE, {})
    STATE.setdefault("provider", "zenex"); STATE.setdefault("custom", {}); STATE.setdefault("disabled", []); STATE.setdefault("mino_ranges", [])
    # ====================================
        await update.message.reply_text(tr(lang,"pick_service"), reply_markup=services_kb(lang)); return
        await update.message.reply_text(tr(lang,"choose_lang"), reply_markup=lang_kb()); return
    if "🛠" in t and is_admin:
        await update.message.reply_text(make_bold_unicode("🛠 Admin Panel"), parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

async def on_document(update, ctx):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS: return
    sid = ctx.user_data.get("combo_sid")
    if not sid:
        await update.message.reply_text("⚠️ اختر أولاً الخدمة من: 🛠 Admin → 📤 رفع كومبو"); return
    doc = update.message.document
    if not doc: return
    fname = (doc.file_name or "combo.txt")
    base = os.path.splitext(fname)[0]
    file = await doc.get_file()
    path = f"/tmp/{fname}"
    await file.download_to_drive(path)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f: raw = f.read()
    finally:
        try: os.remove(path)
        except Exception: pass
    numbers = []
    for line in raw.splitlines():
        n = re.sub(r"[^\d+]", "", line)
        if len(re.sub(r"\D", "", n)) >= 6: numbers.append(n)
    if not numbers:
        await update.message.reply_text("⚠️ الملف لا يحتوي أرقاماً."); return
    iso = guess_iso(numbers[0])
    COMBOS.setdefault(sid, {})[base] = {"numbers": numbers, "used": [], "iso": iso}
    save_combos()
    ctx.user_data.pop("combo_sid", None)
    await update.message.reply_text(
        f"✅ رُفع الكومبو <b>{base}</b> ({len(numbers)} رقم) للخدمة <b>{svc_name(sid,'ar')}</b>.\n"
        f"سيظهر كقائمة داخل هذه الخدمة.",
        parse_mode=ParseMode.HTML)

async def send_number(ctx, chat_id, uid, sid, iso, edit_mid=None):
    u = get_user(uid); lang = u["lang"]
    svc = SERVICE_MAP.get(sid, {"emoji":"📱"})
    rg = best_range(sid, iso)
    if not rg:
        text = tr(lang, "no_range")
        if edit_mid:
            try: await ctx.bot.edit_message_text(text, chat_id=chat_id, message_id=edit_mid)
            except Exception: await ctx.bot.send_message(chat_id, text)
        else: await ctx.bot.send_message(chat_id, text)
        return None
    if edit_mid:
        try:
            await ctx.bot.edit_message_text(
                f"{tr(lang,'reserving')}\n{svc['emoji']} <b>{svc_name(sid,lang)}</b> — {flag(iso)} {iso_name(iso,lang)}",
                chat_id=chat_id, message_id=edit_mid, parse_mode=ParseMode.HTML)
        except Exception: pass
    res = reserve_number(rg["range"])
    if not res:
        text = tr(lang, "no_range")
        if edit_mid:
            try: await ctx.bot.edit_message_text(text, chat_id=chat_id, message_id=edit_mid)
            except Exception: pass
        else: await ctx.bot.send_message(chat_id, text)
        return None
    country = iso_name(iso, lang) or res.get("country") or "—"
    op = res.get("operator") or "—"
    u["stats"]["numbers"] += 1; save_users()
    # ====== إرسال الستيكر (آمن) ======
    sticker_file_id = SERVICE_STICKERS.get(sid)
    if sticker_file_id:
        try:
            await ctx.bot.send_sticker(chat_id=chat_id, sticker=sticker_file_id)
        except Exception as e:
            logging.warning(f"send_sticker failed for {sid}: {e}")
    # =================================
    # تصميم رسالة "الرقم المحجوز" شبيه بصورة FOX BOT
    header = f"{flag(iso)} <b>{make_bold_unicode(country)} Number Assigned:</b>"
    box = (f"┌──────────────────────┐\n"
           f"│   ⏳ {make_bold_unicode(tr(lang,'waiting_code'))}   │\n"
           f"└──────────────────────┘")
    body = (f"{header}\n{box}\n"
            f"\n{svc['emoji']} <b>{make_bold_unicode(svc_name(sid,lang))}</b> — {tr(lang,'operator')}: <code>{make_bold_unicode(op)}</code>\n"
            f"☎️ <code>+{re.sub(r'[^0-9]','',str(res['number']))}</code>\n"
            f"<i>{tr(lang,'copy_hint')}</i>")
    kb = number_kb(sid, iso, res["number"], lang)
    if edit_mid:
        try:
            await ctx.bot.edit_message_text(body, chat_id=chat_id, message_id=edit_mid, parse_mode=ParseMode.HTML, reply_markup=kb); mid = edit_mid
        except Exception:
            m = await ctx.bot.send_message(chat_id, body, parse_mode=ParseMode.HTML, reply_markup=kb); mid = m.message_id
    else:
        m = await ctx.bot.send_message(chat_id, body, parse_mode=ParseMode.HTML, reply_markup=kb); mid = m.message_id
    register_reservation(res["number"], uid, sid, iso, svc_name(sid,lang), country)
    return {"number": res["number"], "range": rg["range"], "msg_id": mid, "combo": res.get("combo"), "svc_name": svc_name(sid,lang), "country": country, "iso": iso, "sid": sid}

async def run_session(ctx, chat_id, uid, sid, iso, init_mid=None):
    u = get_user(uid); lang = u["lang"]
    seen = set()
    current = await send_number(ctx, chat_id, uid, sid, iso, edit_mid=init_mid)
    if not current: return
    end = time.time() + POLL_TIMEOUT
    try:
        while time.time() < end:
            await asyncio.sleep(POLL_INTERVAL)
            hit = find_otp_for(current["number"], seen)
            if hit:
                seen.add(hit["id"])
                u["stats"]["otps"] += 1
                u["history"].append({"ts": int(time.time()), "service": current["svc_name"], "number": current["number"], "iso": iso, "otp": hit["code"]})
                u["history"] = u["history"][-100:]; save_users()
                if current.get("combo"):
                    consume_combo(current["combo"][0], current["combo"][1], current["number"])
                cancel_number(current["number"])
                unregister_reservation(current["number"])
                set_last_otp(uid, current["number"], hit["code"], current["svc_name"], current["country"], iso)
                dm_kb = None
                gu = group_url()
                if gu:
                    dm_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "goto_group"), url=gu, style="primary")]])
                # ستيكر عند وصول الكود (آمن)
                st = SERVICE_STICKERS.get(current.get("sid") or sid)
                if st:
                    try: await ctx.bot.send_sticker(chat_id=chat_id, sticker=st)
                    except Exception: pass
                iso_up = (iso or "").upper()
                pretty_num = "+" + re.sub(r'[^0-9]','', str(current['number']))
                await ctx.bot.send_message(chat_id,
    f"🔔 <b>OTP وصل!</b> 🔔\n"
    f"{flag(iso)} <b>{make_bold_unicode(iso_up)}</b> | 📱 SMS <code>{pretty_num}</code> | 🎉 <b>{make_bold_unicode(current['svc_name'])}</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    f"🌍 <b>{make_bold_unicode(current['country'])}</b>\n"
    f"<b>{make_bold_unicode(tr(lang,'code_label'))}:</b>\n"
    f"<code>{make_bold_unicode(str(hit['code']))}</code>\n"  # ← هذا السطر مهم جداً
    f"<i>{tr(lang,'copy_hint')}</i>",
    parse_mode=ParseMode.HTML, reply_markup=dm_kb)
                if OTP_GROUP_ID:
                    try:
                        shown_code = mask_code(hit["code"]) if MASK_GROUP_CODE else hit["code"]
                        gkb = None
                        bu = bot_url()
                        if bu:
                            gkb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "open_bot"), url=bu, style="primary")]])
                        code_line = (f"🔑 <b>الرمز:</b>\n<pre>{shown_code}</pre>" if MASK_GROUP_CODE else f"🔑 <b><code>{shown_code}</code></b>")
                        who = u.get("username")
                        who_line = f"👤 <b>سحب بواسطة:</b> @{who}\n" if who else f"👤 <b>سحب بواسطة:</b> {u.get('name') or ('ID '+str(uid))}\n"
                        await ctx.bot.send_message(
                            OTP_GROUP_ID,
                            "🔔 <b>OTP وصل</b>\n"
                            "━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📱 <b>{current['svc_name']}</b>\n"
                            f"🌍 {flag(iso)} {current['country']}\n"
                            f"☎️ <code>{mask_number(current['number'])}</code>\n"
                            f"{code_line}\n"
                            f"{who_line}",
                            parse_mode=ParseMode.HTML, reply_markup=gkb)
                    except Exception as e: log.warning("group send failed: %s", e)
                return
    except asyncio.CancelledError:
        unregister_reservation(current["number"]); return
    try:
        cancel_number(current["number"])
        unregister_reservation(current["number"])
        await ctx.bot.send_message(chat_id, f"{tr(lang,'timeout')}: <code>{current['number']}</code>", parse_mode=ParseMode.HTML)
    except Exception: pass

async def on_callback(update, ctx):
    q = update.callback_query
    data = q.data or ""
    uid = q.from_user.id
    chat_id = q.message.chat_id
    u = note_user(q.from_user); lang = u["lang"]
    if u.get("banned"): await q.answer(tr(lang,"banned"), show_alert=True); return
    await q.answer()

    if data == "noop": return
    if data == "sub:check":
        ok, missing = await check_subscription(ctx, uid)
        if ok:
            try: await q.edit_message_text("✅", reply_markup=services_kb(lang))
            except Exception: pass
        else:
            try: await q.edit_message_text(tr(lang,"not_subbed"), reply_markup=sub_kb(missing, lang))
            except Exception: pass
        return

    gated = data.startswith(("svc:","co:","new:","cop:"))
    if gated:
        ok, missing = await check_subscription(ctx, uid)
        if not ok:
            try: await q.edit_message_text(tr(lang,"must_join"), reply_markup=sub_kb(missing, lang))
            except Exception: pass
            return

    if data == "services":
        cancel_task(ctx, chat_id)
        await q.edit_message_text(tr(lang,"pick_service"), reply_markup=services_kb(lang)); return

    if data.startswith("lang:"):
        u["lang"] = data.split(":",1)[1]; save_users()
        try: await q.edit_message_text(tr(u["lang"], "lang_set"))
        except Exception: pass
        try: await ctx.bot.send_message(chat_id, "✅", reply_markup=main_kb(u["lang"], uid in ADMIN_IDS))
        except Exception: pass
        return

    if data.startswith("svc:"):
        sid = data.split(":",1)[1]; cancel_task(ctx, chat_id)
        kb = countries_kb(sid, lang, 0)
        if not kb:
            await q.edit_message_text(tr(lang,"no_country"),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang,"back"), callback_data="services", style="danger")]]))
            return
        s = SERVICE_MAP.get(sid, {})
        await q.edit_message_text(f"{s.get('emoji','')} <b>{svc_name(sid,lang)}</b>\n{tr(lang,'pick_country')}", parse_mode=ParseMode.HTML, reply_markup=kb); return

    if data.startswith("cop:"):
        _, sid, page = data.split(":",2)
        try: await q.edit_message_reply_markup(reply_markup=countries_kb(sid, lang, int(page)))
        except Exception: pass
        return

    if data.startswith("co:") or data.startswith("new:"):
        _, sid, iso = data.split(":",2)
        cancel_task(ctx, chat_id)
        task = asyncio.create_task(run_session(ctx, chat_id, uid, sid, iso, init_mid=q.message.message_id))
        set_task(ctx, chat_id, task); return

    if data.startswith("cp:"):
        num = data.split(":",1)[1]
        await ctx.bot.send_message(chat_id, f"<code>{num}</code>", parse_mode=ParseMode.HTML); return

    if data.startswith("cxl:"):
        num = data.split(":")[1]
        cancel_task(ctx, chat_id); cancel_number(num); u["stats"]["cancels"] += 1; save_users()
        try: await q.edit_message_text(f"❌ <code>{num}</code>", parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang,"back"), callback_data="services", style="danger")]]))
        except Exception: pass
        return

    if data.startswith("adm:") and uid in ADMIN_IDS:
        sub = data.split(":",1)[1]
        if sub == "panel":
            await q.edit_message_text(make_bold_unicode("🛠 Admin"), parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return
        if sub == "prov":
            STATE["provider"] = "zyron" if STATE.get("provider","zenex") == "zenex" else "zenex"
            save_state(); await q.edit_message_text(make_bold_unicode("🛠 Admin"), parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return
        if sub == "toggle":
            rows = []
            for sid, s in SERVICE_MAP.items():
                mark = "✅" if sid not in STATE.get("disabled", []) else "🚫"
                rows.append([InlineKeyboardButton(f"{mark} {s['emoji']} {svc_name(sid,lang)}", callback_data=f"tgl:{sid}", style="primary")])
            rows.append([InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")])
            await q.edit_message_text("Services", reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "add_zx":
            rows = [[InlineKeyboardButton(make_bold_unicode(f"{sv['emoji']} {svc_name(sid_,lang)}"), callback_data=f"addsvc:{sid_}", style="primary")] for sid_, sv in SERVICE_MAP.items()]
            rows.append([InlineKeyboardButton(make_bold_unicode("⬅️"), callback_data="adm:panel", style="danger")])
            await q.edit_message_text(make_bold_unicode("➕ إضافة رينج زينيكس — اختر خدمة:"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "add_mino":
            rows = [[InlineKeyboardButton(make_bold_unicode(f"{sv['emoji']} {svc_name(sid_,lang)}"), callback_data=f"addminosvc:{sid_}", style="success")] for sid_, sv in SERVICE_MAP.items()]
            rows.append([InlineKeyboardButton(make_bold_unicode("⬅️"), callback_data="adm:panel", style="danger")])
            await q.edit_message_text(make_bold_unicode("➕ إضافة رينج Mino — اختر خدمة:"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "del_mino":
            rows = []
            for r in STATE.get("mino_ranges", []):
                rid = r.get("rid",""); sid_ = r.get("sid",""); iso = r.get("iso","")
                rows.append([InlineKeyboardButton(f"🗑 Mino {sid_} {flag(iso.upper())} rid={rid}", callback_data=f"delmino:{rid}", style="danger")])
            rows.append([InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")])
            await q.edit_message_text(make_bold_unicode("🗑 حذف رينج Mino:"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "del":
            rows = []
            for sid, arr in STATE.get("custom", {}).items():
                for r in arr:
                    rows.append([InlineKeyboardButton(f"🗑 {sid} {r['range']} ({r.get('country','')})", callback_data=f"delrng:{sid}:{r['range']}", style="danger")])
            rows.append([InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")])
            await q.edit_message_text("حذف رينج:", reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "combo_up":
            rows = [[InlineKeyboardButton(f"{s['emoji']} {svc_name(sid,lang)}", callback_data=f"cbsvc:{sid}", style="success")] for sid, s in SERVICE_MAP.items()]
            rows.append([InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")])
            await q.edit_message_text("📤 اختر الخدمة لرفع الكومبو:", reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "combo_list":
            rows = []
            for sid, dct in COMBOS.items():
                for name, c in dct.items():
                    rows.append([InlineKeyboardButton(f"📁 {sid}/{name} — {len(c['numbers'])} (used {len(c.get('used',[]))})", callback_data=f"cbdel:{sid}:{name}", style="primary")])
            rows.append([InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")])
            await q.edit_message_text("Combos (اضغط للحذف):", reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "list":
            base = all_ranges()
            lines = [f"📋 {len(base)}:"]
            for r in base[:60]:
                lines.append(f"• {r.get('service')} — <code>{r.get('range')}</code> {flag((r.get('iso') or '').lower())} {r.get('hits',0)}")
            await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")]])); return
        if sub == "bc":
            ctx.user_data["await_bc"] = True
            await q.edit_message_text("📣 أرسل نص الإعلان."); return
        if sub == "ban":
            ctx.user_data["await_ban"] = True
            await q.edit_message_text("🚫 أرسل <b>ID</b> المستخدم لحظره أو فك حظره.\n(الايدي يظهر بجانب اسم المستخدم في قائمة 👥 مستخدمون)", parse_mode=ParseMode.HTML); return
        if sub == "users":
            lines = [f"👥 <b>المستخدمون:</b> {len(USERS)}", "━━━━━━━━━━━━━━━━━━━━━"]
            items = sorted(USERS.items(), key=lambda kv: -(kv[1].get("stats", {}).get("numbers", 0)))
            for k, x in items[:40]:
                st = x.get("stats", {})
                name = x.get("name") or "—"
                un = f"@{x['username']}" if x.get("username") else ""
                ban = "⛔ " if x.get("banned") else ""
                lines.append(f"{ban}<b>{name}</b> {un}\n   🆔 <code>{k}</code> — 📞 {st.get('numbers',0)} • 🔑 {st.get('otps',0)} • ❌ {st.get('cancels',0)}")
            txt = "\n".join(lines)
            if len(txt) > 3900: txt = txt[:3900] + "\n…"
            await q.edit_message_text(txt, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")]])); return
        if sub == "stats":
            n = sum(x.get("stats", {}).get("numbers", 0) for x in USERS.values())
            o = sum(x.get("stats", {}).get("otps", 0) for x in USERS.values())
            c = sum(x.get("stats", {}).get("cancels", 0) for x in USERS.values())
            banned = sum(1 for x in USERS.values() if x.get("banned"))
            await q.edit_message_text(
                "📊 <b>إحصائيات عامة</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 المستخدمون: <b>{len(USERS)}</b>\n"
                f"⛔ المحظورون: <b>{banned}</b>\n"
                f"📞 الأرقام المحجوزة: <b>{n}</b>\n"
                f"🔑 الأكواد الواصلة: <b>{o}</b>\n"
                f"❌ الإلغاءات: <b>{c}</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")]])); return
        if sub == "logins":
            await q.edit_message_text("🔐 جاري فحص تسجيل الدخول للموقعين...")
            report = await asyncio.to_thread(logins_report)
            await q.edit_message_text(report, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 إعادة الفحص", callback_data="adm:logins", style="primary")],
                    [InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")]])); return

    if data.startswith("tgl:") and uid in ADMIN_IDS:
        sid = data.split(":",1)[1]
        dis = STATE.setdefault("disabled", [])
        (dis.remove(sid) if sid in dis else dis.append(sid))
        save_state(); q.data = "adm:toggle"; await on_callback(update, ctx); return
    if data.startswith("addsvc:") and uid in ADMIN_IDS:
        sid = data.split(":",1)[1]
        ctx.user_data["await_range_for"] = sid
        await q.edit_message_text(
            f"➕ رينج زينيكس — {svc_name(sid,'ar')}\n\nأرسل: <code>code|country</code>\nمثال: <code>+9627|الأردن</code> أو <code>+20|Egypt</code>",
            parse_mode=ParseMode.HTML); return
    if data.startswith("delrng:") and uid in ADMIN_IDS:
        _, sid, code = data.split(":",2)
        STATE["custom"][sid] = [r for r in STATE.get("custom",{}).get(sid,[]) if r["range"] != code]
        save_state(); await q.edit_message_text(f"✅ حُذف {code}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")]])); return
    if data.startswith("addminosvc:") and uid in ADMIN_IDS:
        sid = data.split(":",1)[1]
        ctx.user_data["await_mino_range_for"] = sid
        await q.edit_message_text(
            f"➕ رينج Mino — {svc_name(sid,'ar')}\n\nأرسل: <code>rid|country</code>\nمثال: <code>12345|السودان</code> أو <code>12345|Egypt</code> أو <code>12345|249</code>",
            parse_mode=ParseMode.HTML); return
    if data.startswith("delmino:") and uid in ADMIN_IDS:
        rid = data.split(":",1)[1]
        STATE["mino_ranges"] = [r for r in STATE.get("mino_ranges", []) if str(r.get("rid")) != rid]
        save_state()
        await q.edit_message_text(f"✅ حُذف rid={rid}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")]])); return

    if data.startswith("cbsvc:") and uid in ADMIN_IDS:
        sid = data.split(":",1)[1]
        ctx.user_data["combo_sid"] = sid
        await q.edit_message_text(
            f"📤 <b>{svc_name(sid,'ar')}</b>\nأرسل الآن ملف <code>.txt</code> يحتوي رقم في كل سطر.\n"
            f"سيتم استخدامه كمصدر للأرقام لهذه الخدمة (لا سحب من الموقع).",
            parse_mode=ParseMode.HTML); return
    if data.startswith("cbdel:") and uid in ADMIN_IDS:
        _, sid, name = data.split(":",2)
        COMBOS.get(sid, {}).pop(name, None); save_combos()
        await q.edit_message_text(f"🗑 تم حذف {sid}/{name}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel", style="danger")]])); return

# ══════════════════ Main ══════════════════
async def on_startup(app):
    global BOT_USERNAME, OTP_GROUP_LINK
    try:
        me = await app.bot.get_me()
        BOT_USERNAME = me.username or ""
        log.info("Bot username: @%s", BOT_USERNAME)
    except Exception as e:
        log.warning("get_me failed: %s", e)
    if not OTP_GROUP_LINK and OTP_GROUP_ID:
        try:
            OTP_GROUP_LINK = await app.bot.export_chat_invite_link(OTP_GROUP_ID)
            log.info("OTP group invite link ready")
        except Exception as e:
            log.warning("export group link failed (البوت يجب أن يكون أدمن بالجروب): %s", e)
    try:
        report = await asyncio.to_thread(logins_report)
        info = (f"{report}\n🤖 <b>Bot</b>: @{BOT_USERNAME or '—'}\n"
                f"🔔 <b>Group link</b>: {OTP_GROUP_LINK or '⚪ غير متاح'}")
        for aid in ADMIN_IDS:
            try: await app.bot.send_message(aid, info, parse_mode=ParseMode.HTML)
            except Exception: pass
    except Exception as e:
        log.warning("startup report failed: %s", e)

# ═══════════════════════════════════════════════════════════════
# 🔧 خادم ويب صغير للحفاظ على البوت نشطاً
# ═══════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
# 🔧 خادم ويب صغير للحفاظ على البوت نشطاً
# ═══════════════════════════════════════════════════════════════
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
    zyron_login()
    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("last", cmd_last))
    app.add_handler(CommandHandler("pm",   cmd_pm))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("🚀 OTP APP IBRAHIM started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
