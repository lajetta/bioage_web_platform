from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table


def build_pdf(report_json: dict[str, Any], lang: str = "en") -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="BioAge Reset Report")
    styles = getSampleStyleSheet()

    story: list[Any] = []
    story.append(Paragraph("BioAge Reset Protocol", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(report_json.get("disclaimer", ""), styles["Italic"]))
    story.append(Spacer(1, 12))

    summary = report_json.get("summary", {}) or {}
    story.append(Paragraph("Summary", styles["Heading2"]))
    story.append(Paragraph(f"BioAge estimate: {summary.get('bioage_estimate','')}", styles["BodyText"]))

    key_focus = summary.get("key_focus", []) or []
    if key_focus:
        story.append(Paragraph("Key focus:", styles["BodyText"]))
        story.append(Paragraph(", ".join(key_focus), styles["BodyText"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("90-day plan (weekly)", styles["Heading2"]))

    plan = report_json.get("plan_90_days", []) or []
    rows = [["Week", "Focus", "Actions"]]
    for item in plan:
        rows.append([
            str(item.get("week", "")),
            str(item.get("focus", "")),
            "\n".join(item.get("actions", []) or []),
        ])

    story.append(Table(rows, hAlign="LEFT"))
    story.append(Spacer(1, 12))

    warnings = report_json.get("warnings", []) or []
    if warnings:
        story.append(Paragraph("Warnings", styles["Heading2"]))
        for w in warnings:
            story.append(Paragraph(f"• {w}", styles["BodyText"]))

    doc.build(story)
    return buf.getvalue()
