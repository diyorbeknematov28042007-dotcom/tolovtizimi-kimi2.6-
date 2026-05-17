"""Asosiy bot - Maxsus to'lov boti (Webhook + Health Check)
Deploy: Render Web Service
Database: Neon PostgreSQL
"""
import os
import json
import logging
import tempfile
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes
)
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
import uvicorn
from config import (
    BOT_TOKEN, ADMIN_ID, PAYMENT_GROUP_ID, DEFAULT_LANGUAGE,
    LANGUAGES, get_text, get_button, get_site_names, get_site_count,
    STATE_SITE_SELECTION, STATE_WAITING_ORDER_NUMBER, STATE_WAITING_SCREENSHOT
)
from database import db
from payments import payment_service
from screenshot_checker import screenshot_checker
from admin import (
    is_admin, admin_panel, admin_stats, admin_broadcast_start,
    admin_broadcast_send, admin_report, admin_daily_report,
    admin_weekly_report, admin_set_welcome_start, admin_set_welcome_save,
    admin_set_questions_start, admin_set_questions_save,
    admin_set_about_start, admin_set_about_save
)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Avtomatik tasdiqlash chegarasi (85% ishonch)
AUTO_APPROVE_THRESHOLD = 0.85

# ========== YORDAMCHI FUNKSIYALAR ==========

def get_user_lang(user_id):
    """Foydalanuvchi tilini olish"""
    user = db.get_user(user_id)
    return user['language'] if user else DEFAULT_LANGUAGE

