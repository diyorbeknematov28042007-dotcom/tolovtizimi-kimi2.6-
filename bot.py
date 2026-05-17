"""
bot.py - Asosiy Telegram Bot
Universal To'lov Boti v2.0
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import (
    BOT_TOKEN, ADMIN_IDS, WELCOME_MESSAGE, ABOUT_MESSAGE,
    HELP_MESSAGE, BUSINESS_INTEGRATION_MESSAGE, RECEIPT_TYPES
)
from database import (
    init_db, get_active_services, get_service_by_id,
    create_payment, get_or_create_user, get_pending_payments,
    create_business_request, get_pending_business_requests,
    update_business_request_status, add_service
)
from payments import verify_site_payment, verify_bot_payment, process_personal_receipt
from admin import (
    is_admin, get_admin_keyboard, get_payment_action_keyboard,
    get_business_request_keyboard, show_stats, show_pending_payments,
    approve_payment, reject_payment, show_business_requests,
    approve_business_request, reject_business_request
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot va Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ============================================
# STATES (FSM)
# ============================================
class PaymentStates(StatesGroup):
    waiting_order_number = State()
    waiting_screenshot = State()
    waiting_receipt_type = State()
    waiting_receipt_number = State()
    waiting_business_name = State()
    waiting_business_type = State()
    waiting_contact = State()
    waiting_description = State()
    waiting_broadcast = State()

# ============================================
# KEYBOARDS
# ============================================

def get_main_keyboard():
    """Asosiy menyu keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 To'lov tasdiqlash")],
            [KeyboardButton(text="📋 To'lovlar tarixi")],
            [KeyboardButton(text="ℹ️ Bot haqida")],
            [KeyboardButton(text="❓ Yordam")]
        ],
        resize_keyboard=True
    )


def get_services_keyboard():
    """Ulangan xizmatlar keyboard"""
    services = asyncio.run(get_active_services())

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Saytlar
    websites = [s for s in services if s['type'] == 'website']
    if websites:
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="🌐 SAYTLAR:", callback_data="header_websites")]
        )
        for site in websites:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🌐 {site['name']}",
                    callback_data=f"service_website_{site['id']}"
                )
            ])

    # Botlar
    bots = [s for s in services if s['type'] == 'telegram_bot']
    if bots:
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="🤖 TELEGRAM BOTlar:", callback_data="header_bots")]
        )
        for b in bots:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🤖 {b['name']}",
                    callback_data=f"service_bot_{b['id']}"
                )
            ])

    # Separator va shaxsiy chek
    if websites or bots:
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="───────────────", callback_data="separator")]
        )

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="📄 Shaxsiy chekni tekshirish",
            callback_data="personal_receipt"
        )
    ])

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_main")
    ])

    return keyboard


def get_receipt_type_keyboard():
    """Chek turi tanlash keyboard"""
    buttons = []
    for key, name in RECEIPT_TYPES.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"receipt_{key}")])

    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_services")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_business_keyboard():
    """Biznes integratsiya keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Sayt ulash", callback_data="connect_website")],
        [InlineKeyboardButton(text="🤖 Bot ulash", callback_data="connect_bot")],
        [InlineKeyboardButton(text="📊 Nima olaman?", callback_data="benefits")],
        [InlineKeyboardButton(text="📝 Ariza yuborish", callback_data="apply_business")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_about")]
    ])


# ============================================
# START HANDLER
# ============================================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """/start handler - Deep link tekshirish"""
    await state.clear()

    # Foydalanuvchini saqlash
    await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    # Deep link tekshirish
    args = message.text.split()
    if len(args) > 1:
        param = args[1]

        # Format: service_{ID}_order_{ORDER_ID}
        if param.startswith("service_"):
            parts = param.split("_")
            if len(parts) >= 4:
                service_id = parts[1]
                order_id = parts[3]

                service = await get_service_by_id(int(service_id))
                if service:
                    await message.answer(
                        f"🔗 <b>Siz {service['name']} xizmatidan yo'naltirildingiz.</b>

"
                        f"📦 Buyurtma: <code>#{order_id}</code>

"
                        f"To'lovni tasdiqlash uchun quyidagi tugmani bosing:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(
                                text="✅ To'lovni tasdiqlash",
                                callback_data=f"verify_direct_{service_id}_{order_id}"
                            )]
                        ])
                    )
                    return

    # Oddiy start
    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


# ============================================
# MAIN MENU HANDLERS
# ============================================

@dp.message(F.text == "💳 To'lov tasdiqlash")
async def payment_verify(message: Message):
    """To'lov tasdiqlash bosilganda"""
    await message.answer(
        "📋 <b>Quyidagi xizmatlardan birini tanlang</b>
"
        "yoki shaxsiy chekni tekshiring:",
        reply_markup=get_services_keyboard(),
        parse_mode="HTML"
    )


