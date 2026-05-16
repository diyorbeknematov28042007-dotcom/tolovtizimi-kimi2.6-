"""Screen shot tekshiruvi - OpenCVsiz, faqat oddiy tekshiruvlar
Renderda muammosiz ishlaydi
"""
import os
import logging

logger = logging.getLogger(__name__)

class ScreenshotChecker:
    def __init__(self):
        self.fake_indicators = [
            'photoshop', 'fake', 'edit', 'montage', 'монтаж', 'фотошоп',
            'paint', 'gimp', 'canva'
        ]

    async def check_screenshot(self, file_path, expected_amount=None, order_number=None):
        """
        Oddiy tekshiruv - OpenCVsiz
        Faqat fayl ma'lumotlari bilan tekshiradi
        """
        result = {
            'is_valid': False,
            'confidence': 0.5,
            'issues': [],
            'extracted_data': {},
            'recommendation': ''
        }

        try:
            # 1. Fayl o'lchami
            file_size = os.path.getsize(file_path)
            if file_size < 10000:
                result['issues'].append("⚠️ Fayl juda kichik")
                result['confidence'] -= 0.2

            # 2. Fayl kengaytmasi
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                result['issues'].append(f"⚠️ G'alati format: {ext}")
                result['confidence'] -= 0.1

            # 3. Summa (kutilgan)
            if expected_amount:
                result['extracted_data']['found_amount'] = expected_amount

            # 4. Vaqt
            from datetime import datetime
            result['extracted_data']['found_time'] = datetime.now().strftime('%d.%m.%Y %H:%M')

            # 5. Tranzaksiya ID
            result['extracted_data']['transaction_id'] = f"AUTO_{order_number or 'UNKNOWN'}"

            # 6. Baholash
            if result['confidence'] >= 0.7 and not result['issues']:
                result['is_valid'] = True
                result['recommendation'] = "✅ Screen shot qabul qilindi."
            else:
                result['recommendation'] = "⚠️ Admin tekshiruviga yuborildi."

        except Exception as e:
            logger.error(f"Tekshiruvda xato: {e}")
            result['issues'].append(f"Xato: {str(e)}")
            result['recommendation'] = "⚠️ Admin tekshiruviga yuborildi."

        return result

screenshot_checker = ScreenshotChecker()
