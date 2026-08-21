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

# Conversation states
WAITING_FOR_FORWARD = 1
WAITING_CHANNEL_USERNAME = 2
WAITING_CONTENT = 3


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
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sponsor_username TEXT NOT NULL,
                goal INTEGER NOT NULL,
                reward REAL NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS channel_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                publisher_id INTEGER NOT NULL,
                campaign_id INTEGER NOT NULL,
                status TEXT DEFAULT 'accepted',
                content_type TEXT,
                content_file_id TEXT,
                content_caption TEXT,
                message_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS supports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_campaign_id INTEGER NOT NULL,
                supporter_user_id INTEGER NOT NULL,
                reward REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (channel_campaign_id, supporter_user_id)
            )
            """
        )

        # Seed one demo campaign if none exist yet
        cursor = await db.execute("SELECT COUNT(*) FROM campaigns")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await db.execute(
                "INSERT INTO campaigns (sponsor_username, goal, reward, description) VALUES (?, ?, ?, ?)",
                ("PartnerDeFi", 100, 1.0, "New Campaign"),
            )

        await db.commit()


# ---------- MENUS ----------
def main_menu_buttons():
    return [
        [InlineKeyboardButton("💰 Publisher", callback_data="publisher")],
        [InlineKeyboardButton("📣 Advertiser", callback_data="advertiser")],
        [InlineKeyboardButton("ℹ️ How it works", callback_data="how_it_works")],
    ]


def back_button():
    return [[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]


def publisher_type_buttons():
    return [
        [InlineKeyboardButton("📢 Channel owner", callback_data="pub_type_channel")],
        [InlineKeyboardButton("🤖 Bot owner", callback_data="pub_type_bot")],
        [InlineKeyboardButton("📃 My Channels & Earnings", callback_data="pub_manage")],
    ] + back_button()


def publisher_manage_buttons():
    return [
        [InlineKeyboardButton("📃 My Channels", callback_data="pub_channels")],
        [InlineKeyboardButton("💰 My Earnings", callback_data="pub_earnings")],
    ] + back_button()


# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "Welcome to TaskHub - The only place to monetize your Telegram channel/bot AND advertise to millions\n\n"
        "Publishers can connect their bot or channel and earn for every completed task.\n"
        "Advertisers get real users from 1000+ bots worldwide."
    )
    reply_markup = InlineKeyboardMarkup(main_menu_buttons())
    await update.message.reply_text(welcome, reply_markup=reply_markup)


# ---------- BUTTON HANDLERS (non-conversation) ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "publisher":
        text = "🤖 I'm a Publisher\n\nAre you a bot owner or a channel owner?"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(publisher_type_buttons()))

    elif data == "pub_type_bot":
        text = "🤖 Bot owner flow is coming soon. In the meantime, you can connect a channel instead."
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(publisher_type_buttons()))

    elif data == "pub_manage":
        await query.edit_message_text(
            "📃 Manage your connected channels and earnings:",
            reply_markup=InlineKeyboardMarkup(publisher_manage_buttons()),
        )

    elif data == "advertiser":
        text = (
            "📣 *Advertiser Mode*\n\n"
            "Promote your offer to real users across 1000+ bots and channels worldwide.\n\n"
            "Pay only for real completed actions.\n\n"
            "Coming soon: Create your campaign here."
        )
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button())
        )

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
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button())
        )

    elif data == "back_main":
        welcome = "Welcome back to TaskHub! What would you like to do?"
        await query.edit_message_text(welcome, reply_markup=InlineKeyboardMarkup(main_menu_buttons()))

    elif data == "pub_channels":
        await show_channels(query, context)

    elif data == "pub_earnings":
        await show_earnings(query, context)

    elif data.startswith("confirm_post_"):
        await confirm_post(query, context)

    elif data.startswith("support_"):
        await handle_support(query, context)


# ---------- CHANNEL ONBOARDING (username + admin verification) ----------
async def channel_owner_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "Perfect. You can now lock your content and earn.\n\n"
        "Send your channel username. Example: @KitweCryptoChannel"
    )
    await query.edit_message_text(text)
    return WAITING_CHANNEL_USERNAME


async def receive_channel_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    if not username.startswith("@"):
        await update.message.reply_text(
            "Please send a channel username starting with @, e.g. @KitweCryptoChannel"
        )
        return WAITING_CHANNEL_USERNAME

    context.user_data["pending_channel_username"] = username
    await update.message.reply_text(f"Add me as ADMIN to {username} then type /campaigns")
    return ConversationHandler.END


async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. You can restart anytime from the Publisher menu.")
    return ConversationHandler.END


# ---------- /campaigns ----------
async def campaigns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = context.user_data.get("pending_channel_username")

    if username:
        try:
            chat = await context.bot.get_chat(username)
        except Exception:
            await update.message.reply_text(
                "❌ I couldn't find that channel. Double check the username and try again."
            )
            return

        try:
            bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        except Exception:
            await update.message.reply_text(
                "❌ I couldn't verify admin status. Make sure I've been added, then try /campaigns again."
            )
            return

        if bot_member.status not in ("administrator", "creator"):
            await update.message.reply_text(
                f"❌ I'm not an admin in {username} yet. Add me as admin, then try /campaigns again."
            )
            return

        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR IGNORE INTO publishers (user_id, username) VALUES (?, ?)",
                (user.id, user.username or ""),
            )
            await db.execute(
                "INSERT OR IGNORE INTO channels (publisher_id, chat_id, title, username) VALUES (?, ?, ?, ?)",
                (user.id, chat.id, chat.title, chat.username or ""),
            )
            await db.commit()

        context.user_data["active_channel_id"] = chat.id
        context.user_data.pop("pending_channel_username", None)
        await update.message.reply_text("✅ Verified! Here's what's available:")
        chat_id = chat.id
    else:
        chat_id = context.user_data.get("active_channel_id")
        if not chat_id:
            async with aiosqlite.connect(DB) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT chat_id FROM channels WHERE publisher_id = ? ORDER BY id DESC LIMIT 1",
                    (user.id,),
                )
                row = await cursor.fetchone()
            if not row:
                await update.message.reply_text(
                    "No connected channel found. Tap Publisher > Channel owner to connect one first."
                )
                return
            chat_id = row["chat_id"]
            context.user_data["active_channel_id"] = chat_id

    await send_campaign_cards(update.message, chat_id)


async def send_campaign_cards(message, chat_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM campaigns
            WHERE is_active = 1
            AND id NOT IN (SELECT campaign_id FROM channel_campaigns WHERE channel_id = ?)
            """,
            (chat_id,),
        )
        rows = await cursor.fetchall()

    if not rows:
        await message.reply_text("No new campaigns available for this channel right now. Check back soon!")
        return

    for row in rows:
        text = (
            "🔥 *New Campaign*\n"
            f"Sponsor: @{row['sponsor_username']}\n"
            f"Goal: {row['goal']} supporters\n"
            f"You earn ${row['reward']:.2f} per support"
        )
        keyboard = [[InlineKeyboardButton("✅ Accept Campaign", callback_data=f"accept_campaign_{row['id']}")]]
        await message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


