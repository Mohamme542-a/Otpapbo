import sys
import os
import asyncio
import re
import glob
import logging
from threading import Thread
from flask import Flask

from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters as PTBFilters, ContextTypes
)

# ══════════════════ خادم خفيف لـ Render ══════════════════
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is active!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# ══════════════════ الإعدادات ══════════════════
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8893399262:AAGQXKaZI-na_mTAoO4RKqwlDoQ6h3f89h0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8619521184))

user_states = {}
temp_data = {}
active_userbots = {}  # phone -> Client
ptb_app = None  # reference to telegram app

# ══════════════════ التقاط الرموز بشكل أقوى ══════════════════
def attach_otp_handler(userbot_client: Client, phone_num: str):
    """ربط معالج لالتقاط رموز الدخول"""
    
    @userbot_client.on_message(filters.user(777000) | filters.service)
    async def auto_forward_otp(client, message):
        try:
            # التأكد من وجود نص في الرسالة
            msg_text = message.text or message.caption or ""
            
            # طباعة للتصحيح
            logging.info(f"📩 رسالة جديدة من 777000: {msg_text[:100]}")
            
            # التحقق من وجود رمز
            if msg_text:
                # البحث عن أرقام (رموز)
                codes = re.findall(r'\b\d{5,6}\b', msg_text)
                
                # إذا كان هناك رمز أو كان النص يحتوي على كلمات مفتاحية
                if codes or any(x in msg_text.lower() for x in ["login code", "رمز الدخول", "code:", "كود"]):
                    # إرسال الرمز للأدمن
                    await ptb_app.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"🔐 **رمز دخول جديد للحساب `+{phone_num}`**\n\n"
                             f"```\n{msg_text}\n```\n\n"
                             f"📌 الرمز المستخرج: `{codes[0] if codes else 'غير واضح'}`",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    logging.info(f"✅ تم إرسال رمز للحساب +{phone_num}")
                    
        except Exception as e:
            logging.error(f"خطأ في إرسال الرمز: {e}")