def get_main_keyboard(lang):
    """Asosiy menyu tugmalari"""
    keyboard = [
        [InlineKeyboardButton(get_button(lang, "payment_confirm"), callback_data='payment_confirm')],
        [InlineKeyboardButton(get_button(lang, "about_me"), callback_data='about_me'),
         InlineKeyboardButton(get_button(lang, "payment_history"), callback_data='payment_history')],
        [InlineKeyboardButton(get_button(lang, "settings"), callback_data='settings'),
         InlineKeyboardButton(get_button(lang, "about_bot"), callback_data='about_bot')],
        [InlineKeyboardButton(get_button(lang, "questions"), callback_data='questions')]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== START VA ASOSIY MENYU ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    user = update.effective_user

    db.add_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    lang = get_user_lang(user.id)
    welcome_text, welcome_links = db.get_welcome_data()

    text = welcome_text.format(name=user.first_name)

    keyboard = []
    for link in welcome_links:
        keyboard.append([InlineKeyboardButton(link['name'], url=link['url'])])

    keyboard.extend([
        [InlineKeyboardButton(get_button(lang, "payment_confirm"), callback_data='payment_confirm')],
        [InlineKeyboardButton(get_button(lang, "about_me"), callback_data='about_me'),
         InlineKeyboardButton(get_button(lang, "payment_history"), callback_data='payment_history')],
        [InlineKeyboardButton(get_button(lang, "settings"), callback_data='settings'),
         InlineKeyboardButton(get_button(lang, "about_bot"), callback_data='about_bot')],
        [InlineKeyboardButton(get_button(lang, "questions"), callback_data='questions')]
    ])

    if await is_admin(user.id):
        keyboard.append([InlineKeyboardButton("🔧 Admin panel", callback_data='admin_panel')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

# ========== TO'LOV TASDIQLASH ==========

async def payment_confirm_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lov tasdiqlashni boshlash - avval sayt tanlash"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    sites = get_site_names()

    if len(sites) <= 1:
        context.user_data['site_index'] = 0
        await query.edit_message_text(
            get_text(lang, "enter_order_number"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]
            ])
        )
        context.user_data['state'] = STATE_WAITING_ORDER_NUMBER
        return

    keyboard = []
    for index, name in sites:
        keyboard.append([InlineKeyboardButton(f"🌐 {name}", callback_data=f'site_{index}')])
    keyboard.append([InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')])

    await query.edit_message_text(
        get_text(lang, "select_site"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    context.user_data['state'] = STATE_SITE_SELECTION

async def process_site_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saytni tanlash"""
    if context.user_data.get('state') != STATE_SITE_SELECTION:
        return

    query = update.callback_query
    await query.answer()

    site_index = int(query.data.split('_')[1])
    context.user_data['site_index'] = site_index

    lang = get_user_lang(query.from_user.id)

    await query.edit_message_text(
        get_text(lang, "enter_order_number"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]
        ])
    )

    context.user_data['state'] = STATE_WAITING_ORDER_NUMBER

async def process_order_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtma raqamini qabul qilish"""
    if context.user_data.get('state') != STATE_WAITING_ORDER_NUMBER:
        return

    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    order_number = update.message.text.strip()

    site_index = context.user_data.get('site_index', 0)
    from payments import PaymentService
    current_payment_service = PaymentService(site_index)
    order_data = await current_payment_service.check_order(order_number)

    if not order_data['found']:
        await update.message.reply_text(
            get_text(lang, "order_not_found"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]
            ])
        )
        context.user_data['state'] = None
        return

    context.user_data['order_number'] = order_number
    context.user_data['order_amount'] = order_data['amount']

    text = get_text(lang, "order_found",
                    amount=f"{order_data['amount']:,.0f}",
                    status=order_data['status'])

    await update.message.reply_text(text)

    payment_id = db.add_payment(
        user_id=user_id,
        site_index=site_index,
        site_name=order_data.get('site_name', "Asosiy sayt"),
        order_number=order_number,
        amount=order_data['amount']
    )
    context.user_data['payment_id'] = payment_id

    screenshot_msg = """📸 Iltimos, to'lov chekining screen shotini yuboring:

💡 Bot avtomatik tekshiradi:
 ✅ Rasm haqiqiyligi
 ✅ Summa to'g'riligi
 ✅ Vaqt belgisi
 ✅ Tranzaksiya ID"""

    await update.message.reply_text(screenshot_msg)
    context.user_data['state'] = STATE_WAITING_SCREENSHOT

async def process_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Screen shotni qabul qilish va AVTO TEKSHIRISH"""
    if context.user_data.get('state') != STATE_WAITING_SCREENSHOT:
        return

    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    payment_id = context.user_data.get('payment_id')
    order_number = context.user_data.get('order_number')
    order_amount = context.user_data.get('order_amount')

    if not payment_id:
        return

    file_id = None
    file_type = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = 'photo'
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = 'document'
    else:
        await update.message.reply_text("❌ Iltimos, rasm yuboring.")
        return

    db.update_payment_screenshot(payment_id, file_id, update.message.message_id)
    await update.message.reply_text("🔍 Screen shot avtomatik tekshirilmoqda...")

    try:
        file = await context.bot.get_file(file_id)

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            await file.download_to_drive(tmp_file.name)
            tmp_path = tmp_file.name

        check_result = await screenshot_checker.check_screenshot(
            tmp_path,
            expected_amount=order_amount,
            order_number=order_number
        )

        os.unlink(tmp_path)

        validity = "✅ Haqiqiy" if check_result['is_valid'] else "⚠️ Shubhali"
        recommendation = check_result.get('recommendation', 'Admin tekshiruvini kuting')

        status_text = f"""📊 Tekshirish natijasi:

🎯 Ishonch darajasi: {check_result['confidence']*100:.0f}%
{validity}

📋 Topilgan ma'lumotlar:
💰 Summa: {check_result['extracted_data'].get('found_amount', 'N/A')}
🕐 Vaqt: {check_result['extracted_data'].get('found_time', 'N/A')}
🆔 Tranzaksiya ID: {check_result['extracted_data'].get('transaction_id', 'N/A')}

{"✅ Avtomatik tasdiqlandi!" if check_result['is_valid'] else recommendation}"""

        if check_result['issues']:
            issues_text = "\n".join([f" • {issue}" for issue in check_result['issues']])
            status_text += f"\n\n⚠️ Muammolar:\n{issues_text}"

        await update.message.reply_text(status_text)

        if check_result['is_valid'] and check_result['confidence'] >= AUTO_APPROVE_THRESHOLD:
            db.approve_payment(payment_id, 0)
            await payment_service.confirm_payment(order_number)

            auto_msg = f"""🎉 To'lovingiz avtomatik tasdiqlandi!

✅ Endi saytdan davom etishingiz mumkin.
📋 Buyurtma: #{order_number}
💰 Summa: {order_amount:,.0f} so'm"""

            await update.message.reply_text(auto_msg)

            if PAYMENT_GROUP_ID:
                user = update.effective_user
                group_auto_msg = f"""✅ AVTO TASDIQLANDI!

👤 Foydalanuvchi: {user.first_name} (@{user.username or "Noma'lum"})
🆔 ID: {user.id}
📋 Buyurtma: #{order_number}
💰 Summa: {order_amount:,.0f} so'm
🎯 Ishonch: {check_result['confidence']*100:.0f}%
🤖 Avtomatik tasdiq"""

                await context.bot.send_message(
                    chat_id=PAYMENT_GROUP_ID,
                    text=group_auto_msg
                )

        else:
            pending_msg = """⏳ Screen shot admin tekshiruviga yuborildi.
Natijasi tez orada xabar qilinadi."""

            await update.message.reply_text(pending_msg)

            if PAYMENT_GROUP_ID:
                user = update.effective_user
                issues_str = "\n".join(check_result['issues']) if check_result['issues'] else "Yo'q"

                group_text = f"""⚠️ TEKSHIRUV TALAB ETILADI!

👤 Foydalanuvchi: {user.first_name} (@{user.username or "Noma'lum"})
🆔 ID: {user.id}
📋 Buyurtma: #{order_number}
💰 Summa: {order_amount:,.0f} so'm
⏰ Vaqt: {update.message.date.strftime('%d.%m.%Y %H:%M')}
🎯 Ishonch: {check_result['confidence']*100:.0f}%

📋 Tekshirish natijalari:
💰 Topilgan summa: {check_result['extracted_data'].get('found_amount', 'N/A')}
🕐 Topilgan vaqt: {check_result['extracted_data'].get('found_time', 'N/A')}
🆔 Tranzaksiya ID: {check_result['extracted_data'].get('transaction_id', 'N/A')}

⚠️ Muammolar:
{issues_str}"""

                if file_type == 'photo':
                    group_message = await context.bot.send_photo(
                        chat_id=PAYMENT_GROUP_ID,
                        photo=file_id,
                        caption=group_text
                    )
                else:
                    group_message = await context.bot.send_document(
                        chat_id=PAYMENT_GROUP_ID,
                        document=file_id,
                        caption=group_text
                    )

                confirm_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f'approve_{payment_id}'),
                        InlineKeyboardButton("❌ Rad etish", callback_data=f'reject_{payment_id}')
                    ]
                ])

                await context.bot.send_message(
                    chat_id=PAYMENT_GROUP_ID,
                    text="To'lovni tasdiqlaysizmi?",
                    reply_markup=confirm_keyboard
                )

                db.update_payment_group_message(payment_id, group_message.message_id)

    except Exception as e:
        logger.error(f"Avto tekshiruvda xato: {e}")
        await update.message.reply_text(
            "⚠️ Avtomatik tekshirishda xato. Admin tekshiruviga yuborildi."
        )

    context.user_data['state'] = None

