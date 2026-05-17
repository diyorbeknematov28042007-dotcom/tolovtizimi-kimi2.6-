"""
config.py - Bot sozlamalari
Universal To'lov Boti v2.0
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Bot
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Adminlar
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# API
API_BASE_URL = os.getenv("API_BASE_URL", "https://your-bot.onrender.com")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "super_secret_key")

# Guruh (admin tasdiqlash uchun)
PAYMENT_GROUP_ID = os.getenv("PAYMENT_GROUP_ID")

# Komissiya (foizda)
DEFAULT_COMMISSION = float(os.getenv("DEFAULT_COMMISSION", "0.00"))

# Xabarlar
WELCOME_MESSAGE = """
👋 Assalomu alaykum!

💳 <b>To'lovlarni tasdiqlash botiga xush kelibsiz!</b>

Bu bot orqali siz:
• 🌐 Ulangan saytlardan xaridlarni tasdiqlashingiz
• 🤖 Telegram botlar orqali to'lovlarni tekshirishingiz  
• 📄 Shaxsiy cheklaringizni yuborib tasdiqlatishingiz mumkin

Quyidagi tugmalar orqali davom eting 👇
"""

ABOUT_MESSAGE = """
💳 <b>To'lov Tasdiqlash Boti</b>

Bu bot orqali siz:
• 🌐 Ulangan saytlardan xaridlarni tasdiqlashingiz
• 🤖 Telegram botlar orqali to'lovlarni tekshirishingiz
• 📄 Shaxsiy cheklaringizni yuborib tasdiqlatishingiz mumkin

<b>🏢 Biznes egalari uchun:</b>
O'z saytingiz yoki botingizni bizga ulab, avtomatik to'lov tasdiqlashni yoqing!
"""

HELP_MESSAGE = """
❓ <b>Yordam</b>

<b>💳 To'lovni qanday tasdiqlash?</b>
1. "To'lov tasdiqlash" tugmasini bosing
2. Xizmatni tanlang (Sayt/Bot)
3. Buyurtma raqamini kiriting
4. To'lov screenshotini yuboring
5. Admin tasdiqlashini kuting

<b>📄 Shaxsiy chekni qanday tekshirish?</b>
1. "To'lov tasdiqlash" → "Shaxsiy chekni tekshirish"
2. To'lov tizimini tanlang (Click/Payme/Apelsin)
3. Screenshot yuboring
4. Admin tekshiruvini kuting

<b>🏢 Biznesimni ulashni xohlayman?</b>
"Bot haqida" → "Biznes Integratsiya" bo'limiga o'ting
"""

BUSINESS_INTEGRATION_MESSAGE = """
🏢 <b>Biznes Integratsiya</b>

Sizning biznesingizni bizga ulash orqali:

<b>🌐 Sayt uchun:</b>
1. API kalit oling
2. Saytingizga kod qo'shing
3. Avtomatik tasdiqlashni yoqing

<b>🤖 Telegram Bot uchun:</b>
1. Bot tokeningizni bering
2. Webhook sozlang
3. Deep linkingni yoqing

<b>📊 Nima olasiz?</b>
✅ Avtomatik to'lov tasdiqlash
✅ Screenshot tekshiruvi
✅ Statistika va hisobotlar
✅ 24/7 qo'llab-quvvatlash
✅ Minimal komissiya
"""

# Chek turlari
RECEIPT_TYPES = {
    'click': '💳 Click',
    'payme': '💳 Payme',
    'apelsin': '🍊 Apelsin',
    'uzum': '📱 Uzum Bank',
    'other': '🏦 Boshqa bank'
}
