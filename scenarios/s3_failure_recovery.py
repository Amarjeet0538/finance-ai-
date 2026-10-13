"""Scenario 3: Failure Injection & Idempotent Recovery."""

import os
import sys
import uuid

# Enable all 4 failure injections
os.environ["INJECT_TRANSIENT_500"] = "1"
os.environ["INJECT_VALIDATION_ERROR"] = "1"
os.environ["INJECT_SLOW_PAGE"] = "1"
os.environ["INJECT_SESSION_EXPIRY"] = "1"
os.environ["SESSION_TTL_SECONDS"] = "5"

from agent.orchestrator import Orchestrator
from finance_app.app import reset_injections
from finance_app.seed import seed_database


def run_s3():
    print("=" * 60)
    print("RUNNING SCENARIO 3: FAILURE INJECTION & RECOVERY")
    print("=" * 60)

    seed_database(reset=True)
    reset_injections()

    run_id = f"s3_{uuid.uuid4().hex[:8]}"
    orchestrator = Orchestrator(run_id=run_id, goal="Process Priya Sharma's Q3 claims under failure injection")

    report = orchestrator.process_all_claims(
        auto_approvals={},
        scenario_name="s3",
    )

    print(f"\nScenario 3 Completed. Verification Verdict: {report.overall_result}")
    print(f"Passed: {report.pass_count} | Failed: {report.fail_count}")

    if report.overall_result != "PASS":
        print("VERIFICATION FAILED!")
        for r in report.results:
            if r.result == "FAIL":
                print(f"  - Claim {r.claim_id}: {r.details}")
        sys.exit(1)

    print("ALL SCENARIO 3 FAILURE RECOVERY CHECKS PASSED!")


if __name__ == "__main__":
    run_s3()
