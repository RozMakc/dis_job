import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from config import config
from database.db import init_db
from database import queries

logger = logging.getLogger("discord_bot")

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

_tg_sender = None


def set_tg_sender(sender):
    global _tg_sender
    _tg_sender = sender


async def _notify_tg(text: str):
    if _tg_sender is not None:
        try:
            await _tg_sender(config.TELEGRAM_CHAT_ID, text)
        except Exception as e:
            logger.error("TG notify error: %s", e)


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}с"
    if seconds < 3600:
        return f"{seconds // 60}м {seconds % 60}с"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}ч {m}м {s}с"


def _user_display(member: discord.Member) -> str:
    return member.display_name or member.name


@bot.event
async def on_ready():
    logger.info("Discord bot ready as %s", bot.user)
    await init_db()
    ch = bot.get_channel(config.DISCORD_CHANNEL_ID)
    if ch and isinstance(ch, discord.VoiceChannel):
        await queries.set_monitored_channel(ch.id, ch.guild.id, ch.name)
        logger.info("Monitoring channel: %s (%s)", ch.name, ch.id)

        for member in ch.members:
            if not member.bot:
                await queries.upsert_user(
                    member.id, member.name, _user_display(member),
                    member.display_avatar.url if member.display_avatar else "",
                )
                active = await queries.get_active_sessions()
                if not any(s["discord_id"] == member.id for s in active):
                    await queries.create_session(member.id)


@bot.event
async def on_voice_state_update(
    member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
):
    if member.bot:
        return

    target_id = config.DISCORD_CHANNEL_ID
    was_in = before.channel and before.channel.id == target_id
    now_in = after.channel and after.channel.id == target_id

    if was_in == now_in:
        return

    display = _user_display(member)
    now = datetime.now(timezone.utc).strftime("%H:%M")

    if now_in and not was_in:
        await queries.upsert_user(
            member.id, member.name, display,
            member.display_avatar.url if member.display_avatar else "",
        )
        await queries.create_session(member.id)
        logger.info("%s joined channel at %s", display, now)
        await _notify_tg(f"🟢 <b>{display}</b> зашёл в канал в {now}")

    elif was_in and not now_in:
        duration = await queries.close_session(member.id)
        if duration is not None:
            logger.info("%s left channel at %s (duration: %s)", display, now, _format_duration(duration))
            await _notify_tg(
                f"🔴 <b>{display}</b> вышел из канала в {now} (был {_format_duration(duration)})"
            )


async def start_discord():
    await bot.start(config.DISCORD_TOKEN)


async def stop_discord():
    await bot.close()
