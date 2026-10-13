"""Scenario 1: Happy Path (Clean ALLOW Claims 1, 2, 6)."""

import sys
import uuid
from agent.orchestrator import Orchestrator
from finance_app.seed import seed_database


def run_s1():
    print("=" * 60)
    print("RUNNING SCENARIO 1: HAPPY PATH (CLAIMS 1, 2, 6)")
    print("=" * 60)

    # Reset database for deterministic run
    seed_database(reset=True)

    run_id = f"s1_{uuid.uuid4().hex[:8]}"
    orchestrator = Orchestrator(run_id=run_id, goal="Process Priya Sharma's Q3 clean expense claims")

    # Only process clean ALLOW claims in S1
    report = orchestrator.process_all_claims(
        auto_approvals={},
        scenario_name="s1",
    )

    print(f"\nScenario 1 Completed. Verification Verdict: {report.overall_result}")
    print(f"Passed: {report.pass_count} | Failed: {report.fail_count}")

    if report.overall_result != "PASS":
        print("VERIFICATION FAILED!")
        sys.exit(1)

    print("ALL SCENARIO 1 CHECKS PASSED!")


if __name__ == "__main__":
    run_s1()