async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lovni tasdiqlash (admin)"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(query.from_user.id):
        await query.answer("❌ Sizga ruxsat yo'q!", show_alert=True)
        return

    payment_id = int(query.data.split('_')[1])
    payment = db.get_payment(payment_id)

    if not payment:
        await query.edit_message_text("❌ To'lov topilmadi.")
        return

    db.approve_payment(payment_id, query.from_user.id)
    await payment_service.confirm_payment(payment['order_number'])

    user_lang = get_user_lang(payment['user_id'])
    try:
        await context.bot.send_message(
            chat_id=payment['user_id'],
            text=get_text(user_lang, "payment_approved")
        )
    except Exception as e:
        logger.error(f"Xabar yuborishda xato: {e}")

    await query.edit_message_text(
        f"✅ To'lov tasdiqlandi!\n\n📋 Buyurtma: #{payment['order_number']}\n💰 Summa: {payment['amount']:,.0f} so'm"
    )

async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lovni rad etish (admin)"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(query.from_user.id):
        await query.answer("❌ Sizga ruxsat yo'q!", show_alert=True)
        return

    payment_id = int(query.data.split('_')[1])
    payment = db.get_payment(payment_id)

    if not payment:
        await query.edit_message_text("❌ To'lov topilmadi.")
        return

    db.reject_payment(payment_id)

    user_lang = get_user_lang(payment['user_id'])
    try:
        await context.bot.send_message(
            chat_id=payment['user_id'],
            text=get_text(user_lang, "payment_rejected")
        )
    except Exception as e:
        logger.error(f"Xabar yuborishda xato: {e}")

    await query.edit_message_text(
        f"❌ To'lov rad etildi!\n\n📋 Buyurtma: #{payment['order_number']}\n💰 Summa: {payment['amount']:,.0f} so'm"
    )

