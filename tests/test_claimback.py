from datetime import date
from pathlib import Path

from claimback import analyze
from claimback.classify import classify
from claimback.deadlines import appeal_deadline
from claimback.parse import parse

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load(name):
    return (SAMPLES / name).read_text()


def test_prior_auth_sample():
    a = analyze(load("sample_denial_prior_auth.txt"), today=date(2026, 11, 7))
    f = a.fields
    assert f.insurer == "Aetna"
    assert f.member_id == "W123456789"
    assert f.claim_number == "2026091500123"
    assert f.date_of_service == date(2026, 8, 28)
    assert f.notice_date == date(2026, 9, 15)
    assert f.amount_denied == 2450.00
    assert "197" in f.carc_codes
    assert f.provider == "Baltimore Imaging Center"
    assert f.service == "MRI lumbar spine without contrast"
    assert a.category.key == "prior_auth"
    assert a.deadline.plan_type == "erisa"
    assert a.deadline.due == date(2027, 3, 14)
    assert "W123456789" in a.letter and "$2,450.00" in a.letter


def test_medical_necessity_sample():
    a = analyze(load("sample_denial_medical_necessity.txt"), today=date(2026, 11, 7))
    f = a.fields
    assert f.insurer == "UnitedHealthcare"
    assert f.member_name == "Priya Shah"
    assert f.claim_number == "UHC-55501-ZQ"
    assert f.date_of_service == date(2026, 9, 10)
    assert f.notice_date == date(2026, 10, 2)
    assert f.service == "Biologic asthma therapy (dupilumab)"
    assert a.category.key == "medical_necessity"
    assert a.deadline.plan_type == "aca_individual"


def test_scanned_image_ocr():
    import shutil
    import pytest
    if not shutil.which("tesseract"):
        pytest.skip("tesseract not installed")
    from claimback.extract import text_from_path
    a = analyze(text_from_path(SAMPLES / "sample_denial_scan.png"))
    assert a.fields.member_id == "W123456789"
    assert a.category.key == "prior_auth"


def test_keyword_classification():
    assert classify("This provider is out-of-network for your plan.").key == "out_of_network"
    assert classify("Considered experimental and investigational.").key == "experimental"
    assert classify("Nothing useful here.").key == "unknown"


def test_carc_beats_keywords():
    assert classify("not covered", ["50"]).key == "medical_necessity"


def test_missing_fields_become_placeholders():
    a = analyze("Your claim was denied.")
    assert "[Member ID]" in a.letter and "[Claim number]" in a.letter


def test_deadline_without_notice_date():
    d = appeal_deadline(None, None)
    assert d.due is None and d.days == 180


def test_parse_handles_ocr_noise():
    f = parse("CLAIM NUMBER: AB-99812\nMember ID: XYZ12345\nDate of service 3/4/26")
    assert f.claim_number == "AB-99812" and f.member_id == "XYZ12345"
    assert f.date_of_service == date(2026, 3, 4)
