"""
Клавіатури для бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Головне меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📩 Задати анонімне питання", callback_data="ask_question")
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ Як це працює / Про анонімність", callback_data="how_it_works")
    )
    return builder.as_markup()


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка скасування під час введення"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Скасувати"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def confirm_question_keyboard(request_id: str = "") -> InlineKeyboardMarkup:
    """Підтвердження надсилання питання"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Надіслати анонімно", callback_data="confirm_send"),
        InlineKeyboardButton(text="✏️ Редагувати", callback_data="edit_question"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_question")
    )
    return builder.as_markup()


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Повернення до головного меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Головне меню", callback_data="back_to_menu")
    )
    return builder.as_markup()


def rating_keyboard(request_id: str) -> InlineKeyboardMarkup:
    """Рейтинг відповіді"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👍 Корисно", callback_data=f"rate:{request_id}:1"),
        InlineKeyboardButton(text="👎 Не корисно", callback_data=f"rate:{request_id}:0"),
    )
    return builder.as_markup()


def admin_reply_keyboard(request_id: str) -> InlineKeyboardMarkup:
    """Кнопка відповіді для адміна"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"↩️ Відповісти на #{request_id}",
            callback_data=f"admin_reply:{request_id}"
        )
    )
    return builder.as_markup()


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Адмін меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="📋 Очікують відповіді", callback_data="admin_pending"),
    )
    return builder.as_markup()