# ========== MEN HAQIMDA ==========

async def about_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Men haqimda"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang = get_user_lang(user_id)

    sites = db.get_user_sites(user_id)

    if not sites:
        text = "📭 Hali ro'yxatdan o'tgan saytlar mavjud emas."
    else:
        text = "👤 Sizning saytlaringiz:\n\n"
        for i, site in enumerate(sites, 1):
            text += f"{i}. {site['site_name']}\n"
            text += f" 🔗 {site['site_url']}\n"
            text += f" 👤 Login: {site['login']}\n"
            text += f" 🔑 Parol: {site['password']}\n\n"

    keyboard = [[InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ========== TO'LOVLAR TARIXI ==========

async def payment_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lovlar tarixi"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang = get_user_lang(user_id)

    payments = db.get_user_payments(user_id)

    if not payments:
        text = get_text(lang, "no_history")
    else:
        text = "📋 To'lovlar tarixi:\n\n"
        for payment in payments:
            status = "✅ Tasdiqlandi" if payment['status'] == 'approved' else \
                "⏳ Kutilmoqda" if payment['status'] == 'pending' else "❌ Rad etildi"
            auto = "🤖 Avto" if payment.get('approved_by') == 0 else "👤 Admin"
            text += f"📋 #{payment['order_number']} - {payment['amount']:,.0f} so'm\n"
            text += f" 📅 {payment['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            text += f" 📊 {status} ({auto})\n\n"

    keyboard = [[InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ========== SOZLAMALAR ==========

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sozlamalar"""
    query = update.callback_query
    await query.answer()

    lang = get_user_lang(query.from_user.id)

    keyboard = [
        [InlineKeyboardButton(get_button(lang, "change_language"), callback_data='change_language')],
        [InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]
    ]

    await query.edit_message_text(
        "⚙️ Sozlamalar:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tilni o'zgartirish"""
    query = update.callback_query
    await query.answer()

    keyboard = []
    for code, name in LANGUAGES.items():
        keyboard.append([InlineKeyboardButton(name, callback_data=f'lang_{code}')])

    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data='settings')])

    await query.edit_message_text(
        "🌐 Tilni tanlang / Выберите язык:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tilni saqlash"""
    query = update.callback_query
    await query.answer()

    lang_code = query.data.split('_')[1]
    db.update_language(query.from_user.id, lang_code)

    await query.edit_message_text(
        get_text(lang_code, "language_changed"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_button(lang_code, "back"), callback_data='back_main')]
        ])
    )

# ========== BOT HAQIDA ==========

