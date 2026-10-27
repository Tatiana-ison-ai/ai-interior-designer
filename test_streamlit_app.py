"""
Тесты для нового Streamlit-интерфейса (streamlit_app.py) и интеграции со st.secrets.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

import streamlit_app
from streamlit_app import reset_form, apply_example, DEFAULT_VALUES
from openrouter_client import get_api_key, generate_interior_brief


class TestStreamlitApp(unittest.TestCase):
    """Проверка логики Streamlit-приложения."""

    def test_default_values_structure(self):
        """Проверка наличия всех дефолтных значений полей."""
        self.assertIn("room_type", DEFAULT_VALUES)
        self.assertIn("area", DEFAULT_VALUES)
        self.assertIn("style", DEFAULT_VALUES)
        self.assertIn("budget", DEFAULT_VALUES)
        self.assertIn("description", DEFAULT_VALUES)
        self.assertIn("wishes", DEFAULT_VALUES)
        self.assertIsNone(DEFAULT_VALUES["result"])
        self.assertIsNone(DEFAULT_VALUES["error"])

    def test_apply_example_function(self):
        """Проверка функции подстановки примера в session_state."""
        with patch.dict(streamlit_app.st.session_state, {}, clear=True):
            apply_example(
                room_type="Спальня",
                area="19",
                style="Минимализм",
                budget="900 000 руб.",
                desc="Высокие окна",
                wishes="Тёмные тона",
            )
            self.assertEqual(streamlit_app.st.session_state["room_type"], "Спальня")
            self.assertEqual(streamlit_app.st.session_state["area"], "19")
            self.assertEqual(streamlit_app.st.session_state["style"], "Минимализм")
            self.assertEqual(streamlit_app.st.session_state["budget"], "900 000 руб.")
            self.assertEqual(streamlit_app.st.session_state["description"], "Высокие окна")
            self.assertEqual(streamlit_app.st.session_state["wishes"], "Тёмные тона")
            self.assertIsNone(streamlit_app.st.session_state["result"])
            self.assertIsNone(streamlit_app.st.session_state["error"])

    def test_reset_form_function(self):
        """Проверка функции сброса формы reset_form."""
        with patch.dict(streamlit_app.st.session_state, {}, clear=True):
            streamlit_app.st.session_state["area"] = "45"
            streamlit_app.st.session_state["budget"] = "1 000 000"
            reset_form()
            self.assertEqual(streamlit_app.st.session_state["area"], "")
            self.assertEqual(streamlit_app.st.session_state["budget"], "")
            self.assertEqual(streamlit_app.st.session_state["room_type"], "Кухня-гостиная")

    def test_get_api_key_from_st_secrets(self):
        """Проверка извлечения OPENROUTER_API_KEY из st.secrets при отсутствии в os.environ."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
            mock_secrets = {"OPENROUTER_API_KEY": "sk-or-v1-streamlit-secrets-key"}
            with patch("streamlit.secrets", mock_secrets, create=True):
                key = get_api_key()
                self.assertEqual(key, "sk-or-v1-streamlit-secrets-key")

    @patch("openrouter_client._dispatch_http_request")
    def test_streamlit_flow_with_secrets(self, mock_dispatch):
        """Проверка успешной генерации ТЗ с ключом, полученным из st.secrets."""
        mock_reply = "### 📋 Краткое техническое задание (ТЗ)\n- **Назначение помещения:** Кухня"
        import json
        mock_dispatch.return_value = (
            200,
            json.dumps({"choices": [{"message": {"content": mock_reply}}]}),
        )

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
            mock_secrets = {"OPENROUTER_API_KEY": "sk-or-v1-test-streamlit-secret"}
            with patch("streamlit.secrets", mock_secrets, create=True):
                ok, res = generate_interior_brief(
                    room_type="Кухня",
                    area="14",
                    style="Скандинавский",
                    budget="500 000",
                    description="Новостройка с коммуникациями",
                    wishes="Встроенный духовой шкаф",
                )
                self.assertTrue(ok)
                self.assertIn("### 📋 Краткое техническое задание (ТЗ)", res)


if __name__ == "__main__":
    unittest.main()
