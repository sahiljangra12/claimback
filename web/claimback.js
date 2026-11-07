/* ClaimBack core logic — browser port of the Python package.
   Works in the browser (window.ClaimBack) and in Node (module.exports). */
(function (root) {
  "use strict";

  // ---------------- parsing ----------------
  const KNOWN_INSURERS = [
    "UnitedHealthcare", "Aetna", "Cigna", "Humana", "Anthem", "Elevance",
    "Blue Cross Blue Shield", "BlueCross BlueShield", "CareFirst", "Kaiser Permanente",
    "Molina", "Centene", "Ambetter", "Oscar", "Highmark", "Florida Blue",
    "Priority Health", "Medica", "WellCare", "Tricare", "Medicaid", "Medicare",
  ];
  const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
  const DATE_RE = "(\\d{1,2}[/-]\\d{1,2}[/-]\\d{2,4}|\\d{4}-\\d{2}-\\d{2}|" +
    "(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\\.? \\d{1,2}, \\d{4})";

  function iso(y, m, d) {
    const dt = new Date(Date.UTC(y, m - 1, d));
    if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== m - 1 || dt.getUTCDate() !== d) return null;
    return dt.toISOString().slice(0, 10);
  }

  function parseDate(s) {
    s = s.trim().replace(/\./g, "");
    let m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) return iso(+m[1], +m[2], +m[3]);
    m = s.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$/);
    if (m) {
      let y = +m[3];
      if (m[3].length === 2) y += y < 70 ? 2000 : 1900;
      return iso(y, +m[1], +m[2]);
    }
    m = s.match(/^([A-Za-z]+) (\d{1,2}), (\d{4})$/);
    if (m) {
      const mi = MONTHS.indexOf(m[1].slice(0, 3).toLowerCase());
      if (mi >= 0) return iso(+m[3], mi + 1, +m[2]);
    }
    return null;
  }

  function labeled(text, labels, value) {
    value = value || "([A-Z0-9][A-Z0-9\\-]{3,})";
    for (const label of labels) {
      const flags = label.multiline ? "im" : "i";
      const src = (label.src || label) + "\\s*(?:#|number|no\\.?|ID)?\\s*[:#]?\\s*" + value;
      const m = text.match(new RegExp(src, flags));
      if (m) return m[1].trim();
    }
    return null;
  }

  function labeledDate(text, labels) {
    for (const label of labels) {
      const m = text.match(new RegExp(label + "[^\\n\\d]{0,25}" + DATE_RE, "i"));
      if (m) {
        const d = parseDate(m[1]);
        if (d) return d;
      }
    }
    return null;
  }

  function money(text, labels) {
    for (const label of labels) {
      const m = text.match(new RegExp(label + "[^\\n$]{0,30}\\$\\s?([\\d,]+(?:\\.\\d{2})?)", "i"));
      if (m) return parseFloat(m[1].replace(/,/g, ""));
    }
    return null;
  }

  const line = (s) => ({ src: "^\\s*" + s, multiline: true });

  function parse(text) {
    const f = {
      insurer: null, member_name: null, member_id: null, claim_number: null, provider: null,
      service: null, date_of_service: null, notice_date: null, amount_billed: null,
      amount_denied: null, carc_codes: [], reason_text: null, plan_type_hint: null,
    };
    const low = text.toLowerCase();
    f.insurer = KNOWN_INSURERS.find((n) => low.includes(n.toLowerCase())) || null;

    f.member_name = labeled(text, ["member name", "patient name", "patient", "member"],
      "([A-Z][a-zA-Z'\\-]+(?: [A-Z][a-zA-Z'\\-\\.]+){0,3})");
    f.member_id = labeled(text, ["member id", "subscriber id", "member number", "id number"]);
    f.claim_number = labeled(text, ["claim number", "claim no", "claim id", "claim"]);
    f.provider = labeled(text, [line("(?:rendering )?provider(?: name)?\\s*:"), line("facility\\s*:")],
      "([A-Z][^\\n]{2,60})");
    f.service = labeled(text, [line("(?:description of )?service\\s*:"), line("procedure\\s*:"), line("item\\s*:")],
      "([A-Za-z][^\\n]{2,80})");

    f.date_of_service = labeledDate(text, ["date of service", "service date", "dos"]);
    f.notice_date = labeledDate(text, ["date of (?:this )?(?:notice|letter)", "notice date",
      "letter date", "date mailed", "^date"]);
    if (!f.notice_date) {
      const first = text.match(new RegExp(DATE_RE));
      if (first) f.notice_date = parseDate(first[1]);
    }

    f.amount_billed = money(text, ["amount billed", "billed amount", "total charges", "charges"]);
    f.amount_denied = money(text, ["amount denied", "denied amount", "not covered",
      "patient responsibility", "you (?:may )?owe"]);

    const codes = new Set();
    const re = /\b(?:CARC|reason code|code)\s*[:#]?\s*(?:CO|PR|OA|PI)?-?(\d{1,3}|[A-Z]\d{1,2})\b/gi;
    let m;
    while ((m = re.exec(text))) codes.add(m[1]);
    f.carc_codes = [...codes].sort();

    m = text.match(/(?:reason for (?:the )?denial|denial reason|why (?:was )?(?:your|this) claim (?:was )?denied|we denied[^\n]*because|reason)\s*[:\-]?\s*([^\n]+(?:\n(?!\s*\n)[^\n]+){0,3})/i);
    if (m) f.reason_text = m[1].split(/\s+/).join(" ").slice(0, 600);

    if (/erisa|employer|group health plan/.test(low)) f.plan_type_hint = "erisa";
    else if (low.includes("medicare")) f.plan_type_hint = "medicare";
    else if (low.includes("medicaid")) f.plan_type_hint = "medicaid";
    else if (/marketplace|healthcare\.gov/.test(low)) f.plan_type_hint = "aca_individual";
    return f;
  }

  // ---------------- classification ----------------
  const C = (key, label, plain, win, who, evidence, argument) => ({ key, label, plain, win, who, evidence, argument });
  const CATEGORIES = [
    C("medical_necessity", "Not medically necessary",
      "The insurer says the care wasn't needed for your condition, or that a cheaper option should have been tried first.",
      "medium", "You and your doctor",
      ["Letter of medical necessity from your doctor", "Relevant clinic notes and test results",
        "List of treatments already tried and why they failed", "Clinical guidelines supporting the treatment"],
      "The treatment is medically necessary for my diagnosed condition, is consistent with accepted clinical guidelines, and less costly alternatives have been tried or are clinically inappropriate, as documented in the enclosed records. I request that the plan provide the specific clinical criteria it relied on and that this appeal be reviewed by a physician in the same or a similar specialty."),
    C("prior_auth", "No prior authorization",
      "The insurer says it needed to approve this care in advance and didn't.",
      "high", "Usually your doctor's office",
      ["Proof that authorization was requested or approved (reference number, fax confirmation)",
        "Records showing the care was urgent or an emergency, if it was", "Letter of medical necessity"],
      "Authorization was requested before the service (see enclosed documentation), or the service was urgent and could not reasonably wait for prior approval. The service is a covered benefit and was medically necessary, so the lack of an authorization number should not bar payment."),
    C("out_of_network", "Out of network",
      "The doctor or facility isn't in your plan's network.",
      "medium", "You",
      ["Proof the provider was listed as in-network in the plan directory when you booked (screenshot)",
        "Records showing it was an emergency, or that you had no choice of provider",
        "Evidence no in-network provider was available within a reasonable distance or time"],
      "This service should be processed at the in-network level. Under the No Surprises Act, emergency care and certain care from out-of-network providers at in-network facilities must be covered at in-network cost sharing. In addition, I relied on the plan's provider directory and/or no in-network provider was reasonably available."),
    C("coding_error", "Billing or coding problem",
      "Something on the claim itself looks wrong: a code, modifier or diagnosis that doesn't match.",
      "high", "Your doctor's billing office",
      ["Corrected claim from the provider", "Itemized bill", "Confirmation from the billing office of the correct codes"],
      "The denial results from a billing or coding error, not from a lack of coverage. The provider is submitting a corrected claim, and I request that the plan reprocess it and pay the covered service."),
    C("missing_info", "Missing information",
      "The insurer says it didn't get everything it needed to process the claim.",
      "high", "Your doctor's office (sometimes you)",
      ["The specific documents the letter asks for", "Updated coordination-of-benefits form if requested"],
      "The information the plan requested is enclosed. I request that the claim be reprocessed for payment."),
    C("not_covered", "Not a covered benefit / excluded",
      "The insurer says your plan doesn't cover this service at all.",
      "low", "You",
      ["Your plan's Summary of Benefits and Coverage and full policy document",
        "Evidence the service fits a covered benefit category", "Records showing it treats a covered condition"],
      "Under the terms of my plan, this service falls within a covered benefit category. I request the specific plan provision relied on for this denial and ask that the plan reconsider coverage based on the enclosed records."),
    C("experimental", "Experimental or investigational",
      "The insurer considers the treatment unproven.",
      "medium", "You and your doctor",
      ["Published studies supporting the treatment", "FDA approval status for your condition",
        "Letter from your doctor explaining why it's standard of care for you"],
      "The treatment is not experimental for my condition: it is supported by peer-reviewed evidence and accepted clinical practice, as documented in the enclosed materials. I request review by an independent physician with relevant expertise."),
    C("timely_filing", "Filed too late",
      "The claim reached the insurer after its filing deadline.",
      "medium", "Usually your doctor's office — often you shouldn't owe this",
      ["Proof of the original submission date", "Records of any insurer delays or incorrect insurance info on file"],
      "The claim was originally submitted on time (see enclosed proof of submission), or the delay was caused by circumstances outside my control. I request that the claim be processed."),
    C("coverage_terminated", "Coverage not active / eligibility",
      "The insurer says you weren't covered on the date of service.",
      "high", "You",
      ["Insurance card and proof of premium payments", "Enrollment confirmation", "Employer HR confirmation of coverage dates"],
      "I had active coverage on the date of service, as shown in the enclosed enrollment and premium-payment records. I request that the plan correct its eligibility records and reprocess the claim."),
    C("duplicate", "Duplicate claim",
      "The insurer thinks this claim was already submitted.",
      "high", "Your doctor's billing office",
      ["Itemized bill showing distinct services or dates"],
      "This claim is not a duplicate: it covers a separate service or date of service, as shown on the enclosed itemized bill."),
    C("cob", "Other insurance should pay first",
      "The insurer thinks another plan (Medicare, a spouse's plan) is responsible first.",
      "high", "You",
      ["Completed coordination-of-benefits form", "Proof the other coverage ended or doesn't apply"],
      "This plan is my primary coverage for this service (see enclosed coordination-of-benefits information). I request that the claim be reprocessed as primary."),
    C("unknown", "Reason unclear",
      "The letter doesn't clearly say why the claim was denied.",
      "medium", "You",
      ["A copy of your full claim file — you have a right to it free of charge"],
      "The notice does not state a specific reason for the denial with enough detail for me to respond. I request the specific reason, the plan provision and any clinical criteria relied on, and copies of all documents relevant to my claim, free of charge."),
  ];
  const BY_KEY = Object.fromEntries(CATEGORIES.map((c) => [c.key, c]));

  const CARC_MAP = {
    50: "medical_necessity", 56: "medical_necessity", 151: "medical_necessity",
    197: "prior_auth", 15: "prior_auth", 198: "prior_auth",
    242: "out_of_network", 243: "out_of_network", 38: "out_of_network",
    4: "coding_error", 5: "coding_error", 6: "coding_error", 11: "coding_error", 97: "coding_error",
    146: "coding_error", 181: "coding_error", 182: "coding_error",
    16: "missing_info", 252: "missing_info", 226: "missing_info",
    96: "not_covered", 204: "not_covered", 109: "not_covered", 167: "not_covered", 49: "not_covered",
    55: "experimental", 29: "timely_filing",
    27: "coverage_terminated", 26: "coverage_terminated", 31: "coverage_terminated", 177: "coverage_terminated",
    18: "duplicate", 22: "cob", 23: "cob",
  };

  const KEYWORDS = [
    ["prior_auth", ["prior authorization", "preauthorization", "pre-authorization", "precertification",
      "authorization was not obtained", "no authorization", "referral"]],
    ["out_of_network", ["out-of-network", "out of network", "non-participating", "not in network", "non-network"]],
    ["experimental", ["experimental", "investigational", "unproven"]],
    ["medical_necessity", ["medically necessary", "medical necessity", "not necessary", "clinical criteria",
      "step therapy", "less costly alternative"]],
    ["timely_filing", ["timely filing", "filing limit", "submitted after", "time limit"]],
    ["coverage_terminated", ["coverage terminated", "not eligible", "not enrolled", "coverage was not active",
      "policy terminated", "eligibility"]],
    ["duplicate", ["duplicate"]],
    ["cob", ["coordination of benefits", "other insurance", "primary payer"]],
    ["missing_info", ["additional information", "missing information", "information requested",
      "incomplete", "medical records requested"]],
    ["coding_error", ["modifier", "procedure code", "diagnosis code", "coding", "inconsistent with",
      "bundled", "invalid code"]],
    ["not_covered", ["not a covered", "not covered", "excluded", "exclusion", "benefit limit"]],
  ];

  function count(hay, needle) {
    let n = 0, i = 0;
    while ((i = hay.indexOf(needle, i)) !== -1) { n++; i += needle.length; }
    return n;
  }

  function classify(text, carcCodes) {
    for (const code of carcCodes || []) {
      const k = CARC_MAP[String(code).replace(/^0+/, "")];
      if (k) return BY_KEY[k];
    }
    const low = text.toLowerCase();
    let best = "unknown", hits = 0;
    for (const [key, words] of KEYWORDS) {
      const h = words.reduce((s, w) => s + count(low, w), 0);
      if (h > hits) { best = key; hits = h; }
    }
    return BY_KEY[best];
  }

  // ---------------- deadlines ----------------
  const RULES = {
    erisa: [180, "Employer plan (ERISA): at least 180 days from the denial notice to file an internal appeal."],
    aca_individual: [180, "Individual/Marketplace plan: at least 180 days from the denial notice to file an internal appeal."],
    medicaid: [60, "Medicaid managed care: 60 days from the denial notice to file an appeal with the plan."],
    medicare: [60, "Medicare Advantage: about 60 days from the notice to request reconsideration — check your notice for the exact date."],
  };
  const PLAN_LABELS = {
    erisa: "Employer plan (through a job)",
    aca_individual: "Individual / Marketplace plan",
    medicaid: "Medicaid managed care",
    medicare: "Medicare Advantage",
  };

  function addDays(isoDate, days) {
    const d = new Date(isoDate + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
  }
  function daysBetween(a, b) {
    return Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 864e5);
  }

  function appealDeadline(noticeDate, planType, today) {
    planType = RULES[planType] ? planType : "aca_individual";
    const [days, rule] = RULES[planType];
    if (!noticeDate) return { planType, days, due: null, daysLeft: null, rule };
    const due = addDays(noticeDate, days);
    return { planType, days, due, daysLeft: daysBetween(today, due), rule };
  }

  // ---------------- letter ----------------
  const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December"];
  function longDate(isoDate) {
    const [y, m, d] = isoDate.split("-").map(Number);
    return `${MONTH_NAMES[m - 1]} ${d}, ${y}`;
  }
  function v(value, placeholder, isDate) {
    if (value === null || value === undefined || value === "") return `[${placeholder}]`;
    return isDate ? longDate(value) : String(value);
  }

  function draftLetter(f, cat, today, extra) {
    const moneyText = f.amount_denied ? ` for $${Number(f.amount_denied).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "";
    const enclosures = cat.evidence.map((e, i) => `  ${i + 1}. ${e}`).join("\n");
    const context = extra && extra.trim() ? `\n\nAdditional details: ${extra.trim()}` : "";
    return `${v(f.member_name, "Your full name")}
[Your address]
[Your phone] | [Your email]

${longDate(today)}

${v(f.insurer, "Insurance company")} — Appeals Department
[Appeals address from your denial letter]

RE: Request for internal appeal
Member: ${v(f.member_name, "Your full name")}
Member ID: ${v(f.member_id, "Member ID")}
Claim number: ${v(f.claim_number, "Claim number")}
Date of service: ${v(f.date_of_service, "Date of service", true)}
Provider: ${v(f.provider, "Provider name")}
Date of denial notice: ${v(f.notice_date, "Date on denial letter", true)}

To the Appeals Department:

I am writing to formally appeal the denial of the claim above${moneyText}. The notice states that the claim was denied because: "${v(f.reason_text, "denial reason as written on your letter")}".

${cat.argument}${context}

Under federal claims and appeals rules, I also request:
  • the specific plan provision, guideline or clinical criteria used to deny this claim;
  • copies of all documents, records and other information relevant to my claim, free of charge;
  • the name and credentials of any medical reviewer involved in the decision.

Please reverse this decision and process the claim for payment. If the denial is upheld, please send a written explanation and information on how to request an independent external review.

Enclosed:
${enclosures}
  ${cat.evidence.length + 1}. Copy of the denial notice

Sincerely,

${v(f.member_name, "Your full name")}
`;
  }

  function analyze(text, planType, today, extra) {
    const fields = parse(text);
    const category = classify(text, fields.carc_codes);
    const deadline = appealDeadline(fields.notice_date, planType || fields.plan_type_hint, today);
    const letter = draftLetter(fields, category, today, extra || "");
    return { fields, category, deadline, letter };
  }

  const api = { parse, parseDate, classify, appealDeadline, draftLetter, analyze, CATEGORIES, BY_KEY, PLAN_LABELS, longDate };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ClaimBack = api;
})(typeof window !== "undefined" ? window : globalThis);
