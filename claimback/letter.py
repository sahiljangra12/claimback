"""Draft an internal appeal letter from the parsed fields and the denial category."""
from __future__ import annotations

import os
from datetime import date

from .classify import DenialCategory
from .parse import DenialFields


def _v(value, placeholder: str) -> str:
    if value is None or value == "":
        return f"[{placeholder}]"
    if isinstance(value, date):
        return value.strftime("%B %d, %Y").replace(" 0", " ")
    return str(value)


def draft_letter(f: DenialFields, cat: DenialCategory, today: date | None = None,
                 extra_context: str = "") -> str:
    today = today or date.today()
    money = f" for ${f.amount_denied:,.2f}" if f.amount_denied else ""
    enclosures = "\n".join(f"  {i}. {e}" for i, e in enumerate(cat.evidence, 1))
    context = f"\n\nAdditional details: {extra_context.strip()}" if extra_context.strip() else ""

    return f"""{_v(f.member_name, "Your full name")}
[Your address]
[Your phone] | [Your email]

{_v(today, "Date")}

{_v(f.insurer, "Insurance company")} — Appeals Department
[Appeals address from your denial letter]

RE: Request for internal appeal
Member: {_v(f.member_name, "Your full name")}
Member ID: {_v(f.member_id, "Member ID")}
Claim number: {_v(f.claim_number, "Claim number")}
Date of service: {_v(f.date_of_service, "Date of service")}
Provider: {_v(f.provider, "Provider name")}
Date of denial notice: {_v(f.notice_date, "Date on denial letter")}

To the Appeals Department:

I am writing to formally appeal the denial of the claim above{money}. The notice states that the claim was denied because: "{_v(f.reason_text, "denial reason as written on your letter")}".

{cat.argument}{context}

Under federal claims and appeals rules, I also request:
  • the specific plan provision, guideline or clinical criteria used to deny this claim;
  • copies of all documents, records and other information relevant to my claim, free of charge;
  • the name and credentials of any medical reviewer involved in the decision.

Please reverse this decision and process the claim for payment. If the denial is upheld, please send a written explanation and information on how to request an independent external review.

Enclosed:
{enclosures}
  {len(cat.evidence) + 1}. Copy of the denial notice

Sincerely,

{_v(f.member_name, "Your full name")}
"""


def polish_with_claude(letter: str, letter_text: str) -> str:
    """Optional: tighten the draft with Claude. Requires ANTHROPIC_API_KEY.

    The model is told not to add facts; placeholders in [brackets] must stay.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return letter
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=os.getenv("CLAIMBACK_MODEL", "claude-sonnet-5-5"),
        max_tokens=2000,
        system=(
            "You edit health insurance appeal letters written by patients. Improve clarity and persuasiveness "
            "using only facts present in the draft or the denial notice. Never invent medical facts, dates, "
            "codes, studies or laws. Keep every [bracketed placeholder] exactly as is. Return only the letter."
        ),
        messages=[{"role": "user", "content": f"Denial notice:\n{letter_text[:8000]}\n\nDraft letter:\n{letter}"}],
    )
    return msg.content[0].text
