import aiosqlite
import os

DB_PATH = "accounts.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                password TEXT,
                otp TEXT,
                price INTEGER NOT NULL,
                description TEXT,
                is_sold BOOLEAN DEFAULT 0,
                sold_to INTEGER,
                sold_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                payment_method TEXT,
                payment_txid TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP
            )
        """)
        await db.commit()

async def add_account(phone, password, otp, price, description=""):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO accounts (phone, password, otp, price, description) VALUES (?,?,?,?,?)",
            (phone, password, otp, price, description)
        )
        await db.commit()
        return cursor.lastrowid

async def get_available_accounts():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM accounts WHERE is_sold=0 ORDER BY price")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_account_by_id(acc_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM accounts WHERE id=?", (acc_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def mark_account_sold(acc_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE accounts SET is_sold=1, sold_to=?, sold_at=CURRENT_TIMESTAMP WHERE id=?",
            (user_id, acc_id)
        )
        await db.commit()

async def update_account_otp(acc_id, new_otp):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE accounts SET otp=? WHERE id=?", (new_otp, acc_id))
        await db.commit()

async def create_order(user_id, account_id, payment_method="manual"):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO orders (user_id, account_id, payment_method, status) VALUES (?,?,?,'pending')",
            (user_id, account_id, payment_method)
        )
        await db.commit()
        return cursor.lastrowid

async def get_order(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def update_order_status(order_id, status, txid=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if txid:
            await db.execute(
                "UPDATE orders SET status=?, payment_txid=?, confirmed_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, txid, order_id)
            )
        else:
            await db.execute(
                "UPDATE orders SET status=?, confirmed_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, order_id)
            )
        await db.commit()

async def get_orders_by_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (user_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_all_orders():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
