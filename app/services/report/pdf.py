from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from app.core.questions import QUESTIONS


_L10N: dict[str, dict[str, str]] = {
    "en": {
        "cover_title": "BioAge Reset Protocol",
        "cover_subtitle": "Personalized 90-Day Optimization Report",
        "cover_disclaimer": "Educational report. Not medical advice.",
        "generated": "Generated (UTC)",
        "client_profile": "Client Profile",
        "goal": "Goal",
        "metric": "Metric",
        "value": "Value",
        "executive_summary": "Executive Summary",
        "priority_actions": "Priority Actions",
        "section_scores": "Section Scores",
        "section": "Section",
        "score_100": "Score (100)",
        "notes": "Notes",
        "summary": "Summary",
        "bioage_estimate": "BioAge estimate",
        "key_focus": "Key focus",
        "plan_weekly": "90-day plan (weekly)",
        "week": "Week",
        "focus": "Focus",
        "actions": "Actions",
        "phases": "90-Day Phases",
        "objective": "Objective",
        "habits": "Habits",
        "training": "Training",
        "nutrition": "Nutrition",
        "recovery": "Recovery",
        "safety_notes": "Safety Notes",
        "next_steps": "Next Steps",
        "assessment_snapshot": "Assessment Snapshot",
    },
    "uk": {
        "cover_title": "BioAge Reset Protocol",
        "cover_subtitle": "\u041f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u0456\u0437\u043e\u0432\u0430\u043d\u0438\u0439 90-\u0434\u0435\u043d\u043d\u0438\u0439 \u0437\u0432\u0456\u0442 \u043e\u043f\u0442\u0438\u043c\u0456\u0437\u0430\u0446\u0456\u0457",
        "cover_disclaimer": "\u041e\u0441\u0432\u0456\u0442\u043d\u0456\u0439 \u0437\u0432\u0456\u0442. \u041d\u0435 \u0454 \u043c\u0435\u0434\u0438\u0447\u043d\u043e\u044e \u043f\u043e\u0440\u0430\u0434\u043e\u044e.",
        "generated": "\u0421\u0442\u0432\u043e\u0440\u0435\u043d\u043e (UTC)",
        "client_profile": "\u041f\u0440\u043e\u0444\u0456\u043b\u044c \u043a\u043b\u0456\u0454\u043d\u0442\u0430",
        "goal": "\u0426\u0456\u043b\u044c",
        "metric": "\u041c\u0435\u0442\u0440\u0438\u043a\u0430",
        "value": "\u0417\u043d\u0430\u0447\u0435\u043d\u043d\u044f",
        "executive_summary": "\u041a\u043e\u0440\u043e\u0442\u043a\u0438\u0439 \u0432\u0438\u0441\u043d\u043e\u0432\u043e\u043a",
        "priority_actions": "\u041f\u0440\u0456\u043e\u0440\u0438\u0442\u0435\u0442\u043d\u0456 \u0434\u0456\u0457",
        "section_scores": "\u041e\u0446\u0456\u043d\u043a\u0430 \u0440\u043e\u0437\u0434\u0456\u043b\u0456\u0432",
        "section": "\u0420\u043e\u0437\u0434\u0456\u043b",
        "score_100": "\u041e\u0446\u0456\u043d\u043a\u0430 (100)",
        "notes": "\u041d\u043e\u0442\u0430\u0442\u043a\u0438",
        "summary": "\u041f\u0456\u0434\u0441\u0443\u043c\u043e\u043a",
        "bioage_estimate": "\u041e\u0446\u0456\u043d\u043a\u0430 BioAge",
        "key_focus": "\u041a\u043b\u044e\u0447\u043e\u0432\u0438\u0439 \u0444\u043e\u043a\u0443\u0441",
        "plan_weekly": "90-\u0434\u0435\u043d\u043d\u0438\u0439 \u043f\u043b\u0430\u043d (\u043f\u043e \u0442\u0438\u0436\u043d\u044f\u0445)",
        "week": "\u0422\u0438\u0436\u0434\u0435\u043d\u044c",
        "focus": "\u0424\u043e\u043a\u0443\u0441",
        "actions": "\u0414\u0456\u0457",
        "phases": "\u0424\u0430\u0437\u0438 90 \u0434\u043d\u0456\u0432",
        "objective": "\u041c\u0435\u0442\u0430",
        "habits": "\u0417\u0432\u0438\u0447\u043a\u0438",
        "training": "\u0422\u0440\u0435\u043d\u0443\u0432\u0430\u043d\u043d\u044f",
        "nutrition": "\u0425\u0430\u0440\u0447\u0443\u0432\u0430\u043d\u043d\u044f",
        "recovery": "\u0412\u0456\u0434\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f",
        "safety_notes": "\u041d\u043e\u0442\u0430\u0442\u043a\u0438 \u0437 \u0431\u0435\u0437\u043f\u0435\u043a\u0438",
        "next_steps": "\u041d\u0430\u0441\u0442\u0443\u043f\u043d\u0456 \u043a\u0440\u043e\u043a\u0438",
        "assessment_snapshot": "\u0417\u043d\u0456\u043c\u043e\u043a \u0430\u043d\u043a\u0435\u0442\u0438",
    },
    "ru": {
        "cover_title": "BioAge Reset Protocol",
        "cover_subtitle": "\u041f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u0438\u0437\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0439 90-\u0434\u043d\u0435\u0432\u043d\u044b\u0439 \u043e\u0442\u0447\u0435\u0442 \u043e\u043f\u0442\u0438\u043c\u0438\u0437\u0430\u0446\u0438\u0438",
        "cover_disclaimer": "\u041e\u0431\u0440\u0430\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c\u043d\u044b\u0439 \u043e\u0442\u0447\u0435\u0442. \u041d\u0435 \u043c\u0435\u0434\u0438\u0446\u0438\u043d\u0441\u043a\u0430\u044f \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438\u044f.",
        "generated": "\u0421\u0444\u043e\u0440\u043c\u0438\u0440\u043e\u0432\u0430\u043d\u043e (UTC)",
        "client_profile": "\u041f\u0440\u043e\u0444\u0438\u043b\u044c \u043a\u043b\u0438\u0435\u043d\u0442\u0430",
        "goal": "\u0426\u0435\u043b\u044c",
        "metric": "\u041c\u0435\u0442\u0440\u0438\u043a\u0430",
        "value": "\u0417\u043d\u0430\u0447\u0435\u043d\u0438\u0435",
        "executive_summary": "\u041a\u0440\u0430\u0442\u043a\u043e\u0435 \u0440\u0435\u0437\u044e\u043c\u0435",
        "priority_actions": "\u041f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442\u043d\u044b\u0435 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f",
        "section_scores": "\u041e\u0446\u0435\u043d\u043a\u0430 \u0440\u0430\u0437\u0434\u0435\u043b\u043e\u0432",
        "section": "\u0420\u0430\u0437\u0434\u0435\u043b",
        "score_100": "\u041e\u0446\u0435\u043d\u043a\u0430 (100)",
        "notes": "\u0417\u0430\u043c\u0435\u0442\u043a\u0438",
        "summary": "\u0418\u0442\u043e\u0433",
        "bioage_estimate": "\u041e\u0446\u0435\u043d\u043a\u0430 BioAge",
        "key_focus": "\u041a\u043b\u044e\u0447\u0435\u0432\u043e\u0439 \u0444\u043e\u043a\u0443\u0441",
        "plan_weekly": "90-\u0434\u043d\u0435\u0432\u043d\u044b\u0439 \u043f\u043b\u0430\u043d (\u043f\u043e \u043d\u0435\u0434\u0435\u043b\u044f\u043c)",
        "week": "\u041d\u0435\u0434\u0435\u043b\u044f",
        "focus": "\u0424\u043e\u043a\u0443\u0441",
        "actions": "\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u044f",
        "phases": "\u0424\u0430\u0437\u044b 90 \u0434\u043d\u0435\u0439",
        "objective": "\u0426\u0435\u043b\u044c",
        "habits": "\u041f\u0440\u0438\u0432\u044b\u0447\u043a\u0438",
        "training": "\u0422\u0440\u0435\u043d\u0438\u0440\u043e\u0432\u043a\u0438",
        "nutrition": "\u041f\u0438\u0442\u0430\u043d\u0438\u0435",
        "recovery": "\u0412\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435",
        "safety_notes": "\u0417\u0430\u043c\u0435\u0442\u043a\u0438 \u043f\u043e \u0431\u0435\u0437\u043e\u043f\u0430\u0441\u043d\u043e\u0441\u0442\u0438",
        "next_steps": "\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0435 \u0448\u0430\u0433\u0438",
        "assessment_snapshot": "\u0421\u043d\u0438\u043c\u043e\u043a \u0430\u043d\u043a\u0435\u0442\u044b",
    },
}


