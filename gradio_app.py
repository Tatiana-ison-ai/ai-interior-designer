"""
Веб-приложение «AI-помощник дизайнера интерьера» на Gradio.
Формирует структурированное первичное ТЗ и список вопросов заказчику
на базе OpenRouter API без додумывания фактов.
"""

import os
from typing import Tuple
import gradio as gr

from sanitizer import PII_DISCLAIMER
from openrouter_client import generate_interior_brief, DEFAULT_MODEL


def process_brief(
    room_type: str,
    area: str,
    style: str,
    budget: str,
    description: str,
    wishes: str,
) -> str:
    """
    Обработчик нажатия кнопки «Сформировать ТЗ».
    Использует логику валидации, маскирования PII и вызова OpenRouter API из openrouter_client.py.
    """
    clean_style = style
    if clean_style and "Не определён" in clean_style:
        clean_style = ""

    success, result = generate_interior_brief(
        room_type=room_type,
        area=area,
        style=clean_style,
        budget=budget,
        description=description,
        wishes=wishes,
    )

    if not success:
        return (
            f"### ⚠️ Обратите внимание\n\n"
            f"{result}\n\n"
            f"---\n"
            f"*Пожалуйста, скорректируйте введённые данные или проверьте настройки ключа.*"
        )

    return result


def clear_form() -> Tuple[str, str, str, str, str, str, str]:
    """Сбрасывает все поля формы и блок вывода в исходное состояние."""
    return (
        "",
        "",
        "Не определён / Требуется подбор",
        "",
        "",
        "",
        "*Здесь появится сформированное ТЗ и список вопросов к заказчику...*",
    )


def create_app() -> gr.Blocks:
    """Создаёт интерфейс Gradio с настройкой компонентов, темы и примеров."""
    theme = gr.themes.Soft(
        primary_hue="indigo",
        secondary_hue="slate",
        font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
    )

    with gr.Blocks(title="AI-помощник дизайнера интерьера") as demo:
        gr.Markdown(
            """
            # 🛋️ AI-помощник дизайнера интерьера
            Инструмент для составления первичного технического задания (ТЗ) дизайн-проекта на основе фактов.
            
            > 🛡️ **Конфиденциальность и безопасность:**  
            > *Пожалуйста, не вводите конфиденциальные персональные данные (ФИО, телефоны, email).*  
            > *Очевидные контактные данные фильтруются автоматически. ИИ не придумывает неизвестные параметры объекта.*
            """
        )

        with gr.Row():
            # Левая колонка: форма ввода данных
            with gr.Column(scale=1):
                gr.Markdown("### 📝 Исходные данные объекта")

                room_type_input = gr.Dropdown(
                    label="Назначение помещения *",
                    choices=[
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
                    ],
                    value="Кухня-гостиная",
                    allow_custom_value=True,
                    info="Выберите из списка или введите своё название",
                )

                with gr.Row():
                    area_input = gr.Textbox(
                        label="Площадь помещения (м²) *",
                        placeholder="Например: 28.5",
                        info="Только число в м²",
                    )
                    style_input = gr.Dropdown(
                        label="Желаемый стиль",
                        choices=[
                            "Не определён / Требуется подбор",
                            "Современный",
                            "Минимализм",
                            "Скандинавский",
                            "Неоклассика",
                            "Лофт",
                            "Джапанди",
                            "Прованс",
                            "Эко-стиль",
                        ],
                        value="Не определён / Требуется подбор",
                        allow_custom_value=True,
                    )

                budget_input = gr.Textbox(
                    label="Ориентировочный бюджет",
                    placeholder="Например: 1 500 000 руб. (или оставьте пустым)",
                    info="Если не указан, ИИ вынесет бюджет в раздел вопросов",
                )

                description_input = gr.Textbox(
                    label="Описание помещения и текущее состояние *",
                    placeholder="Высота потолков, форма комнаты, окна, стены, текущая отделка, особенности планировки...",
                    lines=4,
                )

                wishes_input = gr.Textbox(
                    label="Пожелания клиента",
                    placeholder="Пожелания по зонированию, любимые цвета, состав мебели, техника, места хранения...",
                    lines=3,
                )

                with gr.Row():
                    submit_btn = gr.Button("📋 Сформировать ТЗ", variant="primary", scale=2)
                    clear_btn = gr.Button("🗑️ Очистить", variant="secondary", scale=1)

            # Правая колонка: отображение результатов
            with gr.Column(scale=1):
                gr.Markdown("### 📄 Результат формирования ТЗ")
                output_display = gr.Markdown(
                    value="*Заполните форму слева и нажмите **«Сформировать ТЗ»**.*",
                    line_breaks=True,
                )

        # Интерактивные примеры для быстрого тестирования
        gr.Markdown("### 💡 Примеры для проверки сценариев")
        gr.Examples(
            examples=[
                [
                    "Гостиная",
                    "32",
                    "Неоклассика",
                    "2 500 000 руб.",
                    "Высота потолков 3.1 м, панорамные окна в пол, черновая отделка.",
                    "Каминная зона, светлые тона, паркет елочкой, акцентная люстра.",
                ],
                [
                    "Кухня",
                    "14",
                    "Не определён / Требуется подбор",
                    "",
                    "Новостройка, бетонные стены без отделки, выводы под раковину в углу.",
                    "Организовать удобную рабочую зону и обеденный стол на 4 персоны.",
                ],
                [
                    "Гардеробная",
                    "3.5",
                    "Минимализм",
                    "150 000 руб.",
                    "Узкая ниша в коридоре, высота потолка 2.7 м.",
                    "Максимум полок до потолка, зеркало, светодиодная подсветка.",
                ],
            ],
            inputs=[
                room_type_input,
                area_input,
                style_input,
                budget_input,
                description_input,
                wishes_input,
            ],
            label="Нажмите на любой пример, чтобы заполнить поля",
        )

        # Привязка событий клика
        submit_btn.click(
            fn=process_brief,
            inputs=[
                room_type_input,
                area_input,
                style_input,
                budget_input,
                description_input,
                wishes_input,
            ],
            outputs=output_display,
        )

        clear_btn.click(
            fn=clear_form,
            inputs=[],
            outputs=[
                room_type_input,
                area_input,
                style_input,
                budget_input,
                description_input,
                wishes_input,
                output_display,
            ],
        )

    # Сохраняем тему в объекте для передачи в launch
    demo.theme = theme
    return demo


demo = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    # В Gradio 6 theme передаётся в launch()
    try:
        demo.launch(server_name="0.0.0.0", server_port=port, theme=getattr(demo, "theme", None))
    except TypeError:
        demo.launch(server_name="0.0.0.0", server_port=port)
