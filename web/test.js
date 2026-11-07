// Run: node web/test.js — same checks as tests/test_claimback.py
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const CB = require("./claimback.js");

const sample = (n) => fs.readFileSync(path.join(__dirname, "..", "samples", n), "utf8");
const today = "2026-11-07";

let a = CB.analyze(sample("sample_denial_prior_auth.txt"), null, today);
assert.equal(a.fields.insurer, "Aetna");
assert.equal(a.fields.member_id, "W123456789");
assert.equal(a.fields.claim_number, "2026091500123");
assert.equal(a.fields.date_of_service, "2026-08-28");
assert.equal(a.fields.notice_date, "2026-09-15");
assert.equal(a.fields.amount_denied, 2450);
assert.ok(a.fields.carc_codes.includes("197"));
assert.equal(a.fields.provider, "Baltimore Imaging Center");
assert.equal(a.fields.service, "MRI lumbar spine without contrast");
assert.equal(a.category.key, "prior_auth");
assert.equal(a.deadline.planType, "erisa");
assert.equal(a.deadline.due, "2027-03-14");
assert.ok(a.letter.includes("W123456789") && a.letter.includes("$2,450.00"));

a = CB.analyze(sample("sample_denial_medical_necessity.txt"), null, today);
assert.equal(a.fields.insurer, "UnitedHealthcare");
assert.equal(a.fields.member_name, "Priya Shah");
assert.equal(a.fields.claim_number, "UHC-55501-ZQ");
assert.equal(a.fields.date_of_service, "2026-09-10");
assert.equal(a.fields.notice_date, "2026-10-02");
assert.equal(a.fields.service, "Biologic asthma therapy (dupilumab)");
assert.equal(a.category.key, "medical_necessity");
assert.equal(a.deadline.planType, "aca_individual");

assert.equal(CB.classify("This provider is out-of-network for your plan.").key, "out_of_network");
assert.equal(CB.classify("Considered experimental and investigational.").key, "experimental");
assert.equal(CB.classify("Nothing useful here.").key, "unknown");
assert.equal(CB.classify("not covered", ["50"]).key, "medical_necessity");

a = CB.analyze("Your claim was denied.", null, today);
assert.ok(a.letter.includes("[Member ID]") && a.letter.includes("[Claim number]"));

const f = CB.parse("CLAIM NUMBER: AB-99812\nMember ID: XYZ12345\nDate of service 3/4/26");
assert.equal(f.claim_number, "AB-99812");
assert.equal(f.member_id, "XYZ12345");
assert.equal(f.date_of_service, "2026-03-04");

console.log("all web tests passed");
