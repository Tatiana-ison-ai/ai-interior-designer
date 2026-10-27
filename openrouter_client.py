"""
Клиент для взаимодействия с OpenRouter API.
Использует модель openrouter/free, строго считывает ключ из OPENROUTER_API_KEY
и обрабатывает все сетевые и логические ошибки.

Поддерживает работу как через requests (для Hugging Face Spaces),
так и через стандартный модуль urllib.request (для чистого Python 3.10 без сторонних пакетов).
"""

import os
import json
from typing import Tuple, Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error

from prompt import SYSTEM_PROMPT, build_user_message
from sanitizer import PII_DISCLAIMER

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"
REQUEST_TIMEOUT = 35  # секунд


def get_api_key() -> str:
    """
    Безопасно извлекает API-ключ строго из переменной окружения или st.secrets.
    Ключ никогда не логируется и не выводится в консоль.
    """
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "OPENROUTER_API_KEY" in st.secrets:
                key = str(st.secrets["OPENROUTER_API_KEY"]).strip()
        except Exception:
            pass
    return key


def validate_input_fields(
    room_type: str,
    area: str,
    description: str,
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет обязательные поля перед отправкой запроса.
    """
    if not room_type or not room_type.strip():
        return False, "⚠️ Ошибка валидации: Пожалуйста, укажите назначение помещения (например, 'Гостиная', 'Кухня', 'Спальня')."

    if not area or not str(area).strip():
        return False, "⚠️ Ошибка валидации: Пожалуйста, укажите площадь помещения в квадратных метрах."

    # Проверка числового формата площади
    try:
        area_num = float(str(area).replace(",", ".").replace("м2", "").replace("м²", "").strip())
        if area_num <= 0:
            return False, "⚠️ Ошибка валидации: Площадь помещения должна быть положительным числом больше 0."
        if area_num > 10000:
            return False, "⚠️ Ошибка валидации: Площадь помещения превышает допустимый максимум (10 000 м²)."
    except ValueError:
        return False, f"⚠️ Ошибка валидации: Некорректное значение площади ('{area}'). Введите число, например: 24 или 35.5."

    if not description or not description.strip() or len(description.strip()) < 5:
        return False, "⚠️ Ошибка валидации: Поле 'Описание помещения' должно содержать хотя бы краткое пояснение (минимум 5 символов)."

    return True, None


def _call_api_requests(
    api_key: str,
    payload: Dict[str, Any],
    session: Optional[Any] = None,
) -> Tuple[int, str]:
    """Отправка запроса через библиотеку requests."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://huggingface.co/spaces",
        "X-Title": "AI Interior Designer Assistant",
    }
    client = session or requests
    resp = client.post(
        OPENROUTER_API_URL,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    return resp.status_code, resp.text


def _call_api_urllib(api_key: str, payload: Dict[str, Any]) -> Tuple[int, str]:
    """Отправка запроса через стандартную библиотеку urllib.request."""
    import urllib.request
    import urllib.error

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://huggingface.co/spaces",
        "X-Title": "AI Interior Designer Assistant",
        "User-Agent": "AI-Interior-Assistant/1.0",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OPENROUTER_API_URL, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8")
            return status, body
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8") if err.fp else ""
        return err.code, body


def _dispatch_http_request(
    api_key: str,
    payload: Dict[str, Any],
    session: Optional[Any] = None,
) -> Tuple[int, str]:
    """Единый диспетчер сетевых запросов: использует requests при наличии, иначе urllib."""
    if HAS_REQUESTS or session is not None:
        return _call_api_requests(api_key, payload, session=session)
    return _call_api_urllib(api_key, payload)


def generate_interior_brief(
    room_type: str,
    area: str,
    style: str,
    budget: str,
    description: str,
    wishes: str,
    model: str = DEFAULT_MODEL,
    session: Optional[Any] = None,
) -> Tuple[bool, str]:
    """
    Основная функция генерации технического задания через OpenRouter API.

    Возвращает:
        (success: bool, content: str)
        где content — это либо готовый Markdown-текст ТЗ с вопросами,
        либо понятное сообщение об ошибке для пользователя.
    """
    # 1. Валидация входных данных
    is_valid, validation_error = validate_input_fields(room_type, area, description)
    if not is_valid:
        return False, validation_error

    # 2. Проверка наличия API-ключа
    api_key = get_api_key()
    if not api_key:
        return False, (
            "❌ Ошибка конфигурации: Переменная окружения `OPENROUTER_API_KEY` не задана или пуста.\n\n"
            "**Как исправить:**\n"
            "- При локальном запуске: укажите ключ в терминале (`export OPENROUTER_API_KEY=\"ваш-ключ\"`) или в файле `.env`.\n"
            "- На Hugging Face Spaces: перейдите в **Settings -> Variables and secrets** и добавьте секрет `OPENROUTER_API_KEY`."
        )

    # 3. Предварительное маскирование PII на стороне Python
    user_message_text, detected_pii = build_user_message(
        room_type=room_type,
        area=area,
        style=style,
        budget=budget,
        description=description,
        wishes=wishes,
    )

    # 4. Подготовка полезной нагрузки для OpenRouter
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message_text},
        ],
        "temperature": 0.2,  # Низкая температура для минимизации фантазий и строгого следования фактам
    }

    # 5. Выполнение сетевого запроса с обработкой ошибок (Сценарий В)
    try:
        status_code, raw_text = _dispatch_http_request(api_key, payload, session=session)
    except TimeoutError:
        return False, (
            f"⏱️ Превышено время ожидания ответа от OpenRouter ({REQUEST_TIMEOUT} сек). "
            "Возможно, сервис перегружен. Пожалуйста, повторите попытку через минуту."
        )
    except Exception as exc:
        exc_name = type(exc).__name__
        exc_str = str(exc)
        if "timeout" in exc_str.lower() or "timed out" in exc_str.lower():
            return False, (
                f"⏱️ Превышено время ожидания ответа от OpenRouter ({REQUEST_TIMEOUT} сек). "
                "Возможно, сервис перегружен. Пожалуйста, повторите попытку через минуту."
            )
        if "connection" in exc_str.lower() or "resolve" in exc_str.lower() or "refused" in exc_str.lower():
            return False, (
                "🌐 Ошибка сетевого подключения: Не удалось соединиться с сервером OpenRouter (`openrouter.ai`). "
                "Проверьте доступность интернета."
            )
        return False, f"⚠️ Сетевая ошибка при обращении к API ({exc_name}): {exc_str[:150]}"

    # 6. Обработка HTTP-кодов ответа
    if status_code == 401:
        return False, (
            "🔒 Ошибка авторизации (401 Unauthorized): Указанный `OPENROUTER_API_KEY` недействителен "
            "или был отозван. Проверьте правильность ключа на https://openrouter.ai/settings/keys."
        )
    elif status_code == 402:
        return False, (
            "💳 Недостаточно кредитов на балансе OpenRouter (402 Payment Required). "
            "Убедитесь, что используется бесплатная модель или пополните баланс."
        )
    elif status_code == 429:
        return False, (
            "⏳ Превышен лимит запросов к OpenRouter (429 Too Many Requests). "
            "Пожалуйста, подождите несколько секунд и попробуйте снова."
        )
    elif status_code >= 500:
        return False, (
            f"🛠️ Ошибка на стороне сервера OpenRouter (HTTP {status_code}). "
            "Сервис временно недоступен. Попробуйте повторить запрос позже."
        )
    elif status_code != 200:
        return False, f"⚠️ Сервер OpenRouter вернул код {status_code}: {raw_text[:200]}"

    # 7. Извлечение и валидация текста ответа
    try:
        data = json.loads(raw_text)
        choices = data.get("choices", [])
        if not choices:
            return False, "⚠️ Ответ от модели получен, но не содержит вариантов текста (пустой choices)."
        result_text = choices[0].get("message", {}).get("content", "").strip()
        if not result_text:
            return False, "⚠️ Модель вернула пустой ответ. Попробуйте повторить запрос."
    except (json.JSONDecodeError, AttributeError) as exc:
        return False, f"⚠️ Ошибка разбора ответа OpenRouter: {exc}"

    # 8. Добавление предупреждений о маскировании персональных данных при необходимости
    result_parts = [result_text]
    if detected_pii:
        warning_box = (
            f"\n\n> 🛡️ **Защита данных**: Во входных данных обнаружены и автоматически "
            f"замаскированы персональные сведения ({', '.join(detected_pii)}).\n"
            f"> *{PII_DISCLAIMER}*"
        )
        result_parts.append(warning_box)

    return True, "".join(result_parts)
