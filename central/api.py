# central/api.py
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
import aiosqlite
import uvicorn

app = FastAPI(title="TaskHub API")

DB = "taskhub.db"


@app.get("/")
async def home():
    return {"status": "TaskHub API is running", "message": "Welcome to TaskHub"}


@app.get("/tasks")
async def get_tasks():
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, title, type, reward, link FROM tasks WHERE is_active = 1")
        rows = await cursor.fetchall()
        tasks = [dict(row) for row in rows]
    return {"tasks": tasks}


@app.get("/r/{task_id}")
async def redirect_tracker(task_id: int, request: Request):
    """This is the go-link that solves Telegram link bans"""
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT link FROM tasks WHERE id = ? AND is_active = 1", (task_id,))
        row = await cursor.fetchone()

        if not row:
            return {"error": "Task not found"}

        target_url = row[0]

        # Here we can later log the click (user, publisher, etc.)
        # For now we just redirect

    return RedirectResponse(url=target_url)


# This allows us to run the API directly
if __name__ == "__main__":
    uvicorn.run("central.api:app", host="0.0.0.0", port=8000, reload=True)