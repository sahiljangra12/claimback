"""Classify why a claim was denied and say what usually wins the appeal.

Categories are matched from Claim Adjustment Reason Codes (CARC, the standard
X12 codes printed on EOBs) first, then from keywords in the letter text.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DenialCategory:
    key: str
    label: str
    plain_english: str
    winnability: str  # "high", "medium", "low" — rough guide, not a prediction
    who_fixes_it: str
    evidence: tuple[str, ...]
    argument: str


CATEGORIES: dict[str, DenialCategory] = {c.key: c for c in [
    DenialCategory(
        "medical_necessity", "Not medically necessary",
        "The insurer says the care wasn't needed for your condition, or that a cheaper option should have been tried first.",
        "medium", "You and your doctor",
        ("Letter of medical necessity from your doctor", "Relevant clinic notes and test results",
         "List of treatments already tried and why they failed", "Clinical guidelines supporting the treatment"),
        "The treatment is medically necessary for my diagnosed condition, is consistent with accepted clinical "
        "guidelines, and less costly alternatives have been tried or are clinically inappropriate, as documented "
        "in the enclosed records. I request that the plan provide the specific clinical criteria it relied on and "
        "that this appeal be reviewed by a physician in the same or a similar specialty.",
    ),
    DenialCategory(
        "prior_auth", "No prior authorization",
        "The insurer says it needed to approve this care in advance and didn't.",
        "high", "Usually your doctor's office",
        ("Proof that authorization was requested or approved (reference number, fax confirmation)",
         "Records showing the care was urgent or an emergency, if it was",
         "Letter of medical necessity"),
        "Authorization was requested before the service (see enclosed documentation), or the service was urgent "
        "and could not reasonably wait for prior approval. The service is a covered benefit and was medically "
        "necessary, so the lack of an authorization number should not bar payment.",
    ),
    DenialCategory(
        "out_of_network", "Out of network",
        "The doctor or facility isn't in your plan's network.",
        "medium", "You",
        ("Proof the provider was listed as in-network in the plan directory when you booked (screenshot)",
         "Records showing it was an emergency, or that you had no choice of provider (e.g. anesthesiologist at an in-network hospital)",
         "Evidence no in-network provider was available within a reasonable distance or time"),
        "This service should be processed at the in-network level. Under the No Surprises Act, emergency care and "
        "certain care from out-of-network providers at in-network facilities must be covered at in-network cost "
        "sharing. In addition, I relied on the plan's provider directory and/or no in-network provider was "
        "reasonably available.",
    ),
    DenialCategory(
        "coding_error", "Billing or coding problem",
        "Something on the claim itself looks wrong: a code, modifier or diagnosis that doesn't match.",
        "high", "Your doctor's billing office",
        ("Corrected claim from the provider", "Itemized bill",
         "Confirmation from the billing office of the correct codes"),
        "The denial results from a billing or coding error, not from a lack of coverage. The provider is submitting "
        "a corrected claim, and I request that the plan reprocess it and pay the covered service.",
    ),
    DenialCategory(
        "missing_info", "Missing information",
        "The insurer says it didn't get everything it needed to process the claim.",
        "high", "Your doctor's office (sometimes you)",
        ("The specific documents the letter asks for", "Updated coordination-of-benefits form if requested"),
        "The information the plan requested is enclosed. I request that the claim be reprocessed for payment.",
    ),
    DenialCategory(
        "not_covered", "Not a covered benefit / excluded",
        "The insurer says your plan doesn't cover this service at all.",
        "low", "You",
        ("Your plan's Summary of Benefits and Coverage and full policy document",
         "Evidence the service fits a covered benefit category",
         "Records showing it treats a covered condition"),
        "Under the terms of my plan, this service falls within a covered benefit category. I request the specific "
        "plan provision relied on for this denial and ask that the plan reconsider coverage based on the enclosed "
        "records.",
    ),
    DenialCategory(
        "experimental", "Experimental or investigational",
        "The insurer considers the treatment unproven.",
        "medium", "You and your doctor",
        ("Published studies supporting the treatment", "FDA approval status for your condition",
         "Letter from your doctor explaining why it's standard of care for you"),
        "The treatment is not experimental for my condition: it is supported by peer-reviewed evidence and accepted "
        "clinical practice, as documented in the enclosed materials. I request review by an independent physician "
        "with relevant expertise.",
    ),
    DenialCategory(
        "timely_filing", "Filed too late",
        "The claim reached the insurer after its filing deadline.",
        "medium", "Usually your doctor's office — often you shouldn't owe this",
        ("Proof of the original submission date", "Records of any insurer delays or incorrect insurance info on file"),
        "The claim was originally submitted on time (see enclosed proof of submission), or the delay was caused by "
        "circumstances outside my control. I request that the claim be processed.",
    ),
    DenialCategory(
        "coverage_terminated", "Coverage not active / eligibility",
        "The insurer says you weren't covered on the date of service.",
        "high", "You",
        ("Insurance card and proof of premium payments", "Enrollment confirmation", "Employer HR confirmation of coverage dates"),
        "I had active coverage on the date of service, as shown in the enclosed enrollment and premium-payment "
        "records. I request that the plan correct its eligibility records and reprocess the claim.",
    ),
    DenialCategory(
        "duplicate", "Duplicate claim",
        "The insurer thinks this claim was already submitted.",
        "high", "Your doctor's billing office",
        ("Itemized bill showing distinct services or dates",),
        "This claim is not a duplicate: it covers a separate service or date of service, as shown on the enclosed "
        "itemized bill.",
    ),
    DenialCategory(
        "cob", "Other insurance should pay first",
        "The insurer thinks another plan (Medicare, a spouse's plan) is responsible first.",
        "high", "You",
        ("Completed coordination-of-benefits form", "Proof the other coverage ended or doesn't apply"),
        "This plan is my primary coverage for this service (see enclosed coordination-of-benefits information). "
        "I request that the claim be reprocessed as primary.",
    ),
    DenialCategory(
        "unknown", "Reason unclear",
        "The letter doesn't clearly say why the claim was denied.",
        "medium", "You",
        ("A copy of your full claim file — you have a right to it free of charge",),
        "The notice does not state a specific reason for the denial with enough detail for me to respond. I request "
        "the specific reason, the plan provision and any clinical criteria relied on, and copies of all documents "
        "relevant to my claim, free of charge.",
    ),
]}

# CARC code -> category key
CARC_MAP = {
    "50": "medical_necessity", "56": "medical_necessity", "151": "medical_necessity",
    "197": "prior_auth", "15": "prior_auth", "198": "prior_auth",
    "242": "out_of_network", "243": "out_of_network", "38": "out_of_network",
    "4": "coding_error", "5": "coding_error", "6": "coding_error", "11": "coding_error",
    "97": "coding_error", "146": "coding_error", "181": "coding_error", "182": "coding_error",
    "16": "missing_info", "252": "missing_info", "226": "missing_info",
    "96": "not_covered", "204": "not_covered", "109": "not_covered", "167": "not_covered", "49": "not_covered",
    "55": "experimental",
    "29": "timely_filing",
    "27": "coverage_terminated", "26": "coverage_terminated", "31": "coverage_terminated", "177": "coverage_terminated",
    "18": "duplicate",
    "22": "cob", "23": "cob",
}

KEYWORDS = [
    ("prior_auth", ["prior authorization", "preauthorization", "pre-authorization", "precertification",
                    "authorization was not obtained", "no authorization", "referral"]),
    ("out_of_network", ["out-of-network", "out of network", "non-participating", "not in network", "non-network"]),
    ("experimental", ["experimental", "investigational", "unproven"]),
    ("medical_necessity", ["medically necessary", "medical necessity", "not necessary", "clinical criteria",
                           "step therapy", "less costly alternative"]),
    ("timely_filing", ["timely filing", "filing limit", "submitted after", "time limit"]),
    ("coverage_terminated", ["coverage terminated", "not eligible", "not enrolled", "coverage was not active",
                             "policy terminated", "eligibility"]),
    ("duplicate", ["duplicate"]),
    ("cob", ["coordination of benefits", "other insurance", "primary payer"]),
    ("missing_info", ["additional information", "missing information", "information requested",
                      "incomplete", "medical records requested"]),
    ("coding_error", ["modifier", "procedure code", "diagnosis code", "coding", "inconsistent with",
                      "bundled", "invalid code"]),
    ("not_covered", ["not a covered", "not covered", "excluded", "exclusion", "benefit limit"]),
]


def classify(text: str, carc_codes: list[str] | None = None) -> DenialCategory:
    for code in carc_codes or []:
        key = CARC_MAP.get(code.lstrip("0") or code)
        if key:
            return CATEGORIES[key]
    low = text.lower()
    best, best_hits = "unknown", 0
    for key, words in KEYWORDS:
        hits = sum(low.count(w) for w in words)
        if hits > best_hits:
            best, best_hits = key, hits
    return CATEGORIES[best]
