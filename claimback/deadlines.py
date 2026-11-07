"""Appeal deadlines by plan type.

These are the general federal rules. The deadline printed on the denial
notice always wins — plans can give more time, and some states give more.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

RULES = {
    # Employer plans (ERISA) and ACA individual plans: 29 CFR 2560.503-1(h); 45 CFR 147.136
    "erisa": (180, "Employer plan (ERISA): at least 180 days from the denial notice to file an internal appeal."),
    "aca_individual": (180, "Individual/Marketplace plan: at least 180 days from the denial notice to file an internal appeal."),
    # Medicaid managed care: 42 CFR 438.402(c)(2)
    "medicaid": (60, "Medicaid managed care: 60 days from the denial notice to file an appeal with the plan."),
    # Medicare Advantage — check the notice; use the shorter figure to be safe.
    "medicare": (60, "Medicare Advantage: about 60 days from the notice to request reconsideration — check your notice for the exact date."),
}
DEFAULT = "aca_individual"


@dataclass
class Deadline:
    plan_type: str
    days: int
    due: date | None
    days_left: int | None
    rule: str
    external_review_note: str = (
        "If the internal appeal is denied, you can usually ask for an independent external review within "
        "4 months of the final denial. The external reviewer's decision is binding on the insurer."
    )
    urgent_note: str = (
        "If waiting could seriously harm your health, ask for an expedited (urgent) appeal: the insurer "
        "generally must decide within 72 hours."
    )


def appeal_deadline(notice_date: date | None, plan_type: str | None, today: date | None = None) -> Deadline:
    plan_type = plan_type if plan_type in RULES else DEFAULT
    days, rule = RULES[plan_type]
    today = today or date.today()
    if notice_date is None:
        return Deadline(plan_type, days, None, None, rule)
    due = notice_date + timedelta(days=days)
    return Deadline(plan_type, days, due, (due - today).days, rule)
