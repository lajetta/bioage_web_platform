from __future__ import annotations

import json
from typing import Any

from app.core.settings import settings


def _mock_report(answers: dict[str, Any], lang: str) -> dict[str, Any]:
    return {
        "disclaimer": "This report is educational and not medical advice.",
        "summary": {
            "bioage_estimate": "N/A (mock)",
            "key_focus": ["sleep", "nutrition", "training", "stress"],
        },
        "plan_90_days": [
            {"week": 1, "focus": "baseline", "actions": ["Track sleep", "Daily walk 30 min", "Protein target"]},
            {"week": 2, "focus": "consistency", "actions": ["Strength 3x", "Bedtime routine", "Hydration"]},
        ],
        "answers": answers,
        "language": lang,
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

        schema = {
            "type": "object",
            "properties": {
                "disclaimer": {"type": "string"},
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
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["disclaimer", "summary", "plan_90_days"],
        }

        prompt = (
            "You are a longevity coach. Create a founder-led, clean medical style 90-day plan. "
            "Return JSON only. Language: " + lang + ".\n\n"
            "Assessment answers (JSON):\n" + json.dumps(answers, ensure_ascii=False)
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
        return data
    except Exception:
        return _mock_report(answers, lang)
