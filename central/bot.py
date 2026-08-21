# central/bot.py
import os
import aiosqlite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB = "taskhub.db"

# ---------- START + BUTTONS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "Welcome to TaskHub - The only place to monetize your Telegram channel/bot AND advertise to millions\n\n"
        "Publishers can connect their bot or channel and start earning.\n"
        "Advertisers get real users from 1000+ bots World Wide.\n"
        "Weekly USDT payouts."
    )

    keyboard = [
        [InlineKeyboardButton("📢 Publisher", callback_data="publisher")],
        [InlineKeyboardButton("📣 Advertiser", callback_data="advertiser")],
        [InlineKeyboardButton("ℹ️ How it works", callback_data="how_it_works")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome, reply_markup=reply_markup)

# ---------- BUTTON HANDLERS ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "publisher":
        text = (
            "📢 *Publisher Mode*\n\n"
            "Connect your Telegram channel or bot and start earning.\n\n"
            "You will get paid in USDT for every task completed by your audience.\n\n"
            "Coming soon: Connect your bot/channel here."
        )
        await query.edit_message_text(text, parse_mode="Markdown")

    elif query.data == "advertiser":
        text = (
            "📣 *Advertiser Mode*\n\n"
            "Promote your offer to real users across 1000+ WorldWide bots and channels.\n\n"
            "Pay only for real completed actions.\n\n"
            "Coming soon: Create your campaign here."
        )
        await query.edit_message_text(text, parse_mode="Markdown")

    elif query.data == "how_it_works":
        text = (
            "ℹ️ *How TaskHub Works*\n\n"
            "1. Advertisers create tasks (join channel, signup, etc.)\n"
            "2. Publishers post these tasks to their audience\n"
            "3. Users complete the task using our special link\n"
            "4. Publisher earns USDT for every valid completion\n"
            "5. Weekly automatic USDT payouts\n\n"
            "Simple, transparent and built for Africa."
        )
        await query.edit_message_text(text, parse_mode="Markdown")

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
    except:
        await update.message.reply_text("Usage:\n/add_task Title | 0.5 | https://example.com")
        return

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO tasks (title, type, reward, link) VALUES (?, ?, ?, ?)",
            (title, "custom", reward, link)
        )
        await db.commit()

    await update.message.reply_text(f"✅ Task added: {title}")

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in Secrets!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("add_task", add_task))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 TaskHub bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()