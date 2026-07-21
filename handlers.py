from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery  # 👈 YEH IMPORT ADD KIYA
import logging
from database import *
from config import Config

logger = logging.getLogger(__name__)

class BotHandlers:
    def __init__(self, app: Client):
        self.app = app
        self.admin_id = Config.ADMIN_ID

        @app.on_message(filters.command("start"))
        async def start_cmd(client, message):
            await message.reply(
                "👋 Welcome to **Account Shop**!\n"
                "Use /shop to browse available accounts.\n"
                "Admins use /admin for management."
            )

        @app.on_message(filters.command("shop"))
        async def shop_cmd(client, message):
            accounts = await get_available_accounts()
            if not accounts:
                await message.reply("❌ No accounts available right now.")
                return

            text = "📱 **Available Accounts:**\n\n"
            buttons = []
            for acc in accounts:
                phone = acc['phone']
                masked = phone[:4] + "****" + phone[-4:] if len(phone) > 8 else "****"
                text += f"🔹 **ID:** `{acc['id']}` | {masked} | 💰 {acc['price']} ₹\n"
                buttons.append([InlineKeyboardButton(
                    f"Buy {masked} - {acc['price']}₹",
                    callback_data=f"buy_{acc['id']}"
                )])

            await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

        @app.on_callback_query(filters.regex(r"^buy_(\d+)$"))
        async def buy_callback(client, callback: CallbackQuery):
            acc_id = int(callback.matches[0].group(1))
            account = await get_account_by_id(acc_id)
            if not account or account['is_sold']:
                await callback.answer("❌ This account is already sold!", show_alert=True)
                return

            text = (
                f"📱 **Account #{account['id']}**\n"
                f"Phone: `{account['phone']}`\n"
                f"Price: **{account['price']} ₹**\n"
                f"Description: {account['description'] or 'N/A'}\n\n"
                "💳 **Payment Instructions:**\n"
                f"Send **{account['price']}₹** to UPI: `your-upi@bank` or BTC: `1A1zP1...`\n"
                "Then click **'I Paid'** and send the transaction ID.\n\n"
                "⚠️ Accounts are delivered only after payment confirmation."
            )
            buttons = [
                [InlineKeyboardButton("✅ I Paid", callback_data=f"paid_{acc_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_buy")]
            ]
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            await callback.answer()

        @app.on_callback_query(filters.regex(r"^paid_(\d+)$"))
        async def paid_callback(client, callback: CallbackQuery):
            acc_id = int(callback.matches[0].group(1))
            account = await get_account_by_id(acc_id)
            if not account or account['is_sold']:
                await callback.answer("❌ Account already sold.", show_alert=True)
                return

            order_id = await create_order(callback.from_user.id, acc_id, "manual")
            await callback.message.edit_text(
                f"📩 **Order #{order_id}** created.\n"
                "Please send the **transaction ID / proof** to admin via /confirm <txid>.\n"
                "You will receive the account credentials once confirmed."
            )
            await callback.answer("Order placed!")

        @app.on_callback_query(filters.regex(r"^cancel_buy$"))
        async def cancel_buy(client, callback: CallbackQuery):
            await callback.message.edit_text("❌ Purchase cancelled.")
            await callback.answer()

        # ---------- Admin Commands ----------
        @app.on_message(filters.command("admin") & filters.user(Config.ADMIN_ID))
        async def admin_cmd(client, message):
            await message.reply(
                "🔧 **Admin Commands:**\n"
                "/addaccount phone password otp price description\n"
                "/updateotp account_id new_otp\n"
                "/orders - View all orders\n"
                "/confirm order_id txid - Confirm payment"
            )

        @app.on_message(filters.command("addaccount") & filters.user(Config.ADMIN_ID))
        async def add_account_cmd(client, message):
            parts = message.text.split(maxsplit=5)
            if len(parts) < 6:
                await message.reply("Usage: /addaccount <phone> <password> <otp> <price> <description>")
                return
            phone, password, otp, price, desc = parts[1], parts[2], parts[3], int(parts[4]), parts[5]
            acc_id = await add_account(phone, password, otp, price, desc)
            await message.reply(f"✅ Account #{acc_id} added successfully!")

        @app.on_message(filters.command("updateotp") & filters.user(Config.ADMIN_ID))
        async def update_otp_cmd(client, message):
            parts = message.text.split()
            if len(parts) != 3:
                await message.reply("Usage: /updateotp <account_id> <new_otp>")
                return
            acc_id, new_otp = int(parts[1]), parts[2]
            await update_account_otp(acc_id, new_otp)
            await message.reply(f"✅ OTP for account #{acc_id} updated to `{new_otp}`")

        @app.on_message(filters.command("orders") & filters.user(Config.ADMIN_ID))
        async def orders_cmd(client, message):
            orders = await get_all_orders()
            if not orders:
                await message.reply("No orders yet.")
                return
            text = "📦 **All Orders:**\n\n"
            for o in orders:
                text += f"#{o['id']} | Acc #{o['account_id']} | User {o['user_id']} | {o['status']}\n"
            await message.reply(text)

        @app.on_message(filters.command("confirm") & filters.user(Config.ADMIN_ID))
        async def confirm_cmd(client, message):
            parts = message.text.split()
            if len(parts) != 3:
                await message.reply("Usage: /confirm <order_id> <txid_or_proof>")
                return
            order_id, txid = int(parts[1]), parts[2]
            order = await get_order(order_id)
            if not order:
                await message.reply("Order not found.")
                return
            if order['status'] != 'pending':
                await message.reply("Order already processed.")
                return
            acc_id = order['account_id']
            account = await get_account_by_id(acc_id)
            if not account or account['is_sold']:
                await message.reply("Account already sold.")
                return

            await mark_account_sold(acc_id, order['user_id'])
            await update_order_status(order_id, "confirmed", txid)

            creds = (
                f"🎉 **Account #{acc_id} delivered!**\n"
                f"Phone: `{account['phone']}`\n"
                f"Password: `{account['password'] or 'N/A'}`\n"
                f"OTP: `{account['otp'] or 'N/A'}`\n"
                f"Description: {account['description']}\n"
                "⚠️ Change credentials immediately!"
            )
            try:
                await client.send_message(order['user_id'], creds)
            except Exception as e:
                await message.reply(f"⚠️ Could not deliver to user: {e}")

            await message.reply(f"✅ Order #{order_id} confirmed, account delivered to user {order['user_id']}.")

        @app.on_message(filters.command("myorders"))
        async def myorders_cmd(client, message):
            orders = await get_orders_by_user(message.from_user.id)
            if not orders:
                await message.reply("You have no orders.")
                return
            text = "📋 **Your Orders:**\n\n"
            for o in orders:
                text += f"#{o['id']} | Acc #{o['account_id']} | Status: {o['status']}\n"
            await message.reply(text)
