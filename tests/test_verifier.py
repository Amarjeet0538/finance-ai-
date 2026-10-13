"""Unit tests for the Independent Verifier and corruption detection."""

import sqlite3
import pytest
from finance_app.database import reset_db
from finance_app.models import ExpenseClaim
from finance_app.seed import seed_database
from agent.verifier import verify_run


@pytest.fixture
def clean_db():
    seed_database(reset=True)
    return True


def insert_mock_claim(claim_id: int, employee: str, date: str, category: str, amount: float, vendor: str, cost_center: str):
    conn = sqlite3.connect("finance_app/finance.db")
    try:
        conn.execute(
            """INSERT INTO expense_claims (id, employee, date, category, amount_inr, currency, vendor, description, cost_center, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'INR', ?, '', ?, 'SUBMITTED', datetime('now'))""",
            (claim_id, employee, date, category, amount, vendor, cost_center),
        )
        conn.commit()
    finally:
        conn.close()


def test_verifier_s1_pass(clean_db):
    # Insert expected S1 claims: 1, 2, 6
    insert_mock_claim(1, "Priya Sharma", "2026-10-08", "Meals", 850.0, "Main Street Cafe", "CC-42")
    insert_mock_claim(2, "Priya Sharma", "2026-10-03", "Cab", 1200.0, "Uber India", "CC-42")
    insert_mock_claim(6, "Priya Sharma", "2026-09-13", "Lodging", 5500.0, "Lemon Tree Hotel", "CC-42")

    report = verify_run(scenario="s1", run_id="test_v_s1")
    assert report.overall_result == "PASS"
    assert report.fail_count == 0
    assert report.pass_count == 12


def test_verifier_detects_missing_claim(clean_db):
    # Only insert claim 1 and 2, omit claim 6
    insert_mock_claim(1, "Priya Sharma", "2026-10-08", "Meals", 850.0, "Main Street Cafe", "CC-42")
    insert_mock_claim(2, "Priya Sharma", "2026-10-03", "Cab", 1200.0, "Uber India", "CC-42")

    report = verify_run(scenario="s1", run_id="test_v_missing")
    assert report.overall_result == "FAIL"
    assert report.fail_count >= 1
    # Claim 6 failed
    failed_ids = [r.claim_id for r in report.results if r.result == "FAIL"]
    assert "6" in failed_ids


def test_verifier_detects_corrupted_data(clean_db):
    # Insert valid S1 claims
    insert_mock_claim(1, "Priya Sharma", "2026-10-08", "Meals", 850.0, "Main Street Cafe", "CC-42")
    insert_mock_claim(2, "Priya Sharma", "2026-10-03", "Cab", 1200.0, "Uber India", "CC-42")
    insert_mock_claim(6, "Priya Sharma", "2026-09-13", "Lodging", 5500.0, "Lemon Tree Hotel", "CC-42")

    # Corrupt claim 1 amount in DB from 850 to 9999
    conn = sqlite3.connect("finance_app/finance.db")
    try:
        conn.execute("UPDATE expense_claims SET amount_inr = 9999.0 WHERE id = 1")
        conn.commit()
    finally:
        conn.close()

    report = verify_run(scenario="s1", run_id="test_v_corrupted")
    assert report.overall_result == "FAIL"
    failed_ids = [r.claim_id for r in report.results if r.result == "FAIL"]
    assert "1" in failed_ids
