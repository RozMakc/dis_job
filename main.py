import asyncio
import logging
import signal
import sys

from config import config
from database.db import init_db, close_db
from discord_bot import bot as discord_bot_module
from discord_bot.bot import start_discord, stop_discord
from telegram_bot.bot import init_tg_bot, dp
from telegram_bot.handlers import router as tg_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("main")


async def _run_discord():
    try:
        await start_discord()
    except Exception:
        logger.exception("Discord bot crashed")


async def _run_telegram(tg_bot):
    try:
        await dp.start_polling(tg_bot, allowed_updates=dp.resolve_used_update_types())
    except Exception:
        logger.exception("Telegram bot crashed")


async def main():
    if not config.DISCORD_TOKEN or not config.TELEGRAM_TOKEN:
        logger.error("DISCORD_TOKEN and TELEGRAM_TOKEN must be set in .env")
        sys.exit(1)
    if not config.DISCORD_CHANNEL_ID:
        logger.error("DISCORD_CHANNEL_ID must be set in .env")
        sys.exit(1)

    await init_db()

    tg_bot = init_tg_bot(config.TELEGRAM_TOKEN)

    async def tg_send(chat_id: int, text: str):
        await tg_bot.send_message(chat_id=chat_id, text=text)

    discord_bot_module.set_tg_sender(tg_send)

    dp.include_router(tg_router)

    logger.info("Starting bots...")

    stop_event = asyncio.Event()

    def _shutdown():
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass

    while not stop_event.is_set():
        discord_task = asyncio.create_task(_run_discord())
        telegram_task = asyncio.create_task(_run_telegram(tg_bot))

        done, pending = await asyncio.wait(
            [discord_task, telegram_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in done:
            exc = task.exception()
            if exc:
                name = "Discord" if task is discord_task else "Telegram"
                logger.error("%s bot failed: %s", name, exc)

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if not stop_event.is_set():
            logger.info("Restarting crashed bots in 5 seconds...")
            await asyncio.sleep(5)

    logger.info("Shutting down...")
    await stop_discord()
    await tg_bot.session.close()
    await close_db()
    logger.info("Stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