@dp.message(F.text == "📋 To'lovlar tarixi")
async def payment_history(message: Message):
    """To'lovlar tarixi"""
    from database import get_db
    conn = await get_db()
    payments = await conn.fetch(
        """SELECT * FROM payments 
           WHERE user_id = $1 
           ORDER BY created_at DESC LIMIT 10""",
        message.from_user.id
    )
    await conn.close()

    if not payments:
        await message.answer("📭 Sizda hali to'lovlar tarixi yo'q.")
        return

    text = "📋 <b>Sizning to'lovlaringiz:</b>

"
    for i, payment in enumerate(payments, 1):
        status_emoji = {
            'pending': '⏳',
            'verified': '✅',
            'rejected': '❌',
            'auto_verified': '✅🤖'
        }.get(payment['status'], '❓')

        text += (
            f"{i}. {status_emoji} #{payment['id']}
"
            f"   💰 {payment['amount']:,.0f} UZS
"
            f"   📅 {payment['created_at'].strftime('%d.%m.%Y %H:%M')}

"
        )

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "ℹ️ Bot haqida")
async def about_bot(message: Message):
    """Bot haqida"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏢 Biznes Integratsiya", callback_data="business_integration")],
        [InlineKeyboardButton(text="📞 Admin bilan bog'lanish", url="https://t.me/admin_username")]
    ])

    await message.answer(
        ABOUT_MESSAGE,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@dp.message(F.text == "❓ Yordam")
async def help_command(message: Message):
    """Yordam"""
    await message.answer(HELP_MESSAGE, parse_mode="HTML")


# ============================================
# SERVICE SELECTION (Sayt/Bot)
# ============================================

@dp.callback_query(F.data.startswith("service_"))
async def service_selected(callback: CallbackQuery, state: FSMContext):
    """Xizmat (sayt yoki bot) tanlanganda"""
    parts = callback.data.split("_")
    service_type = parts[1]  # website yoki bot
    service_id = int(parts[2])

    service = await get_service_by_id(service_id)

    if not service:
        await callback.answer("Xizmat topilmadi!")
        return

    await state.update_data(
        service_id=service_id,
        service_type=service_type,
        service_name=service['name']
    )

    await callback.message.edit_text(
        f"🌐 <b>{service['name']}</b>

"
        f"Buyurtma raqamini kiriting:
"
        f"(Masalan: <code>ORD-12345</code>)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_services")]
        ]),
        parse_mode="HTML"
    )

    await state.set_state(PaymentStates.waiting_order_number)
    await callback.answer()


@dp.message(PaymentStates.waiting_order_number)
async def process_order_number(message: Message, state: FSMContext):
    """Buyurtma raqami kiritilganda"""
    order_number = message.text.strip().upper()
    data = await state.get_data()

    service_id = data['service_id']
    service_type = data['service_type']
    service_name = data['service_name']

    await message.answer("⏳ Tekshirilmoqda...")

    # Tekshirish
    if service_type == 'website':
        result = await verify_site_payment(service_id, order_number)
    else:
        result = await verify_bot_payment(service_id, order_number)

    if result.get('found'):
        # To'lov topildi
        await state.update_data(
            order_number=order_number,
            amount=result.get('amount', 0),
            verification_method='api'
        )

        await message.answer(
            f"✅ <b>Buyurtma topildi!</b>

"
            f"📦 Xizmat: {service_name}
"
            f"🔢 Buyurtma: <code>#{order_number}</code>
"
            f"💰 Summa: {result['amount']:,.0f} UZS
"
            f"📊 Status: {result.get('status', 'N/A')}

"
            f"Tasdiqlash uchun to'lov screenshotini yuboring:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
            ]),
            parse_mode="HTML"
        )

        await state.set_state(PaymentStates.waiting_screenshot)
    else:
        # To'lov topilmadi
        await message.answer(
            f"❌ <b>Buyurtma #{order_number} topilmadi.</b>

"
            f"Iltimos, raqamni tekshirib qayta kiriting yoki "
            f"shaxsiy chek orqali tekshiring.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Qayta urinish", callback_data=f"service_{service_type}_{service_id}")],
                [InlineKeyboardButton(text="📄 Shaxsiy chek", callback_data="personal_receipt")]
            ]),
            parse_mode="HTML"
        )
        await state.clear()


# ============================================
# DIRECT VERIFICATION (Deep link orqali)
# ============================================

@dp.callback_query(F.data.startswith("verify_direct_"))
async def direct_verify(callback: CallbackQuery, state: FSMContext):
    """Deep link orqali to'lovni tasdiqlash"""
    parts = callback.data.split("_")
    service_id = int(parts[2])
    order_id = parts[3]

    service = await get_service_by_id(service_id)

    if not service:
        await callback.answer("Xizmat topilmadi!")
        return

    await state.update_data(
        service_id=service_id,
        service_type=service['type'],
        service_name=service['name'],
        order_number=order_id
    )

    await callback.message.edit_text(
        f"🔗 <b>{service['name']}</b>

"
        f"📦 Buyurtma: <code>#{order_id}</code>

"
        f"To'lovni tasdiqlash uchun screenshot yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
        ]),
        parse_mode="HTML"
    )

    await state.set_state(PaymentStates.waiting_screenshot)
    await callback.answer()


