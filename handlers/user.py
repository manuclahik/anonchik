"""
Обробники для звичайних користувачів
"""
import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import settings, TEXTS
from services.database import db
from services.spam_filter import check_spam
from utils.keyboards import (
    main_menu_keyboard, cancel_keyboard, confirm_question_keyboard,
    back_to_menu_keyboard, rating_keyboard, admin_reply_keyboard
)
from utils.states import UserStates

logger = logging.getLogger(__name__)
router = Router()


async def show_main_menu(target, text: str = None):
    """Показати головне меню"""
    msg_text = text or TEXTS["welcome"]
    if isinstance(target, Message):
        await target.answer(msg_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    elif isinstance(target, CallbackQuery):
        await target.message.edit_text(msg_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start"""
    await state.clear()
    await show_main_menu(message)
    logger.info(f"Новий користувач запустив бот (id=***)")


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(callback)
    await callback.answer()


@router.callback_query(F.data == "how_it_works")
async def how_it_works(callback: CallbackQuery):
    """Інформація про анонімність"""
    await callback.message.edit_text(
        TEXTS["how_it_works"],
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "ask_question")
async def start_question(callback: CallbackQuery, state: FSMContext):
    """Початок написання питання"""
    # Перевірка rate limit
    wait_seconds = await db.check_rate_limit(callback.from_user.id, settings.RATE_LIMIT_SECONDS)
    if wait_seconds:
        await callback.answer(
            TEXTS["rate_limited"].format(seconds=wait_seconds),
            show_alert=True
        )
        return

    await state.set_state(UserStates.writing_question)
    await callback.message.edit_text(
        TEXTS["ask_question"],
        parse_mode="HTML"
    )
    # Показуємо кнопку скасування через reply keyboard
    await callback.message.answer(
        "👇 Введіть питання нижче:",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(UserStates.writing_question)
async def receive_question(message: Message, state: FSMContext):
    """Отримання тексту питання"""
    # Кнопка скасування
    if message.text and message.text == "❌ Скасувати":
        await state.clear()
        from aiogram.types import ReplyKeyboardRemove
        await message.answer(TEXTS["cancelled"], reply_markup=ReplyKeyboardRemove())
        await show_main_menu(message)
        return

    if not message.text:
        await message.answer("⚠️ Будь ласка, надішліть текстове повідомлення.")
        return

    # Перевірка довжини
    if len(message.text) > settings.MAX_QUESTION_LENGTH:
        await message.answer(TEXTS["question_too_long"])
        return

    # Перевірка спаму
    is_spam, reason = check_spam(message.text)
    if is_spam:
        logger.warning(f"Спам заблоковано: {reason}")
        await message.answer(TEXTS["spam_detected"])
        return

    # Зберігаємо питання в FSM
    await state.update_data(question=message.text)
    await state.set_state(UserStates.confirming_question)

    from aiogram.types import ReplyKeyboardRemove
    await message.answer("✍️ Підтвердіть відправку:", reply_markup=ReplyKeyboardRemove())  # Прибираємо reply keyboard

    await message.answer(
        TEXTS["confirm_question"].format(question=message.text),
        reply_markup=confirm_question_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "confirm_send", UserStates.confirming_question)
async def confirm_send_question(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Підтвердження та надсилання питання"""
    data = await state.get_data()
    question = data.get("question", "")

    if not question:
        await callback.answer("Помилка: питання не знайдено", show_alert=True)
        await state.clear()
        return

    # Ще раз перевіряємо rate limit (між підтвердженням і натисканням могло пройти час)
    wait_seconds = await db.check_rate_limit(callback.from_user.id, settings.RATE_LIMIT_SECONDS)
    if wait_seconds:
        await callback.answer(
            TEXTS["rate_limited"].format(seconds=wait_seconds),
            show_alert=True
        )
        return

    # Зберігаємо в БД
    request_id = await db.create_question(callback.from_user.id, question)

    await state.clear()

    # Повідомляємо користувача
    await callback.message.edit_text(
        TEXTS["question_sent"].format(request_id=request_id),
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )

    # Розсилаємо всім адмінам
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                TEXTS["admin_new_question"].format(
                    request_id=request_id,
                    question=question
                ),
                reply_markup=admin_reply_keyboard(request_id),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не вдалося надіслати питання адміну {admin_id}: {e}")

    logger.info(f"Питання #{request_id} надіслано анонімно (адмінів: {len(settings.ADMIN_IDS)})")
    await callback.answer()


@router.callback_query(F.data == "edit_question", UserStates.confirming_question)
async def edit_question(callback: CallbackQuery, state: FSMContext):
    """Редагування питання"""
    await state.set_state(UserStates.writing_question)
    await callback.message.edit_text(
        TEXTS["ask_question"],
        parse_mode="HTML"
    )
    await callback.message.answer(
        "👇 Введіть нове питання:",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_question")
async def cancel_question(callback: CallbackQuery, state: FSMContext):
    """Скасування питання"""
    await state.clear()
    await show_main_menu(callback, TEXTS["cancelled"] + "\n\n" + TEXTS["welcome"])
    await callback.answer()


@router.callback_query(F.data.startswith("rate:"))
async def rate_answer(callback: CallbackQuery):
    """Оцінка відповіді"""
    parts = callback.data.split(":")
    if len(parts) != 3:
        return

    request_id = parts[1]
    rating = int(parts[2])

    await db.save_rating(request_id, rating)

    emoji = "👍" if rating == 1 else "👎"
    await callback.answer(f"{emoji} Дякуємо за оцінку!")

    # Прибираємо кнопки після оцінки
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    logger.info(f"Оцінка {rating} для запиту #{request_id}")
