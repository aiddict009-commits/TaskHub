import os
import aiosqlite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB = "taskhub.db"

# Conversation state for the "connect channel" flow
WAITING_FOR_FORWARD = 1


# ---------- DB SETUP ----------
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                type TEXT,
                reward REAL NOT NULL,
                link TEXT,
                is_active INTEGER DEFAULT 1
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS publishers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publisher_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL UNIQUE,
                title TEXT,
                username TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (publisher_id) REFERENCES publishers(user_id)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                publisher_id INTEGER NOT NULL,
                channel_id INTEGER,
                reward REAL NOT NULL,
                status TEXT DEFAULT 'approved',
                completed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


# ---------- START + MAIN MENU ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "Welcome to TaskHub - The only place to monetize your Telegram channel/bot AND advertise to millions\n\n"
        "Publishers can connect their bot or channel and earn for every completed task.\n"
        "Advertisers get real users from 1000+ bots worldwide."
    )
    reply_markup = InlineKeyboardMarkup(main_menu_buttons())
    await update.message.reply_text(welcome, reply_markup=reply_markup)


def main_menu_buttons():
    return [
        [InlineKeyboardButton("📢 Publisher", callback_data="publisher")],
        [InlineKeyboardButton("📣 Advertiser", callback_data="advertiser")],
        [InlineKeyboardButton("ℹ️ How it works", callback_data="how_it_works")],
    ]


def publisher_menu_buttons():
    return [
        [InlineKeyboardButton("🔗 Connect a Channel/Bot", callback_data="pub_connect")],
        [InlineKeyboardButton("📃 My Channels", callback_data="pub_channels")],
        [InlineKeyboardButton("💰 My Earnings", callback_data="pub_earnings")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ]


# ---------- BUTTON HANDLERS (non-conversation) ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "publisher":
        text = (
            "📢 *Publisher Mode*\n\n"
            "Connect your Telegram channel and start earning USDT for every "
            "valid task completion from your audience."
        )
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(publisher_menu_buttons())
        )

    elif data == "advertiser":
        text = (
            "📣 *Advertiser Mode*\n\n"
            "Promote your offer to real users across 1000+ bots and channels worldwide.\n\n"
            "Pay only for real completed actions.\n\n"
            "Coming soon: Create your campaign here."
        )
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "how_it_works":
        text = (
            "ℹ️ *How TaskHub Works*\n\n"
            "1. Advertisers create tasks (join channel, signup, etc.)\n"
            "2. Publishers post these tasks to their audience\n"
            "3. Users complete the task using our special link\n"
            "4. Publisher earns USDT for every valid completion\n"
            "5. Weekly automatic USDT payouts\n\n"
            "Simple, transparent and built for the world."
        )
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "back_main":
        welcome = "Welcome back to TaskHub! What would you like to do?"
        await query.edit_message_text(welcome, reply_markup=InlineKeyboardMarkup(main_menu_buttons()))

    elif data == "pub_channels":
        await show_channels(query, context)

    elif data == "pub_earnings":
        await show_earnings(query, context)


# ---------- CONNECT CHANNEL CONVERSATION ----------
async def pub_connect_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🔗 *Connect Your Channel*\n\n"
        "1. Add this bot as an *admin* in your channel.\n"
        "2. Forward any message from that channel to me here.\n\n"
        "I'll verify I'm an admin and link the channel to your account.\n\n"
        "Send /cancel to stop."
    )
    await query.edit_message_text(text, parse_mode="Markdown")
    return WAITING_FOR_FORWARD


async def receive_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    forwarded_chat = message.forward_from_chat

    if not forwarded_chat:
        await message.reply_text(
            "That doesn't look like a forwarded channel message. "
            "Please forward a message directly from your channel, or /cancel."
        )
        return WAITING_FOR_FORWARD

    chat_id = forwarded_chat.id
    user = update.effective_user

    # Verify the bot is actually an admin in that channel
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
    except Exception:
        await message.reply_text(
            "❌ I couldn't check that channel. Make sure I've been added as an admin, then try again."
        )
        return WAITING_FOR_FORWARD

    if bot_member.status not in ("administrator", "creator"):
        await message.reply_text(
            "❌ I'm not an admin in that channel yet. Please add me as an admin first, then forward the message again."
        )
        return WAITING_FOR_FORWARD

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO publishers (user_id, username) VALUES (?, ?)",
            (user.id, user.username or ""),
        )
        try:
            await db.execute(
                "INSERT INTO channels (publisher_id, chat_id, title, username) VALUES (?, ?, ?, ?)",
                (user.id, chat_id, forwarded_chat.title, forwarded_chat.username or ""),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            await message.reply_text("⚠️ This channel is already connected to a TaskHub account.")
            return ConversationHandler.END

    await message.reply_text(
        f"✅ *{forwarded_chat.title}* connected successfully! You can now receive tasks to post there.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. You can restart anytime from the Publisher menu.")
    return ConversationHandler.END


# ---------- CHANNELS + EARNINGS ----------
async def show_channels(query, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT title, username FROM channels WHERE publisher_id = ?", (user_id,)
        )
        rows = await cursor.fetchall()

    if not rows:
        text = "You haven't connected any channels yet."
    else:
        lines = ["📃 *Your Connected Channels:*\n"]
        for row in rows:
            handle = f" (@{row['username']})" if row["username"] else ""
            lines.append(f"• {row['title']}{handle}")
        text = "\n".join(lines)

    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(publisher_menu_buttons())
    )


async def show_earnings(query, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(reward), 0) FROM completions WHERE publisher_id = ? AND status = 'approved'",
            (user_id,),
        )
        total = (await cursor.fetchone())[0]

    text = (
        f"💰 *Your Earnings*\n\n"
        f"Total approved earnings: *${total:.2f}*\n\n"
        f"Payouts are sent weekly in USDT."
    )
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(publisher_menu_buttons())
    )


# ---------- OTHER COMMANDS ----------
async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, title, reward FROM tasks WHERE is_active = 1")
        rows = await cursor.fetchall()

    if not rows:
        await update.message.reply_text("No active tasks right now.")
        return

    text = "📋 *Available Tasks:*\n\n"
    for row in rows:
        text += f"🔹 {row['title']}\nReward: ${row['reward']}\n\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only command.")
        return

    try:
        parts = " ".join(context.args).split("|")
        title = parts[0].strip()
        reward = float(parts[1].strip())
        link = parts[2].strip()
    except Exception:
        await update.message.reply_text("Usage:\n/add_task Title | 0.5 | https://example.com")
        return

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO tasks (title, type, reward, link) VALUES (?, ?, ?, ?)",
            (title, "custom", reward, link),
        )
        await db.commit()

    await update.message.reply_text(f"✅ Task added: {title}")


def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in Secrets!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    async def on_startup(app):
        await init_db()

    app.post_init = on_startup

    connect_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pub_connect_entry, pattern="^pub_connect$")],
        states={
            WAITING_FOR_FORWARD: [
                MessageHandler(filters.FORWARDED & ~filters.COMMAND, receive_forward)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_connect)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("add_task", add_task))
    app.add_handler(connect_conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 TaskHub bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