def _t(lang: str, key: str) -> str:
    base = _L10N.get(lang, _L10N["en"])
    return base.get(key, _L10N["en"].get(key, key))


def _register_unicode_fonts() -> tuple[str, str]:
    preferred_pairs = [
        ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf"),
        ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
        ("Arial.ttf", "Arialbd.ttf"),
    ]
    search_roots = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path("C:/Windows/Fonts"),
    ]

    def find_font(name: str) -> str:
        for root in search_roots:
            if not root.exists():
                continue
            direct = root / name
            if direct.is_file():
                return str(direct)
            try:
                for path in root.rglob(name):
                    if path.is_file():
                        return str(path)
            except Exception:
                continue
        return ""

    regular = ""
    bold = ""
    for regular_name, bold_name in preferred_pairs:
        regular = find_font(regular_name)
        bold = find_font(bold_name)
        if regular and bold:
            break
    if regular and bold:
        if "BioAgeUnicode" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("BioAgeUnicode", regular))
        if "BioAgeUnicodeBold" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("BioAgeUnicodeBold", bold))
        print(f"[report-pdf] Unicode fonts: regular={regular} bold={bold}")
        return "BioAgeUnicode", "BioAgeUnicodeBold"
    print("[report-pdf] Unicode fonts not found, falling back to Helvetica")
    return "Helvetica", "Helvetica-Bold"


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(str(value).replace(",", ".").strip())
    except Exception:
        return None


