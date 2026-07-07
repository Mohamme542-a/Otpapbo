# ═══════════════════════════════════════════════════════════════
# 🤖 OTP APP IBRAHIM — Telegram Bot (Zenex + ZYRON + Combos)
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

# OTP group (send masked notice to this group). 0 = disabled.
OTP_GROUP_ID = -1003921031641
# Public link to the OTP group (t.me/...). If empty, the bot tries to
# export an invite link automatically on startup (the bot must be admin).
OTP_GROUP_LINK = "https://t.me/shHsu77"
OTP_GROUP_TITLE = "🔔 جروب OTP"
# If True, the OTP code sent to the group is hidden with stars, and users
# must open the bot to see the real code.
MASK_GROUP_CODE = False
# Filled automatically on startup (t.me/<username>).
BOT_USERNAME = "@Otptestre_bot"

# Force subscribe to these channels (usernames without @, or -100 IDs)
REQUIRED_CHANNELS = [
    {"id": -1003974736720, "title": "القناة الأولى"},
]
# Also force-join the OTP group before using the bot.
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

ISO_NAMES = {
    # ─── A ───
    "ad": {"ar":"أندورا", "en":"Andorra", "ku":"ئەندۆرا"},
    "ae": {"ar":"الإمارات العربية المتحدة", "en":"UAE", "ku":"ئیمارات"},
    "af": {"ar":"أفغانستان", "en":"Afghanistan", "ku":"ئەفغانستان"},
    "ag": {"ar":"أنتيغوا وباربودا", "en":"Antigua and Barbuda", "ku":"ئانتیگوا و باربودا"},
    "ai": {"ar":"أنغويلا", "en":"Anguilla", "ku":"ئەنگویلا"},
    "al": {"ar":"ألبانيا", "en":"Albania", "ku":"ئەلبانیا"},
    "am": {"ar":"أرمينيا", "en":"Armenia", "ku":"ئەرمەنیا"},
    "ao": {"ar":"أنغولا", "en":"Angola", "ku":"ئەنگۆلا"},
    "aq": {"ar":"أنتاركتيكا", "en":"Antarctica", "ku":"ئەنتارکتیکا"},
    "ar": {"ar":"الأرجنتين", "en":"Argentina", "ku":"ئەرژەنتین"},
    "as": {"ar":"ساموا الأمريكية", "en":"American Samoa", "ku":"ساموای ئەمریکی"},
    "at": {"ar":"النمسا", "en":"Austria", "ku":"نەمسا"},
    "au": {"ar":"أستراليا", "en":"Australia", "ku":"ئوسترالیا"},
    "aw": {"ar":"أروبا", "en":"Aruba", "ku":"ئاروبا"},
    "ax": {"ar":"جزر آلاند", "en":"Åland Islands", "ku":"دوورگەکانی ئالاند"},
    "az": {"ar":"أذربيجان", "en":"Azerbaijan", "ku":"ئازەربایجان"},

    # ─── B ───
    "ba": {"ar":"البوسنة والهرسك", "en":"Bosnia and Herzegovina", "ku":"بۆسنیا و هەرزەگۆڤینا"},
    "bb": {"ar":"باربادوس", "en":"Barbados", "ku":"باربادۆس"},
    "bd": {"ar":"بنغلاديش", "en":"Bangladesh", "ku":"بەنگلادیش"},
    "be": {"ar":"بلجيكا", "en":"Belgium", "ku":"بەلجیکا"},
    "bf": {"ar":"بوركينا فاسو", "en":"Burkina Faso", "ku":"بورکینا فاسۆ"},
    "bg": {"ar":"بلغاريا", "en":"Bulgaria", "ku":"بولگاریا"},
    "bh": {"ar":"البحرين", "en":"Bahrain", "ku":"بەحرەین"},
    "bi": {"ar":"بوروندي", "en":"Burundi", "ku":"بوروندی"},
    "bj": {"ar":"بنين", "en":"Benin", "ku":"بێنین"},
    "bl": {"ar":"سان بارتيلمي", "en":"Saint Barthélemy", "ku":"سەن بارتێلێمی"},
    "bm": {"ar":"برمودا", "en":"Bermuda", "ku":"بێرمودا"},
    "bn": {"ar":"بروناي", "en":"Brunei", "ku":"برونای"},
    "bo": {"ar":"بوليفيا", "en":"Bolivia", "ku":"بۆلیڤیا"},
    "bq": {"ar":"الجزر الكاريبية الهولندية", "en":"Caribbean Netherlands", "ku":"دوورگەکانی کاریبی هۆڵەندی"},
    "br": {"ar":"البرازيل", "en":"Brazil", "ku":"بەرازیل"},
    "bs": {"ar":"جزر البهاما", "en":"Bahamas", "ku":"دوورگەکانی بەهاما"},
    "bt": {"ar":"بوتان", "en":"Bhutan", "ku":"بوتان"},
    "bv": {"ar":"جزيرة بوفيه", "en":"Bouvet Island", "ku":"دوورگەی بۆڤێ"},
    "bw": {"ar":"بوتسوانا", "en":"Botswana", "ku":"بۆتسوانا"},
    "by": {"ar":"بيلاروسيا", "en":"Belarus", "ku":"بیلاڕووس"},
    "bz": {"ar":"بليز", "en":"Belize", "ku":"بەلیز"},

    # ─── C ───
    "ca": {"ar":"كندا", "en":"Canada", "ku":"کەنەدا"},
    "cc": {"ar":"جزر كوكوس", "en":"Cocos (Keeling) Islands", "ku":"دوورگەکانی کۆکۆس"},
    "cd": {"ar":"جمهورية الكونغو الديمقراطية", "en":"DR Congo", "ku":"کۆماری کۆنگۆی دیموکراتیک"},
    "cf": {"ar":"جمهورية أفريقيا الوسطى", "en":"Central African Republic", "ku":"کۆماری ئەفریقای ناوەندی"},
    "cg": {"ar":"الكونغو", "en":"Congo", "ku":"کۆنگۆ"},
    "ch": {"ar":"سويسرا", "en":"Switzerland", "ku":"سویسرا"},
    "ci": {"ar":"ساحل العاج", "en":"Ivory Coast", "ku":"کۆتدیڤوار"},
    "ck": {"ar":"جزر كوك", "en":"Cook Islands", "ku":"دوورگەکانی کوک"},
    "cl": {"ar":"تشيلي", "en":"Chile", "ku":"چیلی"},
    "cm": {"ar":"الكاميرون", "en":"Cameroon", "ku":"کامیرۆن"},
    "cn": {"ar":"الصين", "en":"China", "ku":"چین"},
    "co": {"ar":"كولومبيا", "en":"Colombia", "ku":"کۆلۆمبیا"},
    "cr": {"ar":"كوستاريكا", "en":"Costa Rica", "ku":"کۆستاریکا"},
    "cu": {"ar":"كوبا", "en":"Cuba", "ku":"کوبا"},
    "cv": {"ar":"الرأس الأخضر", "en":"Cape Verde", "ku":"کەیپ ڤەرد"},
    "cw": {"ar":"كوراساو", "en":"Curaçao", "ku":"کوراساو"},
    "cx": {"ar":"جزيرة كريسماس", "en":"Christmas Island", "ku":"دوورگەی کریسمس"},
    "cy": {"ar":"قبرص", "en":"Cyprus", "ku":"قیبرس"},
    "cz": {"ar":"التشيك", "en":"Czech Republic", "ku":"کۆماری چیک"},

    # ─── D ───
    "de": {"ar":"ألمانيا", "en":"Germany", "ku":"ئەڵمانیا"},
    "dj": {"ar":"جيبوتي", "en":"Djibouti", "ku":"جیبوتی"},
    "dk": {"ar":"الدنمارك", "en":"Denmark", "ku":"دانمارک"},
    "dm": {"ar":"دومينيكا", "en":"Dominica", "ku":"دۆمینیکا"},
    "do": {"ar":"جمهورية الدومينيكان", "en":"Dominican Republic", "ku":"کۆماری دۆمینیکان"},

    # ─── E ───
    "ec": {"ar":"الإكوادور", "en":"Ecuador", "ku":"ئیکوادۆر"},
    "ee": {"ar":"إستونيا", "en":"Estonia", "ku":"ئەستۆنیا"},
    "eg": {"ar":"مصر", "en":"Egypt", "ku":"میسر"},
    "er": {"ar":"إريتريا", "en":"Eritrea", "ku":"ئەریتریا"},
    "es": {"ar":"إسبانيا", "en":"Spain", "ku":"ئیسپانیا"},
    "et": {"ar":"إثيوبيا", "en":"Ethiopia", "ku":"ئەتیۆپیا"},

    # ─── F ───
    "fi": {"ar":"فنلندا", "en":"Finland", "ku":"فینلەندا"},
    "fj": {"ar":"فيجي", "en":"Fiji", "ku":"فیجی"},
    "fk": {"ar":"جزر فوكلاند", "en":"Falkland Islands", "ku":"دوورگەکانی فالکلاند"},
    "fm": {"ar":"ميكرونيزيا", "en":"Micronesia", "ku":"میکرۆنیزیا"},
    "fo": {"ar":"جزر فارو", "en":"Faroe Islands", "ku":"دوورگەکانی فارۆ"},
    "fr": {"ar":"فرنسا", "en":"France", "ku":"فەڕەنسا"},

    # ─── G ───
    "ga": {"ar":"الغابون", "en":"Gabon", "ku":"گابۆن"},
    "gb": {"ar":"المملكة المتحدة", "en":"United Kingdom", "ku":"بەریتانیا"},
    "gd": {"ar":"غرينادا", "en":"Grenada", "ku":"گرینادا"},
    "ge": {"ar":"جورجيا", "en":"Georgia", "ku":"جۆرجیا"},
    "gf": {"ar":"غويانا الفرنسية", "en":"French Guiana", "ku":"گویانای فەڕەنسی"},
    "gg": {"ar":"غيرنزي", "en":"Guernsey", "ku":"گێرنزی"},
    "gh": {"ar":"غانا", "en":"Ghana", "ku":"غانا"},
    "gi": {"ar":"جبل طارق", "en":"Gibraltar", "ku":"جیبرالتار"},
    "gl": {"ar":"غرينلاند", "en":"Greenland", "ku":"گرینلاند"},
    "gm": {"ar":"غامبيا", "en":"Gambia", "ku":"گامبیا"},
    "gn": {"ar":"غينيا", "en":"Guinea", "ku":"گینیا"},
    "gp": {"ar":"غوادلوب", "en":"Guadeloupe", "ku":"گوادیلۆپ"},
    "gq": {"ar":"غينيا الاستوائية", "en":"Equatorial Guinea", "ku":"گینای ئیستوایی"},
    "gr": {"ar":"اليونان", "en":"Greece", "ku":"یۆنان"},
    "gs": {"ar":"جورجيا الجنوبية وجزر ساندويتش", "en":"South Georgia", "ku":"جۆرجیای باشوور"},
    "gt": {"ar":"غواتيمالا", "en":"Guatemala", "ku":"گواتیمالا"},
    "gu": {"ar":"غوام", "en":"Guam", "ku":"گوام"},
    "gw": {"ar":"غينيا بيساو", "en":"Guinea-Bissau", "ku":"گینای بیساو"},
    "gy": {"ar":"غيانا", "en":"Guyana", "ku":"گویانا"},

    # ─── H ───
    "hk": {"ar":"هونغ كونغ", "en":"Hong Kong", "ku":"هۆنگ کۆنگ"},
    "hm": {"ar":"جزيرة هيرد وجزر ماكدونالد", "en":"Heard Island", "ku":"دوورگەی هێرد"},
    "hn": {"ar":"هندوراس", "en":"Honduras", "ku":"هۆندۆراس"},
    "hr": {"ar":"كرواتيا", "en":"Croatia", "ku":"کرواتیا"},
    "ht": {"ar":"هايتي", "en":"Haiti", "ku":"هایتی"},
    "hu": {"ar":"المجر", "en":"Hungary", "ku":"مەجارستان"},

    # ─── I ───
    "id": {"ar":"إندونيسيا", "en":"Indonesia", "ku":"ئەندۆنیزیا"},
    "ie": {"ar":"أيرلندا", "en":"Ireland", "ku":"ئێرلەندا"},
    "il": {"ar":"إسرائيل", "en":"Israel", "ku":"ئیسرائیل"},
    "im": {"ar":"جزيرة مان", "en":"Isle of Man", "ku":"دوورگەی مان"},
    "in": {"ar":"الهند", "en":"India", "ku":"هیندستان"},
    "io": {"ar":"إقليم المحيط الهندي البريطاني", "en":"British Indian Ocean Territory", "ku":"هەرێمی ئۆقیانووسی هیندی بەریتانی"},
    "iq": {"ar":"العراق", "en":"Iraq", "ku":"عێراق"},
    "ir": {"ar":"إيران", "en":"Iran", "ku":"ئێران"},
    "is": {"ar":"آيسلندا", "en":"Iceland", "ku":"ئایسلەندا"},
    "it": {"ar":"إيطاليا", "en":"Italy", "ku":"ئیتالیا"},

    # ─── J ───
    "je": {"ar":"جيرسي", "en":"Jersey", "ku":"جێرزی"},
    "jm": {"ar":"جامايكا", "en":"Jamaica", "ku":"جامایکا"},
    "jo": {"ar":"الأردن", "en":"Jordan", "ku":"ئوردن"},
    "jp": {"ar":"اليابان", "en":"Japan", "ku":"ژاپۆن"},

    # ─── K ───
    "ke": {"ar":"كينيا", "en":"Kenya", "ku":"کینیا"},
    "kg": {"ar":"قرغيزستان", "en":"Kyrgyzstan", "ku":"قرغیزستان"},
    "kh": {"ar":"كمبوديا", "en":"Cambodia", "ku":"کەمبۆدیا"},
    "ki": {"ar":"كيريباتي", "en":"Kiribati", "ku":"کیریباتی"},
    "km": {"ar":"جزر القمر", "en":"Comoros", "ku":"دوورگەکانی قەمەر"},
    "kn": {"ar":"سانت كيتس ونيفيس", "en":"Saint Kitts and Nevis", "ku":"سەن کیتس و نیڤیس"},
    "kp": {"ar":"كوريا الشمالية", "en":"North Korea", "ku":"کۆریای باکوور"},
    "kr": {"ar":"كوريا الجنوبية", "en":"South Korea", "ku":"کۆریای باشوور"},
    "kw": {"ar":"الكويت", "en":"Kuwait", "ku":"کوەیت"},
    "ky": {"ar":"جزر كايمان", "en":"Cayman Islands", "ku":"دوورگەکانی کایمان"},
    "kz": {"ar":"كازاخستان", "en":"Kazakhstan", "ku":"کازاخستان"},

    # ─── L ───
    "la": {"ar":"لاوس", "en":"Laos", "ku":"لاوس"},
    "lb": {"ar":"لبنان", "en":"Lebanon", "ku":"لوبنان"},
    "lc": {"ar":"سانت لوسيا", "en":"Saint Lucia", "ku":"سەن لوسیا"},
    "li": {"ar":"ليختنشتاين", "en":"Liechtenstein", "ku":"لیختنشتاین"},
    "lk": {"ar":"سريلانكا", "en":"Sri Lanka", "ku":"سریلانکا"},
    "lr": {"ar":"ليبيريا", "en":"Liberia", "ku":"لیبەریا"},
    "ls": {"ar":"ليسوتو", "en":"Lesotho", "ku":"لەسۆتۆ"},
    "lt": {"ar":"ليتوانيا", "en":"Lithuania", "ku":"لیتوانیا"},
    "lu": {"ar":"لوكسمبورغ", "en":"Luxembourg", "ku":"لوکسمبۆرگ"},
    "lv": {"ar":"لاتفيا", "en":"Latvia", "ku":"لاتڤیا"},
    "ly": {"ar":"ليبيا", "en":"Libya", "ku":"لیبیا"},

    # ─── M ───
    "ma": {"ar":"المغرب", "en":"Morocco", "ku":"مەغریب"},
    "mc": {"ar":"موناكو", "en":"Monaco", "ku":"مۆناکۆ"},
    "md": {"ar":"مولدوفا", "en":"Moldova", "ku":"مۆڵدۆڤا"},
    "me": {"ar":"الجبل الأسود", "en":"Montenegro", "ku":"مۆنتینیگرۆ"},
    "mf": {"ar":"سان مارتن", "en":"Saint Martin", "ku":"سەن مارتن"},
    "mg": {"ar":"مدغشقر", "en":"Madagascar", "ku":"مەدغەسکار"},
    "mh": {"ar":"جزر مارشال", "en":"Marshall Islands", "ku":"دوورگەکانی مارشاڵ"},
    "mk": {"ar":"مقدونيا الشمالية", "en":"North Macedonia", "ku":"مەکدۆنیای باکوور"},
    "ml": {"ar":"مالي", "en":"Mali", "ku":"مالی"},
    "mm": {"ar":"ميانمار", "en":"Myanmar", "ku":"میانمار"},
    "mn": {"ar":"منغوليا", "en":"Mongolia", "ku":"مەنگۆلیا"},
    "mo": {"ar":"ماكاو", "en":"Macau", "ku":"ماکاو"},
    "mp": {"ar":"جزر ماريانا الشمالية", "en":"Northern Mariana Islands", "ku":"دوورگەکانی ماریانای باکوور"},
    "mq": {"ar":"مارتينيك", "en":"Martinique", "ku":"مارتینیک"},
    "mr": {"ar":"موريتانيا", "en":"Mauritania", "ku":"مۆریتانیا"},
    "ms": {"ar":"مونتسيرات", "en":"Montserrat", "ku":"مۆنتسێرات"},
    "mt": {"ar":"مالطا", "en":"Malta", "ku":"ماڵتا"},
    "mu": {"ar":"موريشيوس", "en":"Mauritius", "ku":"مۆریس"},
    "mv": {"ar":"المالديف", "en":"Maldives", "ku":"مالدیف"},
    "mw": {"ar":"مالاوي", "en":"Malawi", "ku":"مالاوی"},
    "mx": {"ar":"المكسيك", "en":"Mexico", "ku":"مەکسیک"},
    "my": {"ar":"ماليزيا", "en":"Malaysia", "ku":"مالیزیا"},
    "mz": {"ar":"موزمبيق", "en":"Mozambique", "ku":"مۆزامبیک"},

    # ─── N ───
    "na": {"ar":"ناميبيا", "en":"Namibia", "ku":"نامیبیا"},
    "nc": {"ar":"كاليدونيا الجديدة", "en":"New Caledonia", "ku":"کالیدۆنیای نوێ"},
    "ne": {"ar":"النيجر", "en":"Niger", "ku":"نیجەر"},
    "nf": {"ar":"جزيرة نورفولك", "en":"Norfolk Island", "ku":"دوورگەی نۆرفۆلک"},
    "ng": {"ar":"نيجيريا", "en":"Nigeria", "ku":"نایجیریا"},
    "ni": {"ar":"نيكاراغوا", "en":"Nicaragua", "ku":"نیکاراگوا"},
    "nl": {"ar":"هولندا", "en":"Netherlands", "ku":"هۆڵەندا"},
    "no": {"ar":"النرويج", "en":"Norway", "ku":"نۆرویج"},
    "np": {"ar":"نيبال", "en":"Nepal", "ku":"نیپال"},
    "nr": {"ar":"ناورو", "en":"Nauru", "ku":"ناورو"},
    "nu": {"ar":"نيوي", "en":"Niue", "ku":"نیوو"},
    "nz": {"ar":"نيوزيلندا", "en":"New Zealand", "ku":"نیوزیلاند"},

    # ─── O ───
    "om": {"ar":"عُمان", "en":"Oman", "ku":"عومان"},

    # ─── P ───
    "pa": {"ar":"بنما", "en":"Panama", "ku":"پەنەما"},
    "pe": {"ar":"البيرو", "en":"Peru", "ku":"پێروو"},
    "pf": {"ar":"بولينيزيا الفرنسية", "en":"French Polynesia", "ku":"پۆلینیزیای فەڕەنسی"},
    "pg": {"ar":"بابوا غينيا الجديدة", "en":"Papua New Guinea", "ku":"پاپوا گینیا نوێ"},
    "ph": {"ar":"الفلبين", "en":"Philippines", "ku":"فلیپین"},
    "pk": {"ar":"باكستان", "en":"Pakistan", "ku":"پاکستان"},
    "pl": {"ar":"بولندا", "en":"Poland", "ku":"پۆڵەندا"},
    "pm": {"ar":"سان بيير وميكلون", "en":"Saint Pierre and Miquelon", "ku":"سەن پیێر و میکێلۆن"},
    "pn": {"ar":"جزر بيتكيرن", "en":"Pitcairn Islands", "ku":"دوورگەکانی پیتکەیرن"},
    "pr": {"ar":"بورتوريكو", "en":"Puerto Rico", "ku":"پۆرتۆ ریکۆ"},
    "ps": {"ar":"فلسطين", "en":"Palestine", "ku":"فەلەستین"},
    "pt": {"ar":"البرتغال", "en":"Portugal", "ku":"پۆرتوگال"},
    "pw": {"ar":"بالاو", "en":"Palau", "ku":"پالاو"},
    "py": {"ar":"باراغواي", "en":"Paraguay", "ku":"پاراگوای"},

    # ─── Q ───
    "qa": {"ar":"قطر", "en":"Qatar", "ku":"قەتەر"},

    # ─── R ───
    "re": {"ar":"لا ريونيون", "en":"Réunion", "ku":"ڕیۆنیۆن"},
    "ro": {"ar":"رومانيا", "en":"Romania", "ku":"ڕۆمانیا"},
    "rs": {"ar":"صربيا", "en":"Serbia", "ku":"سربیا"},
    "ru": {"ar":"روسيا", "en":"Russia", "ku":"ڕوسیا"},
    "rw": {"ar":"رواندا", "en":"Rwanda", "ku":"ڕواندا"},

    # ─── S ───
    "sa": {"ar":"السعودية", "en":"Saudi Arabia", "ku":"سعوودیە"},
    "sb": {"ar":"جزر سليمان", "en":"Solomon Islands", "ku":"دوورگەکانی سولەیمان"},
    "sc": {"ar":"سيشل", "en":"Seychelles", "ku":"سیشێل"},
    "sd": {"ar":"السودان", "en":"Sudan", "ku":"سوودان"},
    "se": {"ar":"السويد", "en":"Sweden", "ku":"سوید"},
    "sg": {"ar":"سنغافورة", "en":"Singapore", "ku":"سەنگافورە"},
    "sh": {"ar":"سانت هيلينا", "en":"Saint Helena", "ku":"سەن هێلینا"},
    "si": {"ar":"سلوفينيا", "en":"Slovenia", "ku":"سلۆڤینیا"},
    "sj": {"ar":"سفالبارد ويان ماين", "en":"Svalbard and Jan Mayen", "ku":"سفالبارد و یان ماین"},
    "sk": {"ar":"سلوفاكيا", "en":"Slovakia", "ku":"سلۆڤاکیا"},
    "sl": {"ar":"سيراليون", "en":"Sierra Leone", "ku":"سیەرالیۆن"},
    "sm": {"ar":"سان مارينو", "en":"San Marino", "ku":"سەن مارینۆ"},
    "sn": {"ar":"السنغال", "en":"Senegal", "ku":"سەنەگال"},
    "so": {"ar":"الصومال", "en":"Somalia", "ku":"سۆماڵیا"},
    "sr": {"ar":"سورينام", "en":"Suriname", "ku":"سورینام"},
    "ss": {"ar":"جنوب السودان", "en":"South Sudan", "ku":"باشووری سوودان"},
    "st": {"ar":"ساو تومي وبرينسيب", "en":"Sao Tome and Principe", "ku":"ساو تۆمێ و پرینسیپ"},
    "sv": {"ar":"السلفادور", "en":"El Salvador", "ku":"ئێل سالڤادۆر"},
    "sx": {"ar":"سينت مارتن", "en":"Sint Maarten", "ku":"سینت مارتن"},
    "sy": {"ar":"سوريا", "en":"Syria", "ku":"سووریا"},
    "sz": {"ar":"إسواتيني", "en":"Eswatini", "ku":"ئیسواتینی"},

    # ─── T ───
    "tc": {"ar":"جزر توركس وكايكوس", "en":"Turks and Caicos Islands", "ku":"دوورگەکانی تورکس و کایکۆس"},
    "td": {"ar":"تشاد", "en":"Chad", "ku":"چاد"},
    "tf": {"ar":"الأراضي الجنوبية الفرنسية", "en":"French Southern Territories", "ku":"خاکەکانی باشووری فەڕەنسی"},
    "tg": {"ar":"توغو", "en":"Togo", "ku":"تۆگۆ"},
    "th": {"ar":"تايلاند", "en":"Thailand", "ku":"تایلەند"},
    "tj": {"ar":"طاجيكستان", "en":"Tajikistan", "ku":"تاجیکستان"},
    "tk": {"ar":"توكيلاو", "en":"Tokelau", "ku":"تۆکێلاو"},
    "tl": {"ar":"تيمور الشرقية", "en":"Timor-Leste", "ku":"تیمۆری ڕۆژهەڵات"},
    "tm": {"ar":"تركمانستان", "en":"Turkmenistan", "ku":"تورکمانستان"},
    "tn": {"ar":"تونس", "en":"Tunisia", "ku":"توونس"},
    "to": {"ar":"تونغا", "en":"Tonga", "ku":"تۆنگا"},
    "tr": {"ar":"تركيا", "en":"Turkey", "ku":"تورکیا"},
    "tt": {"ar":"ترينيداد وتوباغو", "en":"Trinidad and Tobago", "ku":"ترینیداد و تۆباگۆ"},
    "tv": {"ar":"توفالو", "en":"Tuvalu", "ku":"توڤالو"},
    "tw": {"ar":"تايوان", "en":"Taiwan", "ku":"تایوان"},
    "tz": {"ar":"تنزانيا", "en":"Tanzania", "ku":"تانزانیا"},

    # ─── U ───
    "ua": {"ar":"أوكرانيا", "en":"Ukraine", "ku":"ئۆکرانیا"},
    "ug": {"ar":"أوغندا", "en":"Uganda", "ku":"ئوگاندا"},
    "um": {"ar":"جزر الولايات المتحدة النائية", "en":"US Outlying Islands", "ku":"دوورگەکانی دەرەوەی ئەمریکا"},
    "us": {"ar":"الولايات المتحدة", "en":"United States", "ku":"ئەمریکا"},
    "uy": {"ar":"الأوروغواي", "en":"Uruguay", "ku":"ئوروگوای"},
    "uz": {"ar":"أوزبكستان", "en":"Uzbekistan", "ku":"ئوزبەکستان"},

    # ─── V ───
    "va": {"ar":"الفاتيكان", "en":"Vatican City", "ku":"ڤاتیکان"},
    "vc": {"ar":"سانت فينسنت والغرينادين", "en":"Saint Vincent and the Grenadines", "ku":"سەن ڤینسێنت و گرینادین"},
    "ve": {"ar":"فنزويلا", "en":"Venezuela", "ku":"ڤەنزویلا"},
    "vg": {"ar":"جزر العذراء البريطانية", "en":"British Virgin Islands", "ku":"دوورگەکانی ڤێرجینی بەریتانی"},
    "vi": {"ar":"جزر العذراء الأمريكية", "en":"US Virgin Islands", "ku":"دوورگەکانی ڤێرجینی ئەمریکی"},
    "vn": {"ar":"فيتنام", "en":"Vietnam", "ku":"ڤیەتنام"},
    "vu": {"ar":"فانواتو", "en":"Vanuatu", "ku":"ڤانواتو"},

    # ─── W ───
    "wf": {"ar":"واليس وفوتونا", "en":"Wallis and Futuna", "ku":"والیس و فوتونا"},

    # ─── Y ───
    "ye": {"ar":"اليمن", "en":"Yemen", "ku":"یەمەن"},

    # ─── Z ───
    "za": {"ar":"جنوب أفريقيا", "en":"South Africa", "ku":"باشووری ئەفریقا"},
    "zm": {"ar":"زامبيا", "en":"Zambia", "ku":"زامبیا"},
    "zw": {"ar":"زيمبابوي", "en":"Zimbabwe", "ku":"زیمبابوی"},
    "xk": {"ar":"كوسوفو", "en":"Kosovo", "ku":"کۆسۆڤۆ"},
    "yt": {"ar":"مايوت", "en":"Mayotte", "ku":"مایۆت"},
    "va": {"ar":"الفاتيكان", "en":"Vatican City", "ku":"ڤاتیکان"},
    "tf": {"ar":"الأقاليم الجنوبية الفرنسية", "en":"French Southern Territories", "ku":"هەرێمە باشووریەکانی فەڕەنسا"},
}
CC_TO_ISO = {

    "1":"us","20":"eg","212":"ma","213":"dz","216":"tn","218":"ly","220":"gm",
    "221":"sn","222":"mr","223":"ml","224":"gn","225":"ci","226":"bf","227":"ne",
    "228":"tg","229":"bj","230":"mu","231":"lr","232":"sl","233":"gh",
    "234":"ng","235":"td","236":"cf","237":"cm","238":"cv","239":"st",
    "240":"gq","241":"ga","242":"cg","243":"cd","244":"ao","245":"gw","248":"sc",
    "249":"sd","250":"rw","251":"et","252":"so","253":"dj","254":"ke","255":"tz",
    "256":"ug","257":"bi","258":"mz","260":"zm","261":"mg","263":"zw",
    "264":"na","265":"mw","266":"ls","267":"bw","268":"sz","27":"za",
    "290":"sh","291":"er","297":"aw","298":"fo","299":"gl","30":"gr",
    "31":"nl","32":"be","33":"fr","34":"es","351":"pt","352":"lu","353":"ie",
    "354":"is","355":"al","356":"mt","357":"cy","358":"fi","359":"bg","36":"hu",
    "370":"lt","371":"lv","372":"ee","373":"md","374":"am","375":"by",
    "376":"ad","377":"mc","378":"sm","380":"ua","381":"rs","382":"me",  # الجبل الأسود
    "385":"hr","386":"si","387":"ba","389":"mk","39":"it","40":"ro","41":"ch",
    "420":"cz","421":"sk","423":"li","43":"at","44":"gb","45":"dk","46":"se",
    "47":"no","48":"pl","49":"de","500":"fk","501":"bz","502":"gt","503":"sv",
    "504":"hn","505":"ni","506":"cr","507":"pa","508":"pm","509":"ht","51":"pe",
    "52":"mx","53":"cu","54":"ar","55":"br","56":"cl","57":"co","58":"ve",
    "590":"gp","591":"bo","592":"gy","593":"ec","594":"gf","595":"py",
    "596":"mq","597":"sr","598":"uy","60":"my","61":"au","62":"id","63":"ph",
    "64":"nz","65":"sg","66":"th","670":"tl","672":"nf","673":"bn","674":"nr",
    "675":"pg","676":"to","677":"sb","678":"vu","679":"fj","680":"pw",
    "681":"wf","682":"ck","683":"nu","685":"ws","686":"ki","687":"nc",
    "688":"tv","689":"pf","690":"tk","691":"fm","692":"mh","7":"ru",
    "81":"jp","82":"kr","84":"vn","850":"kp","852":"hk","853":"mo","855":"kh",
    "856":"la","86":"cn","880":"bd","886":"tw","90":"tr","91":"in","92":"pk",
    "93":"af","94":"lk","95":"mm","960":"mv","961":"lb","962":"jo","963":"sy",
    "964":"iq","965":"kw","966":"sa","967":"ye","968":"om","970":"ps",
    "971":"ae","972":"il","973":"bh","974":"qa","975":"bt","976":"mn",
    "977":"np","98":"ir","992":"tj",  # طاجيكستان
    "993":"tm","994":"az","995":"ge","996":"kg","998":"uz",
    # ─── إضافات لتغطية كل دول العالم ───
    "211":"ss","246":"io","247":"sh","262":"re","269":"km","290":"sh",
    "383":"xk","385":"hr","500":"fk","508":"pm","590":"gp","599":"cw",
    "672":"nf","674":"nr","677":"sb","678":"vu","681":"wf","684":"ws",
    "687":"nc","689":"pf","690":"tk","691":"fm","692":"mh","800":"us",
    "808":"us","870":"us","878":"us","881":"us","882":"us","883":"us",
    "888":"us","979":"us","971":"ae",
}
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

