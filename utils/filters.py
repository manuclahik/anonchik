"""
Фільтри для хендлерів
"""
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from config import settings


class IsAdmin(BaseFilter):
    """Фільтр: тільки адміністратори"""

    async def __call__(self, event) -> bool:
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None
            return user_id in settings.ADMIN_IDS
        return False
