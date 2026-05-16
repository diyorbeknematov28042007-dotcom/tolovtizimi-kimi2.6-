"""
Screen shot avtomatik tekshiruv tizimi
- OCR (matnni o'qish)
- Fake screen shot aniqlash
- Summa tekshiruvi
- Vaqt tekshiruvi
"""
import cv2
import numpy as np
from PIL import Image
import io
import re
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ScreenshotChecker:
    def __init__(self):
        # Fake screen shot belgilari
        self.fake_indicators = [
            'photoshop', 'fake', 'edit', 'montage', 'монтаж', 'фотошоп'
        ]

    async def check_screenshot(self, file_path, expected_amount=None, order_number=None):
        """
        Screen shotni to'liq tekshirish

        Returns:
            dict: {
                'is_valid': bool,
                'confidence': float (0-1),
                'issues': list,
                'extracted_data': dict,
                'recommendation': str
            }
        """
        result = {
            'is_valid': False,
            'confidence': 0.0,
            'issues': [],
            'extracted_data': {},
            'recommendation': ''
        }

        try:
            # 1. Rasmni yuklash
            image = cv2.imread(file_path)
            if image is None:
                result['issues'].append("❌ Rasm o'qib bo'lmadi")
                return result

            # 2. Rasm sifatini tekshirish
            quality_check = self._check_image_quality(image)
            if not quality_check['passed']:
                result['issues'].extend(quality_check['issues'])

            # 3. Matnni OCR orqali o'qish
            extracted_text = self._extract_text(image)
            result['extracted_data']['text'] = extracted_text

            # 4. Fake screen shot tekshiruvi
            fake_check = self._detect_fake(image, extracted_text)
            if fake_check['is_fake']:
                result['issues'].extend(fake_check['reasons'])
                result['confidence'] = 0.1
                result['recommendation'] = "🚫 Fake screen shot aniqlandi! Admin tekshiruvi talab qilinadi."
                return result

            # 5. Summa tekshiruvi
            if expected_amount:
                amount_check = self._check_amount(extracted_text, expected_amount)
                result['extracted_data']['found_amount'] = amount_check.get('found_amount')
                if not amount_check['match']:
                    result['issues'].append(
                        f"⚠️ Summa mos kelmadi: Kutilgan {expected_amount:,.0f}, "
                        f"Topilgan {amount_check.get('found_amount', 'N/A')}"
                    )

            # 6. Vaqt tekshiruvi
            time_check = self._check_timestamp(extracted_text)
            result['extracted_data']['found_time'] = time_check.get('found_time')
            if not time_check['valid']:
                result['issues'].append(f"⚠️ Vaqt shubhali: {time_check.get('reason', '')}")

            # 7. Tranzaksiya ID / QR kod tekshiruvi
            transaction_check = self._check_transaction_id(extracted_text)
            result['extracted_data']['transaction_id'] = transaction_check.get('transaction_id')
            if not transaction_check['found']:
                result['issues'].append("⚠️ Tranzaksiya ID topilmadi")

            # 8. Umumiy baholash
            confidence = self._calculate_confidence(
                quality_check, fake_check, amount_check, time_check, transaction_check
            )
            result['confidence'] = confidence

            if confidence >= 0.85 and len(result['issues']) == 0:
                result['is_valid'] = True
                result['recommendation'] = "✅ Screen shot haqiqiy ko'rinadi. Avtomatik tasdiqlash mumkin."
            elif confidence >= 0.6:
                result['recommendation'] = "⚠️ Shubhali joylar bor. Admin tekshiruvi tavsiya etiladi."
            else:
                result['recommendation'] = "🚫 Ko'p shubhalar. Admin tekshiruvi talab qilinadi."

        except Exception as e:
            logger.error(f"Screen shot tekshiruvida xato: {e}")
            result['issues'].append(f"Tekshiruvda xato: {str(e)}")
            result['recommendation'] = "⚠️ Tekshirishda xato. Admin tekshiruvi talab qilinadi."

        return result

    def _check_image_quality(self, image):
        """Rasm sifatini tekshirish"""
        result = {'passed': True, 'issues': []}

        # O'lchamni tekshirish
        height, width = image.shape[:2]
        if width < 400 or height < 600:
            result['passed'] = False
            result['issues'].append("⚠️ Rasm juda kichik (fake ehtimoli)")

        # Blur tekshiruvi (screenshot aniq bo'lishi kerak)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 100:
            result['passed'] = False
            result['issues'].append("⚠️ Rasm xira (screenshot emas ehtimoli)")

        return result

    def _extract_text(self, image):
        """OCR orqali matnni o'qish"""
        # EasyOCR yoki pytesseract ishlatish mumkin
        # Hozir oddiy regex bilan simulyatsiya qilamiz

        # Haqiqiy loyihada:
        # import pytesseract
        # text = pytesseract.image_to_string(image, lang='uzb+rus+eng')

        # Simulyatsiya (test uchun)
        return "SUMMA: 50000 UZS TRX_ID: 1234567890"

    def _detect_fake(self, image, text):
        """Fake screen shot aniqlash"""
        result = {'is_fake': False, 'reasons': []}

        # 1. EXIF ma'lumotlarini tekshirish
        # Haqiqiy screenshot da EXIF kam bo'ladi

        # 2. Matn bo'yicha tekshirish
        text_lower = text.lower()
        for indicator in self.fake_indicators:
            if indicator in text_lower:
                result['is_fake'] = True
                result['reasons'].append(f"🚫 Fake belgisi: '{indicator}'")

        # 3. Rasm o'lchamlari (oddiy screenshot 9:16 yoki 16:9)
        height, width = image.shape[:2]
        ratio = width / height
        if not (0.4 < ratio < 2.5):
            result['is_fake'] = True
            result['reasons'].append("🚫 G'alati rasm nisbati")

        # 4. Rang tekshiruvi (screenshot da aniq ranglar bo'ladi)
        mean_color = np.mean(image, axis=(0, 1))
        if np.std(mean_color) < 5:
            result['is_fake'] = True
            result['reasons'].append("🚫 Bir xil ranglar (montaj ehtimoli)")

        return result

    def _check_amount(self, text, expected_amount):
        """Summani tekshirish"""
        result = {'match': False, 'found_amount': None}

        # Summani qidirish (turli formatlar)
        patterns = [
            r'(\d[\d\s,.]*)\s*(?:so\'m|sum|uzs|сум|₩)',
            r'(?:summa|amount|сумма)[\s:]*(\d[\d\s,.]*)',
            r'(\d{5,10})'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text.lower())
            for match in matches:
                # Faqat raqamlarni olish
                amount_str = re.sub(r'[^\d]', '', match)
                if amount_str:
                    found_amount = int(amount_str)
                    result['found_amount'] = found_amount

                    # 5% chegirma bilan tekshirish
                    if abs(found_amount - expected_amount) / expected_amount < 0.05:
                        result['match'] = True
                        return result

        return result

    def _check_timestamp(self, text):
        """Vaqt belgisini tekshirish"""
        result = {'valid': True, 'found_time': None, 'reason': ''}

        # Vaqt formatlarini qidirish
        time_patterns = [
            r'(\d{2}[./-]\d{2}[./-]\d{4}\s+\d{2}:\d{2})',
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
            r'(\d{2}:\d{2}\s+\d{2}[./-]\d{2}[./-]\d{4})'
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                time_str = match.group(1)
                result['found_time'] = time_str

                # Vaqtni parse qilish
                try:
                    # Turli formatlarni sinab ko'rish
                    for fmt in ['%d.%m.%Y %H:%M', '%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M:%S']:
                        try:
                            payment_time = datetime.strptime(time_str, fmt)
                            break
                        except:
                            continue
                    else:
                        result['valid'] = False
                        result['reason'] = "Vaqt formati noto'g'ri"
                        return result

                    # Vaqt cheklovlari
                    now = datetime.now()
                    if payment_time > now:
                        result['valid'] = False
                        result['reason'] = "Kelajakdagi vaqt"
                    elif payment_time < now - timedelta(days=7):
                        result['valid'] = False
                        result['reason'] = "Juda eski vaqt (7+ kun)"

                except Exception as e:
                    result['valid'] = False
                    result['reason'] = f"Vaqt parse xatosi: {e}"

                return result

        # Vaqt topilmadi
        result['valid'] = False
        result['reason'] = "Vaqt belgisi topilmadi"
        return result

    def _check_transaction_id(self, text):
        """Tranzaksiya ID tekshiruvi"""
        result = {'found': False, 'transaction_id': None}

        patterns = [
            r'(?:trx|transaction|id|чек|код)[\s:#]*(\w{6,20})',
            r'(\d{10,20})',
            r'(?:qr|barcode)[\s:]*(\w+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                result['transaction_id'] = match.group(1)
                result['found'] = True
                return result

        return result

    def _calculate_confidence(self, quality, fake, amount, time, transaction):
        """Ishonch darajasini hisoblash"""
        confidence = 1.0

        # Sifat
        if not quality['passed']:
            confidence -= 0.2

        # Fake
        if fake['is_fake']:
            confidence -= 0.5

        # Summa
        if not amount.get('match', False):
            confidence -= 0.15

        # Vaqt
        if not time['valid']:
            confidence -= 0.1

        # Tranzaksiya
        if not transaction['found']:
            confidence -= 0.05

        return max(0.0, min(1.0, confidence))

# Global instance
screenshot_checker = ScreenshotChecker()
