"""
admin.py - Admin panel funksiyalari
Universal To'lov Boti v2.0
"""

from aiogram import types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_pending_payments, update_payment_status, get_stats,
    get_pending_business_requests, update_business_request_status,
    get_service_by_id, add_service
)
from payments import send_webhook_notification
from config import ADMIN_IDS


async def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="Kutilayotgan to'lovlar", callback_data="admin_pending_payments")],
        [InlineKeyboardButton(text="Biznes arizalari", callback_data="admin_business_requests")],
        [InlineKeyboardButton(text="Xizmatlarni boshqarish", callback_data="admin_services")],
        [InlineKeyboardButton(text="Ommaviy xabar", callback_data="admin_broadcast")]
    ])


def get_payment_action_keyboard(payment_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Tasdiqlash", callback_data="admin_approve_" + str(payment_id)),
            InlineKeyboardButton(text="Rad etish", callback_data="admin_reject_" + str(payment_id))
        ],
        [InlineKeyboardButton(text="Izoh qo'shish", callback_data="admin_note_" + str(payment_id))]
    ])


def get_business_request_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Tasdiqlash", callback_data="biz_approve_" + str(request_id)),
            InlineKeyboardButton(text="Rad etish", callback_data="biz_reject_" + str(request_id))
        ]
    ])


async def show_stats(message: types.Message):
    stats = await get_stats()

    text = (
        "Statistika\n\n"
        "To'lovlar:\n"
        "Jami: " + str(stats['total_payments']) + "\n"
        "Tasdiqlangan: " + str(stats['verified_payments']) + "\n"
        "Kutilmoqda: " + str(stats['pending_payments']) + "\n"
        "Umumiy summa: " + str(stats['total_amount']) + " UZS\n\n"
        "Foydalanuvchilar: " + str(stats['total_users']) + "\n"
        "Faol xizmatlar: " + str(stats['total_services'])
    )

    await message.answer(text)


async def show_pending_payments(message: types.Message, bot):
    payments = await get_pending_payments(limit=10)

    if not payments:
        await message.answer("Kutilayotgan to'lovlar yo'q!")
        return

    await message.answer("Kutilayotgan to'lovlar (" + str(len(payments)) + " ta)")

    for payment in payments[:5]:
        service = await get_service_by_id(payment['service_id']) if payment['service_id'] else None
        service_name = service['name'] if service else "Shaxsiy chek"

        text = (
            "To'lov #" + str(payment['id']) + "\n\n"
            "User: @" + str(payment['user_username'] or payment['user_id']) + "\n"
            "Xizmat: " + service_name + "\n"
            "Buyurtma: " + str(payment['order_number'] or 'N/A') + "\n"
            "Summa: " + str(payment['amount']) + " UZS\n"
            "Chek turi: " + str(payment['receipt_type'] or 'N/A') + "\n"
            "Sana: " + payment['created_at'].strftime('%Y-%m-%d %H:%M')
        )

        if payment['receipt_screenshot']:
            await bot.send_photo(
                message.chat.id,
                photo=payment['receipt_screenshot'],
                caption=text,
                reply_markup=get_payment_action_keyboard(payment['id'])
            )
        else:
            await message.answer(
                text,
                reply_markup=get_payment_action_keyboard(payment['id'])
            )


async def approve_payment(callback: types.CallbackQuery, bot, payment_id: int):
    payment = await update_payment_status(
        payment_id=payment_id,
        status='verified',
        admin_id=callback.from_user.id
    )

    from database import get_payment_by_id
    payment_data = await get_payment_by_id(payment_id)

    if payment_data:
        await bot.send_message(
            payment_data['user_id'],
            (
                "To'lovingiz tasdiqlandi!\n\n"
                "Summa: " + str(payment_data['amount']) + " UZS\n"
                "Sana: " + payment_data['verified_at'].strftime('%Y-%m-%d %H:%M') + "\n\n"
                "Rahmat!"
            )
        )

        if payment_data['service_id']:
            await send_webhook_notification(
                payment_data['service_id'],
                payment_id,
                'verified'
            )

    await callback.message.edit_text(
        (callback.message.caption or callback.message.text) + "\n\nTASDIQLANDI"
    )
    await callback.answer("To'lov tasdiqlandi!")


