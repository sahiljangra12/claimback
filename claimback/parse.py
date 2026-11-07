"""Pull the key fields out of a denial letter or Explanation of Benefits."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime

KNOWN_INSURERS = [
    "UnitedHealthcare", "Aetna", "Cigna", "Humana", "Anthem", "Elevance",
    "Blue Cross Blue Shield", "BlueCross BlueShield", "CareFirst", "Kaiser Permanente",
    "Molina", "Centene", "Ambetter", "Oscar", "Highmark", "Florida Blue",
    "Priority Health", "Medica", "WellCare", "Tricare", "Medicaid", "Medicare",
]

DATE_PATTERNS = [
    "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d",
]
DATE_RE = (
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2}, \d{4})"
)


@dataclass
class DenialFields:
    insurer: str | None = None
    member_name: str | None = None
    member_id: str | None = None
    claim_number: str | None = None
    provider: str | None = None
    service: str | None = None
    date_of_service: date | None = None
    notice_date: date | None = None
    amount_billed: float | None = None
    amount_denied: float | None = None
    carc_codes: list[str] = field(default_factory=list)
    reason_text: str | None = None
    plan_type_hint: str | None = None  # "erisa", "aca_individual", "medicare", "medicaid"

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("date_of_service", "notice_date"):
            if d[k]:
                d[k] = d[k].isoformat()
        return d


def parse_date(s: str) -> date | None:
    s = re.sub(r"\bSept\b", "Sep", s.strip()).replace(".", "")
    for fmt in DATE_PATTERNS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _labeled(text: str, labels: list[str], value=r"([A-Z0-9][A-Z0-9\-]{3,})") -> str | None:
    for label in labels:
        m = re.search(label + r"\s*(?:#|number|no\.?|ID)?\s*[:#]?\s*" + value, text, re.I)
        if m:
            return m.group(1).strip()
    return None


def _labeled_date(text: str, labels: list[str]) -> date | None:
    for label in labels:
        m = re.search(label + r"[^\n\d]{0,25}" + DATE_RE, text, re.I)
        if m:
            d = parse_date(m.group(1))
            if d:
                return d
    return None


def _money(text: str, labels: list[str]) -> float | None:
    for label in labels:
        m = re.search(label + r"[^\n$]{0,30}\$\s?([\d,]+(?:\.\d{2})?)", text, re.I)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def parse(text: str) -> DenialFields:
    f = DenialFields()
    low = text.lower()

    for name in KNOWN_INSURERS:
        if name.lower() in low:
            f.insurer = name
            break

    f.member_name = _labeled(text, [r"member name", r"patient name", r"patient", r"member"],
                             value=r"([A-Z][a-zA-Z'\-]+(?: [A-Z][a-zA-Z'\-\.]+){0,3})")
    f.member_id = _labeled(text, [r"member id", r"subscriber id", r"member number", r"id number"])
    f.claim_number = _labeled(text, [r"claim number", r"claim no", r"claim id", r"claim"])
    # Anchor to line starts so "Member Services" or "service date" don't match.
    line = r"(?m)^\s*"
    f.provider = _labeled(text, [line + r"(?:rendering )?provider(?: name)?\s*:", line + r"facility\s*:"],
                          value=r"([A-Z][^\n]{2,60})")
    f.service = _labeled(text, [line + r"(?:description of )?service\s*:", line + r"procedure\s*:",
                                line + r"item\s*:"],
                         value=r"([A-Za-z][^\n]{2,80})")

    f.date_of_service = _labeled_date(text, [r"date of service", r"service date", r"dos"])
    f.notice_date = _labeled_date(text, [r"date of (?:this )?(?:notice|letter)", r"notice date",
                                         r"letter date", r"date mailed", r"^date"])
    if not f.notice_date:
        first = re.search(DATE_RE, text)
        if first:
            f.notice_date = parse_date(first.group(1))

    f.amount_billed = _money(text, [r"amount billed", r"billed amount", r"total charges", r"charges"])
    f.amount_denied = _money(text, [r"amount denied", r"denied amount", r"not covered",
                                    r"patient responsibility", r"you (?:may )?owe"])

    f.carc_codes = sorted(set(re.findall(r"\b(?:CARC|reason code|code)\s*[:#]?\s*(?:CO|PR|OA|PI)?-?(\d{1,3}|[A-Z]\d{1,2})\b",
                                         text, re.I)))

    m = re.search(r"(?:reason for (?:the )?denial|denial reason|why (?:was )?(?:your|this) claim (?:was )?denied|"
                  r"we denied[^\n]*because|reason)\s*[:\-]?\s*([^\n]+(?:\n(?!\s*\n)[^\n]+){0,3})", text, re.I)
    if m:
        f.reason_text = " ".join(m.group(1).split())[:600]

    if "erisa" in low or "employer" in low or "group health plan" in low:
        f.plan_type_hint = "erisa"
    elif "medicare advantage" in low or "medicare" in low:
        f.plan_type_hint = "medicare"
    elif "medicaid" in low:
        f.plan_type_hint = "medicaid"
    elif "marketplace" in low or "healthcare.gov" in low:
        f.plan_type_hint = "aca_individual"
    return f
