"""
Middleware для логування (без особистих даних)
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Анонімне логування подій"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            # Логуємо без username та ID користувача
            text_preview = ""
            if event.text:
                text_len = len(event.text)
                text_preview = f"[{text_len} символів]"

            logger.debug(f"Повідомлення: {text_preview} | стан: {data.get('state', 'None')}")

        try:
            result = await handler(event, data)
            return result
        except Exception as e:
            logger.error(f"Помилка обробки: {e}", exc_info=True)
            if isinstance(event, Message):
                try:
                    await event.answer("⚠️ Сталася помилка. Спробуйте ще раз або натисніть /start")
                except Exception:
                    pass
            raise
