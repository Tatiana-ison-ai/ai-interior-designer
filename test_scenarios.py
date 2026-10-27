"""
Автоматизированный тестовый набор для проверки 3-х сценариев приложения «AI-помощник дизайнера интерьера»:
- Сценарий А: Обычный валидный запрос.
- Сценарий Б: Неполные, необычные данные и предварительная фильтрация PII.
- Сценарий В: Ошибки OpenRouter API (отсутствие ключа, 401, 429, таймаут, сбой сети).
"""

import os
import unittest
from unittest.mock import patch, MagicMock

from sanitizer import sanitize_text, validate_safety
from prompt import SYSTEM_PROMPT, build_user_message
from openrouter_client import (
    validate_input_fields,
    generate_interior_brief,
    DEFAULT_MODEL,
)


class TestScenarioB_IncompleteAndUnusualData(unittest.TestCase):
    """Сценарий Б: Проверка валидации, неполных данных, необычных значений и маскирования PII."""

    def test_empty_required_fields(self):
        """Проверка реакции на пустые обязательные поля."""
        # Пустое назначение
        ok, err = validate_input_fields("", "25", "Светлая комната")
        self.assertFalse(ok)
        self.assertIn("назначение", err.lower())

        # Пустая площадь
        ok, err = validate_input_fields("Гостиная", "", "Светлая комната")
        self.assertFalse(ok)
        self.assertIn("площадь", err.lower())

        # Короткое описание (< 5 символов)
        ok, err = validate_input_fields("Гостиная", "25", "дом")
        self.assertFalse(ok)
        self.assertIn("минимум 5", err.lower())

    def test_invalid_and_unusual_area(self):
        """Проверка отрицательных, нечисловых и граничных площадей."""
        # Отрицательная площадь
        ok, err = validate_input_fields("Спальня", "-10", "Описание комнаты")
        self.assertFalse(ok)
        self.assertIn("положительным", err.lower())

        # Текст вместо числа
        ok, err = validate_input_fields("Спальня", "тридцать метров", "Описание комнаты")
        self.assertFalse(ok)
        self.assertIn("некорректное значение", err.lower())

        # Необычно маленькая площадь (например, гардеробная 3.5 м²) — допустима
        ok, err = validate_input_fields("Гардеробная", "3.5", "Ниша в коридоре под шкаф")
        self.assertTrue(ok)
        self.assertIsNone(err)

        # Превышение допустимого максимума (15 000 м²)
        ok, err = validate_input_fields("Склад", "15000", "Огромное здание")
        self.assertFalse(ok)
        self.assertIn("превышает допустимый максимум", err.lower())

    def test_omitted_optional_fields_marked_as_not_specified(self):
        """Проверка, что опущенные стиль и бюджет явно маркируются как 'Не указано'."""
        msg, pii = build_user_message(
            room_type="Детская",
            area="18",
            style="",
            budget=None,
            description="Комната для двоих детей школьного возраста",
            wishes="  ",
        )
        self.assertIn("- Желаемый стиль: Не указано", msg)
        self.assertIn("- Бюджет: Не указано", msg)
        self.assertIn("- Пожелания клиента: Не указано", msg)
        self.assertIn("- Назначение помещения: Детская", msg)
        self.assertEqual(pii, [])

    def test_pii_sanitization_before_sending(self):
        """Проверка маскирования телефонов и email до передачи во внешний сервис."""
        raw_text = (
            "Стены под покраску. Для замеров звонить 8 (999) 111-22-33 "
            "или писать на designer_client@example.com."
        )
        clean_text, detected = sanitize_text(raw_text)

        self.assertNotIn("8 (999) 111-22-33", clean_text)
        self.assertNotIn("designer_client@example.com", clean_text)
        self.assertIn("[Телефон скрыт]", clean_text)
        self.assertIn("[Контактный email скрыт]", clean_text)
        self.assertIn("телефон", detected)
        self.assertIn("email", detected)

    def test_verbatim_technical_preservation(self):
        """Проверка сохранения исходных технических фраз без искажения при санитизации."""
        tech_text = "Бетонные стены без отделки, потолок 3.20 м, радиаторы биметаллические."
        clean_text, detected = sanitize_text(tech_text)
        self.assertEqual(clean_text, tech_text)
        self.assertEqual(detected, [])