STATE  = _load(STATE_FILE, {"disabled": [], "custom": {}, "provider": "zenex"})
USERS  = _load(USERS_FILE, {})
# COMBOS: { service_id: { combo_name: {"numbers":[...], "used":[...], "iso": "xx"} } }
COMBOS = _load(COMBO_FILE, {})
STATE.setdefault("provider", "zenex"); STATE.setdefault("custom", {}); STATE.setdefault("disabled", [])

def save_state(): _save(STATE_FILE, STATE)
def save_users(): _save(USERS_FILE, USERS)
def save_combos(): _save(COMBO_FILE, COMBOS)

def get_user(uid):
    k = str(uid)
    if k not in USERS:
        USERS[k] = {"lang":"ar","banned":False,
                    "stats":{"numbers":0,"otps":0,"cancels":0},
                    "history":[], "joined": int(time.time())}
        save_users()
    u = USERS[k]
    u.setdefault("lang","ar"); u.setdefault("stats",{"numbers":0,"otps":0,"cancels":0})
    u.setdefault("history",[])
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

# ══════════════════ Colored buttons (visual only) ══════════════════
# Telegram لا يسمح بتلوين الأزرار فعلياً، لذلك نستخدم مربعات ملوّنة
# كشريط أمام النص ليبدو الزر ملوّناً كما في الصورة.

