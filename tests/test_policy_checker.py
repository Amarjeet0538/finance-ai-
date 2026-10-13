"""Unit tests for PolicyChecker validating rules P1 through P11 and the 12 canonical claims."""

import json
from pathlib import Path
import pytest

from agent.claim_extractor import ClaimExtractor
from agent.policy_checker import (
    check_claim,
    check_rule_p1_receipt,
    check_rule_p2_meal_limit,
    check_rule_p3_cab_limit,
    check_rule_p4_flight_preapproval,
    check_rule_p5_lodging_limit,
    check_rule_p6_software,
    check_rule_p7_client_entertainment,
    check_rule_p8_stale_date,
    check_rule_p9_alcohol,
    check_rule_p11_duplicate,
)
from agent.state import ClaimRecord


@pytest.fixture
def inbox_emails():
    with open("company_context/inbox_export.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def extracted_claims():
    extractor = ClaimExtractor()
    return extractor.extract_all()


def test_rule_p1_receipt():
    # Pass: under 500 without receipt
    c_pass = ClaimRecord("1", "Priya", "2026-10-08", "Meals", 400.0, "Cafe", "c.txt")
    setattr(c_pass, "has_receipt", False)
    assert not check_rule_p1_receipt(c_pass).fired

    # Fail: over 500 without receipt
    c_fail = ClaimRecord("2", "Priya", "2026-10-08", "Meals", 1800.0, "Cafe", "c.txt")
    setattr(c_fail, "has_receipt", False)
    r = check_rule_p1_receipt(c_fail)
    assert r.fired and r.clause == "P1" and r.verdict_contribution == "REJECT"


def test_rule_p2_aggregation():
    # Two same-day meals of 850 each (850 + 850 = 1700 > 1500)
    c1 = ClaimRecord("1", "Priya", "2026-10-08", "Meals", 850.0, "Cafe A", "c1.txt")
    c2 = ClaimRecord("2", "Priya", "2026-10-08", "Meals", 850.0, "Cafe B", "c2.txt")
    r1 = check_rule_p2_meal_limit(c1, [c1, c2])
    assert r1.fired and r1.clause == "P2" and r1.verdict_contribution == "REJECT"


def test_rule_p3_cab():
    c_pass = ClaimRecord("1", "Priya", "2026-10-03", "Cab", 1200.0, "Uber", "c.txt")
    assert not check_rule_p3_cab_limit(c_pass).fired

    c_fail = ClaimRecord("2", "Priya", "2026-10-03", "Cab", 3500.0, "Uber", "c.txt")
    assert check_rule_p3_cab_limit(c_fail).fired


def test_rule_p4_flight_preapproval(inbox_emails):
    # With manager approval ref
    c_approved = ClaimRecord("4", "Priya Sharma", "2026-09-23", "Flight", 18500.0, "IndiGo", "c4.txt")
    setattr(c_approved, "inbox_ref", "MSG-001")
    assert not check_rule_p4_flight_preapproval(c_approved, inbox_emails).fired

    # Without approval ref
    c_unapproved = ClaimRecord("5", "Priya Sharma", "2026-09-18", "Flight", 18500.0, "Air India", "c5.txt")
    setattr(c_unapproved, "inbox_ref", None)
    r = check_rule_p4_flight_preapproval(c_unapproved, inbox_emails)
    assert r.fired and r.clause == "P4" and r.verdict_contribution == "NEEDS_APPROVAL"


def test_rule_p5_lodging():
    c_pass = ClaimRecord("6", "Priya", "2026-09-13", "Lodging", 5500.0, "Hotel", "c.txt")
    assert not check_rule_p5_lodging_limit(c_pass).fired

    c_fail = ClaimRecord("6", "Priya", "2026-09-13", "Lodging", 6500.0, "Hotel", "c.txt")
    assert check_rule_p5_lodging_limit(c_fail).fired


def test_rule_p6_software():
    c_pass = ClaimRecord("7", "Priya", "2026-09-08", "Software", 4000.0, "SaaS", "c.txt")
    assert not check_rule_p6_software(c_pass).fired

    c_fail = ClaimRecord("7", "Priya", "2026-09-08", "Software", 7200.0, "JetBrains", "c.txt")
    assert check_rule_p6_software(c_fail).fired


def test_rule_p7_client_entertainment():
    c = ClaimRecord("12", "Priya", "2026-08-24", "Client entertainment", 2800.0, "Pavilion", "c.txt")
    r = check_rule_p7_client_entertainment(c)
    assert r.fired and r.clause == "P7" and r.verdict_contribution == "NEEDS_APPROVAL"


def test_rule_p8_stale_date():
    # Fixed policy reference date 2026-10-13
    # 2026-06-15 is 120 days old (> 90 days)
    c_old = ClaimRecord("9", "Priya", "2026-06-15", "Office", 3000.0, "Cowork", "c.txt")
    r = check_rule_p8_stale_date(c_old)
    assert r.fired and r.clause == "P8" and r.verdict_contribution == "REJECT"

    c_recent = ClaimRecord("1", "Priya", "2026-10-08", "Office", 3000.0, "Cowork", "c.txt")
    assert not check_rule_p8_stale_date(c_recent).fired


def test_rule_p9_alcohol():
    c_clean = ClaimRecord("1", "Priya", "2026-08-29", "Meals", 1300.0, "Grill", "c.txt", notes="dinner", receipt_text="Steak 750")
    assert not check_rule_p9_alcohol(c_clean).fired

    c_alcohol = ClaimRecord("11", "Priya", "2026-08-29", "Meals", 1300.0, "Grill", "c.txt", notes="dinner", receipt_text="Beer (Alcohol beverage) 550")
    r = check_rule_p9_alcohol(c_alcohol)
    assert r.fired and r.clause == "P9" and r.verdict_contribution == "REJECT"


def test_rule_p11_duplicate():
    c1 = ClaimRecord("1", "Priya", "2026-10-08", "Meals", 850.0, "Main St", "c1.txt")
    c10 = ClaimRecord("10", "Priya", "2026-10-08", "Meals", 850.0, "Main St", "c10.txt")
    r = check_rule_p11_duplicate(c10, [c1, c10])
    assert r.fired and r.clause == "P11" and r.verdict_contribution == "REJECT"


def test_canonical_12_claims_verdicts(extracted_claims, inbox_emails):
    """Test all 12 canonical claims matching the roadmap verdict table exactly."""
    verdicts = {}
    for c in extracted_claims:
        v = check_claim(c, extracted_claims, inbox_emails)
        verdicts[c.claim_id] = v

    # Claim 1: ALLOW, []
    assert verdicts["1"].verdict == "ALLOW"
    assert verdicts["1"].clauses_triggered == []

    # Claim 2: ALLOW, []
    assert verdicts["2"].verdict == "ALLOW"
    assert verdicts["2"].clauses_triggered == []

    # Claim 3: REJECT, ["P2"]
    assert verdicts["3"].verdict == "REJECT"
    assert verdicts["3"].clauses_triggered == ["P2"]

    # Claim 4: NEEDS_APPROVAL, ["P10"]
    assert verdicts["4"].verdict == "NEEDS_APPROVAL"
    assert verdicts["4"].clauses_triggered == ["P10"]

    # Claim 5: NEEDS_APPROVAL, ["P4", "P10"]
    assert verdicts["5"].verdict == "NEEDS_APPROVAL"
    assert set(verdicts["5"].clauses_triggered) == {"P4", "P10"}

    # Claim 6: ALLOW, []
    assert verdicts["6"].verdict == "ALLOW"
    assert verdicts["6"].clauses_triggered == []

    # Claim 7: NEEDS_APPROVAL, ["P6"]
    assert verdicts["7"].verdict == "NEEDS_APPROVAL"
    assert verdicts["7"].clauses_triggered == ["P6"]

    # Claim 8: REJECT, ["P1"]
    assert verdicts["8"].verdict == "REJECT"
    assert verdicts["8"].clauses_triggered == ["P1"]

    # Claim 9: REJECT, ["P8"]
    assert verdicts["9"].verdict == "REJECT"
    assert verdicts["9"].clauses_triggered == ["P8"]

    # Claim 10: REJECT, ["P11"]
    assert verdicts["10"].verdict == "REJECT"
    assert verdicts["10"].clauses_triggered == ["P11"]

    # Claim 11: REJECT, ["P9"]
    assert verdicts["11"].verdict == "REJECT"
    assert verdicts["11"].clauses_triggered == ["P9"]

    # Claim 12: NEEDS_APPROVAL, ["P7"]
    assert verdicts["12"].verdict == "NEEDS_APPROVAL"
    assert verdicts["12"].clauses_triggered == ["P7"]

    # Tally assertion: exactly 3 ALLOW, 4 NEEDS_APPROVAL, 5 REJECT
    tally = {}
    for v in verdicts.values():
        tally[v.verdict] = tally.get(v.verdict, 0) + 1

    assert tally == {"ALLOW": 3, "NEEDS_APPROVAL": 4, "REJECT": 5}, f"Unexpected tally: {tally}"
