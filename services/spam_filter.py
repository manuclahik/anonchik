"""
Фільтр спаму та недозволених слів
"""
import re
from config import settings

# Базовий список (доповнюється через .env SPAM_WORDS)
DEFAULT_BAD_WORDS = [
    "спам", "реклама", "казино", "ставки", "крипта",
]

# URL-патерн
URL_PATTERN = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$\-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)


def check_spam(text: str) -> tuple[bool, str]:
    """
    Перевірка тексту на спам.
    Повертає (is_spam: bool, reason: str)
    """
    text_lower = text.lower()

    # Перевірка лайливих слів
    all_bad_words = DEFAULT_BAD_WORDS + settings.SPAM_WORDS
    for word in all_bad_words:
        if word and word in text_lower:
            return True, f"Заборонене слово: {word}"

    # Перевірка посилань (опціонально)
    if URL_PATTERN.search(text):
        return True, "Посилання не дозволені в питаннях"

    # Перевірка повторюваних символів (флуд)
    if re.search(r"(.)\1{9,}", text):
        return True, "Повторювані символи (флуд)"

    # Перевірка CAPS LOCK (> 80% великих літер)
    letters = [c for c in text if c.isalpha()]
    if len(letters) > 10 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.8:
        return True, "Занадто багато великих літер"

    return False, ""
