from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    qid: str
    label_en: str
    label_uk: str
    label_ru: str
    kind: str  # text|number|choice
    required: bool = True
    choices: list[str] | None = None

    def label(self, lang: str) -> str:
        if lang == "uk":
            return self.label_uk
        if lang == "ru":
            return self.label_ru
        return self.label_en


QUESTIONS: list[Question] = [
    Question("age", "Your age", "Ваш вік", "Ваш возраст", "number"),
    Question("sex", "Sex", "Стать", "Пол", "choice", choices=["male", "female"]),
    Question("height_cm", "Height (cm)", "Зріст (см)", "Рост (см)", "number"),
    Question("weight_kg", "Weight (kg)", "Вага (кг)", "Вес (кг)", "number"),
    Question("sleep_hours", "Average sleep per night (hours)", "Сон за ніч (год)", "Сон за ночь (часов)", "number"),
    Question("training", "Training per week (e.g., 3x gym + 2x cardio)", "Тренування на тиждень", "Тренировки в неделю", "text"),
    Question("nutrition", "Main nutrition style (e.g., high-protein, keto, balanced)", "Стиль харчування", "Стиль питания", "text"),
    Question("stress", "Stress level (1-10)", "Рівень стресу (1-10)", "Уровень стресса (1-10)", "number"),
    Question("smoking", "Do you smoke?", "Курите?", "Курите?", "choice", choices=["no", "sometimes", "yes"]),
    Question("alcohol", "Alcohol per week", "Алкоголь на тиждень", "Алкоголь в неделю", "text"),
    Question("conditions", "Known conditions / meds (optional)", "Хвороби / ліки (необов'язково)", "Болезни / лекарства (опционально)", "text", required=False),
    Question("goal", "Your 90-day goal (e.g., lose fat, improve sleep)", "Ціль на 90 днів", "Цель на 90 дней", "text"),
]


def validate_answer(q: Question, value: str) -> str:
    v = (value or "").strip()
    if q.required and not v:
        raise ValueError("This field is required")

    if not v:
        return v

    if q.kind == "number":
        try:
            float(v.replace(",", "."))
        except Exception as e:
            raise ValueError("Please enter a number") from e

    if q.kind == "choice":
        if q.choices and v not in q.choices:
            raise ValueError("Invalid choice")

    return v
