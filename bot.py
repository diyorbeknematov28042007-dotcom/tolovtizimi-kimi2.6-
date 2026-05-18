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
    create_payment, get_or_create_user,
    create_business_request
)
from payments import verify_site_payment, verify_bot_payment
from admin import (
    is_admin, get_admin_keyboard, get_payment_action_keyboard,
    get_business_request_keyboard, show_stats, show_pending_payments,
    approve_payment, reject_payment, show_business_requests,
    approve_business_request, reject_business_request
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


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


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="To'lov tasdiqlash")],
            [KeyboardButton(text="To'lovlar tarixi")],
            [KeyboardButton(text="Bot haqida")],
            [KeyboardButton(text="Yordam")]
        ],
        resize_keyboard=True
    )


def get_services_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="SAYTLAR:", callback_data="header_websites")]
    )
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="Saytni tanlash", callback_data="select_website")
    ])

    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="TELEGRAM BOTlar:", callback_data="header_bots")]
    )
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="Botni tanlash", callback_data="select_bot")
    ])

    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="---------------", callback_data="separator")]
    )
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="Shaxsiy chekni tekshirish",
            callback_data="personal_receipt"
        )
    ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="Orqaga", callback_data="back_main")
    ])

    return keyboard


def get_receipt_type_keyboard():
    buttons = []
    for key, name in RECEIPT_TYPES.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data="receipt_" + key)])
    buttons.append([InlineKeyboardButton(text="Orqaga", callback_data="back_services")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_business_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Sayt ulash", callback_data="connect_website")],
        [InlineKeyboardButton(text="Bot ulash", callback_data="connect_bot")],
        [InlineKeyboardButton(text="Nima olaman?", callback_data="benefits")],
        [InlineKeyboardButton(text="Ariza yuborish", callback_data="apply_business")],
        [InlineKeyboardButton(text="Orqaga", callback_data="back_about")]
    ])


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    args = message.text.split()
    if len(args) > 1:
        param = args[1]
        if param.startswith("service_"):
            parts = param.split("_")
            if len(parts) >= 4:
                service_id = parts[1]
                order_id = parts[3]

                service = await get_service_by_id(int(service_id))
                if service:
                    text = (
                        "Siz " + service["name"] + " xizmatidan yo'naltirildingiz.\n\n"
                        "Buyurtma: #" + order_id + "\n\n"
                        "To'lovni tasdiqlash uchun quyidagi tugmani bosing:"
                    )
                    await message.answer(
                        text,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(
                                text="To'lovni tasdiqlash",
                                callback_data="verify_direct_" + service_id + "_" + order_id
                            )]
                        ])
                    )
                    return

    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@dp.message(F.text == "To'lov tasdiqlash")
async def payment_verify(message: Message):
    await message.answer(
        "Quyidagi xizmatlardan birini tanlang yoki shaxsiy chekni tekshiring:",
        reply_markup=get_services_keyboard()
    )


@dp.message(F.text == "To'lovlar tarixi")
async def payment_history(message: Message):
    from database import get_db
    conn = await get_db()
    payments = await conn.fetch(
        "SELECT * FROM payments WHERE user_id = $1 ORDER BY created_at DESC LIMIT 10",
        message.from_user.id
    )
    await conn.close()

    if not payments:
        await message.answer("Sizda hali to'lovlar tarixi yo'q.")
        return

    text = "Sizning to'lovlaringiz:\n\n"
    for i, payment in enumerate(payments, 1):
        status_emoji = {
            'pending': 'Kutilmoqda',
            'verified': 'Tasdiqlandi',
            'rejected': 'Rad etildi',
            'auto_verified': 'Avtomatik'
        }.get(payment['status'], 'Noma\'lum')

        text += (
            str(i) + ". " + status_emoji + " #" + str(payment['id']) + "\n"
            "   Summa: " + str(payment['amount']) + " UZS\n"
            "   Sana: " + payment['created_at'].strftime('%d.%m.%Y') + "\n\n"
        )

    await message.answer(text)


@dp.message(F.text == "Bot haqida")
async def about_bot(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Biznes Integratsiya", callback_data="business_integration")],
        [InlineKeyboardButton(text="Admin bilan bog'lanish", url="https://t.me/admin_username")]
    ])
    await message.answer(ABOUT_MESSAGE, reply_markup=keyboard, parse_mode="HTML")


@dp.message(F.text == "Yordam")
async def help_command(message: Message):
    await message.answer(HELP_MESSAGE, parse_mode="HTML")


@dp.callback_query(F.data.startswith("service_"))
async def service_selected(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    service_type = parts[1]
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

    text = service['name'] + "\n\nBuyurtma raqamini kiriting:\n(Masalan: ORD-12345)"
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Orqaga", callback_data="back_services")]
        ])
    )

    await state.set_state(PaymentStates.waiting_order_number)
    await callback.answer()


