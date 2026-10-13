"""Human approval workflow manager with IPC polling and CLI fallback."""

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from agent.event_bus import emit, poll_events
from agent.state import ApprovalRequest, ClaimRecord, TaskState


@dataclass
class ApprovalDecision:
    claim_id: str
    decision: str  # APPROVED, DENIED, DEFERRED
    note: str = ""


class HumanApprovalFlow:
    def __init__(self, run_id: str, poll_interval: float = 0.5, timeout_seconds: float = 10.0):
        self.run_id = run_id
        self.poll_interval = poll_interval
        self.timeout_seconds = timeout_seconds

    def request_approval(
        self,
        claim: ClaimRecord,
        reason: str,
        state: Optional[TaskState] = None,
        auto_decision: Optional[str] = None,
    ) -> ApprovalDecision:
        """Post approval request to event bus and poll for resolution."""
        req = ApprovalRequest(
            claim_id=claim.claim_id,
            employee=claim.employee,
            amount_inr=claim.amount_inr,
            reason=reason,
            clauses=claim.clauses_triggered,
            evidence_summary=f"Vendor: {claim.vendor}, Date: {claim.date}, Receipt: {claim.receipt_file}",
            status="PENDING",
        )

        if state:
            state.pending_approvals.append(req)
            state.save()

        # Emit approval_requested event for UI dashboard
        last_event_id = emit(
            run_id=self.run_id,
            event_type="approval_requested",
            payload={
                "claim_id": claim.claim_id,
                "employee": claim.employee,
                "amount_inr": claim.amount_inr,
                "reason": reason,
                "clauses": claim.clauses_triggered,
                "vendor": claim.vendor,
                "date": claim.date,
            },
        )

        # If automated test decision provided (e.g. S2 harness or unit test)
        if auto_decision:
            decision = auto_decision.upper()
            emit(
                run_id=self.run_id,
                event_type="approval_response",
                payload={"claim_id": claim.claim_id, "decision": decision, "note": "Auto harness response"},
            )
            req.status = decision
            if decision == "APPROVED":
                claim.human_approved = True
            return ApprovalDecision(claim_id=claim.claim_id, decision=decision, note="Automated test response")

        # Poll for response event from UI
        start_time = time.time()
        while time.time() - start_time < self.timeout_seconds:
            new_events = poll_events(run_id=self.run_id, since_id=last_event_id, type_filter="approval_response")
            for ev in new_events:
                payload = ev.get("payload", {})
                if str(payload.get("claim_id")) == str(claim.claim_id):
                    decision = str(payload.get("decision", "DENIED")).upper()
                    req.status = decision
                    if decision == "APPROVED":
                        claim.human_approved = True
                    return ApprovalDecision(
                        claim_id=claim.claim_id,
                        decision=decision,
                        note=payload.get("note", "Decided via UI"),
                    )
            time.sleep(self.poll_interval)

        # Timeout reached: mark as DEFERRED
        req.status = "DEFERRED"
        return ApprovalDecision(
            claim_id=claim.claim_id,
            decision="DEFERRED",
            note="Approval request timed out without response.",
        )
