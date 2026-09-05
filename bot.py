import os
import glob
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters as PTBFilters, ContextTypes
)

# ══════════════════ CONFIG ══════════════════
BOT_TOKEN = "8893399262:AAG07XosgkW6YRaTanBpwFuJF9ozJj82x0M"  # توكن بوت تلغرام
ADMIN_ID = 8619521184               # معرف الأدمن الخاص بك

# أجهزة وقوائم حفظ البيانات
user_states = {}
temp_data = {}
active_userbots = []

# ══════════════════ HELPER FUNCTIONS ══════════════════
def attach_otp_handler(userbot_client, phone_num, ptb_app):
    """إلتقاط وتوجيه كود التحقق فور وصوله للحساب"""
    @userbot_client.on_message(filters.me | filters.service | filters.private)
    async def auto_forward_otp(c, msg):
        if (msg.from_user and msg.from_user.id == 777000) or "Login code" in str(msg.text) or "رمز الدخول" in str(msg.text):
            text = f"🔑 **رمز دخول جديد للحساب (`+{phone_num}`):**\n\n{msg.text}"
            await ptb_app.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode=ParseMode.MARKDOWN)

# ══════════════════ KEYBOARDS (الأزرار الملونة) ══════════════════
def admin_menu_kb():
    """لوحة تحكم الأدمن بالأزرار الملونة"""
    keyboard = [
        [
            InlineKeyboardButton("➕ إضافة جلسة جديدة", callback_data="add_session", style="success"),
            InlineKeyboardButton("📱 الجلسات النشطة", callback_data="list_sessions", style="primary")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ══════════════════ HANDLERS ══════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ **هذا البوت مخصص للأدمن فقط.**")
        return
    
    await update.message.reply_text(
        "👋 **أهلاً بك في لوحة إدارة الحسابات والجلسات**",
        reply_markup=admin_menu_kb()
    )

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid != ADMIN_ID:
        await query.answer("⛔ غير مصرح لك.", show_alert=True)
        return
        
    await query.answer()
    data = query.data

    if data == "add_session":
        user_states[ADMIN_ID] = "WAIT_API_ID"
        await query.edit_message_text(
            "📝 **الخطوة 1:** أدخل الآن الـ **API ID** الخاص بك:\n"
            "*(يمكنك الحصول عليه من my.telegram.org)*"
        )
    
    elif data == "list_sessions":
        if not active_userbots:
            await query.edit_message_text("❌ لا توجد جلسات نشطة حالياً.", reply_markup=admin_menu_kb())
            return
        
        text = "📱 **قائمة الحسابات والجلسات المراقبة حالياً:**\n\n"
        for ub in active_userbots:
            phone = ub.name.replace("session_", "")
            text += f"• `+{phone}`\n"
            
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu_kb())

async def handle_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    state = user_states.get(ADMIN_ID)
    text = update.message.text.strip()

    if state == "WAIT_API_ID":
        if not text.isdigit():
            await update.message.reply_text("❌ يرجى إدخال API ID بشكل أرقام فقط.")
            return
        temp_data[ADMIN_ID] = {"api_id": int(text)}
        user_states[ADMIN_ID] = "WAIT_API_HASH"
        await update.message.reply_text("📝 **الخطوة 2:** أدخل الآن الـ **API HASH**:")

    elif state == "WAIT_API_HASH":
        temp_data[ADMIN_ID]["api_hash"] = text
        user_states[ADMIN_ID] = "WAIT_PHONE"
        await update.message.reply_text("📱 **الخطوة 3:** أدخل رقم الهاتف مع رمز الدولة (مثال: `213xxxxxxxxx`):")

    elif state == "WAIT_PHONE":
        phone = text.replace("+", "").replace(" ", "")
        temp_data[ADMIN_ID]["phone"] = phone
        await update.message.reply_text(f"⏳ جاري طلب كود التحقق للرقم `+{phone}`...")

        api_id = temp_data[ADMIN_ID]["api_id"]
        api_hash = temp_data[ADMIN_ID]["api_hash"]

        temp_app = Client(f"session_{phone}", api_id=api_id, api_hash=api_hash)
        await temp_app.connect()

        try:
            code_info = await temp_app.send_code(phone)
            temp_data[ADMIN_ID]["app"] = temp_app
            temp_data[ADMIN_ID]["hash"] = code_info.phone_code_hash
            user_states[ADMIN_ID] = "WAIT_CODE"
            await update.message.reply_text("📩 **وصلك كود التحقق على التلغرام، أدخله هنا:**")
        except Exception as e:
            await temp_app.disconnect()
            user_states.pop(ADMIN_ID, None)
            await update.message.reply_text(f"❌ **حدث خطأ:** `{e}`", reply_markup=admin_menu_kb())

    elif state == "WAIT_CODE":
        code = text
        data = temp_data.get(ADMIN_ID)
        temp_app = data["app"]

        try:
            await temp_app.sign_in(data["phone"], data["hash"], code)
            attach_otp_handler(temp_app, data["phone"], context.application)
            active_userbots.append(temp_app)

            user_states.pop(ADMIN_ID, None)
            temp_data.pop(ADMIN_ID, None)
            
            await update.message.reply_text(
                f"✅ **تمت إضافة الجلسة بنجاح للحساب `+{data['phone']}`!**\n"
                "سيرسل لك البوت أي كود دخول فور وصوله.",
                reply_markup=admin_menu_kb()
            )

        except SessionPasswordNeeded:
            user_states[ADMIN_ID] = "WAIT_2FA"
            await update.message.reply_text("🔐 **الحساب محمي بكلمة سر (2FA). أدخل كلمة السر الآن:**")
        except (PhoneCodeInvalid, PhoneCodeExpired):
            await update.message.reply_text("❌ الرمز غير صحيح أو منتهي الصلاحية.")

    elif state == "WAIT_2FA":
        password = text
        data = temp_data.get(ADMIN_ID)
        temp_app = data["app"]

        try:
            await temp_app.check_password(password)
            attach_otp_handler(temp_app, data["phone"], context.application)
            active_userbots.append(temp_app)

            user_states.pop(ADMIN_ID, None)
            temp_data.pop(ADMIN_ID, None)

            await update.message.reply_text(
                f"✅ **تم التحقق وربط الجلسة بنجاح للحساب `+{data['phone']}`!**",
                reply_markup=admin_menu_kb()
            )
        except Exception as e:
            await update.message.reply_text(f"❌ كلمة السر غير صحيحة: `{e}`")

# ══════════════════ LOAD EXISTING SESSIONS ══════════════════
async def load_existing_sessions(ptb_app):
    session_files = glob.glob("session_*.session")
    for file in session_files:
        session_name = file.replace(".session", "")
        phone = session_name.replace("session_", "")
        try:
            # افتراضياً تستخدم الجلسة السابقة
            app = Client(session_name)
            await app.start()
            attach_otp_handler(app, phone, ptb_app)
            active_userbots.append(app)
            print(f"✅ تم تحميل الجلسة السابقة: {phone}")
        except Exception as e:
            print(f"❌ فشل تحميل {session_name}: {e}")

async def post_init(app: Application):
    await load_existing_sessions(app)
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
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(PTBFilters.TEXT & ~PTBFilters.COMMAND, handle_inputs))

    print("🚀 البوت يعمل وجاهز...")
    app.run_polling()

if __name__ == "__main__":
    main()
