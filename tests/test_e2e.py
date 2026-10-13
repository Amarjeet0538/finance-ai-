"""End-to-End integration test running complete S1 happy path."""

import json
import os
from pathlib import Path
import pytest

from agent.orchestrator import Orchestrator
from agent.verifier import verify_run
from finance_app.seed import seed_database


def test_e2e_scenario_1_happy_path():
    # 1. Reset database
    seed_database(reset=True)

    # 2. Run orchestrator on S1
    run_id = "test_e2e_run"
    orchestrator = Orchestrator(run_id=run_id, goal="E2E test: process clean claims")

    report = orchestrator.process_all_claims(
        auto_approvals={},
        scenario_name="s1",
    )

    # 3. Assertions
    assert report.overall_result == "PASS", f"Verification failed: {report.overall_result}"
    assert report.fail_count == 0, f"Expected 0 failures, got {report.fail_count}"
    assert report.pass_count == 12, f"Expected 12 ground truth passes, got {report.pass_count}"

    # 4. Report generated
    report_file = Path("reports") / f"run_{run_id}_report.md"
    assert report_file.exists(), "Markdown report file missing"

    # 5. Audit log validation
    audit_file = Path("reports") / f"audit_{run_id}.jsonl"
    assert audit_file.exists(), "Audit log file missing"

    with open(audit_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    entries = [json.loads(line) for line in lines]
    assert len(entries) > 0

    # Ensure no unhandled errors
    forbidden_tool_calls = [e for e in entries if e.get("type") == "tool_call" and e.get("gate_decision") == "FORBIDDEN" and e.get("tool_name") == "browser_open"]
    assert len(forbidden_tool_calls) == 0, "Unexpected forbidden tool calls during happy path"
