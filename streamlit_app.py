"""
Веб-приложение «AI-помощник дизайнера интерьера» на Streamlit.
Готово для публикации на Streamlit Community Cloud.
"""

import os
from typing import Optional
import streamlit as st

from sanitizer import PII_DISCLAIMER
from openrouter_client import generate_interior_brief, DEFAULT_MODEL

# Настройка страницы
st.set_page_config(
    page_title="AI-помощник дизайнера интерьера",
    page_icon="🛋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Инициализация session_state
DEFAULT_VALUES = {
    "room_type": "Кухня-гостиная",
    "area": "",
    "style": "Не определён / Требуется подбор",
    "budget": "",
    "description": "",
    "wishes": "",
    "result": None,
    "error": None,
}

for key, val in DEFAULT_VALUES.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset_form():
    """Сброс всех полей формы в исходное состояние."""
    for k, v in DEFAULT_VALUES.items():
        st.session_state[k] = v


def apply_example(room_type: str, area: str, style: str, budget: str, desc: str, wishes: str):
    """Заполнение полей формы из выбранного примера."""
    st.session_state["room_type"] = room_type
    st.session_state["area"] = area
    st.session_state["style"] = style
    st.session_state["budget"] = budget
    st.session_state["description"] = desc
    st.session_state["wishes"] = wishes
    st.session_state["result"] = None
    st.session_state["error"] = None


# Боковая панель с примерами и информацией
with st.sidebar:
    st.header("💡 Примеры для проверки")
    st.caption("Нажмите кнопку, чтобы мгновенно заполнить форму:")

    if st.button("🏠 Пример 1: Гостиная (полные данные)", use_container_width=True):
        apply_example(
            room_type="Гостиная",
            area="32",
            style="Неоклассика",
            budget="2 500 000 руб.",
            desc="Высота потолков 3.1 м, панорамные окна в пол, черновая отделка.",
            wishes="Каминная зона, светлые тона, паркет елочкой, акцентная люстра.",
        )
        st.rerun()

    if st.button("🍳 Пример 2: Кухня (неполные данные)", use_container_width=True):
        apply_example(
            room_type="Кухня",
            area="14",
            style="Не определён / Требуется подбор",
            budget="",
            desc="Новостройка, бетонные стены без отделки, выводы под раковину в углу.",
            wishes="Организовать удобную рабочую зону и обеденный стол на 4 персоны.",
        )
        st.rerun()

    if st.button("🚪 Пример 3: Гардеробная (3.5 м²)", use_container_width=True):
        apply_example(
            room_type="Гардеробная",
            area="3.5",
            style="Минимализм",
            budget="150 000 руб.",
            desc="Узкая ниша в коридоре, высота потолка 2.7 м.",
            wishes="Максимум полок до потолка, зеркало, светодиодная подсветка.",
        )
        st.rerun()

    st.divider()
    st.markdown("### ⚙️ Параметры подключения")
    st.markdown("- **Модель:** `openrouter/free`")
    st.markdown("- **Провайдер:** OpenRouter API")
    st.markdown("- **Конфигурация:** `OPENROUTER_API_KEY` из окружения или `st.secrets`")
    st.caption("Приложение не использует платные сервисы и работает строго с фактами.")


# Основная шапка
st.title("🛋️ AI-помощник дизайнера интерьера")
st.caption("Инструмент для составления первичного технического задания (ТЗ) дизайн-проекта на основе фактов без выдумывания.")

# Предупреждение о конфиденциальности
st.info(
    "🛡️ **Конфиденциальность и безопасность:** Пожалуйста, не вводите конфиденциальные персональные данные (ФИО, телефоны, email). "
    "Очевидные контакты фильтруются автоматически на стороне Python. ИИ не придумывает неизвестные параметры объекта."
)

col_input, col_output = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("📝 Исходные данные объекта")

    ROOM_CHOICES = [
        "Кухня-гостиная",
        "Гостиная",
        "Кухня",
        "Спальня",
        "Детская комната",
        "Прихожая / Холл",
        "Санузел / Ванная",
        "Кабинет",
        "Гардеробная",
        "Квартира-студия",
        "Другое помещение",
    ]

    current_room = st.session_state.get("room_type", "Кухня-гостиная")
    room_index = ROOM_CHOICES.index(current_room) if current_room in ROOM_CHOICES else len(ROOM_CHOICES) - 1

    room_type_selected = st.selectbox(
        "Назначение помещения *",
        options=ROOM_CHOICES,
        index=room_index,
        help="Выберите тип помещения из списка",
    )

    if room_type_selected == "Другое помещение":
        custom_room = st.text_input("Укажите назначение помещения *", value=st.session_state.get("custom_room", ""))
        actual_room_type = custom_room.strip()
    else:
        actual_room_type = room_type_selected

    col_area, col_style = st.columns(2)

    with col_area:
        area_val = st.text_input(
            "Площадь (м²) *",
            value=st.session_state.get("area", ""),
            placeholder="Например: 28.5",
            help="Укажите общую площадь помещения в квадратных метрах",
        )

    STYLE_CHOICES = [
        "Не определён / Требуется подбор",
        "Современный",
        "Минимализм",
        "Скандинавский",
        "Неоклассика",
        "Лофт",
        "Джапанди",
        "Прованс",
        "Эко-стиль",
    ]

    current_style = st.session_state.get("style", "Не определён / Требуется подбор")
    style_index = STYLE_CHOICES.index(current_style) if current_style in STYLE_CHOICES else 0

    with col_style:
        style_val = st.selectbox(
            "Желаемый стиль",
            options=STYLE_CHOICES,
            index=style_index,
        )

    budget_val = st.text_input(
        "Ориентировочный бюджет",
        value=st.session_state.get("budget", ""),
        placeholder="Например: 1 500 000 руб. (или оставьте пустым)",
        help="Если бюджет не указан, ИИ вынесет его в список уточняющих вопросов",
    )

    description_val = st.text_area(
        "Описание помещения и текущее состояние *",
        value=st.session_state.get("description", ""),
        placeholder="Высота потолков, форма комнаты, окна, стены, текущая отделка, особенности планировки...",
        height=130,
    )

    wishes_val = st.text_area(
        "Пожелания клиента",
        value=st.session_state.get("wishes", ""),
        placeholder="Пожелания по зонированию, любимые цвета, состав мебели, техника, места хранения...",
        height=100,
    )

    col_btn_submit, col_btn_clear = st.columns([2, 1])

    with col_btn_submit:
        submit_clicked = st.button("📋 Сформировать ТЗ", type="primary", use_container_width=True)

    with col_btn_clear:
        clear_clicked = st.button("🗑️ Очистить", use_container_width=True)

    if clear_clicked:
        reset_form()
        st.rerun()

    if submit_clicked:
        # Сохраняем актуальные значения в session_state
        st.session_state["room_type"] = actual_room_type
        st.session_state["area"] = area_val
        st.session_state["style"] = style_val
        st.session_state["budget"] = budget_val
        st.session_state["description"] = description_val
        st.session_state["wishes"] = wishes_val

        clean_style = style_val
        if clean_style and "Не определён" in clean_style:
            clean_style = ""

        with st.spinner("Анализируем вводные данные и формируем техническое задание..."):
            success, result_text = generate_interior_brief(
                room_type=actual_room_type,
                area=area_val,
                style=clean_style,
                budget=budget_val,
                description=description_val,
                wishes=wishes_val,
            )

        if success:
            st.session_state["result"] = result_text
            st.session_state["error"] = None
        else:
            st.session_state["error"] = result_text
            st.session_state["result"] = None

        st.rerun()

with col_output:
    st.subheader("📄 Результат формирования ТЗ")

    if st.session_state.get("error"):
        st.warning("### ⚠️ Обратите внимание\n\n" + st.session_state["error"])
    elif st.session_state.get("result"):
        st.markdown(st.session_state["result"])
    else:
        st.markdown(
            """
            *Заполните форму слева и нажмите кнопку **«Сформировать ТЗ»**.*  
            *Или воспользуйтесь готовыми примерами в боковой панели слева.*
            """
        )