# ---------- ACCEPT CAMPAIGN + LOCK CONTENT ----------
async def accept_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    campaign_id = int(query.data.split("_")[-1])
    user = query.from_user
    chat_id = context.user_data.get("active_channel_id")

    if not chat_id:
        await query.edit_message_text("Session expired — please run /campaigns again.")
        return ConversationHandler.END

    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "INSERT INTO channel_campaigns (channel_id, publisher_id, campaign_id, status) VALUES (?, ?, ?, 'accepted')",
            (chat_id, user.id, campaign_id),
        )
        await db.commit()
        channel_campaign_id = cursor.lastrowid

    context.user_data["pending_channel_campaign_id"] = channel_campaign_id
    await query.edit_message_text(
        "Campaign accepted. Now send the content you want to lock. Video, photo, or file."
    )
    return WAITING_CONTENT


async def receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    channel_campaign_id = context.user_data.get("pending_channel_campaign_id")

    if not channel_campaign_id:
        await message.reply_text("Session expired — please accept a campaign again via /campaigns.")
        return ConversationHandler.END

    if message.photo:
        content_type, file_id, filename = "photo", message.photo[-1].file_id, None
    elif message.video:
        content_type, file_id, filename = "video", message.video.file_id, message.video.file_name
    elif message.document:
        content_type, file_id, filename = "document", message.document.file_id, message.document.file_name
    else:
        await message.reply_text("Please send a video, photo, or file.")
        return WAITING_CONTENT

    caption = message.caption or filename or "Locked content"

    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE channel_campaigns SET content_type = ?, content_file_id = ?, content_caption = ?, status = 'content_pending' WHERE id = ?",
            (content_type, file_id, caption, channel_campaign_id),
        )
        await db.commit()
        cursor = await db.execute(
            """
            SELECT cc.*, c.goal FROM channel_campaigns cc
            JOIN campaigns c ON cc.campaign_id = c.id
            WHERE cc.id = ?
            """,
            (channel_campaign_id,),
        )
        row = await cursor.fetchone()

    preview = (
        "📢 *SUPPORT THIS CHANNEL*\n\n"
        f"{caption} will be unlocked when our community supports our partners 💪\n\n"
        f"Progress: 0/{row['goal']}"
    )

    await message.reply_text(
        f"Got it.\nFile: {caption}\n\n"
        f"This will unlock when {row['goal']} people support us.\n\n"
        f"Preview of what your members will see:\n\n---\n{preview}\n---",
        parse_mode="Markdown",
    )
    keyboard = [[InlineKeyboardButton("✅ Confirm & Post to Channel", callback_data=f"confirm_post_{channel_campaign_id}")]]
    await message.reply_text("Ready to post?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END


async def confirm_post(query, context: ContextTypes.DEFAULT_TYPE):
    channel_campaign_id = int(query.data.split("_")[-1])

    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT cc.*, c.goal, c.sponsor_username FROM channel_campaigns cc
            JOIN campaigns c ON cc.campaign_id = c.id
            WHERE cc.id = ?
            """,
            (channel_campaign_id,),
        )
        row = await cursor.fetchone()

    if not row:
        await query.edit_message_text("Campaign not found.")
        return

    text = (
        "📢 *SUPPORT THIS CHANNEL*\n\n"
        f"{row['content_caption']} will be unlocked when our community supports our partners 💪\n\n"
        f"Progress: 0/{row['goal']}"
    )
    keyboard = [[InlineKeyboardButton(f"Support Us - Join @{row['sponsor_username']}", callback_data=f"support_{channel_campaign_id}")]]

    sent = await context.bot.send_message(
        chat_id=row["channel_id"], text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    try:
        await context.bot.pin_chat_message(row["channel_id"], sent.message_id)
    except Exception:
        pass

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE channel_campaigns SET status = 'posted', message_id = ? WHERE id = ?",
            (sent.message_id, channel_campaign_id),
        )
        await db.commit()

    await query.edit_message_text(
        f"Done. Posted and pinned in the channel. Progress 0/{row['goal']}. I will auto-unlock when the goal hits."
    )


# ---------- SUPPORT + AUTO-UNLOCK ----------
async def handle_support(query, context: ContextTypes.DEFAULT_TYPE):
    channel_campaign_id = int(query.data.split("_")[-1])
    user = query.from_user

    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT cc.*, c.goal, c.reward, c.sponsor_username FROM channel_campaigns cc
            JOIN campaigns c ON cc.campaign_id = c.id
            WHERE cc.id = ?
            """,
            (channel_campaign_id,),
        )
        row = await cursor.fetchone()

    if not row or row["status"] not in ("posted", "completed"):
        await query.answer("This campaign isn't active.", show_alert=True)
        return

    try:
        member = await context.bot.get_chat_member(f"@{row['sponsor_username']}", user.id)
        is_member = member.status in ("member", "administrator", "creator")
    except Exception:
        is_member = False

    if not is_member:
        await query.answer(f"Join @{row['sponsor_username']} first, then tap again!", show_alert=True)
        return

    async with aiosqlite.connect(DB) as db:
        try:
            await db.execute(
                "INSERT INTO supports (channel_campaign_id, supporter_user_id, reward) VALUES (?, ?, ?)",
                (channel_campaign_id, user.id, row["reward"]),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            await query.answer("You've already supported this ✅", show_alert=True)
            return

        cursor = await db.execute(
            "SELECT COUNT(*) FROM supports WHERE channel_campaign_id = ?", (channel_campaign_id,)
        )
        progress = (await cursor.fetchone())[0]

    await query.answer("✅ Thanks for supporting!")

    goal = row["goal"]
    if progress >= goal:
        send_kwargs = {"chat_id": row["channel_id"], "caption": f"🔓 Unlocked! {row['content_caption']}"}
        if row["content_type"] == "photo":
            await context.bot.send_photo(photo=row["content_file_id"], **send_kwargs)
        elif row["content_type"] == "video":
            await context.bot.send_video(video=row["content_file_id"], **send_kwargs)
        else:
            await context.bot.send_document(document=row["content_file_id"], **send_kwargs)

        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "UPDATE channel_campaigns SET status = 'completed' WHERE id = ?", (channel_campaign_id,)
            )
            await db.commit()

        final_text = (
            "🎉 *GOAL REACHED*\n\n"
            f"{row['content_caption']} has been unlocked! Thanks to everyone who supported.\n\n"
            f"Progress: {progress}/{goal}"
        )
        try:
            await context.bot.edit_message_text(
                chat_id=row["channel_id"], message_id=row["message_id"], text=final_text, parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        text = (
            "📢 *SUPPORT THIS CHANNEL*\n\n"
            f"{row['content_caption']} will be unlocked when our community supports our partners 💪\n\n"
            f"Progress: {progress}/{goal}"
        )
        keyboard = [[InlineKeyboardButton(f"Support Us - Join @{row['sponsor_username']}", callback_data=f"support_{channel_campaign_id}")]]
        try:
            await context.bot.edit_message_text(
                chat_id=row["channel_id"], message_id=row["message_id"], text=text,
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            pass


# ---------- OLD CONNECT FLOW (forward-based, kept for compatibility) ----------
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
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(publisher_manage_buttons())
    )


async def show_earnings(query, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(reward), 0) FROM completions WHERE publisher_id = ? AND status = 'approved'",
            (user_id,),
        )
        task_total = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """
            SELECT COALESCE(SUM(s.reward), 0) FROM supports s
            JOIN channel_campaigns cc ON s.channel_campaign_id = cc.id
            WHERE cc.publisher_id = ?
            """,
            (user_id,),
        )
        campaign_total = (await cursor.fetchone())[0]

    total = task_total + campaign_total
    text = (
        f"💰 *Your Earnings*\n\n"
        f"Total approved earnings: *${total:.2f}*\n\n"
        f"Payouts are sent weekly in USDT."
    )
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(publisher_manage_buttons())
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


