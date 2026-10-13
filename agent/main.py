"""CLI entry point for running the CenterAlign Autonomous Company Operator."""

import argparse
import sys
import uuid
from agent.orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(description="CenterAlign Autonomous Company Operator")
    parser.add_argument("--run-id", type=str, default=None, help="Run ID for tracking")
    parser.add_argument("--claims", type=str, default="1,2", help="Comma-separated claim IDs to process")
    parser.add_argument("--goal", type=str, default="Process Priya Sharma's Q3 expense claims", help="High-level goal")
    args = parser.parse_args()

    run_id = args.run_id or f"run_{uuid.uuid4().hex[:8]}"
    claim_ids = [c.strip() for c in args.claims.split(",") if c.strip()]

    print(f"Starting Operator [Run ID: {run_id}]")
    print(f"Goal: {args.goal}")
    print(f"Target Claims: {claim_ids}")

    orchestrator = Orchestrator(run_id=run_id, goal=args.goal)
    orchestrator.execute_claims_phase2(claim_ids=claim_ids)

    print(f"Execution finished for run {run_id}. State and audit logs written to reports/.")


if __name__ == "__main__":
    main()
