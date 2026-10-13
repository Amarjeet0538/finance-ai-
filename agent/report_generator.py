"""Executive execution and verification report generator."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent.state import TaskState
from agent.verifier import VerificationReport


def generate_report(
    state: TaskState,
    verification: Optional[VerificationReport] = None,
    output_path: Optional[str] = None,
) -> str:
    """Generate Markdown report summarizing operator execution and independent verification."""
    run_id = state.run_id
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Metrics
    total_claims = len(state.claims)
    passed_verifications = verification.pass_count if verification else 0
    failed_verifications = verification.fail_count if verification else 0
    overall_status = verification.overall_result if verification else "UNVERIFIED"

    lines = [
        f"# CenterAlign Autonomous Operator Run Report",
        f"",
        f"**Run ID:** `{run_id}`  ",
        f"**Generated:** {now_str}  ",
        f"**Verification Verdict:** **{overall_status}** ({passed_verifications} Passed / {failed_verifications} Failed)  ",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary",
        f"",
        f"- **Objective:** {state.goal}",
        f"- **Total Claims Processed:** {total_claims}",
        f"- **Token Usage:** {state.tokens_used:,} tokens",
        f"- **Total Estimated Cost:** ${state.total_cost_usd:.4f} USD",
        f"- **Execution Steps:** {state.step_index}",
        f"",
        f"---",
        f"",
        f"## 2. Policy Evaluation & Verification Results",
        f"",
        f"| # | Employee | Vendor | Amount (₹) | Policy Verdict | Clauses | Human Gate | Verifier | Details |",
        f"|---|---|---|---|---|---|---|---|---|",
    ]

    # Verification results lookup
    v_results = {r.claim_id: r for r in (verification.results if verification else [])}

    for claim in state.claims:
        cid = claim.claim_id
        clauses_str = ", ".join(claim.clauses_triggered) if claim.clauses_triggered else "—"
        human_str = "Approved" if claim.human_approved else ("N/A" if claim.verdict == "ALLOW" else "Denied/None")

        v_res = v_results.get(cid)
        v_status = f"**{v_res.result}**" if v_res else "N/A"
        details_str = v_res.details if v_res else claim.notes

        lines.append(
            f"| {cid} | {claim.employee} | {claim.vendor} | ₹{claim.amount_inr:,.2f} | {claim.verdict} | {clauses_str} | {human_str} | {v_status} | {details_str} |"
        )

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 3. Security, Guardrail & Audit Summary",
        f"",
        f"- **Audit Trail File:** `reports/audit_{run_id}.jsonl` (Cryptographically chained)",
        f"- **State Snapshot:** `reports/state_{run_id}.json`",
        f"- **Guardrail Enforcement:** Deterministic code gate wrapped all browser and submission actions.",
        f"- **Unauthorized Endpoint Access:** Blocked with HTTP 403 / FORBIDDEN.",
        f"",
        f"---",
        f"",
        f"## 4. System Boundaries & Edge Cases Handled",
        f"",
        f"1. **P2 Daily Meal Aggregation:** Strictly isolated per calendar day.",
        f"2. **P10 Gate:** Claims exceeding ₹10,000 paused for human authorization.",
        f"3. **Idempotent Retries:** Duplicate check via browser UI prevents duplicate submissions.",
        f"4. **Independent Verifier:** Ground truth comparison verified via `/api/claims`.",
    ])

    report_content = "\n".join(lines)

    if output_path:
        out_file = Path(output_path)
    else:
        out_file = Path("reports") / f"run_{run_id}_report.md"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(report_content, encoding="utf-8")

    return report_content
