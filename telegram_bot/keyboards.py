from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Сейчас в канале", callback_data="online"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика за сегодня", callback_data="stats_today"),
            InlineKeyboardButton(text="📊 За месяц", callback_data="stats_month"),
        ],
        [
            InlineKeyboardButton(text="📊 Общая статистика", callback_data="stats_all"),
        ],
        [
            InlineKeyboardButton(text="👤 Статистика по участнику", callback_data="user_pick"),
        ],
    ])


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main")],
    ])


def stats_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Сегодня", callback_data="stats_today"),
            InlineKeyboardButton(text="📊 Месяц", callback_data="stats_month"),
        ],
        [
            InlineKeyboardButton(text="📊 Всё время", callback_data="stats_all"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main")],
    ])


def user_list_kb(users: list[dict], page: int = 0, per_page: int = 8) -> InlineKeyboardMarkup:
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]

    buttons = []
    for u in page_users:
        name = u["display_name"] or u["username"]
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"user_{u['discord_id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"upage_{page - 1}"))
    if end < len(users):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"upage_{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_detail_kb(discord_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Сегодня", callback_data=f"ud_{discord_id}_today"),
            InlineKeyboardButton(text="📊 Месяц", callback_data=f"ud_{discord_id}_month"),
        ],
        [
            InlineKeyboardButton(text="📊 Всё время", callback_data=f"ud_{discord_id}_all"),
        ],
        [InlineKeyboardButton(text="⬅️ К списку", callback_data="user_pick")],
    ])