@dp.message(PaymentStates.waiting_order_number)
async def process_order_number(message: Message, state: FSMContext):
    order_number = message.text.strip().upper()
    data = await state.get_data()

    service_id = data['service_id']
    service_type = data['service_type']
    service_name = data['service_name']

    await message.answer("Tekshirilmoqda...")

    if service_type == 'website':
        result = await verify_site_payment(service_id, order_number)
    else:
        result = await verify_bot_payment(service_id, order_number)

    if result.get('found'):
        await state.update_data(
            order_number=order_number,
            amount=result.get('amount', 0),
            verification_method='api'
        )

        text = (
            "Buyurtma topildi!\n\n"
            "Xizmat: " + service_name + "\n"
            "Buyurtma: #" + order_number + "\n"
            "Summa: " + str(result['amount']) + " UZS\n"
            "Status: " + str(result.get('status', 'N/A')) + "\n\n"
            "Tasdiqlash uchun to'lov screenshotini yuboring:"
        )
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Bekor qilish", callback_data="cancel_payment")]
            ])
        )
        await state.set_state(PaymentStates.waiting_screenshot)
    else:
        text = (
            "Buyurtma #" + order_number + " topilmadi.\n\n"
            "Iltimos, raqamni tekshirib qayta kiriting yoki "
            "shaxsiy chek orqali tekshiring."
        )
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Qayta urinish", callback_data="service_" + service_type + "_" + str(service_id))],
                [InlineKeyboardButton(text="Shaxsiy chek", callback_data="personal_receipt")]
            ])
        )
        await state.clear()


@dp.callback_query(F.data.startswith("verify_direct_"))
async def direct_verify(callback: CallbackQuery, state: FSMContext):
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

    text = (
        service['name'] + "\n\n"
        "Buyurtma: #" + order_id + "\n\n"
        "To'lovni tasdiqlash uchun screenshot yuboring:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Bekor qilish", callback_data="cancel_payment")]
        ])
    )

    await state.set_state(PaymentStates.waiting_screenshot)
    await callback.answer()


@dp.callback_query(F.data == "personal_receipt")
async def personal_receipt_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(service_type='personal', service_id=None)
    await callback.message.edit_text(
        "Shaxsiy Chek Tekshiruvi\n\nTo'lov tizimini tanlang:",
        reply_markup=get_receipt_type_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("receipt_"))
async def receipt_type_selected(callback: CallbackQuery, state: FSMContext):
    receipt_type = callback.data.replace("receipt_", "")
    await state.update_data(receipt_type=receipt_type)

    type_name = RECEIPT_TYPES.get(receipt_type, 'Chek')
    text = type_name + " tanlandi.\n\nIltimos, to'lov screenshotini yuboring yoki chek raqamini kiriting:"

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Orqaga", callback_data="back_receipt_types")]
        ])
    )
    await state.set_state(PaymentStates.waiting_screenshot)
    await callback.answer()


@dp.message(PaymentStates.waiting_screenshot)
async def process_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()

    receipt_screenshot = None
    receipt_number = None

    if message.photo:
        photo = message.photo[-1]
        receipt_screenshot = photo.file_id
    elif message.text:
        receipt_number = message.text.strip()
    else:
        await message.answer("Iltimos, screenshot yoki chek raqamini yuboring.")
        return

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

    await send_payment_to_admins(payment_id, message.from_user.id)

    await message.answer(
        "Screenshot qabul qilindi!\n\nAdmin tekshiruviga yuborildi.\nNatija tez orada xabar qilinadi.",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


async def send_payment_to_admins(payment_id: int, user_id: int):
    from database import get_payment_by_id
    payment = await get_payment_by_id(payment_id)
    if not payment:
        return

    from database import get_service_by_id
    service = await get_service_by_id(payment['service_id']) if payment['service_id'] else None
    service_name = service['name'] if service else "Shaxsiy chek"

    text = (
        "Yangi To'lov #" + str(payment['id']) + "\n\n"
        "User: @" + str(payment['user_username'] or user_id) + "\n"
        "Xizmat: " + service_name + "\n"
        "Buyurtma: " + str(payment['order_number'] or 'N/A') + "\n"
        "Summa: " + str(payment['amount']) + " UZS\n"
        "Chek turi: " + str(payment['receipt_type'] or 'N/A') + "\n"
        "Sana: " + payment['created_at'].strftime('%Y-%m-%d %H:%M')
    )

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
                    reply_markup=get_payment_action_keyboard(payment['id'])
                )
        except Exception as e:
            logger.error("Admin xabar yuborishda xatolik: " + str(e))