# ============================================
# PERSONAL RECEIPT
# ============================================

@dp.callback_query(F.data == "personal_receipt")
async def personal_receipt_start(callback: CallbackQuery, state: FSMContext):
    """Shaxsiy chek tekshiruvi boshlandi"""
    await state.update_data(service_type='personal', service_id=None)

    await callback.message.edit_text(
        "📄 <b>Shaxsiy Chek Tekshiruvi</b>

"
        "To'lov tizimini tanlang:",
        reply_markup=get_receipt_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("receipt_"))
async def receipt_type_selected(callback: CallbackQuery, state: FSMContext):
    """Chek turi tanlanganda"""
    receipt_type = callback.data.replace("receipt_", "")

    await state.update_data(receipt_type=receipt_type)

    type_name = RECEIPT_TYPES.get(receipt_type, 'Chek')

    await callback.message.edit_text(
        f"{type_name} tanlandi.

"
        f"Iltimos, to'lov screenshotini yuboring "
        f"yoki chek raqamini kiriting:

"
        f"<i>Masalan: CK1234567890</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_receipt_types")]
        ]),
        parse_mode="HTML"
    )

    await state.set_state(PaymentStates.waiting_screenshot)
    await callback.answer()


@dp.message(PaymentStates.waiting_screenshot)
async def process_screenshot(message: Message, state: FSMContext):
    """Screenshot qabul qilindi"""
    data = await state.get_data()

    # Screenshot yoki chek raqami
    receipt_screenshot = None
    receipt_number = None

    if message.photo:
        photo = message.photo[-1]  # Eng yuqori sifatli
        receipt_screenshot = photo.file_id
    elif message.text:
        receipt_number = message.text.strip()
    else:
        await message.answer("❌ Iltimos, screenshot yoki chek raqamini yuboring.")
        return

    # To'lovni saqlash
    payment_id = await create_payment(
        user_id=message.from_user.id,
        user_username=message.from_user.username,
        service_type=data.get('service_type', 'personal'),
        service_id=data.get('service_id'),
        order_number=data.get('order_number'),
        amount=data.get('amount', 0),
        receipt_type=data.get('receipt_type'),
        receipt_number=receipt_number,
        receipt_screenshot=receipt_screenshot,
        verification_method='screenshot'
    )

    # Admin ga yuborish
    await send_payment_to_admins(payment_id, message.from_user.id)

    await message.answer(
        "✅ <b>Screenshot qabul qilindi!</b>

"
        "⏳ Admin tekshiruviga yuborildi.
"
        "Natija tez orada xabar qilinadi.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


async def send_payment_to_admins(payment_id: int, user_id: int):
    """To'lovni adminlarga yuborish"""
    from database import get_payment_by_id
    payment = await get_payment_by_id(payment_id)

    if not payment:
        return

    service = await get_service_by_id(payment['service_id']) if payment['service_id'] else None
    service_name = service['name'] if service else "Shaxsiy chek"

    text = f"""
📋 <b>Yangi To'lov #{payment['id']}</b>

👤 User: @{payment['user_username'] or user_id}
🏪 Xizmat: {service_name}
🔢 Buyurtma: {payment['order_number'] or 'N/A'}
💰 Summa: {payment['amount']:,.0f} UZS
📄 Chek turi: {payment['receipt_type'] or 'N/A'}
📅 Sana: {payment['created_at'].strftime('%Y-%m-%d %H:%M')}
"""

    for admin_id in ADMIN_IDS:
        try:
            if payment['receipt_screenshot']:
                await bot.send_photo(
                    admin_id,
                    photo=payment['receipt_screenshot'],
                    caption=text,
                    reply_markup=get_payment_action_keyboard(payment['id'])
                )
            else:
                await bot.send_message(
                    admin_id,
                    text,
                    reply_markup=get_payment_action_keyboard(payment['id']),
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xatolik: {e}")


# ============================================
# BUSINESS INTEGRATION
# ============================================

@dp.callback_query(F.data == "business_integration")
async def business_integration(callback: CallbackQuery):
    """Biznes integratsiya bo'limi"""
    await callback.message.edit_text(
        BUSINESS_INTEGRATION_MESSAGE,
        reply_markup=get_business_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "connect_website")
async def connect_website_info(callback: CallbackQuery):
    """Sayt ulash bo'limi"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 API Dokumentatsiya", callback_data="api_docs")],
        [InlineKeyboardButton(text="📝 Ariza yuborish", callback_data="apply_business")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="business_integration")]
    ])

    await callback.message.edit_text(
        "🌐 <b>Sayt Ulanishi</b>

"
        "<b>Kerakli qadamlar:</b>

"
        "1️⃣ <b>Ariza yuboring</b>
"
        "   • Sayt nomi va URL
"
        "   • Biznes ma'lumotlari

"
        "2️⃣ <b>API kalit oling</b>
"
        "   • Xavfsiz kalit beriladi
"
        "   • Endpoint ma'lumotlari

"
        "3️⃣ <b>Kod qo'shing</b>
"
        "   • Python/PHP/Node.js namunalari
"
        "   • Webhook sozlash

"
        "4️⃣ <b>Test qiling</b>
"
        "   • Test to'lov yuboring
"
        "   • Tekshiruvni sinang

"
        "<b>API Endpoints:</b>
"
        "• POST /api/payments/verify
"
        "• GET /api/payments/status
"
        "• POST /webhook/payment-status",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "connect_bot")
async def connect_bot_info(callback: CallbackQuery):
    """Bot ulash bo'limi"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Kod Namunasi", callback_data="bot_code_sample")],
        [InlineKeyboardButton(text="📝 Ariza yuborish", callback_data="apply_business")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="business_integration")]
    ])

    await callback.message.edit_text(
        "🤖 <b>Telegram Bot Ulanishi</b>

"
        "<b>Kerakli qadamlar:</b>

"
        "1️⃣ <b>Ariza yuboring</b>
"
        "   • Bot username (@botname)
"
        "   • Bot token
"
        "   • Biznes ma'lumotlari

"
        "2️⃣ <b>Deep Link sozlang</b>
"
        "   <code>https://t.me/ourbot?start=service_{ID}_order_{ORDER}</code>

"
        "3️⃣ <b>Webhook qabul qiling</b>
"
        "   • /webhook/payment endpoint
"
        "   • JSON formatda status

"
        "4️⃣ <b>Test qiling</b>
"
        "   • Test buyurtma yuboring
"
        "   • Deep link orqali o'ting

"
        "<b>Deep Link Format:</b>
"
        "<code>t.me/ourbot?start=service_5_order_12345</code>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "benefits")
async def show_benefits(callback: CallbackQuery):
    """Nima olasiz?"""
    await callback.message.edit_text(
        "📊 <b>Biznes Integratsiya - Nima olasiz?</b>

"
        "✅ <b>Avtomatik to'lov tasdiqlash</b>
"
        "   Mijozlar to'lovini avtomatik tekshiring

"
        "✅ <b>Screenshot tekshiruvi</b>
"
        "   Mijozlar screenshot yuborsa, admin tekshiradi

"
        "✅ <b>Statistika va hisobotlar</b>
"
        "   Real vaqt statistikasi va to'liq hisobotlar

"
        "✅ <b>24/7 qo'llab-quvvatlash</b>
"
        "   Bot to'xtamay ishlaydi

"
        "✅ <b>Minimal komissiya</b>
"
        "   Eng arzon narxlar

"
        "✅ <b>Webhook xabarlar</b>
"
        "   To'lov statusi o'zgarganda avtomatik xabar

"
        "✅ <b>Deep Link integratsiya</b>
"
        "   Telegram botlar uchun oson ulanish",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Ariza yuborish", callback_data="apply_business")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="business_integration")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "apply_business")
async def apply_business_start(callback: CallbackQuery, state: FSMContext):
    """Biznes arizasi boshlandi"""
    await callback.message.edit_text(
        "📝 <b>Biznes Ariza</b>

"
        "Biznes nomini kiriting:
"
        "(Masalan: MyShop.uz)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Bekor qilish", callback_data="business_integration")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(PaymentStates.waiting_business_name)
    await callback.answer()


@dp.message(PaymentStates.waiting_business_name)
async def process_business_name(message: Message, state: FSMContext):
    """Biznes nomi kiritildi"""
    await state.update_data(business_name=message.text.strip())

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Sayt", callback_data="biz_type_website")],
        [InlineKeyboardButton(text="🤖 Telegram Bot", callback_data="biz_type_bot")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="apply_business")]
    ])

    await message.answer(
        "Biznes turini tanlang:",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("biz_type_"))
