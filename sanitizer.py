"""
Модуль предварительной проверки и маскирования персональных данных (PII) на стороне Python.
Выполняется ДО отправки запроса во внешний сервис (OpenRouter).
"""

import re
from typing import Tuple, List

# Регулярные выражения для поиска очевидных контактных и персональных данных
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    re.IGNORECASE
)

# Российские и международные форматы телефонов (+7, 8, с кодами, скобками, дефисами)
PHONE_REGEX = re.compile(
    r'(?:(?:\+?7|8)[\s\-]?)?(?:\(?\d{3,4}\)?[\s\-]?)?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b'
)

# Паспортные серии и номера (например, 4 цифры пробел 6 цифр)
PASSPORT_REGEX = re.compile(
    r'\b\d{2}\s?\d{2}\s{1,2}\d{6}\b'
)

# Номера банковских карт (4 группы по 4 цифры)
CARD_REGEX = re.compile(
    r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'
)

# СНИЛС (3-3-3 2)
SNILS_REGEX = re.compile(
    r'\b\d{3}[\s\-]\d{3}[\s\-]\d{3}[\s\-]\d{2}\b'
)

PII_DISCLAIMER = (
    "Примечание: Система выполняет автоматическую фильтрацию стандартных контактов "
    "(телефоны, email, документы), но не гарантирует 100% распознавания любых персональных "
    "данных. Пожалуйста, не вводите конфиденциальные сведения заказчиков."
)


def sanitize_text(text: str) -> Tuple[str, List[str]]:
    """
    Маскирует обнаруженные контактные и персональные данные в тексте.
    Возвращает (очищенный текст, список обнаруженных категорий).
    """
    if not text:
        return "", []

    detected_types = []
    sanitized = text

    if EMAIL_REGEX.search(sanitized):
        sanitized = EMAIL_REGEX.sub("[Контактный email скрыт]", sanitized)
        detected_types.append("email")

    if PASSPORT_REGEX.search(sanitized):
        sanitized = PASSPORT_REGEX.sub("[Паспортные данные скрыты]", sanitized)
        detected_types.append("паспортные данные")

    if CARD_REGEX.search(sanitized):
        sanitized = CARD_REGEX.sub("[Номер карты скрыт]", sanitized)
        detected_types.append("номер карты")

    if SNILS_REGEX.search(sanitized):
        sanitized = SNILS_REGEX.sub("[СНИЛС скрыт]", sanitized)
        detected_types.append("СНИЛС")

    # Телефоны фильтруем после более длинных последовательностей цифр
    def _mask_phone(match: re.Match) -> str:
        # Проверяем, что это не единичные короткие размеры помещения (например, "3 4 5")
        digits = re.sub(r'\D', '', match.group(0))
        if len(digits) >= 10:
            return "[Телефон скрыт]"
        return match.group(0)

    phones_found = [m.group(0) for m in PHONE_REGEX.finditer(sanitized) if len(re.sub(r'\D', '', m.group(0))) >= 10]
    if phones_found:
        sanitized = PHONE_REGEX.sub(_mask_phone, sanitized)
        detected_types.append("телефон")

    return sanitized, detected_types


def validate_safety(text: str) -> Tuple[bool, str, str]:
    """
    Проверяет текст на безопасность перед отправкой.
    Возвращает (is_safe, sanitized_text, user_warning_message).
    Если обнаружены критические персональные данные, информирует пользователя.
    """
    if not text:
        return True, "", ""

    sanitized, detected = sanitize_text(text)
    warning = ""
    if detected:
        warning = f"Внимание: во введённом тексте обнаружены и автоматически замаскированы персональные данные ({', '.join(set(detected))})."

    return True, sanitized, warning