def color_bar(color, width=100):
    return color * max(1, width)
def bar_label(color, text, width=12):
    """توليد زر يبدو ملوناً بالكامل (حيلة بصرية)"""
    b = color * max(1, width)  # شريط طويل جداً من المربعات
    return f"{b} {text}"

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
        r = requests.post(f"{ZENEX_URL}/getnum", headers=zx_headers(),
                          json={"range": rng, "is_national": False, "remove_plus": False}, timeout=20)
        if not r.ok: return None
        d = r.json().get("data") or {}
        num = d.get("number") or d.get("copy") or d.get("full_number")
        if not num: return None
        return {"number": str(num), "country": d.get("country") or "",
                "iso": (d.get("iso") or "").lower(), "operator": d.get("operator") or ""}
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

# ══════════════════ ZYRON (auto login from file creds) ══════════════════
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
        s.post(ZYRON_HOST + "/signin",
               data={"username":ZYRON_USER,"password":ZYRON_PASS,"capt":_solve_captcha(r.text)},
               timeout=15, allow_redirects=True)
        _ZY_SESS, _ZY_TS = s, time.time()
        log.info("ZYRON login OK")
        return s
    except Exception as e:
        log.warning("ZYRON login failed: %s", e); return None

# ══════════════════ Login / health status (for admin) ══════════════════
def zenex_status():
    try:
        r = requests.get(f"{ZENEX_URL}/active-ranges", headers=zx_headers(), timeout=15)
        if r.ok:
            n = len((r.json().get("data") or {}).get("active_ranges") or [])
            return True, f"✅ ناجح ({n} رينج نشط)"
        return False, f"❌ فشل (HTTP {r.status_code})"
    except Exception as e:
        return False, f"❌ خطأ: {e}"

