# 💳 Maxsus To'lov Boti

Telegram orqali to'lovlarni qabul qiluvchi maxsus bot.

## 🚀 Xususiyatlari

- **Rus va O'zbek tillari**
- **To'lov tasdiqlash** - Buyurtma raqami orqali tekshirish
- **Screen shot qabul qilish** - Avtomatik tekshirish
- **Guruhga yuborish** - Admin tasdiqlashi
- **To'lovlar tarixi** - Foydalanuvchi uchun
- **Admin paneli** - Statistika, hisobotlar, sozlamalar
- **Ommaviy xabarlar** - Barcha foydalanuvchilarga
- **Neon PostgreSQL** - Ma'lumotlar bazasi
- **Render deploy** - Web service

## 📁 Fayllar

```
payment_bot/
├── bot.py              # Asosiy bot
├── config.py           # Sozlamalar
├── database.py         # Neon DB
├── payments.py         # To'lov tizimi
├── admin.py            # Admin funksiyalari
├── requirements.txt    # Kutubxonalar
├── .env               # Muhit o'zgaruvchilari
└── README.md           # Qo'llanma
```

## ⚙️ O'rnatish

### 1. Bot yaratish
- [@BotFather](https://t.me/BotFather) ga kiring
- Yangi bot yaratib, token oling

### 2. Neon Database
- [neon.tech](https://neon.tech) ga kiring
- Yangi PostgreSQL bazasi yaratib, URL ni oling

### 3. Sozlamalar
`.env` faylini yarating va quyidagilarni to'ldiring:

```env
BOT_TOKEN=your_bot_token
ADMIN_ID=your_telegram_id
DATABASE_URL=postgresql://...
SITE_API_URL=https://your-site.com/api
SITE_API_KEY=your_api_key
PAYMENT_GROUP_ID=-1001234567890
```

### 4. Render ga deploy qilish

#### Render Web Service yaratish:
1. [render.com](https://render.com) ga kiring
2. "New Web Service" tugmasini bosing
3. GitHub reponi ulang
4. Quyidagi sozlamalarni kiriting:

```yaml
Build Command: pip install -r requirements.txt
Start Command: python bot.py
```

5. Environment Variables qismida `.env` dagi qiymatlarni qo'shing

## 🎯 Foydalanish

### Foydalanuvchi uchun:
1. `/start` - Botni ishga tushirish
2. "💳 To'lov tasdiqlash" - Buyurtma raqamini yuborish
3. Screen shot yuborish
4. Tasdiqlashni kutish

### Admin uchun:
1. `/admin` - Admin paneli
2. Statistika ko'rish
3. Ommaviy xabar yuborish
4. To'lov hisobotlari
5. Bot sozlamalarini o'zgartirish

## 🔧 API Integratsiyasi

Sayt API ga quyidagi endpointlar kerak:

```
GET /api/orders/{order_number}  - Buyurtma ma'lumotlari
POST /api/orders/{order_number}/confirm  - To'lovni tasdiqlash
```

## 📞 Aloqa

Muammolar yuzaga kelganda admin bilan bog'laning.
