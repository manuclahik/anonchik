"""
Анонімний бот - Головний файл запуску
"""
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from handlers import setup_routers
from middlewares.throttling import ThrottlingMiddleware
from middlewares.logging import LoggingMiddleware
from services.database import db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    await db.init()
    logger.info("База даних ініціалізована")

    if settings.USE_WEBHOOK:
        await bot.set_webhook(
            url=f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}",
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        logger.info(f"Вебхук встановлено: {settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}")
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Polling режим активовано")


async def on_shutdown(bot: Bot) -> None:
    await db.close()
    if settings.USE_WEBHOOK:
        await bot.delete_webhook()
    logger.info("Бот зупинено")


def create_bot_and_dispatcher():
    bot = Bot(token=settings.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.message.middleware(ThrottlingMiddleware(rate_limit=settings.RATE_LIMIT_SECONDS))
    dp.message.middleware(LoggingMiddleware())

    setup_routers(dp)

    return bot, dp


async def run_polling():
    bot, dp = create_bot_and_dispatcher()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def run_webhook():
    bot, dp = create_bot_and_dispatcher()

    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.WEBHOOK_HOST, port=settings.WEBHOOK_PORT)
    await site.start()

    logger.info(f"Вебсервер запущено на {settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}")

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    if settings.USE_WEBHOOK:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())
