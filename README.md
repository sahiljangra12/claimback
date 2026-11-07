# ClaimBack

**Fight a health insurance denial in minutes, not hours.**

Upload a denial letter or Explanation of Benefits (PDF, photo or text). ClaimBack reads it, explains in plain English why the claim was denied, tells you your appeal deadline, lists the evidence that usually wins, and drafts an appeal letter you can edit and send.

**Try it:** https://claude.ai/artifact/BeuTGbGHBb1DgPkBJvrwLr

There are two versions: a browser app in `web/` (everything runs on the user's device, no server) and a Python/Streamlit app (`app.py`).

## Why this exists

- Insurers on HealthCare.gov denied **19% of in-network claims** in 2024 (37% out-of-network) — KFF analysis of CMS transparency data.
- **Fewer than 1%** of denied claims are appealed, even though a large share of appeals succeed.
- Most people don't know they can appeal, or give up because the process is confusing.

## What the MVP does

| Step | What happens | Code |
|---|---|---|
| Read | PDF text extraction, OCR for photos/scans (Tesseract) | `claimback/extract.py` |
| Parse | Insurer, member ID, claim number, dates, amounts, CARC reason codes, denial reason | `claimback/parse.py` |
| Classify | 12 denial categories from standard CARC codes, then keywords | `claimback/classify.py` |
| Deadline | Federal appeal windows by plan type (employer/ERISA, Marketplace, Medicaid, Medicare Advantage) | `claimback/deadlines.py` |
| Letter | Appeal letter with the right argument and evidence list; optional AI polish that is told never to invent facts | `claimback/letter.py` |
| App | Streamlit UI where the user checks and corrects every field | `app.py` |

## Run it

Browser version: open `web/index.html`, or serve the folder (`python3 -m http.server -d web`). Tests: `node web/test.js`. `netlify.toml` publishes `web/` as a static site.

Python version:

```bash
pip install -r requirements.txt
# OCR also needs the Tesseract binary:  brew install tesseract   (macOS)
streamlit run app.py
```

Try the files in `samples/`. Run tests with `pytest`.

Optional AI polishing: `export ANTHROPIC_API_KEY=...` and switch on "Polish with AI" in the app.

## Roadmap

1. **Denial-risk model** — insurer/plan-level denial rates from CMS Transparency in Coverage public use files, combined with appeal outcomes from users, to predict which denials are winnable and which arguments work against which insurer.
2. **Accounts and tracking** — appeal status, reminders before deadlines, follow-ups.
3. **Insurer data connection** — pull claims and EOBs through payers' CMS-mandated Patient Access (FHIR) APIs instead of OCR.
4. **External review** — guided filing when an internal appeal fails.
5. **Clinic dashboard** — batch appeals for small practices (B2B).

## Important

ClaimBack provides general information, not legal or medical advice. The deadline on the denial notice always takes priority. Uploaded files are processed in memory and not stored. Before handling real patient data at scale, the product needs a security review, a privacy policy, and compliance with the FTC Health Breach Notification Rule and state health-privacy laws.
