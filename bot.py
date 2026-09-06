import os
import sys
import asyncio
import logging
import json
import re
import glob
from threading import Thread
from flask import Flask

# ========== إصلاح مشكلة event loop قبل استيراد Pyrogram ==========
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# ========== استيراد Pyrogram بعد إعداد الحلقة ==========
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

# ========== الإعدادات ==========
API_ID = int(os.environ.get("API_ID", 35821117))
API_HASH = os.environ.get("API_HASH", "302151e03e2373058bffdd3cc7459997")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8893399262:AAGQXKaZI-na_mTAoO4RKqwlDoQ6h3f89h0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8619521184))

logging.basicConfig(level=logging.INFO)

# ========== خادم Flask ==========
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# بدء خادم Flask في thread منفصل
Thread(target=run_flask, daemon=True).start()

# ========== متغيرات البوت ==========
user_states = {}      # user_id -> حالة
temp_data = {}        # بيانات مؤقتة
active_sessions = {}  # phone -> Client

# ========== إنشاء البوت ==========
app = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ========== الأزرار ==========
def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ إضافة حساب", callback_data="add"),
            InlineKeyboardButton("📋 قائمة الحسابات", callback_data="list")
        ],
        [
            InlineKeyboardButton("📩 طلب رمز", callback_data="request"),
            InlineKeyboardButton("🗑 حذف حساب", callback_data="delete")
        ]
    ])

def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ])

