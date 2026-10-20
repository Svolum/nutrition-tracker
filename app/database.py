import asyncio
import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger("uvicorn.error")


def build_engine_config(raw_url: str) -> tuple[URL, dict[str, object]]:
    """
    Нормализует URL подключения и исключает конфликт параметра 'ssl'
    между query-строкой (?ssl=disable) и словарем connect_args.
    """
    parsed_url = make_url(raw_url)
    connect_args: dict[str, object] = {
        "timeout": 10,
        "command_timeout": 15,
    }
    if "ssl" not in parsed_url.query:
        connect_args["ssl"] = settings.db_ssl
    return parsed_url, connect_args


db_url, db_connect_args = build_engine_config(settings.database_url)

engine = create_async_engine(
    db_url,
    connect_args=db_connect_args,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def ensure_database_exists() -> None:
    """
    Проверяет наличие целевой базы данных (nutrition_db) и автоматически
    создает ее, подключаясь к системной БД 'postgres' (или одноименной с логином).
    """
    target_db_name = db_url.database
    if not target_db_name:
        return

    admin_candidates = ["postgres", db_url.username or "postgres"]
    last_exc: Exception | None = None

    for admin_db in dict.fromkeys(admin_candidates):
        admin_url = db_url.set(database=admin_db)
        admin_engine = create_async_engine(
            admin_url,
            connect_args=db_connect_args,
            isolation_level="AUTOCOMMIT",
        )
        try:
            async with admin_engine.connect() as conn:
                exists = await conn.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                    {"db_name": target_db_name},
                )
                if not exists:
                    safe_db_name = target_db_name.replace('"', '""')
                    await conn.execute(text(f'CREATE DATABASE "{safe_db_name}"'))
                    logger.info("База данных '%s' успешно создана автоматически.", target_db_name)
                return
        except Exception as exc:
            last_exc = exc
        finally:
            await admin_engine.dispose()

    if last_exc is not None:
        raise last_exc


async def init_db_with_retry(max_attempts: int = 5, base_delay: float = 2.0) -> None:
    """Инициализирует схему БД с повторными попытками при старте приложения."""
    safe_url_str = db_url.render_as_string(hide_password=True)

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(
                "Подключение к БД (попытка %d/%d): %s",
                attempt,
                max_attempts,
                safe_url_str,
            )
            await ensure_database_exists()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Схема БД успешно проверена и инициализирована.")
            return
        except Exception as exc:
            logger.error(
                "Ошибка подключения к БД на попытке %d/%d: [%s] %s",
                attempt,
                max_attempts,
                type(exc).__name__,
                exc,
            )
            if attempt == max_attempts:
                raise
            await asyncio.sleep(base_delay * attempt)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()