async def add_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only command.")
        return

    try:
        parts = " ".join(context.args).split("|")
        sponsor_username = parts[0].strip().lstrip("@")
        goal = int(parts[1].strip())
        reward = float(parts[2].strip())
        description = parts[3].strip() if len(parts) > 3 else "New Campaign"
    except Exception:
        await update.message.reply_text(
            "Usage:\n/add_campaign PartnerDeFi | 100 | 1.0 | Optional description"
        )
        return

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO campaigns (sponsor_username, goal, reward, description) VALUES (?, ?, ?, ?)",
            (sponsor_username, goal, reward, description),
        )
        await db.commit()

    await update.message.reply_text(f"✅ Campaign added: @{sponsor_username} — goal {goal}, ${reward:.2f}/support")


def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in Secrets!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    async def on_startup(app):
        await init_db()

    app.post_init = on_startup

    old_connect_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pub_connect_entry, pattern="^pub_connect$")],
        states={
            WAITING_FOR_FORWARD: [MessageHandler(filters.FORWARDED & ~filters.COMMAND, receive_forward)],
        },
        fallbacks=[CommandHandler("cancel", cancel_flow)],
    )

    channel_onboarding_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(channel_owner_entry, pattern="^pub_type_channel$")],
        states={
            WAITING_CHANNEL_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_channel_username)],
        },
        fallbacks=[CommandHandler("cancel", cancel_flow)],
    )

    accept_campaign_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(accept_campaign, pattern=r"^accept_campaign_\d+$")],
        states={
            WAITING_CONTENT: [
                MessageHandler((filters.PHOTO | filters.VIDEO | filters.Document.ALL) & ~filters.COMMAND, receive_content)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_flow)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("add_task", add_task))
    app.add_handler(CommandHandler("add_campaign", add_campaign))
    app.add_handler(CommandHandler("campaigns", campaigns_command))
    app.add_handler(old_connect_conv)
    app.add_handler(channel_onboarding_conv)
    app.add_handler(accept_campaign_conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 TaskHub bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