def zyron_status():
    if not (ZYRON_HOST and ZYRON_USER and ZYRON_PASS):
        return False, "⚪ غير مُعدّ"
    global _ZY_SESS, _ZY_TS
    _ZY_SESS, _ZY_TS = None, 0  # force fresh login attempt
    s = zyron_login()
    return (True, "✅ ناجح") if s else (False, "❌ فشل تسجيل الدخول")

def logins_report():
    zx_ok, zx_msg = zenex_status()
    zy_ok, zy_msg = zyron_status()
    return (
        "🔐 <b>حالة الدخول للمواقع</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>Zenex</b>: {zx_msg}\n"
        f"🔵 <b>ZYRON</b>: {zy_msg}\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )


# ══════════════════ Unified ranges ══════════════════
def all_ranges():
    base = zx_active_ranges() if STATE.get("provider") == "zenex" else []
    for sid, arr in STATE.get("custom", {}).items():
        for r in arr: base.append({**r, "service": sid})
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
    # combos for this service become "virtual" countries too
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
    # الكومبو: إعطاء رقم جديد دون تكرار
    if rng.startswith("combo::"):
        _, sid, name = rng.split("::", 2)
        c = COMBOS.get(sid, {}).get(name)
        if not c: return None
        # البحث عن رقم لم يُستخدم بعد (أو لم يُحذف)
        available = [n for n in c.get("numbers", []) if n not in c.get("used", [])]
        if not available:
            # إذا نفدت الأرقام، ننتقل إلى Zenex كحل بديل
            log.info("Combo empty, using Zenex fallback")
            return zx_get_number(rng)
        num = available[0]
        # إضافة الرقم إلى قائمة المستخدمين (حتى لا يُعاد مرة أخرى)
        c.setdefault("used", []).append(num)
        save_combos()
        return {"number": num, "country": name, "iso": c.get("iso") or guess_iso(num),
                "operator": "combo", "combo": (sid, name)}
    # Zenex / Zyron العادي
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
    return None

# ══════════════════ Subscription gate ══════════════════
def required_chats():
    """قائمة القنوات + جروب OTP (إن كان الدخول إجبارياً)."""
    chats = list(REQUIRED_CHANNELS)
    if FORCE_JOIN_GROUP and OTP_GROUP_ID:
        chats.append({"id": OTP_GROUP_ID, "title": OTP_GROUP_TITLE,
                      "url": OTP_GROUP_LINK or None, "is_group": True})
    return chats

async def check_subscription(ctx, uid):
    """Return (ok, missing_channels)."""
    missing = []
    for ch in required_chats():
        try:
            m = await ctx.bot.get_chat_member(ch["id"], uid)
            if m.status in ("left", "kicked"): missing.append(ch)
        except Exception:
            missing.append(ch)
    return (len(missing) == 0), missing

def _chat_url(ch):
    if ch.get("url"): return ch["url"]
    cid = ch["id"]
    # إذا كان معرفًا رقميًا للقناة (يبدأ بـ -100)، نستخدم الرابط المباشر
    if isinstance(cid, int) or (isinstance(cid, str) and cid.lstrip('-').isdigit()):
        return f"https://t.me/c/{str(cid).lstrip('-')}"
    # إذا كان معرفًا نصيًا يبدأ بـ @
    if isinstance(cid, str) and cid.startswith("@"):
        return f"https://t.me/{cid.lstrip('@')}"
    return None

def sub_kb(missing, lang):
    rows = []
    for ch in missing:
        url = _chat_url(ch)
        icon = "🔔" if ch.get("is_group") else "📢"
        if url:
            rows.append([InlineKeyboardButton(f"{icon} {ch['title']}", url=str(url))])
        else:
            rows.append([InlineKeyboardButton(f"{icon} {ch['title']}", callback_data="noop")])
    rows.append([InlineKeyboardButton(tr(lang, "check_sub"), callback_data="sub:check")])
    return InlineKeyboardMarkup(rows)

async def enforce_sub(ctx, chat_id, uid, lang):
    ok, missing = await check_subscription(ctx, uid)
    if ok: return True
    await ctx.bot.send_message(chat_id, tr(lang, "must_join"), reply_markup=sub_kb(missing, lang))
    return False

def bot_url():
    return f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else None
def group_url():
    return OTP_GROUP_LINK or None


# ══════════════════ Keyboards ══════════════════
def main_kb(lang, is_admin):
    rows = [[KeyboardButton(f"🟩 {tr(lang, 'get_number')}")]]
    row2 = [KeyboardButton(f"🟦 {tr(lang, 'language')}")]
    if is_admin: row2.append(KeyboardButton(f"🟥 {tr(lang, 'admin_panel')}"))
    rows.append(row2)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def services_kb(lang):
    rows = []
    for sid, s in SERVICE_MAP.items():
        if sid in STATE.get("disabled", []): continue
        color = SERVICE_COLORS.get(sid, "🟦")
        label = bar_label(color, f"{s['emoji']} {svc_name(sid, lang)}", width=3)
        rows.append([InlineKeyboardButton(label, callback_data=f"svc:{sid}")])
    return InlineKeyboardMarkup(rows)

def services_kb(lang):
    rows = []
    for sid, s in SERVICE_MAP.items():
        if sid in STATE.get("disabled", []): continue
        emoji = s['emoji']
        name = svc_name(sid, lang)
        # زر نظيف بدون أي ألوان أو مربعات
        rows.append([InlineKeyboardButton(f"{emoji} {name}", callback_data=f"svc:{sid}")])
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
            if first_range:
                country_display_name = first_range.get("country", "")
        except:
            pass
            
        if not country_display_name:
            country_display_name = iso_name(iso, lang)
            
        if not country_display_name:
            country_display_name = iso.upper() if iso else "Unknown"
            
        country_display_name = country_display_name.strip()
        
        flag_emoji = flag(iso)
        # زر نظيف: علم + اسم الدولة + العدد
        label = f"{flag_emoji} {country_display_name} ✅ {c['hits']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"co:{sid}:{c['iso']}")])
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("◀️", callback_data=f"cop:{sid}:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{pages}", callback_data="noop"))
    if page < pages - 1: nav.append(InlineKeyboardButton("▶️", callback_data=f"cop:{sid}:{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton("🔄", callback_data=f"cop:{sid}:{page}"),
                 InlineKeyboardButton("⬅️ رجوع", callback_data="services")])
    return InlineKeyboardMarkup(rows)

