"""Admin funksiyalari"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_ID, get_text, get_button
from database import db
from datetime import datetime, timedelta
import json

async def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish"""
    return user_id == ADMIN_ID

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin paneli"""
    user_id = update.effective_user.id

    if not await is_admin(user_id):
        await update.message.reply_text("❌ Sizga ruxsat yo'q.")
        return

    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data='admin_stats')],
        [InlineKeyboardButton("📢 Ommaviy e'lon", callback_data='admin_broadcast')],
        [InlineKeyboardButton("📈 To'lov hisoboti", callback_data='admin_report')],
        [InlineKeyboardButton("✏️ Salomlashuv postini sozlash", callback_data='admin_set_welcome')],
        [InlineKeyboardButton("❓ Savollar qismini sozlash", callback_data='admin_set_questions')],
        [InlineKeyboardButton("📝 Bot haqida qismini sozlash", callback_data='admin_set_about')],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data='back_main')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔧 Admin paneli:", reply_markup=reply_markup)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistika"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(query.from_user.id):
        return

    users_count = db.get_users_count()
    stats = db.get_payments_stats()
    total_payments = stats[0] if stats else 0
    total_amount = stats[1] if stats else 0

    text = f"""📊 Statistika:

👥 Foydalanuvchilar: {users_count}
💰 Jami to'lovlar: {total_payments} ta
💵 Jami summa: {total_amount:,.0f} so'm"""

    keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data='admin_panel')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ommaviy e'lon boshlash"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(query.from_user.id):
        return

    context.user_data['admin_state'] = 'broadcast'
    await query.edit_message_text(
        "📢 Yuboriladigan xabarni kiriting (matn, rasm, video yoki hujjat):\n\n"
        "Eslatma: Xabar barcha foydalanuvchilarga yuboriladi."
    )

async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ommaviy xabar yuborish"""
    if not await is_admin(update.effective_user.id):
        return

    users = db.get_all_users()
    sent_count = 0
    failed_count = 0

    for user in users:
        try:
            if update.message.text:
                await context.bot.send_message(user['telegram_id'], update.message.text)
            elif update.message.photo:
                await context.bot.send_photo(
                    user['telegram_id'],
                    update.message.photo[-1].file_id,
                    caption=update.message.caption
                )
            elif update.message.video:
                await context.bot.send_video(
                    user['telegram_id'],
                    update.message.video.file_id,
                    caption=update.message.caption
                )
            elif update.message.document:
                await context.bot.send_document(
                    user['telegram_id'],
                    update.message.document.file_id,
                    caption=update.message.caption
                )
            sent_count += 1
        except Exception as e:
            print(f"Xabar yuborishda xato (user {user['telegram_id']}): {e}")
            failed_count += 1

    await update.message.reply_text(
        f"📢 Xabar yuborildi!\n\n"
        f"✅ Muvaffaqiyatli: {sent_count}\n"
        f"❌ Xato: {failed_count}"
    )

    context.user_data['admin_state'] = None

async def admin_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lov hisoboti"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(query.from_user.id):
        return

    keyboard = [
        [InlineKeyboardButton("📅 Kunlik hisobot", callback_data='report_daily')],
        [InlineKeyboardButton("📊 Haftalik hisobot", callback_data='report_weekly')],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data='admin_panel')]
    ]

    await query.edit_message_text(
        "📈 To'lov hisobotini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kunlik hisobot"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(query.from_user.id):
        return

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    payments = db.get_payments_by_date(today, tomorrow)
    total_amount = sum(p['amount'] for p in payments if p['status'] == 'approved')

    text = f"""📅 Kunlik hisobot ({today.strftime('%d.%m.%Y')}):

💳 To'lovlar: {len(payments)} ta
💰 Jami summa: {total_amount:,.0f} so'm

Batafsil:"""

    for payment in payments:
        status_emoji = "✅" if payment['status'] == 'approved' else "⏳" if payment['status'] == 'pending' else "❌"
        text += f"\n{status_emoji} #{payment['order_number']} - {payment['amount']:,.0f} so'm"

    keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data='admin_report')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_weekly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Haftalik hisobot"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(query.from_user.id):
        return

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    payments = db.get_payments_by_date(week_ago, today + timedelta(days=1))
    total_amount = sum(p['amount'] for p in payments if p['status'] == 'approved')

    text = f"""📊 Haftalik hisobot ({week_ago.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}):

💳 To'lovlar: {len(payments)} ta
💰 Jami summa: {total_amount:,.0f} so'm

Batafsil:"""

    for payment in payments:
        status_emoji = "✅" if payment['status'] == 'approved' else "⏳" if payment['status'] == 'pending' else "❌"
        text += f"\n{status_emoji} #{payment['order_number']} - {payment['amount']:,.0f} so'm"

    keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data='admin_report')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_set_welcome_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Salomlashuv postini sozlash boshlash"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(query.from_user.id):
        return

    context.user_data['admin_state'] = 'set_welcome'
    current_text, current_links = db.get_welcome_data()

    await query.edit_message_text(
        f"✏️ Joriy salomlashuv matni:\n\n{current_text}\n\n"
        f"Yangi matnni kiriting (HTML formatida, {{name}} - foydalanuvchi ismi):\n\n"
        f"Linklar qo'shish uchun: LINKS: [{json.dumps(current_links)}]"
    )

async def admin_set_welcome_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Salomlashuv postini saqlash"""
    if not await is_admin(update.effective_user.id):
        return

    text = update.message.text
    links = []

    # Linklarni ajratib olish
    if 'LINKS:' in text:
        parts = text.split('LINKS:')
        text = parts[0].strip()
        try:
            links = json.loads(parts[1].strip())
        except:
            pass

    db.set_welcome_data(text, links)

    await update.message.reply_text("✅ Salomlashuv posti yangilandi!")
    context.user_data['admin_state'] = None

async def admin_set_questions_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Savollar qismini sozlash boshlash"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(query.from_user.id):
        return

    context.user_data['admin_state'] = 'set_questions'
    current_text = db.get_setting('questions_text') or 'Savollaringiz bormi?'

    await query.edit_message_text(
        f"❓ Joriy savollar matni:\n\n{current_text}\n\n"
        f"Yangi matnni kiriting:"
    )

async def admin_set_questions_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Savollar qismini saqlash"""
    if not await is_admin(update.effective_user.id):
        return

    db.set_setting('questions_text', update.message.text)
    await update.message.reply_text("✅ Savollar bo'limi yangilandi!")
    context.user_data['admin_state'] = None

async def admin_set_about_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot haqida qismini sozlash boshlash"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(query.from_user.id):
        return

    context.user_data['admin_state'] = 'set_about'
    current_text = db.get_setting('about_text') or 'Bot haqida'

    await query.edit_message_text(
        f"📝 Joriy bot haqida matni:\n\n{current_text}\n\n"
        f"Yangi matnni kiriting (rasm/video yuborish uchun media yuboring):"
    )

async def admin_set_about_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot haqida qismini saqlash"""
    if not await is_admin(update.effective_user.id):
        return

    if update.message.text:
        db.set_setting('about_text', update.message.text)
    elif update.message.photo:
        db.set_setting('about_media', update.message.photo[-1].file_id)
        if update.message.caption:
            db.set_setting('about_text', update.message.caption)
    elif update.message.video:
        db.set_setting('about_media', update.message.video.file_id)
        if update.message.caption:
            db.set_setting('about_text', update.message.caption)

    await update.message.reply_text("✅ Bot haqida bo'limi yangilandi!")
    context.user_data['admin_state'] = None