# ══════════════════ لوحة التحكم ══════════════════
def admin_menu_kb():
    keyboard = [
        [
            InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session"),
            InlineKeyboardButton("📱 الجلسات النشطة", callback_data="list_sessions")
        ],
        [
            InlineKeyboardButton("📩 طلب رمز", callback_data="request_code"),
            InlineKeyboardButton("🗑 حذف جلسة", callback_data="delete_session")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def sessions_kb():
    buttons = []
    for phone in active_userbots.keys():
        buttons.append([
            InlineKeyboardButton(f"📱 +{phone}", callback_data=f"req_{phone}")
        ])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back_menu")])
    return InlineKeyboardMarkup(buttons)

def delete_sessions_kb():
    buttons = []
    for phone in active_userbots.keys():
        buttons.append([
            InlineKeyboardButton(f"🗑 +{phone}", callback_data=f"del_{phone}")
        ])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back_menu")])
    return InlineKeyboardMarkup(buttons)

# ══════════════════ الأوامر ══════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ptb_app
    ptb_app = context.application
    
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ هذا البوت مخصص للأدمن فقط.")
        return

    await update.message.reply_text(
        "👋 **أهلاً بك في لوحة إدارة جلسات تيليجرام**\n\n"
        "📌 **المميزات:**\n"
        "• إضافة حسابات وحفظ الجلسات\n"
        "• استقبال رموز الدخول تلقائياً\n"
        "• طلب رموز جديدة يدوياً\n\n"
        "اختر الخيار المناسب:",
        reply_markup=admin_menu_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ptb_app
    ptb_app = context.application
    
    query = update.callback_query
    uid = query.from_user.id

    if uid != ADMIN_ID:
        await query.answer("⛔ غير مصرح لك.", show_alert=True)
        return

    await query.answer()
    data = query.data

    if data == "back_menu":
        await query.edit_message_text(
            "👋 **لوحة التحكم الرئيسية**",
            reply_markup=admin_menu_kb(),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data == "add_session":
        user_states[ADMIN_ID] = "WAIT_API_ID"
        await query.edit_message_text(
            "📝 **الخطوة 1:** أرسل الآن الـ **API ID**\n"
            "(من موقع my.telegram.org)\n\n"
            "📌 مثال: `12345678`"
        )

    elif data == "list_sessions":
        if not active_userbots:
            text = "⚠️ لا توجد جلسات نشطة حالياً."
        else:
            text = f"📱 **الجلسات النشطة ({len(active_userbots)}):**\n\n"
            for phone in active_userbots:
                try:
                    me = await active_userbots[phone].get_me()
                    username = f"@{me.username}" if me.username else "بدون يوزر"
                    text += f"• `+{phone}` 🟢 {username}\n"
                except:
                    text += f"• `+{phone}` 🔴 غير متصل\n"
        await query.edit_message_text(text, reply_markup=admin_menu_kb(), parse_mode=ParseMode.MARKDOWN)

    elif data == "request_code":
        if not active_userbots:
            await query.edit_message_text("⚠️ لا توجد جلسات مضافة.", reply_markup=admin_menu_kb())
            return
        await query.edit_message_text(
            "📩 **اختر الحساب لطلب رمز جديد:**",
            reply_markup=sessions_kb()
        )

    elif data.startswith("req_"):
        phone = data.replace("req_", "")
        client = active_userbots.get(phone)
        if not client:
            await query.answer("الجلسة غير موجودة", show_alert=True)
            return
        try:
            # طلب رمز جديد
            await client.send_code(phone)
            await query.edit_message_text(
                f"✅ **تم طلب الرمز للحساب `+{phone}`**\n\n"
                "📩 ستصلك رسالة تحتوي على الرمز في تطبيق تلغرام.\n"
                "🔄 سيتم إرسال الرمز لك هنا تلقائياً.",
                reply_markup=admin_menu_kb(),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ فشل طلب الرمز: `{e}`",
                reply_markup=admin_menu_kb(),
                parse_mode=ParseMode.MARKDOWN
            )

    elif data == "delete_session":
        if not active_userbots:
            await query.edit_message_text("⚠️ لا توجد جلسات لحذفها.", reply_markup=admin_menu_kb())
            return
        await query.edit_message_text(
            "🗑 **اختر الجلسة للحذف:**",
            reply_markup=delete_sessions_kb()
        )

    elif data.startswith("del_"):
        phone = data.replace("del_", "")
        client = active_userbots.pop(phone, None)
        if client:
            try:
                await client.stop()
            except:
                pass
            session_file = f"session_{phone}.session"
            if os.path.exists(session_file):
                os.remove(session_file)
            await query.edit_message_text(
                f"✅ **تم حذف الجلسة `+{phone}` بنجاح**",
                reply_markup=admin_menu_kb(),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.answer("الجلسة غير موجودة", show_alert=True)

async def handle_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ptb_app
    ptb_app = context.application
    
    if update.effective_user.id != ADMIN_ID:
        return

    state = user_states.get(ADMIN_ID)
    text = update.message.text.strip()

    if state == "WAIT_API_ID":
        if not text.isdigit():
            await update.message.reply_text("❌ أدخل API ID أرقام فقط.")
            return
        temp_data[ADMIN_ID] = {"api_id": int(text)}
        user_states[ADMIN_ID] = "WAIT_API_HASH"
        await update.message.reply_text(
            "📝 **الخطوة 2:** أرسل الآن الـ **API HASH**\n"
            "(من موقع my.telegram.org)"
        )

    elif state == "WAIT_API_HASH":
        temp_data[ADMIN_ID]["api_hash"] = text
        user_states[ADMIN_ID] = "WAIT_PHONE"
        await update.message.reply_text(
            "📱 **الخطوة 3:** أرسل رقم الهاتف مع رمز الدولة\n"
            "📌 مثال: `213xxxxxxxxx`"
        )

    elif state == "WAIT_PHONE":
        phone = text.replace("+", "").replace(" ", "")
        temp_data[ADMIN_ID]["phone"] = phone
        await update.message.reply_text(f"⏳ جاري طلب كود التحقق للرقم `+{phone}`...")

        api_id = temp_data[ADMIN_ID]["api_id"]
        api_hash = temp_data[ADMIN_ID]["api_hash"]

        client = Client(f"session_{phone}", api_id=api_id, api_hash=api_hash)
        await client.connect()

        try:
            sent = await client.send_code(phone)
            temp_data[ADMIN_ID]["client"] = client
            temp_data[ADMIN_ID]["phone_code_hash"] = sent.phone_code_hash
            user_states[ADMIN_ID] = "WAIT_CODE"
            await update.message.reply_text(
                "📩 **تم إرسال الكود!**\n\n"
                "افتح تطبيق تلغرام وانسخ الكود ثم أرسله هنا:"
            )
        except Exception as e:
            await client.disconnect()
            user_states.pop(ADMIN_ID, None)
            temp_data.pop(ADMIN_ID, None)
            await update.message.reply_text(f"❌ خطأ: `{e}`", reply_markup=admin_menu_kb())

    elif state == "WAIT_CODE":
        code = text
        data = temp_data.get(ADMIN_ID)
        if not data:
            await update.message.reply_text("⚠️ انتهت الجلسة، أعد المحاولة.")
            return
            
        client = data["client"]

        try:
            await client.sign_in(data["phone"], data["phone_code_hash"], code)
            
            # ربط معالج الرموز
            attach_otp_handler(client, data["phone"])
            active_userbots[data["phone"]] = client

            user_states.pop(ADMIN_ID, None)
            temp_data.pop(ADMIN_ID, None)

            await update.message.reply_text(
                f"✅ **تم ربط الجلسة بنجاح للحساب `+{data['phone']}`**\n\n"
                "🔐 الآن أي رمز دخول يصل لهذا الحساب سيتم إرساله لك هنا تلقائياً.",
                reply_markup=admin_menu_kb(),
                parse_mode=ParseMode.MARKDOWN
            )
        except SessionPasswordNeeded:
            user_states[ADMIN_ID] = "WAIT_2FA"
            await update.message.reply_text(
                "🔐 **مطلوب التحقق بخطوتين (2FA)**\n\n"
                "أدخل كلمة السر الخاصة بحسابك:"
            )
        except (PhoneCodeInvalid, PhoneCodeExpired):
            await update.message.reply_text(
                "❌ **الرمز غير صحيح أو منتهي!**\n"
                "أعد إرسال الكود الصحيح:"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ غير متوقع: `{e}`")

    elif state == "WAIT_2FA":
        password = text
        data = temp_data.get(ADMIN_ID)
        if not data:
            await update.message.reply_text("⚠️ انتهت الجلسة، أعد المحاولة.")
            return
            
        client = data["client"]

        try:
            await client.check_password(password)
            
            # ربط معالج الرموز
            attach_otp_handler(client, data["phone"])
            active_userbots[data["phone"]] = client

            user_states.pop(ADMIN_ID, None)
            temp_data.pop(ADMIN_ID, None)

            await update.message.reply_text(
                f"✅ **تم التحقق وربط الجلسة `+{data['phone']}` بنجاح!**",
                reply_markup=admin_menu_kb(),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(f"❌ كلمة السر غير صحيحة: `{e}`")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error("Exception while handling an update:", exc_info=context.error)

async def load_existing_sessions():
    """تحميل الجلسات المحفوظة"""
    global active_userbots
    
    for file in glob.glob("session_*.session"):
        phone = file.replace("session_", "").replace(".session", "")
        try:
            # محاولة تحميل الجلسة
            client = Client(f"session_{phone}")
            await client.start()
            
            # ربط معالج الرموز
            attach_otp_handler(client, phone)
            active_userbots[phone] = client
            logging.info(f"✅ تم تحميل الجلسة: +{phone}")
        except Exception as e:
            logging.error(f"❌ فشل تحميل {phone}: {e}")

async def post_init(app: Application):
    """تشغيل بعد بدء البوت"""
    global ptb_app
    ptb_app = app
    logging.info("🔄 جاري تحميل الجلسات المحفوظة...")
    await load_existing_sessions()
    logging.info(f"✅ تم تحميل {len(active_userbots)} جلسة")

def main():
    global ptb_app
    
    # تشغيل خادم Flask
    Thread(target=run_flask, daemon=True).start()

    # إنشاء تطبيق البوت
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    ptb_app = app

    # إضافة المعالجات
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(PTBFilters.TEXT & ~PTBFilters.COMMAND, handle_inputs))

    logging.info("🚀 البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
