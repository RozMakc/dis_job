import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logger = logging.getLogger("telegram_bot")

bot: Bot | None = None
dp = Dispatcher()


def init_tg_bot(token: str) -> Bot:
    global bot
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    return bot
