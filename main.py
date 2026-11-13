import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot import admin
from bot.config import load_config
from bot.handlers import router
from bot.menu import Menu
from bot.sinks import TelegramSink  # , PosSink
from bot.storage import Storage


async def main():
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    db_path = os.getenv("DB_PATH", "orders.db")
    bot = Bot(cfg.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(admin.router)  # первым, чтобы /admin и админские состояния обрабатывались раньше
    dp.include_router(router)
    # Добавь PosSink() в список, чтобы дублировать заказы в кассу
    dp["sinks"] = [TelegramSink(bot, cfg)]
    dp["storage"] = Storage(db_path)
    dp["menu"] = Menu(db_path)
    dp["cfg"] = cfg
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
