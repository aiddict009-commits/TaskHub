import aiosqlite
import asyncio

DB = "taskhub.db"


async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS publishers (id INTEGER PRIMARY KEY, owner_id INTEGER, bot_username TEXT, earnings REAL DEFAULT 0)")
        await db.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT, type TEXT, reward REAL, link TEXT, is_active INTEGER DEFAULT 1)")
        await db.execute("CREATE TABLE IF NOT EXISTS completions (id INTEGER PRIMARY KEY, user_id INTEGER, task_id INTEGER, publisher_id INTEGER, status TEXT)")
        await db.execute("INSERT OR IGNORE INTO tasks (id,title,type,reward,link) VALUES (1,'Join Binance','signup',1.5,'https://binance.com')")
        await db.commit()
        print("DB created OK")


if __name__ == "__main__":
    asyncio.run(init_db())