def number_kb(sid, iso, number, lang):
    rows = [
        [InlineKeyboardButton(tr(lang, "new_number"), callback_data=f"new:{sid}:{iso}")],
        [InlineKeyboardButton(tr(lang, "change_country"), callback_data=f"svc:{sid}"),
         InlineKeyboardButton(tr(lang, "copy"), callback_data=f"cp:{number}")],
    ]
    gu = group_url()
    if gu:
        rows.append([InlineKeyboardButton(tr(lang, "goto_group"), url=gu)])
    rows.append([InlineKeyboardButton(tr(lang, "cancel_number"), callback_data=f"cxl:{number}:{sid}:{iso}")])
    rows.append([InlineKeyboardButton(tr(lang, "back"), callback_data="services")])
    return InlineKeyboardMarkup(rows)
    rows = [
        [InlineKeyboardButton(bar_label("🟩", tr(lang, "new_number"), width=12), callback_data=f"new:{sid}:{iso}")],
        [InlineKeyboardButton(tr(lang, "change_country"), callback_data=f"svc:{sid}"),
         InlineKeyboardButton(tr(lang, "copy"), callback_data=f"cp:{number}")],
    ]
    gu = group_url()
    if gu:
        rows.append([InlineKeyboardButton(bar_label("🟦", tr(lang, "goto_group"), width=12), url=gu)])
    rows.append([InlineKeyboardButton(tr(lang, "cancel_number"), callback_data=f"cxl:{number}:{sid}:{iso}")])
    rows.append([InlineKeyboardButton(tr(lang, "back"), callback_data="services")])
    return InlineKeyboardMarkup(rows)