async def business_type_selected(callback: CallbackQuery, state: FSMContext):
    """Biznes turi tanlandi"""
    biz_type = callback.data.replace("biz_type_", "")
    await state.update_data(business_type=biz_type)

    await callback.message.edit_text(
        "📞 <b>Aloqa telefon raqamingizni kiriting:</b>
"
        "(Masalan: +998901234567)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="apply_business")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(PaymentStates.waiting_contact)
    await callback.answer()


@dp.message(PaymentStates.waiting_contact)
async def process_contact(message: Message, state: FSMContext):
    """Aloqa ma'lumotlari kiritildi"""
    data = await state.get_data()

    request_id = await create_business_request(
        requester_id=message.from_user.id,
        requester_username=message.from_user.username,
        business_name=data['business_name'],
        business_type=data['business_type'],
        contact_phone=message.text.strip()
    )

    # Adminlarga xabar
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"""
🏢 <b>Yangi Biznes Ariza #{request_id}</b>

🏪 Nomi: {data['business_name']}
📱 Tur: {'Sayt' if data['business_type'] == 'website' else 'Telegram Bot'}
👤 Ariza beruvchi: @{message.from_user.username or message.from_user.id}
📞 Telefon: {message.text.strip()}
""",
                reply_markup=get_business_request_keyboard(request_id),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xatolik: {e}")

    await message.answer(
        "✅ <b>Arizangiz qabul qilindi!</b>

"
        f"🏢 Biznes: {data['business_name']}
"
        f"📱 Tur: {'Sayt' if data['business_type'] == 'website' else 'Telegram Bot'}
"
        f"📞 Aloqa: {message.text.strip()}

"
        "⏳ Admin tekshiruvidan o'tkazilmoqda.
"
        "Natija tez orada xabar qilinadi.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# ============================================
# BACK BUTTONS
# ============================================

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Asosiy menyuga qaytish"""
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "Asosiy menyu:",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_services")
async def back_to_services(callback: CallbackQuery, state: FSMContext):
    """Xizmatlar ro'yxatiga qaytish"""
    await state.clear()
    await callback.message.edit_text(
        "📋 <b>Quyidagi xizmatlardan birini tanlang</b>
"
        "yoki shaxsiy chekni tekshiring:",
        reply_markup=get_services_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "back_about")
async def back_to_about(callback: CallbackQuery):
    """Bot haqida qismiga qaytish"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏢 Biznes Integratsiya", callback_data="business_integration")],
        [InlineKeyboardButton(text="📞 Admin bilan bog'lanish", url="https://t.me/admin_username")]
    ])

    await callback.message.edit_text(
        ABOUT_MESSAGE,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "back_receipt_types")
async def back_to_receipt_types(callback: CallbackQuery, state: FSMContext):
    """Chek turlariga qaytish"""
    await callback.message.edit_text(
        "📄 <b>Shaxsiy Chek Tekshiruvi</b>

"
        "To'lov tizimini tanlang:",
        reply_markup=get_receipt_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    """To'lovni bekor qilish"""
    await state.clear()
    await callback.message.edit_text(
        "❌ To'lov bekor qilindi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Qayta boshlash", callback_data="back_services")]
        ])
    )
    await callback.answer("Bekor qilindi!")