def _clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, v))


def _safe_lines(values: list[Any] | None) -> str:
    if not values:
        return "-"
    parts = [str(v).strip() for v in values if str(v).strip()]
    return "<br/>".join(f"- {p}" for p in parts) if parts else "-"


def _compute_section_scores(answers: dict[str, Any], lang: str) -> list[dict[str, str | int]]:
    def loc(en: str, uk: str, ru: str) -> str:
        if lang == "uk":
            return uk
        if lang == "ru":
            return ru
        return en

    sleep_h = _to_float(answers.get("sleep_hours"))
    stress = _to_float(answers.get("stress"))
    smoking = str(answers.get("smoking", "")).lower()
    training = str(answers.get("training", "")).lower()
    nutrition = str(answers.get("nutrition", "")).lower()
    alcohol = str(answers.get("alcohol", "")).lower()

    sleep_score = 60
    sleep_note = loc("No sleep data.", "\u041d\u0435\u043c\u0430\u0454 \u0434\u0430\u043d\u0438\u0445 \u043f\u0440\u043e \u0441\u043e\u043d.", "\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u043e \u0441\u043d\u0435.")
    if sleep_h is not None:
        if 7 <= sleep_h <= 9:
            sleep_score, sleep_note = 90, loc("Sleep duration is in target range.", "\u0422\u0440\u0438\u0432\u0430\u043b\u0456\u0441\u0442\u044c \u0441\u043d\u0443 \u0432 \u0446\u0456\u043b\u044c\u043e\u0432\u043e\u043c\u0443 \u0434\u0456\u0430\u043f\u0430\u0437\u043e\u043d\u0456.", "\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c \u0441\u043d\u0430 \u0432 \u0446\u0435\u043b\u0435\u0432\u043e\u043c \u0434\u0438\u0430\u043f\u0430\u0437\u043e\u043d\u0435.")
        elif 6 <= sleep_h < 7 or 9 < sleep_h <= 10:
            sleep_score, sleep_note = 75, loc("Sleep is acceptable but can be optimized.", "\u0421\u043e\u043d \u043f\u0440\u0438\u0439\u043d\u044f\u0442\u043d\u0438\u0439, \u0430\u043b\u0435 \u0454 \u043f\u043e\u0442\u0435\u043d\u0446\u0456\u0430\u043b \u0434\u043b\u044f \u043f\u043e\u043a\u0440\u0430\u0449\u0435\u043d\u043d\u044f.", "\u0421\u043e\u043d \u043f\u0440\u0438\u0435\u043c\u043b\u0435\u043c\u044b\u0439, \u043d\u043e \u0435\u0433\u043e \u043c\u043e\u0436\u043d\u043e \u0443\u043b\u0443\u0447\u0448\u0438\u0442\u044c.")
        elif 5 <= sleep_h < 6:
            sleep_score, sleep_note = 55, loc("Sleep appears short; increase consistency.", "\u0421\u043e\u043d \u0432\u0438\u0433\u043b\u044f\u0434\u0430\u0454 \u043a\u043e\u0440\u043e\u0442\u043a\u0438\u043c; \u043f\u0456\u0434\u0432\u0438\u0449\u0456\u0442\u044c \u0441\u0442\u0430\u0431\u0456\u043b\u044c\u043d\u0456\u0441\u0442\u044c.", "\u0421\u043e\u043d, \u043f\u043e\u0445\u043e\u0436\u0435, \u043a\u043e\u0440\u043e\u0442\u043a\u0438\u0439; \u043f\u043e\u0432\u044b\u0441\u044c\u0442\u0435 \u0441\u0442\u0430\u0431\u0438\u043b\u044c\u043d\u043e\u0441\u0442\u044c.")
        else:
            sleep_score, sleep_note = 40, loc("Sleep duration likely limits recovery.", "\u0422\u0440\u0438\u0432\u0430\u043b\u0456\u0441\u0442\u044c \u0441\u043d\u0443, \u0439\u043c\u043e\u0432\u0456\u0440\u043d\u043e, \u043e\u0431\u043c\u0435\u0436\u0443\u0454 \u0432\u0456\u0434\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f.", "\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c \u0441\u043d\u0430, \u0432\u0435\u0440\u043e\u044f\u0442\u043d\u043e, \u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0438\u0432\u0430\u0435\u0442 \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435.")

    activity_score = 60
    activity_note = loc("Training details are limited.", "\u0414\u0430\u043d\u0438\u0445 \u043f\u0440\u043e \u0442\u0440\u0435\u043d\u0443\u0432\u0430\u043d\u043d\u044f \u043d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043d\u044c\u043e.", "\u0414\u0430\u043d\u043d\u044b\u0445 \u043e \u0442\u0440\u0435\u043d\u0438\u0440\u043e\u0432\u043a\u0430\u0445 \u043d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e.")
    if "3" in training or "4" in training or "5" in training:
        activity_score, activity_note = 85, loc("Training frequency appears strong.", "\u0427\u0430\u0441\u0442\u043e\u0442\u0430 \u0442\u0440\u0435\u043d\u0443\u0432\u0430\u043d\u044c \u0432\u0438\u0433\u043b\u044f\u0434\u0430\u0454 \u0434\u043e\u0431\u0440\u0435.", "\u0427\u0430\u0441\u0442\u043e\u0442\u0430 \u0442\u0440\u0435\u043d\u0438\u0440\u043e\u0432\u043e\u043a \u0432\u044b\u0433\u043b\u044f\u0434\u0438\u0442 \u0441\u0438\u043b\u044c\u043d\u043e\u0439.")
    elif "2" in training:
        activity_score, activity_note = 72, loc("Moderate activity; progression recommended.", "\u041f\u043e\u043c\u0456\u0440\u043d\u0430 \u0430\u043a\u0442\u0438\u0432\u043d\u0456\u0441\u0442\u044c; \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u043e\u0432\u0430\u043d\u043e \u043f\u0440\u043e\u0433\u0440\u0435\u0441\u0456\u044e.", "\u0423\u043c\u0435\u0440\u0435\u043d\u043d\u0430\u044f \u0430\u043a\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u044c; \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0443\u0435\u0442\u0441\u044f \u043f\u0440\u043e\u0433\u0440\u0435\u0441\u0441\u0438\u044f.")
    elif training.strip():
        activity_score, activity_note = 62, loc("Activity exists but structure can improve.", "\u0410\u043a\u0442\u0438\u0432\u043d\u0456\u0441\u0442\u044c \u0454, \u0430\u043b\u0435 \u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0443 \u0432\u0430\u0440\u0442\u043e \u043f\u043e\u043a\u0440\u0430\u0449\u0438\u0442\u0438.", "\u0410\u043a\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u044c \u0435\u0441\u0442\u044c, \u043d\u043e \u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0443 \u0441\u0442\u043e\u0438\u0442 \u0443\u043b\u0443\u0447\u0448\u0438\u0442\u044c.")

    nutrition_score = 65
    nutrition_note = loc("Nutrition pattern needs consistency.", "\u0420\u0435\u0436\u0438\u043c \u0445\u0430\u0440\u0447\u0443\u0432\u0430\u043d\u043d\u044f \u043f\u043e\u0442\u0440\u0435\u0431\u0443\u0454 \u0441\u0442\u0430\u0431\u0456\u043b\u044c\u043d\u043e\u0441\u0442\u0456.", "\u0420\u0435\u0436\u0438\u043c \u043f\u0438\u0442\u0430\u043d\u0438\u044f \u043d\u0443\u0436\u0434\u0430\u0435\u0442\u0441\u044f \u0432 \u0441\u0442\u0430\u0431\u0438\u043b\u044c\u043d\u043e\u0441\u0442\u0438.")
    if "protein" in nutrition or "balanced" in nutrition:
        nutrition_score, nutrition_note = 82, loc("Nutrition style looks supportive.", "\u0421\u0442\u0438\u043b\u044c \u0445\u0430\u0440\u0447\u0443\u0432\u0430\u043d\u043d\u044f \u0432\u0438\u0433\u043b\u044f\u0434\u0430\u0454 \u0441\u043f\u0440\u0438\u044f\u0442\u043b\u0438\u0432\u0438\u043c.", "\u0421\u0442\u0438\u043b\u044c \u043f\u0438\u0442\u0430\u043d\u0438\u044f \u0432\u044b\u0433\u043b\u044f\u0434\u0438\u0442 \u043f\u043e\u0434\u0445\u043e\u0434\u044f\u0449\u0438\u043c.")
    if "keto" in nutrition:
        nutrition_score = max(nutrition_score, 75)
        nutrition_note = loc("Structured approach; monitor adherence and recovery.", "\u0421\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u043e\u0432\u0430\u043d\u0438\u0439 \u043f\u0456\u0434\u0445\u0456\u0434; \u0441\u0442\u0435\u0436\u0442\u0435 \u0437\u0430 \u0434\u043e\u0442\u0440\u0438\u043c\u0430\u043d\u043d\u044f\u043c \u0442\u0430 \u0432\u0456\u0434\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f\u043c.", "\u0421\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u043d\u044b\u0439 \u043f\u043e\u0434\u0445\u043e\u0434; \u043e\u0442\u0441\u043b\u0435\u0436\u0438\u0432\u0430\u0439\u0442\u0435 \u043f\u0440\u0438\u0432\u0435\u0440\u0436\u0435\u043d\u043d\u043e\u0441\u0442\u044c \u0438 \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435.")
    if "daily" in alcohol or "every day" in alcohol:
        nutrition_score = _clamp(nutrition_score - 18)
        nutrition_note = loc("Frequent alcohol can reduce recovery quality.", "\u0427\u0430\u0441\u0442\u0435 \u0432\u0436\u0438\u0432\u0430\u043d\u043d\u044f \u0430\u043b\u043a\u043e\u0433\u043e\u043b\u044e \u043c\u043e\u0436\u0435 \u0437\u043d\u0438\u0436\u0443\u0432\u0430\u0442\u0438 \u044f\u043a\u0456\u0441\u0442\u044c \u0432\u0456\u0434\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f.", "\u0427\u0430\u0441\u0442\u043e\u0435 \u0443\u043f\u043e\u0442\u0440\u0435\u0431\u043b\u0435\u043d\u0438\u0435 \u0430\u043b\u043a\u043e\u0433\u043e\u043b\u044f \u043c\u043e\u0436\u0435\u0442 \u0441\u043d\u0438\u0436\u0430\u0442\u044c \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u043e \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f.")

    recovery_score = 65
    recovery_note = loc("Stress management should be monitored.", "\u041a\u0435\u0440\u0443\u0432\u0430\u043d\u043d\u044f \u0441\u0442\u0440\u0435\u0441\u043e\u043c \u0441\u043b\u0456\u0434 \u043a\u043e\u043d\u0442\u0440\u043e\u043b\u044e\u0432\u0430\u0442\u0438.", "\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0441\u0442\u0440\u0435\u0441\u0441\u043e\u043c \u0441\u043b\u0435\u0434\u0443\u0435\u0442 \u043a\u043e\u043d\u0442\u0440\u043e\u043b\u0438\u0440\u043e\u0432\u0430\u0442\u044c.")
    if stress is not None:
        if stress <= 3:
            recovery_score, recovery_note = 88, loc("Low stress profile supports recovery.", "\u041d\u0438\u0437\u044c\u043a\u0438\u0439 \u0440\u0456\u0432\u0435\u043d\u044c \u0441\u0442\u0440\u0435\u0441\u0443 \u0441\u043f\u0440\u0438\u044f\u0454 \u0432\u0456\u0434\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044e.", "\u041d\u0438\u0437\u043a\u0438\u0439 \u0443\u0440\u043e\u0432\u0435\u043d\u044c \u0441\u0442\u0440\u0435\u0441\u0441\u0430 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0435\u0442 \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435.")
        elif stress <= 6:
            recovery_score, recovery_note = 72, loc("Moderate stress; maintain recovery routines.", "\u041f\u043e\u043c\u0456\u0440\u043d\u0438\u0439 \u0441\u0442\u0440\u0435\u0441; \u043f\u0456\u0434\u0442\u0440\u0438\u043c\u0443\u0439\u0442\u0435 \u0440\u0435\u0436\u0438\u043c \u0432\u0456\u0434\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f.", "\u0423\u043c\u0435\u0440\u0435\u043d\u043d\u044b\u0439 \u0441\u0442\u0440\u0435\u0441\u0441; \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0439\u0442\u0435 \u0440\u0435\u0436\u0438\u043c \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f.")
        elif stress <= 8:
            recovery_score, recovery_note = 55, loc("Elevated stress; add daily down-regulation.", "\u041f\u0456\u0434\u0432\u0438\u0449\u0435\u043d\u0438\u0439 \u0441\u0442\u0440\u0435\u0441; \u0434\u043e\u0434\u0430\u0439\u0442\u0435 \u0449\u043e\u0434\u0435\u043d\u043d\u0456 \u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0438 \u0432\u0456\u0434\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f.", "\u041f\u043e\u0432\u044b\u0448\u0435\u043d\u043d\u044b\u0439 \u0441\u0442\u0440\u0435\u0441\u0441; \u0434\u043e\u0431\u0430\u0432\u044c\u0442\u0435 \u0435\u0436\u0435\u0434\u043d\u0435\u0432\u043d\u044b\u0435 \u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0438 \u0441\u043d\u0438\u0436\u0435\u043d\u0438\u044f \u043d\u0430\u043f\u0440\u044f\u0436\u0435\u043d\u0438\u044f.")
        else:
            recovery_score, recovery_note = 42, loc("High stress likely affects progress.", "\u0412\u0438\u0441\u043e\u043a\u0438\u0439 \u0441\u0442\u0440\u0435\u0441, \u0439\u043c\u043e\u0432\u0456\u0440\u043d\u043e, \u0433\u0430\u043b\u044c\u043c\u0443\u0454 \u043f\u0440\u043e\u0433\u0440\u0435\u0441.", "\u0412\u044b\u0441\u043e\u043a\u0438\u0439 \u0441\u0442\u0440\u0435\u0441\u0441, \u0432\u0435\u0440\u043e\u044f\u0442\u043d\u043e, \u0442\u043e\u0440\u043c\u043e\u0437\u0438\u0442 \u043f\u0440\u043e\u0433\u0440\u0435\u0441\u0441.")

    risk_score = 80
    risk_note = loc("No major lifestyle risk marker detected.", "\u0421\u0443\u0442\u0442\u0454\u0432\u0438\u0445 \u043f\u043e\u0432\u0435\u0434\u0456\u043d\u043a\u043e\u0432\u0438\u0445 \u0444\u0430\u043a\u0442\u043e\u0440\u0456\u0432 \u0440\u0438\u0437\u0438\u043a\u0443 \u043d\u0435 \u0432\u0438\u044f\u0432\u043b\u0435\u043d\u043e.", "\u0421\u0435\u0440\u044c\u0435\u0437\u043d\u044b\u0445 \u043f\u043e\u0432\u0435\u0434\u0435\u043d\u0447\u0435\u0441\u043a\u0438\u0445 \u0444\u0430\u043a\u0442\u043e\u0440\u043e\u0432 \u0440\u0438\u0441\u043a\u0430 \u043d\u0435 \u0432\u044b\u044f\u0432\u043b\u0435\u043d\u043e.")
    if smoking == "sometimes":
        risk_score, risk_note = 62, loc("Smoking risk is present; reduction advised.", "\u0420\u0438\u0437\u0438\u043a \u0432\u0456\u0434 \u043a\u0443\u0440\u0456\u043d\u043d\u044f \u043f\u0440\u0438\u0441\u0443\u0442\u043d\u0456\u0439; \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u043e\u0432\u0430\u043d\u043e \u0437\u043c\u0435\u043d\u0448\u0443\u0432\u0430\u0442\u0438.", "\u0420\u0438\u0441\u043a \u043e\u0442 \u043a\u0443\u0440\u0435\u043d\u0438\u044f \u043f\u0440\u0438\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u0435\u0442; \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0443\u0435\u0442\u0441\u044f \u0441\u043d\u0438\u0436\u0435\u043d\u0438\u0435.")
    if smoking == "yes":
        risk_score, risk_note = 40, loc("Smoking is a high-priority risk factor.", "\u041a\u0443\u0440\u0456\u043d\u043d\u044f \u0454 \u0444\u0430\u043a\u0442\u043e\u0440\u043e\u043c \u0432\u0438\u0441\u043e\u043a\u043e\u0433\u043e \u043f\u0440\u0456\u043e\u0440\u0438\u0442\u0435\u0442\u0443 \u0440\u0438\u0437\u0438\u043a\u0443.", "\u041a\u0443\u0440\u0435\u043d\u0438\u0435 \u2014 \u0432\u044b\u0441\u043e\u043a\u043e\u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442\u043d\u044b\u0439 \u0444\u0430\u043a\u0442\u043e\u0440 \u0440\u0438\u0441\u043a\u0430.")

    if lang == "uk":
        labels = ("\u0421\u043e\u043d", "\u0410\u043a\u0442\u0438\u0432\u043d\u0456\u0441\u0442\u044c", "\u0425\u0430\u0440\u0447\u0443\u0432\u0430\u043d\u043d\u044f", "\u0412\u0456\u0434\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f", "\u0420\u0438\u0437\u0438\u043a")
    elif lang == "ru":
        labels = ("\u0421\u043e\u043d", "\u0410\u043a\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u044c", "\u041f\u0438\u0442\u0430\u043d\u0438\u0435", "\u0412\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435", "\u0420\u0438\u0441\u043a")
    else:
        labels = ("Sleep", "Activity", "Nutrition", "Recovery", "Risk")

    return [
        {"section": labels[0], "score": _clamp(sleep_score), "note": sleep_note},
        {"section": labels[1], "score": _clamp(activity_score), "note": activity_note},
        {"section": labels[2], "score": _clamp(nutrition_score), "note": nutrition_note},
        {"section": labels[3], "score": _clamp(recovery_score), "note": recovery_note},
        {"section": labels[4], "score": _clamp(risk_score), "note": risk_note},
    ]


