"""
Обробники для адміністраторів
"""
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import settings, TEXTS
from services.database import db
from utils.keyboards import admin_menu_keyboard, back_to_menu_keyboard, rating_keyboard
from utils.states import AdminStates
from utils.filters import IsAdmin

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Адмін панель"""
    await message.answer(
        "🔧 <b>Адмін панель</b>",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    """Показати статистику"""
    stats = await db.get_stats()
    text = TEXTS["admin_stats"].format(
        total=stats.get("total", 0),
        answered=stats.get("answered", 0),
        pending=stats.get("pending", 0),
        avg_time=stats.get("avg_time", "—"),
        last_question=stats.get("last_question", "—")
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_pending")
async def show_pending(callback: CallbackQuery):
    """Показати питання без відповіді"""
    questions = await db.get_pending_questions()
    if not questions:
        await callback.answer("✅ Всі питання мають відповіді!", show_alert=True)
        return

    text = f"📋 <b>Очікують відповіді ({len(questions)}):</b>\n\n"
    for q in questions[:10]:  # Максимум 10
        text += (
            f"🔢 <code>{q['request_id']}</code>\n"
            f"❓ {q['question'][:100]}{'...' if len(q['question']) > 100 else ''}\n"
            f"🕐 {q['created_at']}\n\n"
        )

    if len(questions) > 10:
        text += f"<i>...та ще {len(questions) - 10} питань</i>"

    from utils.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        __import__('aiogram').types.InlineKeyboardButton(
            text="🔙 Назад", callback_data="admin_back"
        )
    )

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔧 <b>Адмін панель</b>",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_reply:"))
async def start_reply(callback: CallbackQuery, state: FSMContext):
    """Початок написання відповіді"""
    request_id = callback.data.split(":")[1]

    question_data = await db.get_question(request_id)
    if not question_data:
        await callback.answer("❌ Питання не знайдено або вже має відповідь", show_alert=True)
        return

    if question_data["status"] != "pending":
        await callback.answer("⚠️ Це питання вже має відповідь", show_alert=True)
        return

    await state.set_state(AdminStates.writing_answer)
    await state.update_data(
        request_id=request_id,
        question=question_data["question"]
    )

    await callback.message.answer(
        f"✍️ <b>Відповідь на питання #{request_id}:</b>\n\n"
        f"❓ {question_data['question']}\n\n"
        f"Напишіть відповідь (або /cancel для скасування):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("reply"))
async def cmd_reply(message: Message, state: FSMContext):
    """Відповідь через команду: /reply REQUEST_ID"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Використання: <code>/reply REQUEST_ID</code>", parse_mode="HTML")
        return

    request_id = parts[1].strip().upper()
    question_data = await db.get_question(request_id)

    if not question_data:
        await message.answer(f"❌ Питання #{request_id} не знайдено")
        return

    if question_data["status"] != "pending":
        await message.answer(f"⚠️ Питання #{request_id} вже має відповідь")
        return

    await state.set_state(AdminStates.writing_answer)
    await state.update_data(
        request_id=request_id,
        question=question_data["question"]
    )

    await message.answer(
        f"✍️ <b>Відповідь на питання #{request_id}:</b>\n\n"
        f"❓ {question_data['question']}\n\n"
        f"Напишіть відповідь:",
        parse_mode="HTML"
    )


@router.message(Command("cancel"), AdminStates.writing_answer)
async def cancel_reply(message: Message, state: FSMContext):
    """Скасування написання відповіді"""
    await state.clear()
    await message.answer("❌ Відповідь скасовано.")


@router.message(AdminStates.writing_answer)
async def receive_answer(message: Message, state: FSMContext, bot: Bot):
    """Отримання та надсилання відповіді"""
    if not message.text:
        await message.answer("⚠️ Надішліть текстову відповідь.")
        return

    data = await state.get_data()
    request_id = data.get("request_id")
    question = data.get("question", "")

    if not request_id:
        await message.answer("❌ Помилка стану. Спробуйте ще раз.")
        await state.clear()
        return

    # Зберігаємо відповідь і отримуємо user_id
    user_id = await db.save_answer(request_id, message.text)

    if not user_id:
        await message.answer(f"❌ Не вдалося зберегти відповідь для #{request_id}")
        await state.clear()
        return

    await state.clear()

    # Надсилаємо відповідь користувачу
    try:
        await bot.send_message(
            user_id,
            TEXTS["answer_received"].format(
                request_id=request_id,
                question=question,
                answer=message.text
            ),
            reply_markup=rating_keyboard(request_id),
            parse_mode="HTML"
        )

        # Видаляємо user_id після доставки
        await db.mark_delivered(request_id)

        await message.answer(
            f"✅ <b>Відповідь надіслано!</b>\n\n"
            f"🔢 ID запиту: <code>{request_id}</code>\n"
            f"🔐 Дані користувача видалено з системи.",
            parse_mode="HTML"
        )
        logger.info(f"Відповідь на #{request_id} доставлена. user_id видалено.")

    except Exception as e:
        logger.error(f"Не вдалося доставити відповідь на #{request_id}: {e}")
        await message.answer(
            f"⚠️ Відповідь збережена, але не вдалося доставити користувачу.\n"
            f"Можливо, він заблокував бот.\n"
            f"ID: <code>{request_id}</code>",
            parse_mode="HTML"
        )
        # Все одно видаляємо user_id
        await db.mark_delivered(request_id)

    # Публікація у канал (опціонально)
    if settings.ANSWERS_CHANNEL_ID:
        try:
            await bot.send_message(
                settings.ANSWERS_CHANNEL_ID,
                f"❓ <b>Питання:</b>\n{question}\n\n"
                f"💬 <b>Відповідь:</b>\n{message.text}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не вдалося опублікувати у канал: {e}")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика через команду"""
    stats = await db.get_stats()
    text = TEXTS["admin_stats"].format(
        total=stats.get("total", 0),
        answered=stats.get("answered", 0),
        pending=stats.get("pending", 0),
        avg_time=stats.get("avg_time", "—"),
        last_question=stats.get("last_question", "—")
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("cleanup"))
async def cmd_cleanup(message: Message):
    """Очищення старих даних"""
    await db.cleanup_old_data(days=7)
    await message.answer("✅ Старі дані (>7 днів) очищено.")
