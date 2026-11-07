"""ClaimBack: understand an insurance denial and draft an appeal."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .classify import DenialCategory, classify
from .deadlines import Deadline, appeal_deadline
from .letter import draft_letter
from .parse import DenialFields, parse

__all__ = ["analyze", "Analysis"]


@dataclass
class Analysis:
    fields: DenialFields
    category: DenialCategory
    deadline: Deadline
    letter: str


def analyze(text: str, plan_type: str | None = None, today: date | None = None,
            extra_context: str = "") -> Analysis:
    fields = parse(text)
    category = classify(text, fields.carc_codes)
    deadline = appeal_deadline(fields.notice_date, plan_type or fields.plan_type_hint, today)
    letter = draft_letter(fields, category, today, extra_context)
    return Analysis(fields, category, deadline, letter)