def number_kb(sid, iso, number, lang):
    rows = [
        [InlineKeyboardButton(bar_label("🟩", tr(lang, "new_number"), 2), callback_data=f"new:{sid}:{iso}")],
        [InlineKeyboardButton(tr(lang, "change_country"), callback_data=f"svc:{sid}"),
         InlineKeyboardButton(tr(lang, "copy"), callback_data=f"cp:{number}")],
    ]
    gu = group_url()
    if gu:
        rows.append([InlineKeyboardButton(bar_label("🟦", tr(lang, "goto_group"), 2), url=gu)])
    rows.append([InlineKeyboardButton(tr(lang, "cancel_number"), callback_data=f"cxl:{number}:{sid}:{iso}")])
    rows.append([InlineKeyboardButton(tr(lang, "back"), callback_data="services")])
    return InlineKeyboardMarkup(rows)


def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔌 Provider: {STATE.get('provider','zenex').upper()}", callback_data="adm:prov")],
        [InlineKeyboardButton("🟢 تفعيل/إيقاف الخدمات", callback_data="adm:toggle")],
        [InlineKeyboardButton("➕ إضافة رينج يدوي", callback_data="adm:add"),
         InlineKeyboardButton("🗑 حذف رينج يدوي", callback_data="adm:del")],
        [InlineKeyboardButton("📤 رفع كومبو", callback_data="adm:combo_up"),
         InlineKeyboardButton("📁 كومبوهاتي", callback_data="adm:combo_list")],
        [InlineKeyboardButton("📋 الرينجات المباشرة", callback_data="adm:list")],
        [InlineKeyboardButton("📣 إعلان للجميع", callback_data="adm:bc"),
         InlineKeyboardButton("👥 مستخدمون", callback_data="adm:users")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="adm:stats"),
         InlineKeyboardButton("🔐 حالة الدخول", callback_data="adm:logins")],
    ])

