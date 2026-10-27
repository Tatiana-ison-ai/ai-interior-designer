"""
Тестирование интерфейса и обработчиков Gradio-приложения (app.py).
Проверяет запуск приложения, наличие всех требуемых полей и кнопок,
а также корректность работы функций-обработчиков clear_form и process_brief.
"""

import unittest
from unittest.mock import patch, MagicMock

import app
from app import clear_form, process_brief


class TestGradioAppUI(unittest.TestCase):
    """Проверка структуры и логики UI-компонентов Gradio."""

    def test_app_initialization_and_title(self):
        """Проверка инициализации приложения и русскоязычного заголовка."""
        self.assertIsNotNone(app.demo)
        self.assertEqual(app.demo.title, "AI-помощник дизайнера интерьера")

    def test_clear_button_handler(self):
        """Проверка работы функции очистки формы clear_form."""
        cleared_values = clear_form()
        self.assertEqual(len(cleared_values), 7)
        # Назначение, площадь, бюджет, описание, пожелания сбрасываются
        self.assertEqual(cleared_values[0], "")  # room_type
        self.assertEqual(cleared_values[1], "")  # area
        self.assertEqual(cleared_values[2], "Не определён / Требуется подбор")  # style
        self.assertEqual(cleared_values[3], "")  # budget
        self.assertEqual(cleared_values[4], "")  # description
        self.assertEqual(cleared_values[5], "")  # wishes
        self.assertIn("Здесь появится сформированное ТЗ", cleared_values[6])  # output

    def test_process_brief_validation_error_formatting(self):
        """Проверка форматирования ошибок валидации при нажатии кнопки 'Сформировать ТЗ'."""
        # Вызов с пустыми обязательными полями
        result = process_brief(
            room_type="",
            area="",
            style="Современный",
            budget="",
            description="",
            wishes="",
        )
        self.assertIn("### ⚠️ Обратите внимание", result)
        self.assertIn("Ошибка валидации", result)
        self.assertIn("скорректируйте введённые данные", result)

    @patch("app.generate_interior_brief")
    def test_process_brief_success_flow(self, mock_gen):
        """Проверка успешной обработки и нормализации параметров в process_brief."""
        mock_gen.return_value = (True, "### 📋 Краткое техническое задание\n- Тестовое ТЗ")

        result = process_brief(
            room_type="Спальня",
            area="18.5",
            style="Не определён / Требуется подбор",  # Должен нормализоваться в пустую строку
            budget="800 000 руб.",
            description="Большое окно, светлая комната",
            wishes="Кровать 180х200",
        )

        self.assertIn("### 📋 Краткое техническое задание", result)
        mock_gen.assert_called_once_with(
            room_type="Спальня",
            area="18.5",
            style="",  # Проверяем нормализацию
            budget="800 000 руб.",
            description="Большое окно, светлая комната",
            wishes="Кровать 180х200",
        )


if __name__ == "__main__":
    unittest.main()
