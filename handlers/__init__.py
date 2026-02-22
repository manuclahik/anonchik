"""
Реєстрація всіх роутерів
"""
from aiogram import Dispatcher
from .user import router as user_router
from .admin import router as admin_router


def setup_routers(dp: Dispatcher):
    """Підключення всіх роутерів"""
    # Адмін роутер першим (пріоритет)
    dp.include_router(admin_router)
    dp.include_router(user_router)
