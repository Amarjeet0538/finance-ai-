"""Unit tests for ClaimExtractor."""

import pytest
from agent.claim_extractor import ClaimExtractor


def test_claim_extractor_total_count():
    extractor = ClaimExtractor()
    claims = extractor.extract_all()
    assert len(claims) == 12, f"Expected 12 claims, found {len(claims)}"


def test_claim_4_inbox_ref():
    extractor = ClaimExtractor()
    claims = {c.claim_id: c for c in extractor.extract_all()}
    c4 = claims["4"]
    assert getattr(c4, "inbox_ref", None) == "MSG-001"


def test_claim_8_missing_receipt():
    extractor = ClaimExtractor()
    claims = {c.claim_id: c for c in extractor.extract_all()}
    c8 = claims["8"]
    assert getattr(c8, "has_receipt", True) is False


def test_claim_11_alcohol_flag():
    extractor = ClaimExtractor()
    claims = {c.claim_id: c for c in extractor.extract_all()}
    c11 = claims["11"]
    assert "ALCOHOL" in c11.notes.upper() or "alcohol" in c11.receipt_text.lower()


def test_claim_12_ambiguous_category():
    extractor = ClaimExtractor()
    claims = {c.claim_id: c for c in extractor.extract_all()}
    c12 = claims["12"]
    assert getattr(c12, "category_ambiguous", False) is True
    assert c12.category == "Meals"