@dp.callback_query(F.data == "business_integration")
async def business_integration(callback: CallbackQuery):
    await callback.message.edit_text(
        BUSINESS_INTEGRATION_MESSAGE,
        reply_markup=get_business_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "connect_website")
async def connect_website_info(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="API Dokumentatsiya", callback_data="api_docs")],
        [InlineKeyboardButton(text="Ariza yuborish", callback_data="apply_business")],
        [InlineKeyboardButton(text="Orqaga", callback_data="business_integration")]
    ])
    text = (
        "Sayt Ulanishi\n\n"
        "Kerakli qadamlar:\n\n"
        "1. Ariza yuboring\n"
        "   - Sayt nomi va URL\n"
        "   - Biznes ma'lumotlari\n\n"
        "2. API kalit oling\n"
        "   - Xavfsiz kalit beriladi\n"
        "   - Endpoint ma'lumotlari\n\n"
        "3. Kod qo'shing\n"
        "   - Python/PHP/Node.js namunalari\n"
        "   - Webhook sozlash\n\n"
        "4. Test qiling\n"
        "   - Test to'lov yuboring\n"
        "   - Tekshiruvni sinang\n\n"
        "API Endpoints:\n"
        "- POST /api/payments/verify\n"
        "- GET /api/payments/status\n"
        "- POST /webhook/payment-status"
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "connect_bot")
async def connect_bot_info(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Kod Namunasi", callback_data="bot_code_sample")],
        [InlineKeyboardButton(text="Ariza yuborish", callback_data="apply_business")],
        [InlineKeyboardButton(text="Orqaga", callback_data="business_integration")]
    ])
    text = (
        "Telegram Bot Ulanishi\n\n"
        "Kerakli qadamlar:\n\n"
        "1. Ariza yuboring\n"
        "   - Bot username (@botname)\n"
        "   - Bot token\n"
        "   - Biznes ma'lumotlari\n\n"
        "2. Deep Link sozlang\n"
        "   https://t.me/ourbot?start=service_{ID}_order_{ORDER}\n\n"
        "3. Webhook qabul qiling\n"
        "   - /webhook/payment endpoint\n"
        "   - JSON formatda status\n\n"
        "4. Test qiling\n"
        "   - Test buyurtma yuboring\n"
        "   - Deep link orqali o'ting\n\n"
        "Deep Link Format:\n"
        "t.me/ourbot?start=service_5_order_12345"
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "benefits")
async def show_benefits(callback: CallbackQuery):
    text = (
        "Biznes Integratsiya - Nima olasiz?\n\n"
        "Avtomatik to'lov tasdiqlash\n"
        "   Mijozlar to'lovini avtomatik tekshiring\n\n"
        "Screenshot tekshiruvi\n"
        "   Mijozlar screenshot yuborsa, admin tekshiradi\n\n"
        "Statistika va hisobotlar\n"
        "   Real vaqt statistikasi va to'liq hisobotlar\n\n"
        "24/7 qo'llab-quvvatlash\n"
        "   Bot to'xtamay ishlaydi\n\n"
        "Minimal komissiya\n"
        "   Eng arzon narxlar\n\n"
        "Webhook xabarlar\n"
        "   To'lov statusi o'zgarganda avtomatik xabar\n\n"
        "Deep Link integratsiya\n"
        "   Telegram botlar uchun oson ulanish"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Ariza yuborish", callback_data="apply_business")],
            [InlineKeyboardButton(text="Orqaga", callback_data="business_integration")]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "apply_business")
async def apply_business_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Biznes Ariza\n\nBiznes nomini kiriting:\n(Masalan: MyShop.uz)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Bekor qilish", callback_data="business_integration")]
        ])
    )
    await state.set_state(PaymentStates.waiting_business_name)
    await callback.answer()


@dp.message(PaymentStates.waiting_business_name)
async def process_business_name(message: Message, state: FSMContext):
    await state.update_data(business_name=message.text.strip())
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Sayt", callback_data="biz_type_website")],
        [InlineKeyboardButton(text="Telegram Bot", callback_data="biz_type_bot")],
        [InlineKeyboardButton(text="Orqaga", callback_data="apply_business")]
    ])
    await message.answer("Biznes turini tanlang:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("biz_type_"))
async def business_type_selected(callback: CallbackQuery, state: FSMContext):
    biz_type = callback.data.replace("biz_type_", "")
    await state.update_data(business_type=biz_type)
    await callback.message.edit_text(
        "Aloqa telefon raqamingizni kiriting:\n(Masalan: +998901234567)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Orqaga", callback_data="apply_business")]
        ])
    )
    await state.set_state(PaymentStates.waiting_contact)
    await callback.answer()


