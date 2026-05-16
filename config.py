"""
Bot sozlamalari
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")

# Admin ID (o'zingizning Telegram ID'ingiz)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Neon Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@host/db")

# Sayt API (to'lov tekshirish uchun)
SITE_API_URL = os.getenv("SITE_API_URL", "https://sizning-saytingiz.com/api")
SITE_API_KEY = os.getenv("SITE_API_KEY", "api_keyingiz")

# Guruh ID (to'lov screen shotlari yuboriladigan guruh)
PAYMENT_GROUP_ID = int(os.getenv("PAYMENT_GROUP_ID", "0"))

# Til sozlamalari
DEFAULT_LANGUAGE = "uz"

LANGUAGES = {
    "uz": "O'zbek",
    "ru": "Русский"
}

# Tugmalar matnlari
BUTTONS = {
    "uz": {
        "payment_confirm": "💳 To'lov tasdiqlash",
        "about_me": "👤 Men haqimda",
        "payment_history": "📋 To'lovlar tarixi",
        "settings": "⚙️ Sozlamalar",
        "about_bot": "🤖 Bot haqida",
        "questions": "❓ Savollar",
        "contact_admin": "📞 Admin bilan bog'lanish",
        "back": "⬅️ Orqaga",
        "change_language": "🌐 Tilni o'zgartirish",
        "statistics": "📊 Statistika",
        "broadcast": "📢 Ommaviy e'lon",
        "payment_report": "📈 To'lov hisoboti",
        "set_welcome": "✏️ Salomlashuv postini sozlash",
        "set_questions": "❓ Savollar qismini sozlash",
        "set_about": "📝 Bot haqida qismini sozlash",
        "daily_report": "📅 Kunlik hisobot",
        "weekly_report": "📊 Haftalik hisobot"
    },
    "ru": {
        "payment_confirm": "💳 Подтверждение оплаты",
        "about_me": "👤 Обо мне",
        "payment_history": "📋 История платежей",
        "settings": "⚙️ Настройки",
        "about_bot": "🤖 О боте",
        "questions": "❓ Вопросы",
        "contact_admin": "📞 Связаться с админом",
        "back": "⬅️ Назад",
        "change_language": "🌐 Сменить язык",
        "statistics": "📊 Статистика",
        "broadcast": "📢 Массовая рассылка",
        "payment_report": "📈 Отчет по платежам",
        "set_welcome": "✏️ Настроить приветствие",
        "set_questions": "❓ Настроить вопросы",
        "set_about": "📝 Настроить раздел о боте",
        "daily_report": "📅 Ежедневный отчет",
        "weekly_report": "📊 Еженедельный отчет"
    }
}

MESSAGES = {
    "uz": {
        "welcome": "Assalomu alaykum! {name}",
        "enter_order_number": "Saytdan olgan buyurtma raqamingizni yuboring:",
        "order_not_found": "❌ Bu raqam bo'yicha buyurtma topilmadi. Iltimos, qayta tekshiring.",
        "order_found": "✅ Buyurtma topildi!

💰 Summa: {amount} so'm
📦 Status: {status}

To'lovni amalga oshirgach, screen shot yuboring:",
        "screenshot_received": "📸 Screen shot qabul qilindi. Tekshirilmoqda...",
        "payment_approved": "✅ To'lovingiz tasdiqlandi! Endi saytdan davom etishingiz mumkin.",
        "payment_rejected": "❌ To'lov tasdiqlanmadi. Iltimos, qayta urinib ko'ring yoki admin bilan bog'laning.",
        "no_history": "📭 Hali to'lovlar tarixi mavjud emas.",
        "select_language": "Tilni tanlang:",
        "language_changed": "✅ Til o'zgartirildi!",
        "not_authorized": "❌ Sizga ruxsat yo'q.",
        "broadcast_sent": "📢 Xabar {count} ta foydalanuvchiga yuborildi.",
        "enter_broadcast": "Yuboriladigan xabarni kiriting (matn, rasm, video yoki hujjat):",
        "enter_welcome_text": "Salomlashuv matnini kiriting (HTML formatida):",
        "welcome_updated": "✅ Salomlashuv posti yangilandi!",
        "enter_question_text": "Savollar bo'limi matnini kiriting:",
        "questions_updated": "✅ Savollar bo'limi yangilandi!",
        "enter_about_text": "Bot haqida matnini kiriting:",
        "about_updated": "✅ Bot haqida bo'limi yangilandi!",
        "stats_users": "👥 Foydalanuvchilar: {count}",
        "stats_payments": "💰 Jami to'lovlar: {count} ta ({amount} so'm)",
        "daily_report": "📅 Kunlik hisobot ({date}):

💳 To'lovlar: {count} ta
💰 Jami summa: {amount} so'm",
        "weekly_report": "📊 Haftalik hisobot ({start} - {end}):

💳 To'lovlar: {count} ta
💰 Jami summa: {amount} so'm"
    },
    "ru": {
        "welcome": "Здравствуйте! {name}",
        "enter_order_number": "Отправьте номер вашего заказа с сайта:",
        "order_not_found": "❌ Заказ с таким номером не найден. Пожалуйста, проверьте.",
        "order_found": "✅ Заказ найден!

💰 Сумма: {amount} сум
📦 Статус: {status}

После оплаты отправьте скриншот:",
        "screenshot_received": "📸 Скриншот получен. Проверяется...",
        "payment_approved": "✅ Ваш платеж подтвержден! Теперь вы можете продолжить на сайте.",
        "payment_rejected": "❌ Платеж не подтвержден. Попробуйте снова или свяжитесь с админом.",
        "no_history": "📭 История платежей пока пуста.",
        "select_language": "Выберите язык:",
        "language_changed": "✅ Язык изменен!",
        "not_authorized": "❌ У вас нет доступа.",
        "broadcast_sent": "📢 Сообщение отправлено {count} пользователям.",
        "enter_broadcast": "Введите сообщение для рассылки (текст, фото, видео или документ):",
        "enter_welcome_text": "Введите текст приветствия (в формате HTML):",
        "welcome_updated": "✅ Приветственный пост обновлен!",
        "enter_question_text": "Введите текст раздела вопросов:",
        "questions_updated": "✅ Раздел вопросов обновлен!",
        "enter_about_text": "Введите текст раздела о боте:",
        "about_updated": "✅ Раздел о боте обновлен!",
        "stats_users": "👥 Пользователей: {count}",
        "stats_payments": "💰 Всего платежей: {count} ({amount} сум)",
        "daily_report": "📅 Ежедневный отчет ({date}):

💳 Платежей: {count}
💰 Общая сумма: {amount} сум",
        "weekly_report": "📊 Еженедельный отчет ({start} - {end}):

💳 Платежей: {count}
💰 Общая сумма: {amount} сум"
    }
}

def get_text(lang, key, **kwargs):
    """Til bo'yicha matn olish"""
    text = MESSAGES.get(lang, MESSAGES["uz"]).get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text

def get_button(lang, key):
    """Til bo'yicha tugma matnini olish"""
    return BUTTONS.get(lang, BUTTONS["uz"]).get(key, key)
