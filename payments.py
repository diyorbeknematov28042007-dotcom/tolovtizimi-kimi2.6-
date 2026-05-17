"""
payments.py - To'lov tekshiruvi va verifikatsiya
Universal To'lov Boti v2.0
"""

import aiohttp
import hashlib
import hmac
from typing import Dict, Any, Optional
from database import get_service_by_id


async def verify_site_payment(service_id: int, order_number: str) -> Dict[str, Any]:
    """
    Sayt orqali buyurtma tekshiruvi
    Xizmatning API endpointiga so'rov yuboradi
    """
    service = await get_service_by_id(service_id)

    if not service:
        return {"found": False, "error": "Xizmat topilmadi"}

    if not service['api_endpoint']:
        return {"found": False, "error": "API endpoint sozlanmagan"}

    try:
        # API so'rovini tayyorlash
        timestamp = str(int(__import__('time').time()))
        signature = generate_api_signature(
            service['api_secret'],
            order_number=order_number,
            timestamp=timestamp
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{service['api_endpoint']}/orders/{order_number}",
                headers={
                    "X-API-Key": service['api_key'],
                    "X-Signature": signature,
                    "X-Timestamp": timestamp
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:

                if response.status == 200:
                    data = await response.json()
                    return {
                        "found": True,
                        "order_number": order_number,
                        "amount": data.get('amount', 0),
                        "status": data.get('status', 'unknown'),
                        "customer_name": data.get('customer_name'),
                        "customer_phone": data.get('customer_phone')
                    }
                elif response.status == 404:
                    return {"found": False, "error": "Buyurtma topilmadi"}
                else:
                    return {"found": False, "error": f"API xatoligi: {response.status}"}

    except aiohttp.ClientError as e:
        return {"found": False, "error": f"Ulanish xatoligi: {str(e)}"}
    except Exception as e:
        return {"found": False, "error": f"Xatolik: {str(e)}"}


async def verify_bot_payment(service_id: int, order_number: str) -> Dict[str, Any]:
    """
    Telegram bot orqali buyurtma tekshiruvi
    Xizmat botining API orqali tekshiruvi
    """
    service = await get_service_by_id(service_id)

    if not service:
        return {"found": False, "error": "Xizmat topilmadi"}

    # Bot to'lovlari webhook orqali tekshiriladi
    # Bu yerda bizning serverga webhook orqali ma'lumot keladi
    # Vaqtinchalik: bot tomonidan yuborilgan ma'lumotni tekshirish

    # Agar bot webhook orqali ma'lumot yuborgan bo'lsa,
    # payments jadvalida qidiramiz
    from database import get_db
    conn = await get_db()

    # Bot tomonidan avval yuborilgan to'lovni qidirish
    row = await conn.fetchrow(
        """SELECT * FROM payments 
           WHERE service_id = $1 AND order_number = $2 
           AND service_type = 'telegram_bot'
           AND status IN ('pending', 'verified')
           ORDER BY created_at DESC LIMIT 1""",
        service_id, order_number
    )
    await conn.close()

    if row:
        return {
            "found": True,
            "order_number": order_number,
            "amount": row['amount'],
            "status": row['status'],
            "payment_id": row['id']
        }

    return {"found": False, "error": "Bot buyurtmasi topilmadi. Iltimos, avval tashqi botdan to'lovni boshlang."}


async def process_personal_receipt(file_id: str, receipt_type: str, receipt_number: str = None) -> Dict[str, Any]:
    """
    Shaxsiy chekni qayta ishlash
    Screenshotni AI yoki admin tekshiruviga yuborish
    """
    # Hozircha admin tekshiruviga yuboriladi
    # Kelajakda: OCR/AI orqali avtomatik tekshirish

    return {
        "processed": True,
        "receipt_type": receipt_type,
        "receipt_number": receipt_number,
        "file_id": file_id,
        "verification_required": True,
        "message": "Chek admin tekshiruviga yuborildi"
    }


def generate_api_signature(secret: str, **params) -> str:
    """API so'rovi uchun signature yaratish"""
    sorted_params = sorted(params.items())
    param_string = "&".join([f"{k}={v}" for k, v in sorted_params])
    return hmac.new(
        secret.encode(),
        param_string.encode(),
        hashlib.sha256
    ).hexdigest()


async def send_webhook_notification(service_id: int, payment_id: int, status: str):
    """
    Xizmatga webhook orqali xabar yuborish
    """
    service = await get_service_by_id(service_id)

    if not service or not service['webhook_url']:
        return False

    from database import get_payment_by_id
    payment = await get_payment_by_id(payment_id)

    if not payment:
        return False

    payload = {
        "event": f"payment.{status}",
        "payment_id": payment_id,
        "order_number": payment['order_number'],
        "amount": float(payment['amount']),
        "currency": payment['currency'],
        "status": status,
        "user_id": payment['user_id'],
        "verified_at": str(payment['verified_at']) if payment['verified_at'] else None
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                service['webhook_url'],
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return response.status == 200
    except Exception:
        return False
