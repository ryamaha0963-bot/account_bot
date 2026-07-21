import asyncpg
import os
from config import Config

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise Exception("DATABASE_URL not set. Add PostgreSQL in Railway.")
        _pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)
    return _pool

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                phone TEXT NOT NULL,
                password TEXT,
                otp TEXT,
                price INTEGER NOT NULL,
                description TEXT,
                is_sold BOOLEAN DEFAULT FALSE,
                sold_to BIGINT,
                sold_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                account_id INTEGER NOT NULL,
                payment_method TEXT,
                payment_txid TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP
            )
        """)

# ---------- Account CRUD ----------
async def add_account(phone, password, otp, price, description=""):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO accounts (phone, password, otp, price, description) VALUES ($1,$2,$3,$4,$5) RETURNING id",
            phone, password, otp, price, description
        )

async def get_available_accounts():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM accounts WHERE is_sold=FALSE ORDER BY price")
        return [dict(row) for row in rows]

async def get_account_by_id(acc_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM accounts WHERE id=$1", acc_id)
        return dict(row) if row else None

async def mark_account_sold(acc_id, user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE accounts SET is_sold=TRUE, sold_to=$1, sold_at=CURRENT_TIMESTAMP WHERE id=$2",
            user_id, acc_id
        )

async def update_account_otp(acc_id, new_otp):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE accounts SET otp=$1 WHERE id=$2", new_otp, acc_id)

# ---------- Orders ----------
async def create_order(user_id, account_id, payment_method="manual"):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO orders (user_id, account_id, payment_method, status) VALUES ($1,$2,$3,'pending') RETURNING id",
            user_id, account_id, payment_method
        )

async def get_order(order_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM orders WHERE id=$1", order_id)
        return dict(row) if row else None

async def update_order_status(order_id, status, txid=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if txid:
            await conn.execute(
                "UPDATE orders SET status=$1, payment_txid=$2, confirmed_at=CURRENT_TIMESTAMP WHERE id=$3",
                status, txid, order_id
            )
        else:
            await conn.execute(
                "UPDATE orders SET status=$1, confirmed_at=CURRENT_TIMESTAMP WHERE id=$2",
                status, order_id
            )

async def get_orders_by_user(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM orders WHERE user_id=$1 ORDER BY created_at DESC", user_id)
        return [dict(row) for row in rows]

async def get_all_orders():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM orders ORDER BY created_at DESC")
        return [dict(row) for row in rows]