def sessions_list():
    buttons = []
    for phone in active_sessions:
        buttons.append([InlineKeyboardButton(f"📱 +{phone}", callback_data=f"req_{phone}")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
    return InlineKeyboardMarkup(buttons)

def delete_list():
    buttons = []
    for phone in active_sessions:
        buttons.append([InlineKeyboardButton(f"🗑 +{phone}", callback_data=f"del_{phone}")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
    return InlineKeyboardMarkup(buttons)

# ========== معالج الرموز (OTP) ==========
def attach_otp_handler(client_obj, phone):
    @client_obj.on_message(filters.user(777000) | filters.service)
    async def otp_handler(c, m):
        try:
            text = m.text or m.caption or ""
            if text:
                codes = re.findall(r'\b\d{5,6}\b', text)
                if codes or any(k in text.lower() for k in ["login code", "رمز", "code:"]):
                    await app.send_message(
                        ADMIN_ID,
                        f"🔐 **رمز جديد للحساب `+{phone}`**\n\n"
                        f"```\n{text}\n```\n"
                        f"📌 الرمز: `{codes[0] if codes else 'غير واضح'}`"
                    )
        except Exception as e:
            logging.error(f"OTP error: {e}")

# ========== معالجات البوت ==========
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ هذا البوت للأدمن فقط.")
        return
    user_states.pop(ADMIN_ID, None)
    await message.reply(
        "👋 **لوحة التحكم**\nاختر الخيار المناسب:",
        reply_markup=admin_menu()
    )

@app.on_callback_query()
async def callback(client, query):
    uid = query.from_user.id
    if uid != ADMIN_ID:
        await query.answer("غير مصرح", show_alert=True)
        return
    await query.answer()
    data = query.data

    if data == "back":
        await query.edit_message_text(
            "👋 **لوحة التحكم**",
            reply_markup=admin_menu()
        )
        return

    if data == "add":
        user_states[ADMIN_ID] = "WAIT_PHONE"
        await query.edit_message_text(
            "📱 **أرسل رقم الهاتف مع رمز الدولة**\nمثال: `213xxxxxxxxx`"
        )
        return

    if data == "list":
        if not active_sessions:
            text = "⚠️ لا توجد حسابات نشطة."
        else:
            text = f"📱 **الحسابات النشطة ({len(active_sessions)}):**\n\n"
            for phone in active_sessions:
                try:
                    me = await active_sessions[phone].get_me()
                    text += f"• `+{phone}` 🟢 @{me.username or 'بدون'}\n"
                except:
                    text += f"• `+{phone}` 🔴 غير متصل\n"
        await query.edit_message_text(text, reply_markup=admin_menu())
        return

    if data == "request":
        if not active_sessions:
            await query.edit_message_text("⚠️ لا توجد حسابات.", reply_markup=admin_menu())
            return
        await query.edit_message_text("📩 **اختر الحساب:**", reply_markup=sessions_list())
        return

    if data.startswith("req_"):
        phone = data[4:]
        if phone not in active_sessions:
            await query.answer("الحساب غير موجود", show_alert=True)
            return
        try:
            await active_sessions[phone].send_code(phone)
            await query.edit_message_text(
                f"✅ تم طلب الرمز لـ `+{phone}`\nسيصلك هنا تلقائياً.",
                reply_markup=admin_menu()
            )
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ: `{e}`", reply_markup=admin_menu())
        return

    if data == "delete":
        if not active_sessions:
            await query.edit_message_text("⚠️ لا توجد حسابات.", reply_markup=admin_menu())
            return
        await query.edit_message_text("🗑 **اختر الحساب للحذف:**", reply_markup=delete_list())
        return

    if data.startswith("del_"):
        phone = data[4:]
        if phone in active_sessions:
            try:
                await active_sessions[phone].stop()
            except:
                pass
            del active_sessions[phone]
            # حذف ملف الجلسة إن وجد
            sess_file = f"session_{phone}.session"
            if os.path.exists(sess_file):
                os.remove(sess_file)
            await query.edit_message_text(f"✅ تم حذف `+{phone}`", reply_markup=admin_menu())
        else:
            await query.answer("غير موجود", show_alert=True)
        return

# ========== معالجة الرسائل النصية (إدخال الرقم والكود) ==========
@app.on_message(filters.text & filters.private & ~filters.command("start"))
async def handle_text(client, message):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return

    state = user_states.get(uid)
    text = message.text.strip()

    if state == "WAIT_PHONE":
        phone = text.replace("+", "").replace(" ", "")
        if not phone.isdigit() or len(phone) < 10:
            await message.reply("❌ رقم غير صحيح، حاول مرة أخرى.")
            return
        temp_data[uid] = {"phone": phone}
        await message.reply(f"⏳ جاري طلب الكود لـ `+{phone}`...")

        try:
            # إنشاء عميل مؤقت
            client_temp = Client(f"temp_{phone}", api_id=API_ID, api_hash=API_HASH)
            await client_temp.connect()
            sent = await client_temp.send_code(phone)
            temp_data[uid]["client"] = client_temp
            temp_data[uid]["hash"] = sent.phone_code_hash
            user_states[uid] = "WAIT_CODE"
            await message.reply("📩 **أرسل الكود الذي وصل إليك:**")
        except Exception as e:
            await message.reply(f"❌ خطأ: `{e}`")
            user_states.pop(uid, None)
            temp_data.pop(uid, None)

    elif state == "WAIT_CODE":
        code = text
        data = temp_data.get(uid)
        if not data:
            await message.reply("⚠️ انتهت الجلسة، أعد المحاولة.")
            return

        client_temp = data["client"]
        try:
            await client_temp.sign_in(data["phone"], data["hash"], code)
            # نجاح تسجيل الدخول
            attach_otp_handler(client_temp, data["phone"])
            active_sessions[data["phone"]] = client_temp
            # حفظ الجلسة (ملف .session يتم إنشاؤه تلقائياً)
            user_states.pop(uid, None)
            temp_data.pop(uid, None)
            await message.reply(
                f"✅ **تم إضافة الحساب `+{data['phone']}` بنجاح!**\n"
                "الآن ستصل الرموز هنا تلقائياً.",
                reply_markup=admin_menu()
            )
        except SessionPasswordNeeded:
            user_states[uid] = "WAIT_2FA"
            await message.reply("🔐 **مطلوب كلمة سر 2FA، أرسلها:**")
        except (PhoneCodeInvalid, PhoneCodeExpired):
            await message.reply("❌ الكود غير صحيح أو منتهي، أعد الإرسال:")
        except Exception as e:
            await message.reply(f"❌ خطأ: `{e}`")
            user_states.pop(uid, None)
            temp_data.pop(uid, None)

    elif state == "WAIT_2FA":
        password = text
        data = temp_data.get(uid)
        if not data:
            await message.reply("⚠️ انتهت الجلسة.")
            return
        client_temp = data["client"]
        try:
            await client_temp.check_password(password)
            attach_otp_handler(client_temp, data["phone"])
            active_sessions[data["phone"]] = client_temp
            user_states.pop(uid, None)
            temp_data.pop(uid, None)
            await message.reply(
                f"✅ **تم إضافة الحساب `+{data['phone']}` بنجاح!**",
                reply_markup=admin_menu()
            )
        except Exception as e:
            await message.reply(f"❌ كلمة السر خطأ: `{e}`")

# ========== تحميل الجلسات المحفوظة ==========
async def load_sessions():
    for file in glob.glob("session_*.session"):
        phone = file.replace("session_", "").replace(".session", "")
        try:
            client = Client(f"session_{phone}")
            await client.start()
            attach_otp_handler(client, phone)
            active_sessions[phone] = client
            logging.info(f"✅ تحميل جلسة: +{phone}")
        except Exception as e:
            logging.error(f"❌ فشل تحميل {phone}: {e}")

# ========== التشغيل ==========
async def main():
    await app.start()
    await load_sessions()
    logging.info("🚀 البوت يعمل...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    # التأكد من وجود حلقة events
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("تم الإيقاف")
