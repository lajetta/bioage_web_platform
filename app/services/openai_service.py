from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from app.core.questions import QUESTIONS
from app.core.settings import settings


def _local(lang: str, en: str, uk: str, ru: str) -> str:
    if lang == "uk":
        return uk
    if lang == "ru":
        return ru
    return en


def _json_text(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[\u0400-\u04FF]", text))


def _is_wrong_language(data: dict[str, Any], lang: str) -> bool:
    if lang not in {"uk", "ru"}:
        return False
    text = _json_text(data)
    if not text.strip():
        return False
    return not _has_cyrillic(text)


def _translate_report_json(client: Any, data: dict[str, Any], lang: str, schema: dict[str, Any]) -> dict[str, Any] | None:
    prompt = (
        "Translate all string values in this JSON to language code "
        + lang
        + ". Keep structure, keys, arrays, and numeric values unchanged. Return JSON only.\n\n"
        + _json_text(data)
    )
    try:
        resp = client.responses.create(
            model=settings.openai_model,
            input=[{"role": "user", "content": prompt}],
            response_format={"type": "json_schema", "json_schema": {"name": "bioage_report_translated", "schema": schema}},
        )
        out = json.loads(resp.output_text)
        if isinstance(out, dict):
            return out
    except Exception:
        pass
    return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(str(value).replace(",", ".").strip())
    except Exception:
        return None


def _assessment_context(answers: dict[str, Any], lang: str) -> dict[str, Any]:
    label_map = {q.qid: q.label(lang) for q in QUESTIONS}
    labeled_answers = []
    for q in QUESTIONS:
        labeled_answers.append(
            {
                "id": q.qid,
                "label": label_map[q.qid],
                "value": answers.get(q.qid, ""),
            }
        )

    age = _to_float(answers.get("age"))
    height_cm = _to_float(answers.get("height_cm"))
    weight_kg = _to_float(answers.get("weight_kg"))
    sleep_hours = _to_float(answers.get("sleep_hours"))
    stress = _to_float(answers.get("stress"))
    bmi = None
    if height_cm and height_cm > 0 and weight_kg and weight_kg > 0:
        h_m = height_cm / 100.0
        bmi = round(weight_kg / (h_m * h_m), 1)

    return {
        "generated_at_utc": datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat(),
        "raw_answers": answers,
        "answers_labeled": labeled_answers,
        "derived_metrics": {
            "age": age,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "sleep_hours": sleep_hours,
            "stress_1_10": stress,
            "bmi": bmi,
        },
    }


def _mock_report(answers: dict[str, Any], lang: str) -> dict[str, Any]:
    ctx = _assessment_context(answers, lang)
    return {
        "title": _local(
            lang,
            "BioAge Reset Protocol - 90-Day Plan",
            "BioAge Reset Protocol - 90-\u0434\u0435\u043d\u043d\u0438\u0439 \u043f\u043b\u0430\u043d",
            "BioAge Reset Protocol - 90-\u0434\u043d\u0435\u0432\u043d\u044b\u0439 \u043f\u043b\u0430\u043d",
        ),
        "generated_at_utc": ctx["generated_at_utc"],
        "language": lang,
        "disclaimer": _local(
            lang,
            "This report is educational and not medical advice.",
            "\u0426\u0435\u0439 \u0437\u0432\u0456\u0442 \u043c\u0430\u0454 \u043e\u0441\u0432\u0456\u0442\u043d\u0456\u0439 \u0445\u0430\u0440\u0430\u043a\u0442\u0435\u0440 \u0456 \u043d\u0435 \u0454 \u043c\u0435\u0434\u0438\u0447\u043d\u043e\u044e \u043f\u043e\u0440\u0430\u0434\u043e\u044e.",
            "\u042d\u0442\u043e\u0442 \u043e\u0442\u0447\u0435\u0442 \u0438\u043c\u0435\u0435\u0442 \u043e\u0431\u0440\u0430\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c\u043d\u044b\u0439 \u0445\u0430\u0440\u0430\u043a\u0442\u0435\u0440 \u0438 \u043d\u0435 \u044f\u0432\u043b\u044f\u0435\u0442\u0441\u044f \u043c\u0435\u0434\u0438\u0446\u0438\u043d\u0441\u043a\u043e\u0439 \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438\u0435\u0439.",
        ),
        "profile": {
            "goal": str(answers.get("goal", "")).strip()
            or _local(lang, "Improve health markers and consistency", "\u041f\u043e\u043a\u0440\u0430\u0449\u0438\u0442\u0438 \u043f\u043e\u043a\u0430\u0437\u043d\u0438\u043a\u0438 \u0437\u0434\u043e\u0440\u043e\u0432'\u044f \u0456 \u0441\u0442\u0430\u0431\u0456\u043b\u044c\u043d\u0456\u0441\u0442\u044c", "\u0423\u043b\u0443\u0447\u0448\u0438\u0442\u044c \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u0438 \u0437\u0434\u043e\u0440\u043e\u0432\u044c\u044f \u0438 \u0441\u0442\u0430\u0431\u0438\u043b\u044c\u043d\u043e\u0441\u0442\u044c"),
            "derived_metrics": ctx["derived_metrics"],
        },
        "executive_summary": [
            "Focus on sleep regularity, strength training consistency, and nutrition quality.",
            "Keep stress under control with a daily recovery routine.",
        ],
        "priority_actions": [
            "Sleep 7.5-8.5 hours with fixed bedtime/wakeup window.",
            "Strength train 3x/week and walk 8k-10k steps daily.",
            "Protein-first meals and hydration target each day.",
        ],
        "risk_flags": [
            "If symptoms worsen or you have chronic conditions, consult a licensed clinician.",
        ],
        "summary": {
            "bioage_estimate": "N/A (mock)",
            "key_focus": ["sleep", "nutrition", "training", "stress"],
        },
        "plan_90_days": [
            {"week": 1, "focus": "baseline", "actions": ["Track sleep", "Daily walk 30 min", "Protein target"]},
            {"week": 2, "focus": "consistency", "actions": ["Strength 3x", "Bedtime routine", "Hydration"]},
        ],
        "phases": [
            {
                "name": "Days 1-30: Foundation",
                "objective": "Build routine and baseline consistency.",
                "habits": ["Track sleep", "Morning light", "Daily walk"],
                "training": ["2-3 strength sessions/week", "2 cardio sessions/week"],
                "nutrition": ["Protein target", "Whole-food meals", "Limit alcohol"],
                "recovery": ["Evening wind-down", "Stress breathing 10 min/day"],
            },
            {
                "name": "Days 31-60: Progression",
                "objective": "Increase workload gradually while maintaining recovery.",
                "habits": ["Step goal progression", "Weekly check-in"],
                "training": ["Progressive overload", "Zone-2 cardio"],
                "nutrition": ["Fiber target", "Meal timing consistency"],
                "recovery": ["1 deload day/week", "Screen cut-off before sleep"],
            },
            {
                "name": "Days 61-90: Optimization",
                "objective": "Refine plan based on adherence and response.",
                "habits": ["Review adherence", "Adjust weak points"],
                "training": ["Maintain intensity", "Technique quality"],
                "nutrition": ["Fine-tune calories", "Hydration and electrolytes"],
                "recovery": ["Stress-management consistency", "Recovery audit"],
            },
        ],
        "answers": answers,
        "next_steps": [
            _local(
                lang,
                "Repeat assessment in 30 days and compare trends.",
                "\u041f\u043e\u0432\u0442\u043e\u0440\u0456\u0442\u044c \u043e\u0446\u0456\u043d\u043a\u0443 \u0447\u0435\u0440\u0435\u0437 30 \u0434\u043d\u0456\u0432 \u0456 \u043f\u043e\u0440\u0456\u0432\u043d\u044f\u0439\u0442\u0435 \u0434\u0438\u043d\u0430\u043c\u0456\u043a\u0443.",
                "\u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435 \u043e\u0446\u0435\u043d\u043a\u0443 \u0447\u0435\u0440\u0435\u0437 30 \u0434\u043d\u0435\u0439 \u0438 \u0441\u0440\u0430\u0432\u043d\u0438\u0442\u0435 \u0434\u0438\u043d\u0430\u043c\u0438\u043a\u0443.",
            )
        ],
    }


def generate_report_json(answers: dict[str, Any], lang: str) -> dict[str, Any]:
    """Generate structured JSON for the PDF.

    If OPENAI_API_KEY is not set, returns a deterministic mock.
    """

    if not settings.openai_api_key:
        return _mock_report(answers, lang)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)

        ctx = _assessment_context(answers, lang)

        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "generated_at_utc": {"type": "string"},
                "language": {"type": "string"},
                "disclaimer": {"type": "string"},
                "profile": {
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string"},
                        "derived_metrics": {"type": "object"},
                    },
                    "required": ["goal", "derived_metrics"],
                },
                "executive_summary": {"type": "array", "items": {"type": "string"}},
                "priority_actions": {"type": "array", "items": {"type": "string"}},
                "risk_flags": {"type": "array", "items": {"type": "string"}},
                "summary": {
                    "type": "object",
                    "properties": {
                        "bioage_estimate": {"type": "string"},
                        "key_focus": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["bioage_estimate", "key_focus"],
                },
                "plan_90_days": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "week": {"type": "integer"},
                            "focus": {"type": "string"},
                            "actions": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["week", "focus", "actions"],
                    },
                },
                "phases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "objective": {"type": "string"},
                            "habits": {"type": "array", "items": {"type": "string"}},
                            "training": {"type": "array", "items": {"type": "string"}},
                            "nutrition": {"type": "array", "items": {"type": "string"}},
                            "recovery": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["name", "objective", "habits", "training", "nutrition", "recovery"],
                    },
                },
                "warnings": {"type": "array", "items": {"type": "string"}},
                "next_steps": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "generated_at_utc", "language", "disclaimer", "summary", "plan_90_days"],
        }

        prompt = (
            "You are a founder-level longevity coach creating a practical educational report.\n"
            "Hard requirements:\n"
            "1) Return valid JSON only.\n"
            "2) Language must be exactly: " + lang + ".\n"
            "3) Be specific and actionable, but non-diagnostic and non-prescriptive.\n"
            "4) Keep tone clinical, concise, and structured.\n"
            "5) Use the user's goals and metrics to personalize priorities.\n\n"
            "Assessment context (JSON):\n" + json.dumps(ctx, ensure_ascii=False)
        )

        # Use Responses API if available; fall back to chat.
        try:
            resp = client.responses.create(
                model=settings.openai_model,
                input=[{"role": "user", "content": prompt}],
                response_format={"type": "json_schema", "json_schema": {"name": "bioage_report", "schema": schema}},
            )
            text = resp.output_text
        except Exception:
            chat = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": prompt + "\n\nJSON schema:\n" + json.dumps(schema)},
                ],
                temperature=0.2,
            )
            text = chat.choices[0].message.content or "{}"

        data = json.loads(text)
        # basic validation
        if not isinstance(data, dict) or "plan_90_days" not in data:
            return _mock_report(answers, lang)
        data.setdefault("language", lang)
        data.setdefault("generated_at_utc", ctx["generated_at_utc"])
        data.setdefault("title", "BioAge Reset Protocol - 90-Day Plan")
        data.setdefault("profile", {"goal": str(answers.get("goal", "")), "derived_metrics": ctx["derived_metrics"]})
        data.setdefault("executive_summary", [])
        data.setdefault("priority_actions", [])
        data.setdefault("risk_flags", [])
        data.setdefault("phases", [])
        data.setdefault("next_steps", [])
        if not isinstance(data.get("summary"), dict):
            data["summary"] = {"bioage_estimate": "N/A", "key_focus": []}
        if not isinstance(data.get("plan_90_days"), list):
            data["plan_90_days"] = []
        # For RU/UK, force a translation pass to avoid partial English blocks.
        if lang in {"uk", "ru"}:
            translated = _translate_report_json(client, data, lang, schema)
            if isinstance(translated, dict):
                data = translated
            if _is_wrong_language(data, lang):
                # Fallback to deterministic localized report if model ignored target language.
                return _mock_report(answers, lang)
        return data
    except Exception:
        return _mock_report(answers, lang)