# ============================================
# ADMIN PANEL
# ============================================

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Admin paneli"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Sizda ruxsat yo'q!")
        return

    await message.answer(
        "🔧 <b>Admin Paneli</b>",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """Admin statistika"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return

    await show_stats(callback.message)
    await callback.answer()


@dp.callback_query(F.data == "admin_pending_payments")
async def admin_pending(callback: CallbackQuery):
    """Kutilayotgan to'lovlar"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return

    await show_pending_payments(callback.message, bot)
    await callback.answer()


@dp.callback_query(F.data == "admin_business_requests")
async def admin_business(callback: CallbackQuery):
    """Biznes arizalari"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return

    await show_business_requests(callback.message)
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve(callback: CallbackQuery):
    """Admin to'lovni tasdiqlash"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return

    payment_id = int(callback.data.split("_")[2])
    await approve_payment(callback, bot, payment_id)


@dp.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject(callback: CallbackQuery):
    """Admin to'lovni rad etish"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return

    payment_id = int(callback.data.split("_")[2])
    await reject_payment(callback, bot, payment_id)


@dp.callback_query(F.data.startswith("biz_approve_"))
async def biz_approve(callback: CallbackQuery):
    """Biznes arizasini tasdiqlash"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return

    request_id = int(callback.data.split("_")[2])
    await approve_business_request(callback, request_id)


@dp.callback_query(F.data.startswith("biz_reject_"))
async def biz_reject(callback: CallbackQuery):
    """Biznes arizasini rad etish"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return

    request_id = int(callback.data.split("_")[2])
    await reject_business_request(callback, request_id)


# ============================================
# MAIN
# ============================================

async def main():
    """Botni ishga tushirish"""
    # Database init
    await init_db()
    logger.info("Database initialized!")

    # Polling
    logger.info("Bot started!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
