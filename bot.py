import os
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

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8893399262:AAG07XosgkW6YRaTanBpwFuJF9ozJj82x0M")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8619521184))

user_states = {}
temp_data = {}
active_userbots = {}  # phone -> Client

# ══════════════════ التقاط الرموز بشكل أقوى ══════════════════
def attach_otp_handler(userbot_client: Client, phone_num: str, ptb_app):
    @userbot_client.on_message(filters.incoming)
    async def auto_forward_otp(client, message):
        try:
            is_telegram = message.from_user and message.from_user.id == 777000
            msg_text = message.text or message.caption or ""

            # شروط أقوى لالتقاط الرمز
            if is_telegram or any(x in msg_text.lower() for x in ["login code", "رمز الدخول", "code:", "كود"]):
                text = f"🚨 **رمز جديد للحساب (`+{phone_num}`):**\n\n`{msg_text}`"
                await ptb_app.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logging.error(f"خطأ في إرسال الرمز: {e}")

# ══════════════════ لوحة التحكم (أزرار ملونة) ══════════════════
def admin_menu_kb():
    keyboard = [
        [
            InlineKeyboardButton("🟢 ➕ إضافة جلسة", callback_data="add_session", style="success"),
            InlineKeyboardButton("🔵 📱 الجلسات النشطة", callback_data="list_sessions", style="primary")
        ],
        [
            InlineKeyboardButton("📩 طلب رمز", callback_data="request_code", style="primary"),
            InlineKeyboardButton("🔴 🗑 حذف جلسة", callback_data="delete_session", style="danger")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def sessions_kb():
    buttons = []
    for phone in active_userbots.keys():
        buttons.append([
            InlineKeyboardButton(f"📱 +{phone}", callback_data=f"req_{phone}", style="primary")
        ])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back_menu", style="danger")])
    return InlineKeyboardMarkup(buttons)

def delete_sessions_kb():
    buttons = []
    for phone in active_userbots.keys():
        buttons.append([
            InlineKeyboardButton(f"🗑 +{phone}", callback_data=f"del_{phone}", style="danger")
        ])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back_menu", style="primary")])
    return InlineKeyboardMarkup(buttons)

# ══════════════════ الأوامر ══════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ هذا البوت مخصص للأدمن فقط.")
        return

    await update.message.reply_text(
        "👋 **أهلاً بك في لوحة إدارة جلسات تيليجرام**\n\n"
        "يمكنك إضافة جلساتك الخاصة واستقبال رموز الدخول مباشرة هنا.",
        reply_markup=admin_menu_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            "(من موقع my.telegram.org)"
        )

    elif data == "list_sessions":
        if not active_userbots:
            text = "⚠️ لا توجد جلسات نشطة حالياً."
        else:
            text = f"📱 **الجلسات النشطة ({len(active_userbots)}):**\n\n"
            for phone in active_userbots:
                text += f"• `+{phone}` 🟢\n"
        await query.edit_message_text(text, reply_markup=admin_menu_kb(), parse_mode=ParseMode.MARKDOWN)

    elif data == "request_code":
        if not active_userbots:
            await query.edit_message_text("⚠️ لا توجد جلسات مضافة.", reply_markup=admin_menu_kb())
            return
        await query.edit_message_text(
            "📩 **اختر الحساب اللي تبي تطلب له رمز:**",
            reply_markup=sessions_kb()
        )

    elif data.startswith("req_"):
        phone = data.replace("req_", "")
        client = active_userbots.get(phone)
        if not client:
            await query.answer("الجلسة غير موجودة", show_alert=True)
            return
        try:
            # محاولة إرسال كود (يعمل إذا الحساب يحتاج تسجيل دخول جديد)
            await client.send_code(phone)
            await query.edit_message_text(
                f"✅ تم طلب الرمز للحساب `+{phone}`\n"
                "راح يوصلك الرمز هنا تلقائياً إن وصل.",
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
            "🗑 **اختر الجلسة اللي تبي تحذفها:**",
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
            # حذف ملف الجلسة
            session_file = f"session_{phone}.session"
            if os.path.exists(session_file):
                os.remove(session_file)
            await query.edit_message_text(
                f"✅ تم حذف الجلسة `+{phone}`",
                reply_markup=admin_menu_kb(),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.answer("الجلسة غير موجودة", show_alert=True)

async def handle_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("📝 **الخطوة 2:** أرسل الآن الـ **API HASH**:")

    elif state == "WAIT_API_HASH":
        temp_data[ADMIN_ID]["api_hash"] = text
        user_states[ADMIN_ID] = "WAIT_PHONE"
        await update.message.reply_text("📱 **الخطوة 3:** أرسل رقم الهاتف مع رمز الدولة (مثال: `213xxxxxxxxx`):")

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
            await update.message.reply_text("📩 وصلك كود التحقق، أرسله هنا:")
        except Exception as e:
            await client.disconnect()
            user_states.pop(ADMIN_ID, None)
            await update.message.reply_text(f"❌ خطأ: `{e}`", reply_markup=admin_menu_kb())

    elif state == "WAIT_CODE":
        code = text
        data = temp_data.get(ADMIN_ID)
        client = data["client"]

        try:
            await client.sign_in(data["phone"], data["phone_code_hash"], code)
            attach_otp_handler(client, data["phone"], context.application)
            active_userbots[data["phone"]] = client

            user_states.pop(ADMIN_ID, None)
            temp_data.pop(ADMIN_ID, None)

            await update.message.reply_text(
                f"✅ **تم ربط الجلسة بنجاح للحساب `+{data['phone']}`**\n"
                "الآن أي رمز يوصل لهذا الحساب راح يجيلك هنا مباشرة.",
                reply_markup=admin_menu_kb(),
                parse_mode=ParseMode.MARKDOWN
            )
        except SessionPasswordNeeded:
            user_states[ADMIN_ID] = "WAIT_2FA"
            await update.message.reply_text("🔐 الحساب محمي بـ 2FA. أرسل كلمة السر:")
        except (PhoneCodeInvalid, PhoneCodeExpired):
            await update.message.reply_text("❌ الرمز غير صحيح أو منتهي.")

    elif state == "WAIT_2FA":
        password = text
        data = temp_data.get(ADMIN_ID)
        client = data["client"]

        try:
            await client.check_password(password)
            attach_otp_handler(client, data["phone"], context.application)
            active_userbots[data["phone"]] = client

            user_states.pop(ADMIN_ID, None)
            temp_data.pop(ADMIN_ID, None)

            await update.message.reply_text(
                f"✅ **تم التحقق وربط الجلسة `+{data['phone']}` بنجاح!**",
                reply_markup=admin_menu_kb(),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(f"❌ كلمة السر خطأ: `{e}`")

async def load_existing_sessions(ptb_app):
    for file in glob.glob("session_*.session"):
        phone = file.replace("session_", "").replace(".session", "")
        try:
            client = Client(f"session_{phone}")
            await client.start()
            attach_otp_handler(client, phone, ptb_app)
            active_userbots[phone] = client
            print(f"✅ تم تحميل الجلسة: +{phone}")
        except Exception as e:
            print(f"❌ فشل تحميل {phone}: {e}")

async def post_init(app: Application):
    await load_existing_sessions(app)

def main():
    Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
app.add_handler(CallbackQueryHandler(on_callback))
app.add_handler(MessageHandler(PTBFilters.TEXT & \~PTBFilters.COMMAND, handle_inputs))

print("🚀 البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
