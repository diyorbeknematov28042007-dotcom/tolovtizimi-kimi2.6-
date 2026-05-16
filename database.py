"""
Neon PostgreSQL bilan ishlash
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL
import json
from datetime import datetime, timedelta

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Bazaga ulanish"""
        self.conn = psycopg2.connect(DATABASE_URL)
        self.conn.autocommit = True

    def create_tables(self):
        """Jadvallarni yaratish"""
        with self.conn.cursor() as cur:
            # Foydalanuvchilar jadvali
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(100),
                    first_name VARCHAR(100),
                    last_name VARCHAR(100),
                    language VARCHAR(10) DEFAULT 'uz',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Saytlar jadvali (foydalanuvchining ro'yxatdan o'tgan saytlari)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_sites (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(telegram_id),
                    site_name VARCHAR(200),
                    site_url VARCHAR(500),
                    login VARCHAR(100),
                    password VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # To'lovlar jadvali
            cur.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(telegram_id),
                    order_number VARCHAR(100),
                    amount DECIMAL(12,2),
                    status VARCHAR(50) DEFAULT 'pending',
                    screenshot_file_id VARCHAR(500),
                    screenshot_message_id BIGINT,
                    group_message_id BIGINT,
                    payment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_at TIMESTAMP,
                    approved_by BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Bot sozlamalari jadvali
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    id SERIAL PRIMARY KEY,
                    key VARCHAR(100) UNIQUE NOT NULL,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Default sozlamalarni qo'shish
            defaults = [
                ('welcome_text', 'Assalomu alaykum! {name}\n\nBizning xizmatlarimizdan foydalaning.'),
                ('welcome_links', '[]'),
                ('questions_text', 'Savollaringiz bormi? Admin bilan bog\'laning.'),
                ('about_text', 'Bu bot to\'lov xizmatlarini boshqarish uchun yaratilgan.'),
                ('about_media', ''),
                ('contact_admin', '@admin')
            ]

            for key, value in defaults:
                cur.execute("""
                    INSERT INTO bot_settings (key, value) 
                    VALUES (%s, %s) 
                    ON CONFLICT (key) DO NOTHING
                """, (key, value))

    # ========== FOYDALANUVCHILAR ==========

    def get_user(self, telegram_id):
        """Foydalanuvchini olish"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            return cur.fetchone()

    def add_user(self, telegram_id, username, first_name, last_name, language='uz'):
        """Foydalanuvchi qo'shish yoki yangilash"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name, language)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_active = CURRENT_TIMESTAMP
            """, (telegram_id, username, first_name, last_name, language))

    def update_language(self, telegram_id, language):
        """Tilni yangilash"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET language = %s WHERE telegram_id = %s
            """, (language, telegram_id))

    def get_all_users(self):
        """Barcha foydalanuvchilarni olish"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users ORDER BY created_at DESC")
            return cur.fetchall()

    def get_users_count(self):
        """Foydalanuvchilar soni"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            return cur.fetchone()[0]

    # ========== SAYTLAR ==========

    def add_site(self, user_id, site_name, site_url, login, password):
        """Sayt qo'shish"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_sites (user_id, site_name, site_url, login, password)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, site_name, site_url, login, password))

    def get_user_sites(self, user_id):
        """Foydalanuvchining saytlarini olish"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM user_sites WHERE user_id = %s", (user_id,))
            return cur.fetchall()

    # ========== TO'LOVLAR ==========

    def add_payment(self, user_id, order_number, amount, status='pending'):
        """To'lov qo'shish"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO payments (user_id, order_number, amount, status)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (user_id, order_number, amount, status))
            return cur.fetchone()[0]

    def update_payment_screenshot(self, payment_id, file_id, message_id):
        """Screen shot ma'lumotlarini yangilash"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE payments 
                SET screenshot_file_id = %s, screenshot_message_id = %s
                WHERE id = %s
            """, (file_id, message_id, payment_id))

    def update_payment_group_message(self, payment_id, group_message_id):
        """Guruh xabar ID sini yangilash"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE payments SET group_message_id = %s WHERE id = %s
            """, (group_message_id, payment_id))

    def approve_payment(self, payment_id, admin_id):
        """To'lovni tasdiqlash"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE payments 
                SET status = 'approved', approved_at = CURRENT_TIMESTAMP, approved_by = %s
                WHERE id = %s
            """, (admin_id, payment_id))

    def reject_payment(self, payment_id):
        """To'lovni rad etish"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE payments SET status = 'rejected' WHERE id = %s
            """, (payment_id,))

    def get_payment(self, payment_id):
        """To'lovni olish"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM payments WHERE id = %s", (payment_id,))
            return cur.fetchone()

    def get_user_payments(self, user_id):
        """Foydalanuvchining to'lovlarini olish"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM payments 
                WHERE user_id = %s 
                ORDER BY created_at DESC
            """, (user_id,))
            return cur.fetchall()

    def get_payments_by_date(self, start_date, end_date):
        """Sana bo'yicha to'lovlarni olish"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM payments 
                WHERE created_at BETWEEN %s AND %s
                ORDER BY created_at DESC
            """, (start_date, end_date))
            return cur.fetchall()

    def get_payments_stats(self):
        """To'lovlar statistikasi"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_count,
                    COALESCE(SUM(amount), 0) as total_amount
                FROM payments 
                WHERE status = 'approved'
            """)
            return cur.fetchone()

    # ========== SOZLAMALAR ==========

    def get_setting(self, key):
        """Sozlamani olish"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT value FROM bot_settings WHERE key = %s", (key,))
            result = cur.fetchone()
            return result[0] if result else None

    def set_setting(self, key, value):
        """Sozlamani yangilash"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bot_settings (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, value))

    def get_welcome_data(self):
        """Salomlashuv ma'lumotlarini olish"""
        text = self.get_setting('welcome_text') or 'Assalomu alaykum! {name}'
        links = self.get_setting('welcome_links')
        try:
            links = json.loads(links) if links else []
        except:
            links = []
        return text, links

    def set_welcome_data(self, text, links=None):
        """Salomlashuv ma'lumotlarini saqlash"""
        self.set_setting('welcome_text', text)
        if links is not None:
            self.set_setting('welcome_links', json.dumps(links))

    def close(self):
        """Ulanishni yopish"""
        if self.conn:
            self.conn.close()

# Global database instance
db = Database()
