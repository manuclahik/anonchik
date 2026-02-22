"""
FSM Стани для керування діалогами
"""
from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    """Стани для звичайних користувачів"""
    writing_question = State()      # Користувач вводить питання
    confirming_question = State()   # Підтвердження перед відправкою


class AdminStates(StatesGroup):
    """Стани для адміністраторів"""
    writing_answer = State()        # Адмін вводить відповідь
