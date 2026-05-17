"""
database.py - Neon PostgreSQL ulanish va modellar
Universal To'lov Boti v2.0
"""

import asyncpg
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db():
    """Database ulanish"""
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    """Jadvallarni yaratish"""
    conn = await get_db()

    # 1. SERVICES - Ulangan xizmatlar (sayt yoki bot)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            type VARCHAR(20) NOT NULL CHECK (type IN ('website', 'telegram_bot')),

            -- Sayt uchun maydonlar
            site_url VARCHAR(500),
            api_endpoint VARCHAR(500),
            api_key VARCHAR(255),
            api_secret VARCHAR(255),

            -- Telegram bot uchun maydonlar
            bot_username VARCHAR(100),
            bot_token VARCHAR(255),
            webhook_url VARCHAR(500),

            -- Umumiy
            owner_id BIGINT NOT NULL,
            owner_username VARCHAR(100),
            status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'suspended')),
            commission_percent DECIMAL(5,2) DEFAULT 0.00,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # 2. PAYMENTS - To'lovlar
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            user_username VARCHAR(100),

            -- Xizmat ma'lumotlari
            service_id INTEGER REFERENCES services(id) ON DELETE SET NULL,
            service_type VARCHAR(20) CHECK (service_type IN ('website', 'telegram_bot', 'personal')),

            -- Buyurtma ma'lumotlari
            order_number VARCHAR(100),
            amount DECIMAL(12,2),
            currency VARCHAR(10) DEFAULT 'UZS',

            -- Shaxsiy chek uchun
            receipt_type VARCHAR(50),
            receipt_number VARCHAR(100),
            receipt_screenshot TEXT,

            -- Status
            status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'verified', 'rejected', 'auto_verified')),
            verification_method VARCHAR(20) CHECK (verification_method IN ('api', 'screenshot', 'manual')),

            -- Admin ma'lumotlari
            admin_id BIGINT,
            admin_note TEXT,
            verified_at TIMESTAMP,

            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # 3. SERVICE_CONNECTIONS
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS service_connections (
            id SERIAL PRIMARY KEY,
            service_id INTEGER REFERENCES services(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL,
            external_user_id VARCHAR(100),
            connected_at TIMESTAMP DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE
        )
    """)

    # 4. ADMIN_LOGS
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id SERIAL PRIMARY KEY,
            admin_id BIGINT NOT NULL,
            action VARCHAR(50) NOT NULL,
            target_type VARCHAR(20),
            target_id INTEGER,
            details JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # 5. BUSINESS_REQUESTS
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS business_requests (
            id SERIAL PRIMARY KEY,
            requester_id BIGINT NOT NULL,
            requester_username VARCHAR(100),
            business_name VARCHAR(255) NOT NULL,
            business_type VARCHAR(20) CHECK (business_type IN ('website', 'telegram_bot')),
            contact_phone VARCHAR(20),
            contact_email VARCHAR(100),
            description TEXT,
            status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
            admin_note TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # 6. USERS - Foydalanuvchilar
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            username VARCHAR(100),
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            phone VARCHAR(20),
            language VARCHAR(10) DEFAULT 'uz',
            is_blocked BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_active TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.close()
    print("Database initialized successfully!")


# ===================== SERVICES =====================

async def get_active_services() -> List[asyncpg.Record]:
    """Aktiv xizmatlarni olish"""
    conn = await get_db()
    rows = await conn.fetch(
        "SELECT * FROM services WHERE status = 'active' ORDER BY type, name"
    )
    await conn.close()
    return rows

async def get_service_by_id(service_id: int) -> Optional[asyncpg.Record]:
    """Xizmatni ID bo'yicha olish"""
    conn = await get_db()
    row = await conn.fetchrow("SELECT * FROM services WHERE id = $1", service_id)
    await conn.close()
    return row

async def get_service_by_api_key(api_key: str) -> Optional[asyncpg.Record]:
    """API kalit bo'yicha xizmatni olish"""
    conn = await get_db()
    row = await conn.fetchrow("SELECT * FROM services WHERE api_key = $1 AND status = 'active'", api_key)
    await conn.close()
    return row

async def add_service(name: str, service_type: str, owner_id: int, **kwargs) -> int:
    """Yangi xizmat qo'shish"""
    conn = await get_db()

    if service_type == 'website':
        service_id = await conn.fetchval("""
            INSERT INTO services (name, type, site_url, api_endpoint, api_key, api_secret, owner_id, owner_username)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """, name, service_type, kwargs.get('site_url'), kwargs.get('api_endpoint'),
             kwargs.get('api_key'), kwargs.get('api_secret'), owner_id, kwargs.get('owner_username'))
    else:  # telegram_bot
        service_id = await conn.fetchval("""
            INSERT INTO services (name, type, bot_username, bot_token, webhook_url, owner_id, owner_username)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """, name, service_type, kwargs.get('bot_username'), kwargs.get('bot_token'),
             kwargs.get('webhook_url'), owner_id, kwargs.get('owner_username'))

    await conn.close()
    return service_id


# ===================== PAYMENTS =====================

async def create_payment(user_id: int, service_type: str, **kwargs) -> int:
    """Yangi to'lov yaratish"""
    conn = await get_db()

    payment_id = await conn.fetchval("""
        INSERT INTO payments (user_id, user_username, service_id, service_type, 
                            order_number, amount, currency, receipt_type, receipt_number, 
                            receipt_screenshot, verification_method, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'pending')
        RETURNING id
    """, user_id, kwargs.get('user_username'), kwargs.get('service_id'), service_type,
         kwargs.get('order_number'), kwargs.get('amount'), kwargs.get('currency', 'UZS'),
         kwargs.get('receipt_type'), kwargs.get('receipt_number'),
         kwargs.get('receipt_screenshot'), kwargs.get('verification_method', 'manual'))

    await conn.close()
    return payment_id

async def get_payment_by_id(payment_id: int) -> Optional[asyncpg.Record]:
    """To'lovni ID bo'yicha olish"""
    conn = await get_db()
    row = await conn.fetchrow("SELECT * FROM payments WHERE id = $1", payment_id)
    await conn.close()
    return row

async def get_pending_payments(limit: int = 50) -> List[asyncpg.Record]:
    """Kutilayotgan to'lovlarni olish"""
    conn = await get_db()
    rows = await conn.fetch(
        "SELECT * FROM payments WHERE status = 'pending' ORDER BY created_at DESC LIMIT $1",
        limit
    )
    await conn.close()
    return rows

async def update_payment_status(payment_id: int, status: str, admin_id: int = None, note: str = None):
    """To'lov statusini yangilash"""
    conn = await get_db()
    await conn.execute("""
        UPDATE payments 
        SET status = $1, admin_id = $2, admin_note = $3, verified_at = NOW()
        WHERE id = $4
    """, status, admin_id, note, payment_id)
    await conn.close()


# ===================== BUSINESS REQUESTS =====================

async def create_business_request(requester_id: int, business_name: str, business_type: str, **kwargs) -> int:
    """Biznes arizasi yaratish"""
    conn = await get_db()
    request_id = await conn.fetchval("""
        INSERT INTO business_requests (requester_id, requester_username, business_name, 
                                     business_type, contact_phone, contact_email, description)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
    """, requester_id, kwargs.get('requester_username'), business_name, business_type,
         kwargs.get('contact_phone'), kwargs.get('contact_email'), kwargs.get('description'))
    await conn.close()
    return request_id

async def get_pending_business_requests() -> List[asyncpg.Record]:
    """Kutilayotgan biznes arizalarini olish"""
    conn = await get_db()
    rows = await conn.fetch(
        "SELECT * FROM business_requests WHERE status = 'pending' ORDER BY created_at DESC"
    )
    await conn.close()
    return rows

async def update_business_request_status(request_id: int, status: str, admin_note: str = None):
    """Biznes arizasi statusini yangilash"""
    conn = await get_db()
    await conn.execute("""
        UPDATE business_requests 
        SET status = $1, admin_note = $2
        WHERE id = $3
    """, status, admin_note, request_id)
    await conn.close()


# ===================== USERS =====================

async def get_or_create_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Foydalanuvchini olish yoki yaratish"""
    conn = await get_db()
    user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    if not user:
        await conn.execute("""
            INSERT INTO users (id, username, first_name, last_name)
            VALUES ($1, $2, $3, $4)
        """, user_id, username, first_name, last_name)
    else:
        await conn.execute("""
            UPDATE users SET username = $1, first_name = $2, last_name = $3, last_active = NOW()
            WHERE id = $4
        """, username, first_name, last_name, user_id)

    await conn.close()


# ===================== STATISTICS =====================

async def get_stats() -> Dict[str, Any]:
    """Umumiy statistika"""
    conn = await get_db()

    total_payments = await conn.fetchval("SELECT COUNT(*) FROM payments")
    verified_payments = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status = 'verified'")
    pending_payments = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
    total_amount = await conn.fetchval("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'verified'")
    total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
    total_services = await conn.fetchval("SELECT COUNT(*) FROM services WHERE status = 'active'")

    await conn.close()

    return {
        "total_payments": total_payments,
        "verified_payments": verified_payments,
        "pending_payments": pending_payments,
        "total_amount": total_amount,
        "total_users": total_users,
        "total_services": total_services
    }

async def get_service_stats(service_id: int) -> Dict[str, Any]:
    """Xizmat statistikasi"""
    conn = await get_db()

    total = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE service_id = $1", service_id)
    verified = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE service_id = $1 AND status = 'verified'", service_id)
    rejected = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE service_id = $1 AND status = 'rejected'", service_id)
    pending = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE service_id = $1 AND status = 'pending'", service_id)
    amount = await conn.fetchval("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE service_id = $1 AND status = 'verified'", service_id)

    await conn.close()

    return {
        "total_payments": total,
        "verified_payments": verified,
        "rejected_payments": rejected,
        "pending_payments": pending,
        "total_amount": amount
    }
