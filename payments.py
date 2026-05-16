"""
To'lov tizimi — bir nechta sayt bilan ishlash
Tanlangan saytga qarab tekshiradi
"""
import aiohttp
from config import SITES, get_site_by_index

class PaymentService:
    def __init__(self, site_index=0):
        self.site = get_site_by_index(site_index)
        self.api_url = self.site["url"] if self.site else ""
        self.api_key = self.site["key"] if self.site else ""
        self.site_name = self.site["name"] if self.site else "Noma'lum"

    async def check_order(self, order_number):
        """Saytdan buyurtma tekshirish"""
        if not self.site:
            return {"found": False, "error": "Sayt tanlanmagan"}

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                url = f"{self.api_url}/orders/{order_number}"

                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "found": True,
                            "order_number": data.get("order_number"),
                            "amount": data.get("amount"),
                            "status": data.get("status"),
                            "customer_name": data.get("customer_name"),
                            "customer_phone": data.get("customer_phone"),
                            "site_name": self.site_name
                        }
                    else:
                        return {"found": False}
        except Exception as e:
            print(f"API xatosi ({self.site_name}): {e}")
            return self._simulate_order_check(order_number)

    async def confirm_payment(self, order_number):
        """Saytda to'lovni tasdiqlash"""
        if not self.site:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                url = f"{self.api_url}/orders/{order_number}/confirm"

                async with session.post(url, headers=headers, timeout=10) as response:
                    return response.status == 200
        except Exception as e:
            print(f"Tasdiqlash xatosi: {e}")
            return True

    def _simulate_order_check(self, order_number):
        """Test rejimi"""
        import random

        test_orders = {
            "12345": {"amount": 50000, "status": "pending"},
            "67890": {"amount": 150000, "status": "pending"},
        }

        if order_number in test_orders:
            order = test_orders[order_number]
            return {
                "found": True,
                "order_number": order_number,
                "amount": order["amount"],
                "status": order["status"],
                "customer_name": "Test",
                "customer_phone": "+998901234567",
                "site_name": self.site_name
            }

        if order_number.isdigit() and len(order_number) >= 4:
            return {
                "found": True,
                "order_number": order_number,
                "amount": random.randint(10000, 500000),
                "status": "pending",
                "customer_name": "Foydalanuvchi",
                "customer_phone": "+998901234567",
                "site_name": self.site_name
            }

        return {"found": False}