async def about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot haqida"""
    query = update.callback_query
    await query.answer()

    lang = get_user_lang(query.from_user.id)

    about_text = db.get_setting('about_text') or "Bot haqida ma'lumot"
    about_media = db.get_setting('about_media')

    keyboard = [[InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if about_media:
        try:
            await query.message.delete()
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=about_media,
                caption=about_text,
                reply_markup=reply_markup
            )
            return
        except:
            pass

    await query.edit_message_text(about_text, reply_markup=reply_markup)

# ========== SAVOLLAR ==========

async def questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Savollar"""
    query = update.callback_query
    await query.answer()

    lang = get_user_lang(query.from_user.id)

    questions_text = db.get_setting('questions_text') or 'Savollaringiz bormi?'
    contact = db.get_setting('contact_admin') or '@admin'

    text = f"{questions_text}\n\n📞 Admin bilan bog'lanish: {contact}"

    keyboard = [
        [InlineKeyboardButton(get_button(lang, "contact_admin"), url=f'https://t.me/{contact.replace("@", "")}')],
        [InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ========== ORQAGA ==========

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asosiy menyuga qaytish"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = get_user_lang(user.id)

    welcome_text, welcome_links = db.get_welcome_data()
    text = welcome_text.format(name=user.first_name)

    keyboard = []
    for link in welcome_links:
        keyboard.append([InlineKeyboardButton(link['name'], url=link['url'])])

    keyboard.extend([
        [InlineKeyboardButton(get_button(lang, "payment_confirm"), callback_data='payment_confirm')],
        [InlineKeyboardButton(get_button(lang, "about_me"), callback_data='about_me'),
         InlineKeyboardButton(get_button(lang, "payment_history"), callback_data='payment_history')],
        [InlineKeyboardButton(get_button(lang, "settings"), callback_data='settings'),
         InlineKeyboardButton(get_button(lang, "about_bot"), callback_data='about_bot')],
        [InlineKeyboardButton(get_button(lang, "questions"), callback_data='questions')]
    ])

    if await is_admin(user.id):
        keyboard.append([InlineKeyboardButton("🔧 Admin panel", callback_data='admin_panel')])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ========== XABARLAR HANDLERI ==========

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha xabarlarni qayta ishlash"""
    user_id = update.effective_user.id

    admin_state = context.user_data.get('admin_state')
    if admin_state and await is_admin(user_id):
        if admin_state == 'broadcast':
            await admin_broadcast_send(update, context)
            return
        elif admin_state == 'set_welcome':
            await admin_set_welcome_save(update, context)
            return
        elif admin_state == 'set_questions':
            await admin_set_questions_save(update, context)
            return
        elif admin_state == 'set_about':
            await admin_set_about_save(update, context)
            return

    state = context.user_data.get('state')
    if state == STATE_WAITING_ORDER_NUMBER:
        await process_order_number(update, context)
    elif state == STATE_WAITING_SCREENSHOT:
        await process_screenshot(update, context)
    else:
        lang = get_user_lang(user_id)
        await update.message.reply_text(
            "Iltimos, menyudan tanlang:",
            reply_markup=get_main_keyboard(lang)
        )

# ========== ASOSIY FUNKSIYA (WEBHOOK + HEALTH CHECK) ==========

async def telegram_webhook(request):
    """Telegram webhook updates"""
    try:
        data = await request.json()
        await tg_app.update_queue.put(
            Update.de_json(data=data, bot=tg_app.bot)
        )
        return Response()
    except Exception as e:
        logger.error(f"Webhook xato: {e}")
        return Response(status_code=500)

async def health_check(request):
    """Render health check"""
    return PlainTextResponse(
        content=json.dumps({
            "status": "healthy",
            "service": "telegram-payment-bot",
            "timestamp": str(datetime.now()),
            "webhook": webhook_url
        }),
        status_code=200
    )

async def root(request):
    """Root endpoint"""
    return PlainTextResponse(
        content="🤖 Telegram Payment Bot ishlayapti!",
        status_code=200
    )

# Global variables
tg_app = None
webhook_url = ""

def main():
    """Botni ishga tushirish (Webhook + Health Check)"""
    global tg_app, webhook_url

    # Bot application
    tg_app = Application.builder().token(BOT_TOKEN).build()

    # Komandalar
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("admin", admin_panel))

    # Callback query handlerlar
    tg_app.add_handler(CallbackQueryHandler(payment_confirm_start, pattern='^payment_confirm$'))
    tg_app.add_handler(CallbackQueryHandler(process_site_selection, pattern='^site_'))
    tg_app.add_handler(CallbackQueryHandler(about_me, pattern='^about_me$'))
    tg_app.add_handler(CallbackQueryHandler(payment_history, pattern='^payment_history$'))
    tg_app.add_handler(CallbackQueryHandler(settings, pattern='^settings$'))
    tg_app.add_handler(CallbackQueryHandler(change_language, pattern='^change_language$'))
    tg_app.add_handler(CallbackQueryHandler(set_language, pattern='^lang_'))
    tg_app.add_handler(CallbackQueryHandler(about_bot, pattern='^about_bot$'))
    tg_app.add_handler(CallbackQueryHandler(questions, pattern='^questions$'))
    tg_app.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_main$'))

    # Admin handlerlar
    tg_app.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    tg_app.add_handler(CallbackQueryHandler(admin_stats, pattern='^admin_stats$'))
    tg_app.add_handler(CallbackQueryHandler(admin_broadcast_start, pattern='^admin_broadcast$'))
    tg_app.add_handler(CallbackQueryHandler(admin_report, pattern='^admin_report$'))
    tg_app.add_handler(CallbackQueryHandler(admin_daily_report, pattern='^report_daily$'))
    tg_app.add_handler(CallbackQueryHandler(admin_weekly_report, pattern='^report_weekly$'))
    tg_app.add_handler(CallbackQueryHandler(admin_set_welcome_start, pattern='^admin_set_welcome$'))
    tg_app.add_handler(CallbackQueryHandler(admin_set_questions_start, pattern='^admin_set_questions$'))
    tg_app.add_handler(CallbackQueryHandler(admin_set_about_start, pattern='^admin_set_about$'))

    # To'lov tasdiqlash/rad etish
    tg_app.add_handler(CallbackQueryHandler(approve_payment, pattern='^approve_'))
    tg_app.add_handler(CallbackQueryHandler(reject_payment, pattern='^reject_'))

    # Xabarlar
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    tg_app.add_handler(MessageHandler(filters.PHOTO, handle_message))
    tg_app.add_handler(MessageHandler(filters.Document.ALL, handle_message))
    tg_app.add_handler(MessageHandler(filters.VIDEO, handle_message))

    # Webhook sozlamalari
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
    RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
    PORT_STR = os.environ.get("PORT", "10000")
    PORT = int(PORT_STR) if PORT_STR and PORT_STR.strip() else 10000
    WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "D1yoRBeK")

    # Fallback for local testing
    if not WEBHOOK_URL and not RENDER_EXTERNAL_URL:
        print("⚠️ WEBHOOK_URL va RENDER_EXTERNAL_URL o'rnatilmagan!")
        print("🔄 Polling mode'ga o'tilmoqda...")
        tg_app.run_polling(allowed_updates=Update.ALL_TYPES)
        return

    webhook_url = WEBHOOK_URL or f"{RENDER_EXTERNAL_URL}/telegram"

    # Starlette app
    starlette_app = Starlette(
        routes=[
            Route("/telegram", telegram_webhook, methods=["POST"]),
            Route("/health", health_check, methods=["GET"]),
            Route("/", root, methods=["GET"]),
        ]
    )

    async def run_bot():
        """Botni ishga tushirish"""
        print("🤖 Bot ishga tushdi...")
        print(f"🔗 Webhook URL: {webhook_url}")
        print(f"📡 Port: {PORT}")
        print(f"🏥 Health Check: http://0.0.0.0:{PORT}/health")
        print("🔍 Avtomatik screen shot tekshiruvi yoqildi!")

        await tg_app.bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
            allowed_updates=Update.ALL_TYPES
        )

        async with tg_app:
            await tg_app.start()
            # Bot ishlayotganini kutish
            while True:
                await asyncio.sleep(3600)

    # Web server
    webserver = uvicorn.Server(
        config=uvicorn.Config(
            app=starlette_app,
            host="0.0.0.0",
            port=PORT,
            use_colors=False,
        )
    )

    # Ikkisini parallel ishga tushirish
    async def main_async():
        await asyncio.gather(
            run_bot(),
            webserver.serve()
        )

    asyncio.run(main_async())

if __name__ == '__main__':
    main()
