"""ClaimBack — Streamlit app.

Run:  streamlit run app.py
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

import streamlit as st

from claimback.classify import CATEGORIES, classify
from claimback.deadlines import RULES, appeal_deadline
from claimback.extract import text_from_bytes
from claimback.letter import draft_letter, polish_with_claude
from claimback.parse import parse

PLAN_LABELS = {
    "erisa": "Employer plan (through a job)",
    "aca_individual": "Individual / Marketplace plan",
    "medicaid": "Medicaid managed care",
    "medicare": "Medicare Advantage",
}
WIN_BADGE = {"high": "🟢 Often fixable", "medium": "🟡 Worth fighting", "low": "🟠 Harder, still worth a try"}

st.set_page_config(page_title="ClaimBack", page_icon="📄", layout="centered")
st.title("ClaimBack")
st.caption("Understand your health insurance denial and get an appeal letter in minutes.")

with st.expander("Before you start", expanded=False):
    st.markdown(
        "- Your file is processed in memory and **not stored**.\n"
        "- This tool gives general information, not legal or medical advice.\n"
        "- The deadline printed on your denial notice always wins over the estimate here."
    )

tab_upload, tab_paste = st.tabs(["Upload letter", "Paste text"])
raw_text = ""
with tab_upload:
    up = st.file_uploader("Denial letter or Explanation of Benefits",
                          type=["pdf", "png", "jpg", "jpeg", "txt"])
    if up is not None:
        with st.spinner("Reading your letter…"):
            raw_text = text_from_bytes(up.getvalue(), up.name)
with tab_paste:
    pasted = st.text_area("Paste the text of your letter", height=180)
    if pasted.strip():
        raw_text = pasted

if not raw_text.strip():
    st.info("Upload or paste a denial letter to begin. Try a file from the `samples/` folder.")
    st.stop()

fields = parse(raw_text)

st.subheader("1. Check the details we found")
st.caption("Fix anything that's wrong — the letter uses these values.")
c1, c2 = st.columns(2)
with c1:
    insurer = st.text_input("Insurance company", fields.insurer or "")
    member_name = st.text_input("Member name", fields.member_name or "")
    member_id = st.text_input("Member ID", fields.member_id or "")
    claim_number = st.text_input("Claim number", fields.claim_number or "")
with c2:
    provider = st.text_input("Provider", fields.provider or "")
    dos = st.date_input("Date of service", fields.date_of_service, format="MM/DD/YYYY")
    notice = st.date_input("Date on the denial notice", fields.notice_date, format="MM/DD/YYYY")
    amount = st.number_input("Amount denied ($)", value=float(fields.amount_denied or 0.0), step=10.0)
reason = st.text_area("Denial reason (as written on the letter)", fields.reason_text or "", height=80)

plan_keys = list(PLAN_LABELS)
default_plan = fields.plan_type_hint if fields.plan_type_hint in PLAN_LABELS else "aca_individual"
plan_type = st.selectbox("Type of insurance", plan_keys, index=plan_keys.index(default_plan),
                         format_func=PLAN_LABELS.get)

fields = replace(fields, insurer=insurer or None, member_name=member_name or None,
                 member_id=member_id or None, claim_number=claim_number or None,
                 provider=provider or None, date_of_service=dos, notice_date=notice,
                 amount_denied=amount or None, reason_text=reason or None)

auto_cat = classify(raw_text, fields.carc_codes)
cat_keys = list(CATEGORIES)
cat_key = st.selectbox("Why it was denied", cat_keys, index=cat_keys.index(auto_cat.key),
                       format_func=lambda k: CATEGORIES[k].label)
cat = CATEGORIES[cat_key]

st.subheader("2. What this means")
st.markdown(f"**{cat.label}** — {cat.plain_english}")
m1, m2 = st.columns(2)
m1.metric("Chance it's fixable", WIN_BADGE[cat.winnability])
m2.metric("Who usually fixes it", cat.who_fixes_it)
if cat.key in {"coding_error", "missing_info", "duplicate", "timely_filing"}:
    st.info("Call your doctor's billing office first — this kind of denial is often fixed by them "
            "resubmitting the claim, and you may not owe anything.")

dl = appeal_deadline(fields.notice_date, plan_type, date.today())
st.subheader("3. Your deadline")
if dl.due:
    if dl.days_left is not None and dl.days_left < 0:
        st.error(f"The usual deadline ({dl.due:%B %d, %Y}) may have passed. Check your notice and call the "
                 "insurer anyway — late appeals are sometimes accepted for good cause.")
    else:
        st.success(f"File your appeal by **{dl.due:%B %d, %Y}** — {dl.days_left} days left.")
st.caption(dl.rule)
st.caption(dl.urgent_note)
st.caption(dl.external_review_note)

st.subheader("4. Gather this evidence")
for e in cat.evidence:
    st.checkbox(e, key=f"ev_{e}")

st.subheader("5. Your appeal letter")
extra = st.text_area("Anything else the insurer should know? (optional)",
                     placeholder="e.g. My doctor's office told me they submitted the authorization on Aug 20.")
letter = draft_letter(fields, cat, date.today(), extra)
if st.toggle("Polish with AI (needs ANTHROPIC_API_KEY)", value=False):
    with st.spinner("Polishing…"):
        letter = polish_with_claude(letter, raw_text)
letter = st.text_area("Edit before sending — fill in anything in [brackets]", letter, height=520)
st.download_button("Download letter (.txt)", letter, file_name="appeal_letter.txt")

st.divider()
st.caption("Send the appeal by a trackable method (certified mail, fax with confirmation, or the insurer's "
           "portal) and keep copies of everything.")

with st.expander("Text we read from your file"):
    st.text(raw_text[:5000])