def lang_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang:ar")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")],
        [InlineKeyboardButton("🟨 کوردی", callback_data="lang:ku")],
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
    u = get_user(update.effective_user.id)
    if u.get("banned"): return
    lang = u["lang"]; is_admin = update.effective_user.id in ADMIN_IDS
    await update.message.reply_text(
        f"{WELCOME}\n👋 <b>{tr(lang,'hi')} {update.effective_user.first_name}</b>",
        parse_mode=ParseMode.HTML, reply_markup=main_kb(lang, is_admin))

async def cmd_admin(update, ctx):
    if update.effective_user.id not in ADMIN_IDS:
        u = get_user(update.effective_user.id)
        await update.message.reply_text(tr(u["lang"], "admin_only")); return
    await update.message.reply_text("🛠 <b>Admin Panel</b>", parse_mode=ParseMode.HTML, reply_markup=admin_kb())

async def cmd_lang(update, ctx):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(tr(u["lang"], "choose_lang"), reply_markup=lang_kb())

# ══════════════════ Text handler ══════════════════
async def on_text(update, ctx):
    t = (update.message.text or "").strip()
    uid = update.effective_user.id
    u = get_user(uid); lang = u["lang"]
    if u.get("banned"): return
    is_admin = uid in ADMIN_IDS

    # admin pending inputs
    if is_admin and ctx.user_data.get("await_range_for"):
        sid = ctx.user_data.pop("await_range_for")
        parts = [x.strip() for x in t.split("|")]
        if len(parts) < 2:
            await update.message.reply_text("Format: <code>code|country|iso</code>", parse_mode=ParseMode.HTML); return
        code, cn = parts[0], parts[1]; iso = parts[2].lower() if len(parts) > 2 else guess_iso(code)
        STATE["custom"].setdefault(sid, []).append({"range": code, "country": cn, "iso": iso, "hits": 0})
        save_state()
        await update.message.reply_text(f"✅ أُضيف {code}"); return
    if is_admin and ctx.user_data.get("await_bc"):
        ctx.user_data.pop("await_bc"); sent = 0
        for k in list(USERS.keys()):
            try: await ctx.bot.send_message(int(k), f"📣 {t}"); sent += 1
            except Exception: pass
        await update.message.reply_text(f"✅ {sent}"); return

    if "📞" in t:
        if not await enforce_sub(ctx, update.effective_chat.id, uid, lang): return
        await update.message.reply_text(tr(lang,"pick_service"), reply_markup=services_kb(lang)); return
    if "🌐" in t:
        await update.message.reply_text(tr(lang,"choose_lang"), reply_markup=lang_kb()); return
    if "🛠" in t and is_admin:
        await update.message.reply_text("🛠 <b>Admin Panel</b>", parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return

# ══════════════════ Combo upload (per service) ══════════════════
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
    
    # ✅ التغيير الحاسم: استخدام ذاكرة التخزين بدلاً من حفظ الملف
    file = await doc.get_file()
    raw_bytes = await file.download_as_bytearray()
    raw = raw_bytes.decode("utf-8", errors="ignore")
    
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

# ══════════════════ Number flow ══════════════════
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
    body = (f"{tr(lang,'reserved')}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"{tr(lang,'service')}: {svc['emoji']} <b>{svc_name(sid,lang)}</b>\n"
            f"{tr(lang,'country')}: {flag(iso)} <b>{country}</b>\n"
            f"{tr(lang,'operator')}: <code>{op}</code>\n"
            f"{tr(lang,'number')}: <code>{res['number']}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"{tr(lang,'waiting_code')}")
    kb = number_kb(sid, iso, res["number"], lang)
    if edit_mid:
        try:
            await ctx.bot.edit_message_text(body, chat_id=chat_id, message_id=edit_mid,
                                            parse_mode=ParseMode.HTML, reply_markup=kb); mid = edit_mid
        except Exception:
            m = await ctx.bot.send_message(chat_id, body, parse_mode=ParseMode.HTML, reply_markup=kb); mid = m.message_id
    else:
        m = await ctx.bot.send_message(chat_id, body, parse_mode=ParseMode.HTML, reply_markup=kb); mid = m.message_id
    return {"number": res["number"], "range": rg["range"], "msg_id": mid, "combo": res.get("combo"),
            "svc_name": svc_name(sid,lang), "country": country, "iso": iso, "sid": sid}

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
                u["history"].append({"ts": int(time.time()), "service": current["svc_name"],
                                     "number": current["number"], "iso": iso, "otp": hit["code"]})
                u["history"] = u["history"][-100:]; save_users()
                if current.get("combo"):
                    consume_combo(current["combo"][0], current["combo"][1], current["number"])
                cancel_number(current["number"])
                # DM to user (full code) + optional go-to-group button
                dm_kb = None
                gu = group_url()
                if gu:
                    dm_kb = InlineKeyboardMarkup(
                        [[InlineKeyboardButton(tr(lang, "goto_group"), url=gu)]])
                await ctx.bot.send_message(
                    chat_id,
                    f"{tr(lang,'code_arrived')}\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📱 <b>{current['svc_name']}</b> • {flag(iso)} {current['country']}\n"
                    f"☎️ <code>{current['number']}</code>\n"
                    f"🔑 <b><code>{hit['code']}</code></b>",
                    parse_mode=ParseMode.HTML, reply_markup=dm_kb)
                # Group notice with masked number + masked code + open-bot button
                if OTP_GROUP_ID:
                    try:
                        shown_code = mask_code(hit["code"]) if MASK_GROUP_CODE else hit["code"]
                        gkb = None
                        bu = bot_url()
                        if bu:
                            gkb = InlineKeyboardMarkup(
                                [[InlineKeyboardButton(tr(lang, "open_bot"), url=bu)]])
                        code_line = (f"🔑 <b><code>{shown_code}</code></b>\n{tr(lang,'code_hidden')}"
                                     if MASK_GROUP_CODE else f"🔑 <b><code>{shown_code}</code></b>")
                        await ctx.bot.send_message(
                            OTP_GROUP_ID,
                            "🔔 <b>OTP وصل</b>\n"
                            "━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📱 <b>{current['svc_name']}</b>\n"
                            f"🌍 {flag(iso)} {current['country']}\n"
                            f"☎️ <code>{mask_number(current['number'])}</code>\n"
                            f"{code_line}",
                            parse_mode=ParseMode.HTML, reply_markup=gkb)
                    except Exception as e: log.warning("group send failed: %s", e)
                return
    except asyncio.CancelledError: return
    try:
        cancel_number(current["number"])
        await ctx.bot.send_message(chat_id, f"{tr(lang,'timeout')}: <code>{current['number']}</code>",
                                   parse_mode=ParseMode.HTML)
    except Exception: pass

# ══════════════════ Callbacks ══════════════════
async def on_callback(update, ctx):
    q = update.callback_query
    data = q.data or ""
    uid = q.from_user.id
    chat_id = q.message.chat_id
    u = get_user(uid); lang = u["lang"]
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

    # gate every user-facing action behind subscription
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
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang,"back"), callback_data="services")]]))
            return
        s = SERVICE_MAP.get(sid, {})
        await q.edit_message_text(f"{s.get('emoji','')} <b>{svc_name(sid,lang)}</b>\n{tr(lang,'pick_country')}",
                                  parse_mode=ParseMode.HTML, reply_markup=kb); return

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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang,"back"), callback_data="services")]]))
        except Exception: pass
        return

    # ───── Admin
    if data.startswith("adm:") and uid in ADMIN_IDS:
        sub = data.split(":",1)[1]
        if sub == "panel":
            await q.edit_message_text("🛠 <b>Admin</b>", parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return
        if sub == "prov":
            STATE["provider"] = "zyron" if STATE.get("provider","zenex") == "zenex" else "zenex"
            save_state(); await q.edit_message_text("🛠 <b>Admin</b>", parse_mode=ParseMode.HTML, reply_markup=admin_kb()); return
        if sub == "toggle":
            rows = []
            for sid, s in SERVICE_MAP.items():
                mark = "✅" if sid not in STATE.get("disabled", []) else "🚫"
                rows.append([InlineKeyboardButton(f"{mark} {s['emoji']} {svc_name(sid,lang)}", callback_data=f"tgl:{sid}")])
            rows.append([InlineKeyboardButton("⬅️", callback_data="adm:panel")])
            await q.edit_message_text("Services", reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "add":
            rows = [[InlineKeyboardButton(f"{s['emoji']} {svc_name(sid,lang)}", callback_data=f"addsvc:{sid}")]
                    for sid, s in SERVICE_MAP.items()]
            rows.append([InlineKeyboardButton("⬅️", callback_data="adm:panel")])
            await q.edit_message_text("اختر خدمة:", reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "del":
            rows = []
            for sid, arr in STATE.get("custom", {}).items():
                for r in arr:
                    rows.append([InlineKeyboardButton(f"🗑 {sid} {r['range']} ({r.get('country','')})",
                                                     callback_data=f"delrng:{sid}:{r['range']}")])
            rows.append([InlineKeyboardButton("⬅️", callback_data="adm:panel")])
            await q.edit_message_text("حذف رينج:", reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "combo_up":
            rows = [[InlineKeyboardButton(f"{s['emoji']} {svc_name(sid,lang)}", callback_data=f"cbsvc:{sid}")]
                    for sid, s in SERVICE_MAP.items()]
            rows.append([InlineKeyboardButton("⬅️", callback_data="adm:panel")])
            await q.edit_message_text("📤 اختر الخدمة لرفع الكومبو:", reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "combo_list":
            rows = []
            for sid, dct in COMBOS.items():
                for name, c in dct.items():
                    rows.append([InlineKeyboardButton(
                        f"📁 {sid}/{name} — {len(c['numbers'])} (used {len(c.get('used',[]))})",
                        callback_data=f"cbdel:{sid}:{name}")])
            rows.append([InlineKeyboardButton("⬅️", callback_data="adm:panel")])
            await q.edit_message_text("Combos (اضغط للحذف):", reply_markup=InlineKeyboardMarkup(rows)); return
        if sub == "list":
            base = all_ranges()
            lines = [f"📋 {len(base)}:"]
            for r in base[:60]:
                lines.append(f"• {r.get('service')} — <code>{r.get('range')}</code> {flag((r.get('iso') or '').lower())} {r.get('hits',0)}")
            await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel")]])); return
        if sub == "bc":
            ctx.user_data["await_bc"] = True
            await q.edit_message_text("📣 أرسل نص الإعلان."); return
        if sub == "users":
            await q.edit_message_text(f"👥 {len(USERS)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel")]])); return
        if sub == "stats":
            n = sum(x["stats"]["numbers"] for x in USERS.values())
            o = sum(x["stats"]["otps"] for x in USERS.values())
            await q.edit_message_text(f"👥 {len(USERS)}\n📞 {n}\n🔑 {o}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel")]])); return
        if sub == "logins":
            await q.edit_message_text("🔐 جاري فحص تسجيل الدخول للموقعين...")
            report = await asyncio.to_thread(logins_report)
            await q.edit_message_text(report, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 إعادة الفحص", callback_data="adm:logins")],
                    [InlineKeyboardButton("⬅️", callback_data="adm:panel")]])); return

    if data.startswith("tgl:") and uid in ADMIN_IDS:
        sid = data.split(":",1)[1]
        dis = STATE.setdefault("disabled", [])
        (dis.remove(sid) if sid in dis else dis.append(sid))
        save_state(); q.data = "adm:toggle"; await on_callback(update, ctx); return
    if data.startswith("addsvc:") and uid in ADMIN_IDS:
        sid = data.split(":",1)[1]
        ctx.user_data["await_range_for"] = sid
        await q.edit_message_text(f"أرسل: <code>code|country|iso</code> للخدمة {sid}", parse_mode=ParseMode.HTML); return
    if data.startswith("delrng:") and uid in ADMIN_IDS:
        _, sid, code = data.split(":",2)
        STATE["custom"][sid] = [r for r in STATE.get("custom",{}).get(sid,[]) if r["range"] != code]
        save_state(); await q.edit_message_text(f"✅ حُذف {code}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel")]])); return
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="adm:panel")]])); return

