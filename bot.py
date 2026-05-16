"""
Asosiy bot - Maxsus to'lov boti (Avtomatik screen shot tekshiruvi bilan)
Deploy: Render Web Service
Database: Neon PostgreSQL
"""
import os
import json
import logging
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes
)
from config import (
    BOT_TOKEN, ADMIN_ID, PAYMENT_GROUP_ID, DEFAULT_LANGUAGE,
    LANGUAGES, get_text, get_button
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

# Conversation states
WAITING_ORDER_NUMBER = 1
WAITING_SCREENSHOT = 2

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

    # Foydalanuvchini bazaga qo'shish/yangilash
    db.add_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    lang = get_user_lang(user.id)
    welcome_text, welcome_links = db.get_welcome_data()

    # Salomlashuv matni
    text = welcome_text.format(name=user.first_name)

    # Tugmalar
    keyboard = []

    # Link tugmalari
    for link in welcome_links:
        keyboard.append([InlineKeyboardButton(link['name'], url=link['url'])])

    # Asosiy menyu tugmalari
    keyboard.extend([
        [InlineKeyboardButton(get_button(lang, "payment_confirm"), callback_data='payment_confirm')],
        [InlineKeyboardButton(get_button(lang, "about_me"), callback_data='about_me'),
         InlineKeyboardButton(get_button(lang, "payment_history"), callback_data='payment_history')],
        [InlineKeyboardButton(get_button(lang, "settings"), callback_data='settings'),
         InlineKeyboardButton(get_button(lang, "about_bot"), callback_data='about_bot')],
        [InlineKeyboardButton(get_button(lang, "questions"), callback_data='questions')]
    ])

    # Admin tugmasi
    if await is_admin(user.id):
        keyboard.append([InlineKeyboardButton("🔧 Admin panel", callback_data='admin_panel')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

# ========== TO'LOV TASDIQLASH ==========

async def payment_confirm_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lov tasdiqlashni boshlash"""
    query = update.callback_query
    await query.answer()

    lang = get_user_lang(query.from_user.id)

    await query.edit_message_text(
        get_text(lang, "enter_order_number"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]
        ])
    )

    context.user_data['state'] = WAITING_ORDER_NUMBER

async def process_order_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtma raqamini qabul qilish"""
    if context.user_data.get('state') != WAITING_ORDER_NUMBER:
        return

    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    order_number = update.message.text.strip()

    # Buyurtmani tekshirish
    order_data = await payment_service.check_order(order_number)

    if not order_data['found']:
        await update.message.reply_text(
            get_text(lang, "order_not_found"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]
            ])
        )
        context.user_data['state'] = None
        return

    # Buyurtma topildi
    context.user_data['order_number'] = order_number
    context.user_data['order_amount'] = order_data['amount']

    text = get_text(lang, "order_found",
                   amount=f"{order_data['amount']:,.0f}",
                   status=order_data['status'])

    await update.message.reply_text(text)

    # To'lovni bazaga qo'shish
    payment_id = db.add_payment(user_id, order_number, order_data['amount'])
    context.user_data['payment_id'] = payment_id

    # Screen shot kutilmoqda
    await update.message.reply_text(
        "📸 Iltimos, to'lov chekining screen shotini yuboring:

"
        "💡 Bot avtomatik tekshiradi:
"
        "   ✅ Rasm haqiqiyligi
"
        "   ✅ Summa to'g'riligi
"
        "   ✅ Vaqt belgisi
"
        "   ✅ Tranzaksiya ID"
    )

    context.user_data['state'] = WAITING_SCREENSHOT

async def process_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Screen shotni qabul qilish va AVTO TEKSHIRISH"""
    if context.user_data.get('state') != WAITING_SCREENSHOT:
        return

    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    payment_id = context.user_data.get('payment_id')
    order_number = context.user_data.get('order_number')
    order_amount = context.user_data.get('order_amount')

    if not payment_id:
        return

    # Screen shot ma'lumotlarini olish
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

    # Bazaga saqlash
    db.update_payment_screenshot(payment_id, file_id, update.message.message_id)

    # ⭐ AVTO TEKSHIRISH BOSHLANDI
    await update.message.reply_text("🔍 Screen shot avtomatik tekshirilmoqda...")

    try:
        # Rasmni yuklab olish
        file = await context.bot.get_file(file_id)

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            await file.download_to_drive(tmp_file.name)
            tmp_path = tmp_file.name

        # AVTO TEKSHIRISH
        check_result = await screenshot_checker.check_screenshot(
            tmp_path, 
            expected_amount=order_amount,
            order_number=order_number
        )

        # Vaqtinchalik faylni o'chirish
        os.unlink(tmp_path)

        # Tekshirish natijasini ko'rsatish
        status_text = f"""📊 Tekshirish natijasi:

🎯 Ishonch darajasi: {check_result['confidence']*100:.0f}%
{"✅ Haqiqiy" if check_result['is_valid'] else "⚠️ Shubhali"}

📋 Topilgan ma'lumotlar:
💰 Summa: {check_result['extracted_data'].get('found_amount', 'N/A')}
🕐 Vaqt: {check_result['extracted_data'].get('found_time', 'N/A')}
🆔 Tranzaksiya ID: {check_result['extracted_data'].get('transaction_id', 'N/A')}

{"✅ Avtomatik tasdiqlandi!" if check_result['is_valid'] else check_result['recommendation']}"""

        if check_result['issues']:
            status_text += "

⚠️ Muammolar:
"
            for issue in check_result['issues']:
                status_text += f"   • {issue}
"

        await update.message.reply_text(status_text)

        # AVTO TASDIQLASH (agar ishonch yuqori bo'lsa)
        if check_result['is_valid'] and check_result['confidence'] >= AUTO_APPROVE_THRESHOLD:
            # To'lovni tasdiqlash
            db.approve_payment(payment_id, 0)  # 0 = avtomatik tasdiq

            # Saytda tasdiqlash
            await payment_service.confirm_payment(order_number)

            await update.message.reply_text(
                "🎉 To'lovingiz avtomatik tasdiqlandi!

"
                "✅ Endi saytdan davom etishingiz mumkin.

"
                "📋 Buyurtma: #{order_number}
"
                "💰 Summa: {amount:,.0f} so'm".format(
                    order_number=order_number,
                    amount=order_amount
                )
            )

            # Guruhga xabar (ma'lumot uchun)
            if PAYMENT_GROUP_ID:
                user = update.effective_user
                await context.bot.send_message(
                    chat_id=PAYMENT_GROUP_ID,
                    text=f"""✅ AVTO TASDIQLANDI!

👤 Foydalanuvchi: {user.first_name} (@{user.username or 'Noma\'lum'})
🆔 ID: {user.id}
📋 Buyurtma: #{order_number}
💰 Summa: {order_amount:,.0f} so'm
🎯 Ishonch: {check_result['confidence']*100:.0f}%
🤖 Avtomatik tasdiq"""
                )

        else:
            # Admin tekshiruviga yuborish
            await update.message.reply_text(
                "⏳ Screen shot admin tekshiruviga yuborildi.
"
                "Natijasi tez orada xabar qilinadi."
            )

            # Guruhga yuborish (admin tekshirishi uchun)
            if PAYMENT_GROUP_ID:
                user = update.effective_user

                group_text = f"""⚠️ TEKSHIRUV TALAB ETILADI!

👤 Foydalanuvchi: {user.first_name} (@{user.username or 'Noma\'lum'})
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
{chr(10).join(check_result['issues']) if check_result['issues'] else 'Yo\'q'}"""

                # Screen shotni yuborish
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

                # Tasdiqlash tugmalari
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

    # To'lovni tasdiqlash
    db.approve_payment(payment_id, query.from_user.id)

    # Saytda tasdiqlash
    await payment_service.confirm_payment(payment['order_number'])

    # Foydalanuvchiga xabar
    user_lang = get_user_lang(payment['user_id'])
    try:
        await context.bot.send_message(
            chat_id=payment['user_id'],
            text=get_text(user_lang, "payment_approved")
        )
    except Exception as e:
        logger.error(f"Xabar yuborishda xato: {e}")

    await query.edit_message_text(
        f"✅ To'lov tasdiqlandi!

📋 Buyurtma: #{payment['order_number']}
💰 Summa: {payment['amount']:,.0f} so'm"
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

    # Foydalanuvchiga xabar
    user_lang = get_user_lang(payment['user_id'])
    try:
        await context.bot.send_message(
            chat_id=payment['user_id'],
            text=get_text(user_lang, "payment_rejected")
        )
    except Exception as e:
        logger.error(f"Xabar yuborishda xato: {e}")

    await query.edit_message_text(
        f"❌ To'lov rad etildi!

📋 Buyurtma: #{payment['order_number']}
💰 Summa: {payment['amount']:,.0f} so'm"
    )

# ========== MEN HAqIMDA ==========

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
        text = "👤 Sizning saytlaringiz:

"
        for i, site in enumerate(sites, 1):
            text += f"{i}. {site['site_name']}
"
            text += f"   🔗 {site['site_url']}
"
            text += f"   👤 Login: {site['login']}
"
            text += f"   🔑 Parol: {site['password']}

"

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
        text = "📋 To'lovlar tarixi:

"
        for payment in payments:
            status = "✅ Tasdiqlandi" if payment['status'] == 'approved' else \
                     "⏳ Kutilmoqda" if payment['status'] == 'pending' else "❌ Rad etildi"
            auto = "🤖 Avto" if payment.get('approved_by') == 0 else "👤 Admin"
            text += f"📋 #{payment['order_number']} - {payment['amount']:,.0f} so'm
"
            text += f"   📅 {payment['created_at'].strftime('%d.%m.%Y %H:%M')}
"
            text += f"   📊 {status} ({auto})

"

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

    about_text = db.get_setting('about_text') or 'Bot haqida ma\'lumot'
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

    text = f"{questions_text}

📞 Admin bilan bog'lanish: {contact}"

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

    # Admin state tekshirish
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

    # Foydalanuvchi state tekshirish
    state = context.user_data.get('state')
    if state == WAITING_ORDER_NUMBER:
        await process_order_number(update, context)
    elif state == WAITING_SCREENSHOT:
        await process_screenshot(update, context)
    else:
        # Noma'lum xabar
        lang = get_user_lang(user_id)
        await update.message.reply_text(
            "Iltimos, menyudan tanlang:",
            reply_markup=get_main_keyboard(lang)
        )

# ========== ASOSIY FUNKSIYA ==========

def main():
    """Botni ishga tushirish"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Komandalar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))

    # Callback query handlerlar
    application.add_handler(CallbackQueryHandler(payment_confirm_start, pattern='^payment_confirm$'))
    application.add_handler(CallbackQueryHandler(about_me, pattern='^about_me$'))
    application.add_handler(CallbackQueryHandler(payment_history, pattern='^payment_history$'))
    application.add_handler(CallbackQueryHandler(settings, pattern='^settings$'))
    application.add_handler(CallbackQueryHandler(change_language, pattern='^change_language$'))
    application.add_handler(CallbackQueryHandler(set_language, pattern='^lang_'))
    application.add_handler(CallbackQueryHandler(about_bot, pattern='^about_bot$'))
    application.add_handler(CallbackQueryHandler(questions, pattern='^questions$'))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_main$'))

    # Admin handlerlar
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern='^admin_stats$'))
    application.add_handler(CallbackQueryHandler(admin_broadcast_start, pattern='^admin_broadcast$'))
    application.add_handler(CallbackQueryHandler(admin_report, pattern='^admin_report$'))
    application.add_handler(CallbackQueryHandler(admin_daily_report, pattern='^report_daily$'))
    application.add_handler(CallbackQueryHandler(admin_weekly_report, pattern='^report_weekly$'))
    application.add_handler(CallbackQueryHandler(admin_set_welcome_start, pattern='^admin_set_welcome$'))
    application.add_handler(CallbackQueryHandler(admin_set_questions_start, pattern='^admin_set_questions$'))
    application.add_handler(CallbackQueryHandler(admin_set_about_start, pattern='^admin_set_about$'))

    # To'lov tasdiqlash/rad etish
    application.add_handler(CallbackQueryHandler(approve_payment, pattern='^approve_'))
    application.add_handler(CallbackQueryHandler(reject_payment, pattern='^reject_'))

    # Xabarlar
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_message))
    application.add_handler(MessageHandler(filters.VIDEO, handle_message))

    print("🤖 Bot ishga tushdi...")
    print("🔍 Avtomatik screen shot tekshiruvi yoqildi!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
