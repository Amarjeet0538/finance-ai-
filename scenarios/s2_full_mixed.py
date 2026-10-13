"""Scenario 2: Full Mixed 12 Claims with Human Approvals."""

import sys
import uuid
from agent.orchestrator import Orchestrator
from finance_app.seed import seed_database


def run_s2():
    print("=" * 60)
    print("RUNNING SCENARIO 2: FULL MIXED 12 CLAIMS")
    print("=" * 60)

    seed_database(reset=True)

    run_id = f"s2_{uuid.uuid4().hex[:8]}"
    orchestrator = Orchestrator(run_id=run_id, goal="Process Priya Sharma's Q3 mixed expense claims")

    # In S2: Approve claims 4 & 12; Deny claims 5 & 7
    approvals = {
        "4": "APPROVED",
        "12": "APPROVED",
        "5": "DENIED",
        "7": "DENIED",
    }

    report = orchestrator.process_all_claims(
        auto_approvals=approvals,
        scenario_name="s2",
    )

    print(f"\nScenario 2 Completed. Verification Verdict: {report.overall_result}")
    print(f"Passed: {report.pass_count} | Failed: {report.fail_count}")

    if report.overall_result != "PASS":
        print("VERIFICATION FAILED!")
        for r in report.results:
            if r.result == "FAIL":
                print(f"  - Claim {r.claim_id}: {r.details}")
        sys.exit(1)

    print("ALL SCENARIO 2 CHECKS PASSED!")


if __name__ == "__main__":
    run_s2()
