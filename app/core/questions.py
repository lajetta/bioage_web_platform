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
    Question("age", "Your age", "\u0412\u0430\u0448 \u0432\u0456\u043a", "\u0412\u0430\u0448 \u0432\u043e\u0437\u0440\u0430\u0441\u0442", "number"),
    Question("sex", "Sex", "\u0421\u0442\u0430\u0442\u044c", "\u041f\u043e\u043b", "choice", choices=["male", "female"]),
    Question("height_cm", "Height (cm)", "\u0417\u0440\u0456\u0441\u0442 (\u0441\u043c)", "\u0420\u043e\u0441\u0442 (\u0441\u043c)", "number"),
    Question("weight_kg", "Weight (kg)", "\u0412\u0430\u0433\u0430 (\u043a\u0433)", "\u0412\u0435\u0441 (\u043a\u0433)", "number"),
    Question("sleep_hours", "Average sleep per night (hours)", "\u0421\u043e\u043d \u0437\u0430 \u043d\u0456\u0447 (\u0433\u043e\u0434)", "\u0421\u043e\u043d \u0437\u0430 \u043d\u043e\u0447\u044c (\u0447\u0430\u0441\u043e\u0432)", "number"),
    Question("training", "Training per week (e.g., 3x gym + 2x cardio)", "\u0422\u0440\u0435\u043d\u0443\u0432\u0430\u043d\u043d\u044f \u043d\u0430 \u0442\u0438\u0436\u0434\u0435\u043d\u044c", "\u0422\u0440\u0435\u043d\u0438\u0440\u043e\u0432\u043a\u0438 \u0432 \u043d\u0435\u0434\u0435\u043b\u044e", "text"),
    Question("nutrition", "Main nutrition style (e.g., high-protein, keto, balanced)", "\u0421\u0442\u0438\u043b\u044c \u0445\u0430\u0440\u0447\u0443\u0432\u0430\u043d\u043d\u044f", "\u0421\u0442\u0438\u043b\u044c \u043f\u0438\u0442\u0430\u043d\u0438\u044f", "text"),
    Question("stress", "Stress level (1-10)", "\u0420\u0456\u0432\u0435\u043d\u044c \u0441\u0442\u0440\u0435\u0441\u0443 (1-10)", "\u0423\u0440\u043e\u0432\u0435\u043d\u044c \u0441\u0442\u0440\u0435\u0441\u0441\u0430 (1-10)", "number"),
    Question("smoking", "Do you smoke?", "\u041a\u0443\u0440\u0438\u0442\u0435?", "\u041a\u0443\u0440\u0438\u0442\u0435?", "choice", choices=["no", "sometimes", "yes"]),
    Question("alcohol", "Alcohol per week", "\u0410\u043b\u043a\u043e\u0433\u043e\u043b\u044c \u043d\u0430 \u0442\u0438\u0436\u0434\u0435\u043d\u044c", "\u0410\u043b\u043a\u043e\u0433\u043e\u043b\u044c \u0432 \u043d\u0435\u0434\u0435\u043b\u044e", "text"),
    Question("conditions", "Known conditions / meds (optional)", "\u0425\u0432\u043e\u0440\u043e\u0431\u0438 / \u043b\u0456\u043a\u0438 (\u043d\u0435\u043e\u0431\u043e\u0432'\u044f\u0437\u043a\u043e\u0432\u043e)", "\u0411\u043e\u043b\u0435\u0437\u043d\u0438 / \u043b\u0435\u043a\u0430\u0440\u0441\u0442\u0432\u0430 (\u043e\u043f\u0446\u0438\u043e\u043d\u0430\u043b\u044c\u043d\u043e)", "text", required=False),
    Question("goal", "Your 90-day goal (e.g., lose fat, improve sleep)", "\u0426\u0456\u043b\u044c \u043d\u0430 90 \u0434\u043d\u0456\u0432", "\u0426\u0435\u043b\u044c \u043d\u0430 90 \u0434\u043d\u0435\u0439", "text"),
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