class TestScenarioC_OpenRouterAPIErrors(unittest.TestCase):
    """Сценарий В: Обработка ошибок OpenRouter API (отсутствие ключа, 401, 429, таймаут, сбой сети)."""

    def test_missing_api_key(self):
        """Проверка поведения при отсутствии переменной OPENROUTER_API_KEY."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
            ok, msg = generate_interior_brief(
                room_type="Кухня",
                area="12",
                style="Скандинавский",
                budget="500 000 руб.",
                description="П-образная планировка, газовый котел",
                wishes="Много мест хранения",
            )
            self.assertFalse(ok)
            self.assertIn("OPENROUTER_API_KEY", msg)
            self.assertIn("не задана или пуста", msg)

    @patch("openrouter_client._dispatch_http_request")
    def test_http_401_unauthorized(self, mock_call):
        """Проверка обработки недействительного ключа API."""
        mock_call.return_value = (401, '{"error": {"message": "Invalid API key"}}')

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-secret-test-key-401"}):
            ok, msg = generate_interior_brief(
                room_type="Кухня",
                area="12",
                style="Лофт",
                budget="1 000 000",
                description="Кирпичная стена, открытая проводка",
                wishes="Остров по центру",
            )
            self.assertFalse(ok)
            self.assertIn("401 Unauthorized", msg)
            # Проверка, что сам секретный ключ не попал в сообщение об ошибке
            self.assertNotIn("sk-secret-test-key-401", msg)

    @patch("openrouter_client._dispatch_http_request")
    def test_http_429_rate_limit(self, mock_call):
        """Проверка превышения лимитов запросов."""
        mock_call.return_value = (429, "Too Many Requests")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            ok, msg = generate_interior_brief(
                room_type="Санузел",
                area="6",
                style="Минимализм",
                budget="300 000",
                description="Совмещенный санузел, инсталляция",
                wishes="Душевой трап в пол",
            )
            self.assertFalse(ok)
            self.assertIn("429 Too Many Requests", msg)

    @patch("openrouter_client._dispatch_http_request")
    def test_network_timeout(self, mock_call):
        """Проверка реакции на таймаут сети."""
        mock_call.side_effect = TimeoutError("Connection timed out after 35 seconds")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            ok, msg = generate_interior_brief(
                room_type="Спальня",
                area="16",
                style="Современный",
                budget="Не указано",
                description="Окно на юг, паркетная доска",
                wishes="Блэкаут шторы",
            )
            self.assertFalse(ok)
            self.assertIn("Превышено время ожидания", msg)

    @patch("openrouter_client._dispatch_http_request")
    def test_connection_error(self, mock_call):
        """Проверка реакции на отсутствие соединения с сервером."""
        mock_call.side_effect = Exception("Failed to resolve host openrouter.ai: Name or service not known")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            ok, msg = generate_interior_brief(
                room_type="Прихожая",
                area="8",
                style="Классика",
                budget="150 000",
                description="Входная дверь металлическая",
                wishes="Большое зеркало во весь рост",
            )
            self.assertFalse(ok)
            self.assertIn("Ошибка сетевого подключения", msg)


class TestScenarioA_NormalRequest(unittest.TestCase):
    """Сценарий А: Обычный штатный запрос со всеми заполненными полями."""

    @patch("openrouter_client._dispatch_http_request")
    def test_successful_brief_generation(self, mock_call):
        """Проверка успешной сборки и парсинга ответа от OpenRouter."""
        mock_reply = (
            "### 📋 Краткое техническое задание (ТЗ)\n"
            "- **Назначение помещения:** Гостиная\n"
            "- **Общая площадь:** 32 м²\n"
            "- **Стиль интерьера:** Неоклассика\n"
            "- **Ориентировочный бюджет:** 2 500 000 руб.\n"
            "- **Исходное описание помещения:** Высота потолков 3.1 м, панорамные окна в пол.\n"
            "- **Зафиксированные пожелания клиента:** Каминная зона, светлые тона, паркет елочкой.\n\n"
            "---\n\n"
            "### ❓ Что необходимо уточнить у заказчика\n"
            "1. Какой тип камина планируется (биокамин, электрический)?\n"
            "2. Требуется ли зона домашнего кинотеатра и акустическая подготовка?\n"
            "3. Состав проживающих и наличие домашних животных."
        )

        import json
        fake_body = json.dumps({
            "id": "gen-123",
            "choices": [{"message": {"role": "assistant", "content": mock_reply}}]
        })
        mock_call.return_value = (200, fake_body)

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-valid-key"}):
            ok, result = generate_interior_brief(
                room_type="Гостиная",
                area="32",
                style="Неоклассика",
                budget="2 500 000 руб.",
                description="Высота потолков 3.1 м, панорамные окна в пол.",
                wishes="Каминная зона, светлые тона, паркет елочкой.",
            )

            self.assertTrue(ok)
            self.assertIn("### 📋 Краткое техническое задание (ТЗ)", result)
            self.assertIn("### ❓ Что необходимо уточнить у заказчика", result)
            self.assertIn("Гостиная", result)
            self.assertIn("32 м²", result)

            # Проверяем, что в API переданы правильные параметры
            call_args, _ = mock_call.call_args
            api_key_sent, payload_sent = call_args
            self.assertEqual(api_key_sent, "test-valid-key")
            self.assertEqual(payload_sent["model"], DEFAULT_MODEL)
            self.assertEqual(payload_sent["temperature"], 0.2)
            self.assertEqual(payload_sent["messages"][0]["role"], "system")
            self.assertIn("ЗАПРЕТ ДОДУМЫВАНИЯ", payload_sent["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()
