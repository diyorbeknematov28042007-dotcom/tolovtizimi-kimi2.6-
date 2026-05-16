"""
To'lov tizimi - sayt bilan integratsiya
"""
import aiohttp
from config import SITE_API_URL, SITE_API_KEY

class PaymentService:
    def __init__(self):
        self.api_url = SITE_API_URL
        self.api_key = SITE_API_KEY

    async def check_order(self, order_number):
        """Saytdan buyurtma ma'lumotlarini tekshirish"""
        # Bu yerda sayt API ga so'rov yuboriladi
        # Haqiqiy loyihada sayt API ga moslashtiriladi

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }

                # Misol uchun API endpoint
                url = f"{self.api_url}/orders/{order_number}"

                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'found': True,
                            'order_number': data.get('order_number'),
                            'amount': data.get('amount'),
                            'status': data.get('status'),
                            'customer_name': data.get('customer_name'),
                            'customer_phone': data.get('customer_phone')
                        }
                    else:
                        return {'found': False}
        except Exception as e:
            print(f"API xatosi: {e}")
            # Test rejimida - simulyatsiya
            return self._simulate_order_check(order_number)

    def _simulate_order_check(self, order_number):
        """Test rejimi - simulyatsiya"""
        # Bu test uchun - haqiqiy loyihada o'chiriladi
        import random

        # Test ma'lumotlar
        test_orders = {
            '12345': {'amount': 50000, 'status': 'pending'},
            '67890': {'amount': 150000, 'status': 'pending'},
            '11111': {'amount': 250000, 'status': 'pending'},
        }

        if order_number in test_orders:
            order = test_orders[order_number]
            return {
                'found': True,
                'order_number': order_number,
                'amount': order['amount'],
                'status': order['status'],
                'customer_name': 'Test Foydalanuvchi',
                'customer_phone': '+998901234567'
            }

        # Tasodifiy buyurtma yaratish (test uchun)
        if order_number.isdigit() and len(order_number) >= 4:
            return {
                'found': True,
                'order_number': order_number,
                'amount': random.randint(10000, 500000),
                'status': 'pending',
                'customer_name': 'Foydalanuvchi',
                'customer_phone': '+998901234567'
            }

        return {'found': False}

    async def confirm_payment(self, order_number):
        """Saytda to'lovni tasdiqlash"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }

                url = f"{self.api_url}/orders/{order_number}/confirm"

                async with session.post(url, headers=headers, timeout=10) as response:
                    return response.status == 200
        except Exception as e:
            print(f"Tasdiqlash xatosi: {e}")
            return True  # Test rejimida

# Global instance
payment_service = PaymentService()
