# central/bot.py
import os
import aiosqlite
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Get token from Replit Secrets
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

DB = "taskhub.db"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "Welcome to TaskHub - The only place to monetize your Telegram channel/bot AND advertise to millions\n\n"
        "Publishers can connect their bot or channel and earn for every completed task.\n"
        "Advertisers get real users from 1000+ bots across Africa.\n"
        "Weekly USDT payouts."
    )
    await update.message.reply_text(welcome)


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, title, reward, link FROM tasks WHERE is_active = 1")
        rows = await cursor.fetchall()

    if not rows:
        await update.message.reply_text("No active tasks right now.")
        return

    text = "📋 Available Tasks:\n\n"
    for row in rows:
        text += f"🔹 {row['title']}\nReward: ${row['reward']}\nLink: /r/{row['id']}\n\n"

    await update.message.reply_text(text)


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only command.")
        return

    # Usage: /add_task Title | reward | link
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

    print("🤖 TaskHub bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()