@dp.message(PaymentStates.waiting_contact)
async def process_contact(message: Message, state: FSMContext):
    data = await state.get_data()

    request_id = await create_business_request(
        requester_id=message.from_user.id,
        requester_username=message.from_user.username,
        business_name=data['business_name'],
        business_type=data['business_type'],
        contact_phone=message.text.strip()
    )

    for admin_id in ADMIN_IDS:
        try:
            text = (
                "Yangi Biznes Ariza #" + str(request_id) + "\n\n"
                "Nomi: " + data['business_name'] + "\n"
                "Tur: " + ('Sayt' if data['business_type'] == 'website' else 'Telegram Bot') + "\n"
                "Ariza beruvchi: @" + str(message.from_user.username or message.from_user.id) + "\n"
                "Telefon: " + message.text.strip()
            )
            await bot.send_message(
                admin_id,
                text,
                reply_markup=get_business_request_keyboard(request_id)
            )
        except Exception as e:
            logger.error("Admin xabar yuborishda xatolik: " + str(e))

    await message.answer(
        "Arizangiz qabul qilindi!\n\n"
        "Biznes: " + data['business_name'] + "\n"
        "Tur: " + ('Sayt' if data['business_type'] == 'website' else 'Telegram Bot') + "\n"
        "Aloqa: " + message.text.strip() + "\n\n"
        "Admin tekshiruvidan o'tkazilmoqda.\n"
        "Natija tez orada xabar qilinadi.",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Asosiy menyu:", reply_markup=get_main_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "back_services")
async def back_to_services(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Quyidagi xizmatlardan birini tanlang yoki shaxsiy chekni tekshiring:",
        reply_markup=get_services_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_about")
async def back_to_about(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Biznes Integratsiya", callback_data="business_integration")],
        [InlineKeyboardButton(text="Admin bilan bog'lanish", url="https://t.me/admin_username")]
    ])
    await callback.message.edit_text(ABOUT_MESSAGE, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "back_receipt_types")
async def back_to_receipt_types(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Shaxsiy Chek Tekshiruvi\n\nTo'lov tizimini tanlang:",
        reply_markup=get_receipt_type_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "To'lov bekor qilindi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Qayta boshlash", callback_data="back_services")]
        ])
    )
    await callback.answer("Bekor qilindi!")


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Sizda ruxsat yo'q!")
        return
    await message.answer("Admin Paneli", reply_markup=get_admin_keyboard())


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    await show_stats(callback.message)
    await callback.answer()


@dp.callback_query(F.data == "admin_pending_payments")
async def admin_pending(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    await show_pending_payments(callback.message, bot)
    await callback.answer()


@dp.callback_query(F.data == "admin_business_requests")
async def admin_business(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    await show_business_requests(callback.message)
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    payment_id = int(callback.data.split("_")[2])
    await approve_payment(callback, bot, payment_id)


@dp.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    payment_id = int(callback.data.split("_")[2])
    await reject_payment(callback, bot, payment_id)


@dp.callback_query(F.data.startswith("biz_approve_"))
async def biz_approve(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    request_id = int(callback.data.split("_")[2])
    await approve_business_request(callback, request_id)


@dp.callback_query(F.data.startswith("biz_reject_"))
async def biz_reject(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    request_id = int(callback.data.split("_")[2])
    await reject_business_request(callback, request_id)


# ==================== WEBHOOK + HEALTH CHECK ====================
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import os

PORT = int(os.getenv("PORT", "10000"))
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret")
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"

async def health_handler(request):
    """Render health check"""
    return web.json_response({"status": "ok", "bot": "running", "webhook": WEBHOOK_PATH})

async def on_startup(app):
    """Bot ishga tushganda webhook sozlash"""
    await init_db()
    logger.info("Database initialized!")

    webhook_url = ""
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}{WEBHOOK_PATH}"
    else:
        # Render ba'zan RENDER_EXTERNAL_URL bermaydi, manual URL
        service_name = os.getenv("RENDER_SERVICE_NAME", "")
        if service_name:
            webhook_url = f"https://{service_name}.onrender.com{WEBHOOK_PATH}"

    if webhook_url:
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        logger.info(f"Webhook set: {webhook_url}")
    else:
        logger.error("NO WEBHOOK URL! Set RENDER_EXTERNAL_URL env var!")

def main():
    app = web.Application()

    # Health check
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    # Webhook handler
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)

    # Startup
    app.on_startup.append(on_startup)

    logger.info(f"Starting webhook server on port {PORT}")
    logger.info(f"Webhook path: {WEBHOOK_PATH}")
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