async def reject_payment(callback: types.CallbackQuery, bot, payment_id: int):
    from database import get_payment_by_id
    payment_data = await get_payment_by_id(payment_id)

    await update_payment_status(
        payment_id=payment_id,
        status='rejected',
        admin_id=callback.from_user.id
    )

    if payment_data:
        await bot.send_message(
            payment_data['user_id'],
            (
                "To'lovingiz rad etildi.\n\n"
                "Summa: " + str(payment_data['amount']) + " UZS\n\n"
                "Qo'shimcha ma'lumot uchun admin bilan bog'laning."
            )
        )

    await callback.message.edit_text(
        (callback.message.caption or callback.message.text) + "\n\nRAD ETILDI"
    )
    await callback.answer("To'lov rad etildi!")


async def show_business_requests(message: types.Message):
    requests = await get_pending_business_requests()

    if not requests:
        await message.answer("Kutilayotgan biznes arizalari yo'q!")
        return

    await message.answer("Kutilayotgan arizalar (" + str(len(requests)) + " ta)")

    for req in requests:
        text = (
            "Biznes Ariza #" + str(req['id']) + "\n\n"
            "Nomi: " + req['business_name'] + "\n"
            "Tur: " + ('Sayt' if req['business_type'] == 'website' else 'Telegram Bot') + "\n"
            "Ariza beruvchi: @" + str(req['requester_username'] or req['requester_id']) + "\n"
            "Telefon: " + str(req['contact_phone'] or 'N/A') + "\n"
            "Email: " + str(req['contact_email'] or 'N/A') + "\n"
            "Tavsif: " + str(req['description'] or 'N/A') + "\n"
            "Sana: " + req['created_at'].strftime('%Y-%m-%d %H:%M')
        )

        await message.answer(
            text,
            reply_markup=get_business_request_keyboard(req['id'])
        )


async def approve_business_request(callback: types.CallbackQuery, request_id: int):
    from database import get_db
    conn = await get_db()

    req = await conn.fetchrow(
        "SELECT * FROM business_requests WHERE id = $1", request_id
    )

    if not req:
        await callback.answer("Ariza topilmadi!")
        await conn.close()
        return

    service_id = await add_service(
        name=req['business_name'],
        service_type=req['business_type'],
        owner_id=req['requester_id'],
        owner_username=req['requester_username']
    )

    import secrets
    api_key = secrets.token_urlsafe(32)
    api_secret = secrets.token_urlsafe(32)

    await conn.execute("""
        UPDATE services 
        SET api_key = $1, api_secret = $2 
        WHERE id = $3
    """, api_key, api_secret, service_id)

    await update_business_request_status(request_id, 'approved')
    await conn.close()

    from bot import bot
    await bot.send_message(
        req['requester_id'],
        (
            "Arizangiz tasdiqlandi!\n\n"
            "Xizmat: " + req['business_name'] + "\n"
            "API Kalit: " + api_key + "\n\n"
            "Endi saytingiz/botingizni bizga ulashingiz mumkin."
        )
    )

    await callback.message.edit_text(
        callback.message.text + "\n\nTASDIQLANDI"
    )
    await callback.answer("Ariza tasdiqlandi!")


async def reject_business_request(callback: types.CallbackQuery, request_id: int):
    await update_business_request_status(request_id, 'rejected')

    from database import get_db
    conn = await get_db()
    req = await conn.fetchrow(
        "SELECT requester_id FROM business_requests WHERE id = $1", request_id
    )
    await conn.close()

    if req:
        from bot import bot
        await bot.send_message(
            req['requester_id'],
            "Arizangiz rad etildi. Qo'shimcha ma'lumot uchun admin bilan bog'laning."
        )

    await callback.message.edit_text(
        callback.message.text + "\n\nRAD ETILDI"
    )
    await callback.answer("Ariza rad etildi!")
