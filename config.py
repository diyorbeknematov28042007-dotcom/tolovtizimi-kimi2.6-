"""
Bot sozlamalari — Render Environment Variables
Bir nechta sayt bilan ishlash
"""
import os
import json

# ========== CONVERSATION STATES ==========
STATE_SITE_SELECTION = 0
STATE_WAITING_ORDER_NUMBER = 1
STATE_WAITING_SCREENSHOT = 2

# ========== ASOSIY SOZLAMALAR ==========

def safe_int(env_val, default=0):
    """Xavfsiz int konvertatsiya"""
    try:
        return int(env_val) if env_val and env_val.strip() else default
    except (ValueError, TypeError):
        return default

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = safe_int(os.environ.get("ADMIN_ID"), 0)
PAYMENT_GROUP_ID = safe_int(os.environ.get("PAYMENT_GROUP_ID"), 0)
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "uz")

# ========== SAYTLAR (JSON formatida) ==========
# Renderda ENV: SITES = [{"name":"Sayt 1","url":"https://site1.com/api","key":"key1"}]
SITES_JSON = os.environ.get("SITES", "[]")
try:
    SITES = json.loads(SITES_JSON)
except:
    SITES = []

# ========== TILLAR ==========
LANGUAGES = {
    "uz": "O'zbek",
    "ru": "Русский"
}

# ========== TUGMALAR ==========
BUTTONS = {
    "uz": {
        "payment_confirm": "💳 To'lov tasdiqlash",
        "select_site": "🌐 Sayt tanlash",
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
        "select_site": "🌐 Выбрать сайт",
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
        "select_site": "Qaysi saytga to'lov qilmoqchisiz?",
        "enter_order_number": "Saytdan olgan buyurtma raqamingizni yuboring:",
        "order_not_found": "❌ Bu raqam bo'yicha buyurtma topilmadi.",
        "order_found": "✅ Buyurtma topildi!\n\n💰 Summa: {amount} so'm\n📦 Status: {status}\n\nTo'lovni amalga oshirgach, screen shot yuboring:",
        "screenshot_received": "📸 Screen shot qabul qilindi. Tekshirilmoqda...",
        "payment_approved": "✅ To'lovingiz tasdiqlandi! Endi saytdan davom etishingiz mumkin.",
        "payment_rejected": "❌ To'lov tasdiqlanmadi. Admin bilan bog'laning.",
        "no_history": "📭 Hali to'lovlar tarixi mavjud emas.",
        "select_language": "Tilni tanlang:",
        "language_changed": "✅ Til o'zgartirildi!",
        "not_authorized": "❌ Sizga ruxsat yo'q.",
        "broadcast_sent": "📢 Xabar {count} ta foydalanuvchiga yuborildi.",
        "stats_users": "👥 Foydalanuvchilar: {count}",
        "stats_payments": "💰 Jami to'lovlar: {count} ta ({amount} so'm)",
        "daily_report": "📅 Kunlik hisobot ({date}):\n\n💳 To'lovlar: {count} ta\n💰 Jami summa: {amount} so'm",
        "weekly_report": "📊 Haftalik hisobot ({start} - {end}):\n\n💳 To'lovlar: {count} ta\n💰 Jami summa: {amount} so'm"
    },
    "ru": {
        "welcome": "Здравствуйте! {name}",
        "select_site": "Выберите сайт для оплаты:",
        "enter_order_number": "Отправьте номер вашего заказа с сайта:",
        "order_not_found": "❌ Заказ с таким номером не найден.",
        "order_found": "✅ Заказ найден!\n\n💰 Сумма: {amount} сум\n📦 Статус: {status}\n\nПосле оплаты отправьте скриншот:",
        "screenshot_received": "📸 Скриншот получен. Проверяется...",
        "payment_approved": "✅ Ваш платеж подтвержден! Теперь вы можете продолжить на сайте.",
        "payment_rejected": "❌ Платеж не подтвержден. Свяжитесь с админом.",
        "no_history": "📭 История платежей пока пуста.",
        "select_language": "Выберите язык:",
        "language_changed": "✅ Язык изменен!",
        "not_authorized": "❌ У вас нет доступа.",
        "broadcast_sent": "📢 Сообщение отправлено {count} пользователям.",
        "stats_users": "👥 Пользователей: {count}",
        "stats_payments": "💰 Всего платежей: {count} ({amount} сум)",
        "daily_report": "📅 Ежедневный отчет ({date}):\n\n💳 Платежей: {count}\n💰 Общая сумма: {amount} сум",
        "weekly_report": "📊 Еженедельный отчет ({start} - {end}):\n\n💳 Платежей: {count}\n💰 Общая сумма: {amount} сум"
    }
}

def get_text(lang, key, **kwargs):
    text = MESSAGES.get(lang, MESSAGES["uz"]).get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text

def get_button(lang, key):
    return BUTTONS.get(lang, BUTTONS["uz"]).get(key, key)

def get_site_by_index(index):
    """Sayt indeksi bo'yicha ma'lumot olish"""
    if 0 <= index < len(SITES):
        return SITES[index]
    return None

def get_site_names():
    """Barcha sayt nomlarini ro'yxatini olish"""
    return [(i, site["name"]) for i, site in enumerate(SITES)]

def get_site_count():
    """Saytlar soni"""
    return len(SITES)
