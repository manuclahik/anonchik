"""
Middleware для захисту від флуду
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)

# Зберігаємо лічильники в пам'яті (окремо від БД для швидкодії)
_flood_counter: Dict[int, int] = {}
_MAX_MESSAGES_PER_MINUTE = 15


class ThrottlingMiddleware(BaseMiddleware):
    """Захист від флуду повідомлень"""

    def __init__(self, rate_limit: int = 30):
        self.rate_limit = rate_limit

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id

            # Простий лічильник флуду
            count = _flood_counter.get(user_id, 0)
            _flood_counter[user_id] = count + 1

            if count >= _MAX_MESSAGES_PER_MINUTE:
                logger.warning(f"Флуд від користувача (заблоковано)")
                await event.answer("⚠️ Занадто багато повідомлень. Зачекайте хвилину.")
                return

        return await handler(event, data)
