# central/db.py
import os
from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, select

# Database URL - works on Replit and later on Render
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./taskhub.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class Publisher(Base):
    __tablename__ = "publishers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bot_token: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    channel_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    completions: Mapped[List["Completion"]] = relationship(back_populates="publisher")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    target_url: Mapped[str] = mapped_column(String(500))          # real advertiser link
    reward: Mapped[float] = mapped_column(Float, default=0.01)     # USDT per completion
    max_completions: Mapped[int] = mapped_column(Integer, default=1000)
    current_completions: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    completions: Mapped[List["Completion"]] = relationship(back_populates="task")


class Completion(Base):
    __tablename__ = "completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    publisher_id: Mapped[int] = mapped_column(ForeignKey("publishers.id"))
    user_telegram_id: Mapped[int] = mapped_column(Integer, index=True)
    reward: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="completions")
    publisher: Mapped["Publisher"] = relationship(back_populates="completions")


async def init_db():
    """Create all tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created successfully")


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


# ---------- Helper functions we will use later ----------

async def create_task(title: str, description: str, target_url: str, reward: float = 0.01, max_completions: int = 1000):
    async with AsyncSessionLocal() as session:
        task = Task(
            title=title,
            description=description,
            target_url=target_url,
            reward=reward,
            max_completions=max_completions
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


async def get_active_tasks():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Task).where(Task.is_active == True, Task.current_completions < Task.max_completions)
        )
        return result.scalars().all()


async def get_task_by_id(task_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()