def build_pdf(report_json: dict[str, Any], lang: str = "en") -> bytes:
    theme = {
        "ink": colors.HexColor("#0B1220"),
        "muted": colors.HexColor("#5B677A"),
        "accent": colors.HexColor("#2563EB"),
        "accent_soft": colors.HexColor("#EAF1FF"),
        "panel": colors.HexColor("#F8FAFC"),
        "grid": colors.HexColor("#D8E0EA"),
    }

    def section_header(text: str, styles_: dict[str, ParagraphStyle]) -> Table:
        t = Table([[text]], colWidths=[170 * mm], hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), theme["accent_soft"]),
                    ("TEXTCOLOR", (0, 0), (-1, -1), theme["ink"]),
                    ("FONTNAME", (0, 0), (-1, -1), bold_font),
                    ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        return t

    def draw_chrome(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFillColor(theme["muted"])
        canvas_obj.setFont(regular_font, 8)
        canvas_obj.drawString(doc_obj.leftMargin, 8 * mm, "BioAge Reset Protocol")
        canvas_obj.drawRightString(A4[0] - doc_obj.rightMargin, 8 * mm, str(canvas_obj.getPageNumber()))
        canvas_obj.restoreState()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        title="BioAge Reset Report",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    regular_font, bold_font = _register_unicode_fonts()
    styles["Normal"].fontName = regular_font
    styles["BodyText"].fontName = regular_font
    styles["Italic"].fontName = regular_font
    styles["Title"].fontName = bold_font
    styles["Heading1"].fontName = bold_font
    styles["Heading2"].fontName = bold_font
    styles["Heading3"].fontName = bold_font
    styles.add(ParagraphStyle(name="Muted", parent=styles["BodyText"], textColor=theme["muted"]))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=9, leading=12))
    styles.add(ParagraphStyle(name="Lead", parent=styles["BodyText"], fontSize=10.5, leading=15))
    styles["Heading1"].fontSize = 20
    styles["Heading1"].leading = 24
    styles["Heading2"].fontSize = 14
    styles["Heading2"].leading = 18

    story: list[Any] = []
    title = str(report_json.get("title") or _t(lang, "cover_title"))
    generated = str(report_json.get("generated_at_utc") or "")

    cover = Table([[title], [_t(lang, "cover_subtitle")]], colWidths=[170 * mm], hAlign="LEFT")
    cover.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), theme["accent_soft"]),
                ("FONTNAME", (0, 0), (0, 0), bold_font),
                ("FONTSIZE", (0, 0), (0, 0), 28),
                ("FONTSIZE", (0, 1), (0, 1), 12),
                ("TEXTCOLOR", (0, 0), (0, 0), theme["ink"]),
                ("TEXTCOLOR", (0, 1), (0, 1), theme["muted"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 18),
                ("RIGHTPADDING", (0, 0), (-1, -1), 18),
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
            ]
        )
    )
    story.append(Spacer(1, 45 * mm))
    story.append(cover)
    story.append(Spacer(1, 14 * mm))
    if generated:
        story.append(Paragraph(f"{_t(lang, 'generated')}: {generated}", styles["BodyText"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(_t(lang, "cover_disclaimer"), styles["Italic"]))
    story.append(PageBreak())

    story.append(Paragraph(title, styles["Heading1"]))
    if generated:
        story.append(Paragraph(f"{_t(lang, 'generated')}: {generated}", styles["Muted"]))
    story.append(Spacer(1, 8))

    disclaimer = str(report_json.get("disclaimer", "")).strip()
    if disclaimer:
        story.append(Paragraph(disclaimer, styles["Lead"]))
        story.append(Spacer(1, 10))

    profile = report_json.get("profile", {}) or {}
    goal = str(profile.get("goal", "")).strip()
    metrics = profile.get("derived_metrics", {}) or {}
    story.append(section_header(_t(lang, "client_profile"), styles))
    story.append(Spacer(1, 6))
    if goal:
        story.append(Paragraph(f"<b>{_t(lang, 'goal')}:</b> {goal}", styles["BodyText"]))
    metric_rows = [[_t(lang, "metric"), _t(lang, "value")]]
    for key in ("age", "height_cm", "weight_kg", "bmi", "sleep_hours", "stress_1_10"):
        if metrics.get(key) is not None and str(metrics.get(key)).strip() != "":
            metric_rows.append([key.replace("_", " ").title(), str(metrics.get(key))])
    if len(metric_rows) > 1:
        mt = Table(metric_rows, hAlign="LEFT", colWidths=[70 * mm, 70 * mm])
        mt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), theme["panel"]),
                    ("GRID", (0, 0), (-1, -1), 0.5, theme["grid"]),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBFDFF")]),
                ]
            )
        )
        story.append(Spacer(1, 6))
        story.append(mt)
    story.append(Spacer(1, 10))

    summary_points = report_json.get("executive_summary", []) or []
    if summary_points:
        story.append(section_header(_t(lang, "executive_summary"), styles))
        story.append(Spacer(1, 6))
        story.append(Paragraph(_safe_lines(summary_points), styles["BodyText"]))
        story.append(Spacer(1, 8))

    priority_actions = report_json.get("priority_actions", []) or []
    if priority_actions:
        story.append(section_header(_t(lang, "priority_actions"), styles))
        story.append(Spacer(1, 6))
        story.append(Paragraph(_safe_lines(priority_actions), styles["BodyText"]))
        story.append(Spacer(1, 8))

    answers = report_json.get("answers", {}) or {}
    score_rows = [[_t(lang, "section"), _t(lang, "score_100"), _t(lang, "notes")]]
    for item in _compute_section_scores(answers, lang):
        score_rows.append([str(item["section"]), str(item["score"]), str(item["note"])])
    st = Table(score_rows, hAlign="LEFT", colWidths=[35 * mm, 25 * mm, 110 * mm], repeatRows=1)
    st.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), theme["ink"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("GRID", (0, 0), (-1, -1), 0.5, theme["grid"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBFDFF")]),
            ]
        )
    )
    story.append(section_header(_t(lang, "section_scores"), styles))
    story.append(Spacer(1, 6))
    story.append(st)
    story.append(Spacer(1, 10))

    summary = report_json.get("summary", {}) or {}
    story.append(section_header(_t(lang, "summary"), styles))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"{_t(lang, 'bioage_estimate')}: {summary.get('bioage_estimate', '')}", styles["BodyText"]))
    key_focus = summary.get("key_focus", []) or []
    if key_focus:
        story.append(Paragraph(f"{_t(lang, 'key_focus')}: " + ", ".join(key_focus), styles["BodyText"]))
    story.append(Spacer(1, 10))

    story.append(section_header(_t(lang, "plan_weekly"), styles))
    story.append(Spacer(1, 6))
    plan = report_json.get("plan_90_days", []) or []
    rows = [[_t(lang, "week"), _t(lang, "focus"), _t(lang, "actions")]]
    for item in plan:
        rows.append(
            [
                str(item.get("week", "")),
                str(item.get("focus", "")),
                "\n".join(item.get("actions", []) or []),
            ]
        )
    plan_table = Table(rows, hAlign="LEFT", colWidths=[20 * mm, 45 * mm, 95 * mm], repeatRows=1)
    plan_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), theme["ink"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("GRID", (0, 0), (-1, -1), 0.5, theme["grid"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBFDFF")]),
            ]
        )
    )
    story.append(plan_table)
    story.append(Spacer(1, 10))

    phases = report_json.get("phases", []) or []
    if phases:
        story.append(section_header(_t(lang, "phases"), styles))
        story.append(Spacer(1, 6))
        for phase in phases:
            phase_title = Table([[str(phase.get("name", ""))]], colWidths=[170 * mm], hAlign="LEFT")
            phase_title.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), theme["panel"]),
                        ("TEXTCOLOR", (0, 0), (-1, -1), theme["ink"]),
                        ("FONTNAME", (0, 0), (-1, -1), bold_font),
                        ("FONTSIZE", (0, 0), (-1, -1), 11),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(phase_title)
            objective = str(phase.get("objective", "")).strip()
            if objective:
                story.append(Paragraph(f"<b>{_t(lang, 'objective')}:</b> {objective}", styles["BodyText"]))
            story.append(Paragraph(f"<b>{_t(lang, 'habits')}:</b><br/>{_safe_lines(phase.get('habits'))}", styles["Small"]))
            story.append(Paragraph(f"<b>{_t(lang, 'training')}:</b><br/>{_safe_lines(phase.get('training'))}", styles["Small"]))
            story.append(Paragraph(f"<b>{_t(lang, 'nutrition')}:</b><br/>{_safe_lines(phase.get('nutrition'))}", styles["Small"]))
            story.append(Paragraph(f"<b>{_t(lang, 'recovery')}:</b><br/>{_safe_lines(phase.get('recovery'))}", styles["Small"]))
            story.append(Spacer(1, 8))

    warnings = report_json.get("warnings", []) or []
    risk_flags = report_json.get("risk_flags", []) or []
    combined_risks = [str(x) for x in [*risk_flags, *warnings] if str(x).strip()]
    if combined_risks:
        story.append(section_header(_t(lang, "safety_notes"), styles))
        story.append(Spacer(1, 6))
        for w in combined_risks:
            story.append(Paragraph(f"- {w}", styles["BodyText"]))

    next_steps = report_json.get("next_steps", []) or []
    if next_steps:
        story.append(Spacer(1, 8))
        story.append(section_header(_t(lang, "next_steps"), styles))
        story.append(Spacer(1, 6))
        for step in next_steps:
            story.append(Paragraph(f"- {step}", styles["BodyText"]))

    if answers:
        story.append(Spacer(1, 8))
        story.append(section_header(_t(lang, "assessment_snapshot"), styles))
        story.append(Spacer(1, 6))
        qlabels = {q.qid: q.label(lang) for q in QUESTIONS}
        for k, v in answers.items():
            label = qlabels.get(k, k)
            story.append(Paragraph(f"<b>{label}</b>: {v}", styles["Small"]))

    doc.build(story, onFirstPage=draw_chrome, onLaterPages=draw_chrome)
    return buf.getvalue()
