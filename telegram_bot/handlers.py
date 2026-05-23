import logging
from datetime import datetime, timezone

from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram import Router

from database import queries
from telegram_bot.keyboards import (
    main_menu_kb, back_to_main_kb, stats_menu_kb,
    user_list_kb, user_detail_kb,
)

logger = logging.getLogger("telegram_handlers")
router = Router()

_user_list_cache: list[dict] = []


def _fmt_dur(seconds: int | float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}с"
    if s < 3600:
        return f"{s // 60}м {s % 60}с"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h < 24:
        return f"{h}ч {m}м {sec}с"
    d, rh = divmod(h, 24)
    return f"{d}д {rh}ч {m}м"


def _fmt_online(sessions: list[dict]) -> str:
    if not sessions:
        return "🔇 Канал пуст — никого нет."

    lines = []
    now = datetime.now(timezone.utc)
    for s in sessions:
        joined = datetime.strptime(s["joined_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        dur = int((now - joined).total_seconds())
        name = s["display_name"] or s["username"]
        lines.append(f"  • <b>{name}</b> — {_fmt_dur(dur)} (с {joined.strftime('%H:%M')})")

    header = f"🔊 В канале: {len(sessions)} чел.\n"
    return header + "\n".join(lines)


def _fmt_channel_stats(stats: dict, period_label: str) -> str:
    ts = int(stats.get("total_seconds", 0))
    sessions = stats.get("total_sessions", 0)
    users = stats.get("unique_users", 0)
    avg = int(stats.get("avg_session_seconds", 0))
    mx = int(stats.get("max_session_seconds", 0))
    peak = stats.get("peak_online", 0) or 0

    return (
        f"📊 <b>Статистика канала — {period_label}</b>\n\n"
        f"⏱ Суммарное время: <b>{_fmt_dur(ts)}</b>\n"
        f"📋 Сессий: <b>{sessions}</b>\n"
        f"👥 Уникальных участников: <b>{users}</b>\n"
        f"⏱ Среднее время сессии: <b>{_fmt_dur(avg)}</b>\n"
        f"🏆 Макс. время сессии: <b>{_fmt_dur(mx)}</b>\n"
        f"📈 Пик онлайна: <b>{peak}</b> чел."
    )


def _fmt_user_stats(stats: dict, name: str, period_label: str) -> str:
    ts = int(stats.get("total_seconds", 0))
    sessions = stats.get("total_sessions", 0)
    avg = int(stats.get("avg_session_seconds", 0))
    mx = int(stats.get("max_session_seconds", 0))
    first = stats.get("first_joined", "—")
    last = stats.get("last_joined", "—")

    return (
        f"👤 <b>{name}</b> — {period_label}\n\n"
        f"⏱ Суммарное время: <b>{_fmt_dur(ts)}</b>\n"
        f"📋 Сессий: <b>{sessions}</b>\n"
        f"⏱ Среднее время сессии: <b>{_fmt_dur(avg)}</b>\n"
        f"🏆 Макс. время сессии: <b>{_fmt_dur(mx)}</b>\n"
        f"📅 Первое подключение: {first}\n"
        f"📅 Последнее подключение: {last}"
    )


def _fmt_top_users(users: list[dict], period_label: str) -> str:
    if not users:
        return f"📊 Топ участников — {period_label}\n\nДанных нет."
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(users):
        medal = medals[i] if i < 3 else f"{i + 1}."
        name = u["display_name"] or u["username"]
        lines.append(f"  {medal} <b>{name}</b> — {_fmt_dur(u['total_seconds'])} ({u['total_sessions']} сессий)")
    return f"📊 Топ участников — {period_label}\n\n" + "\n".join(lines)


PERIOD_LABELS = {"today": "Сегодня", "month": "За месяц", "all": "За всё время"}


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("🎧 Мониторинг голосового канала", reply_markup=main_menu_kb())


@router.callback_query(lambda c: c.data == "main")
async def cb_main(call: CallbackQuery):
    await call.message.edit_text("🎧 Мониторинг голосового канала", reply_markup=main_menu_kb())


@router.callback_query(lambda c: c.data == "online")
async def cb_online(call: CallbackQuery):
    sessions = await queries.get_active_sessions()
    text = _fmt_online(sessions)
    await call.message.edit_text(text, reply_markup=back_to_main_kb())


@router.callback_query(lambda c: c.data and c.data.startswith("stats_"))
async def cb_stats(call: CallbackQuery):
    period = call.data.split("_")[1]
    label = PERIOD_LABELS.get(period, period)
    stats = await queries.get_channel_stats(period)
    top = await queries.get_top_users(period, limit=5)
    text = _fmt_channel_stats(stats, label) + "\n\n" + _fmt_top_users(top, label)
    await call.message.edit_text(text, reply_markup=stats_menu_kb())


@router.callback_query(lambda c: c.data == "user_pick")
async def cb_user_pick(call: CallbackQuery):
    global _user_list_cache
    _user_list_cache = await queries.get_all_users()
    if not _user_list_cache:
        await call.message.edit_text("Пользователей пока нет.", reply_markup=back_to_main_kb())
        return
    await call.message.edit_text("👤 Выберите участника:", reply_markup=user_list_kb(_user_list_cache, page=0))


@router.callback_query(lambda c: c.data and c.data.startswith("upage_"))
async def cb_user_page(call: CallbackQuery):
    page = int(call.data.split("_")[1])
    await call.message.edit_text("👤 Выберите участника:", reply_markup=user_list_kb(_user_list_cache, page=page))


@router.callback_query(lambda c: c.data and c.data.startswith("user_") and not c.data.startswith("ud_"))
async def cb_user_select(call: CallbackQuery):
    discord_id = int(call.data.split("_")[1])
    name = await queries.get_user_display_name(discord_id)
    text = f"👤 <b>{name}</b>\nВыберите период:"
    await call.message.edit_text(text, reply_markup=user_detail_kb(discord_id))


@router.callback_query(lambda c: c.data and c.data.startswith("ud_"))
async def cb_user_detail(call: CallbackQuery):
    parts = call.data.split("_")
    discord_id = int(parts[1])
    period = parts[2]
    label = PERIOD_LABELS.get(period, period)
    name = await queries.get_user_display_name(discord_id)
    stats = await queries.get_user_stats(discord_id, period)
    text = _fmt_user_stats(stats, name, label)
    await call.message.edit_text(text, reply_markup=user_detail_kb(discord_id))