# ══════════════════ Main ══════════════════
async def on_startup(app):
    """يحدّث اسم البوت ورابط الجروب ويُبلّغ الأدمن بحالة الدخول."""
    global BOT_USERNAME, OTP_GROUP_LINK
    try:
        me = await app.bot.get_me()
        BOT_USERNAME = me.username or ""
        log.info("Bot username: @%s", BOT_USERNAME)
    except Exception as e:
        log.warning("get_me failed: %s", e)
    # حاول جلب رابط دعوة للجروب تلقائياً إن لم يُضبط يدوياً
    if not OTP_GROUP_LINK and OTP_GROUP_ID:
        try:
            OTP_GROUP_LINK = await app.bot.export_chat_invite_link(OTP_GROUP_ID)
            log.info("OTP group invite link ready")
        except Exception as e:
            log.warning("export group link failed (البوت يجب أن يكون أدمن بالجروب): %s", e)
    # تقرير حالة الدخول للأدمن
    try:
        report = await asyncio.to_thread(logins_report)
        info = (f"{report}\n🤖 <b>Bot</b>: @{BOT_USERNAME or '—'}\n"
                f"🔔 <b>Group link</b>: {OTP_GROUP_LINK or '⚪ غير متاح'}")
        for aid in ADMIN_IDS:
            try: await app.bot.send_message(aid, info, parse_mode=ParseMode.HTML)
            except Exception: pass
    except Exception as e:
        log.warning("startup report failed: %s", e)

def main():
    zyron_login()  # try auto-login using file credentials
    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("🚀 OTP APP IBRAHIM started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
# =====================================================
# 🔧 إضافة خادم ويب صغير لإبقاء البوت نشطاً في Render
# =====================================================
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running! 🚀"

def run_web():
    app.run(host='0.0.0.0', port=8080)

# تشغيل السيرفر في خلفية البوت
threading.Thread(target=run_web, daemon=True).start()
if __name__ == "__main__":
    main()
