"""Guardrail Gate: Deterministic pre-execution safety and policy enforcement."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from agent.state import ClaimRecord, TaskState
from agent.tools.schemas import ToolResult


@dataclass
class ProposedAction:
    tool_name: str
    arguments: Dict[str, Any]


@dataclass
class GateDecision:
    verdict: str  # ALLOW, NEEDS_APPROVAL, FORBIDDEN
    rule_triggered: Optional[str] = None
    reason: str = ""


class GuardrailGate:
    def __init__(self, target_employee: str = "Priya Sharma"):
        self.target_employee = target_employee

    def evaluate_action(
        self,
        action: ProposedAction,
        claim: Optional[ClaimRecord] = None,
        state: Optional[TaskState] = None,
    ) -> GateDecision:
        tool_name = action.tool_name
        args = action.arguments

        # 1. FORBIDDEN: Any navigation to /admin or forbidden zone
        if tool_name in ("browser_open", "open_url"):
            url = str(args.get("url", "")).lower()
            if "/admin" in url:
                return GateDecision(
                    verdict="FORBIDDEN",
                    rule_triggered="RULE_FORBIDDEN_ZONE",
                    reason="Access to administrative endpoint /admin is strictly prohibited.",
                )
            # Enforce that the agent never calls /api/ endpoints (reserved for Verifier)
            if "/api/" in url:
                return GateDecision(
                    verdict="FORBIDDEN",
                    rule_triggered="RULE_VERIFIER_API_PROTECTION",
                    reason="Direct agent access to internal verifier API (/api/) is prohibited.",
                )

        # 2. FORBIDDEN: Actions targeting other employees
        emp_in_args = args.get("employee")
        if emp_in_args and str(emp_in_args).strip().lower() != self.target_employee.lower():
            return GateDecision(
                verdict="FORBIDDEN",
                rule_triggered="RULE_EMPLOYEE_ISOLATION",
                reason=f"Action targets employee '{emp_in_args}', outside authorized scope '{self.target_employee}'.",
            )

        # 3. FORBIDDEN: Delete operations
        if "delete" in tool_name.lower() or any("delete" in str(v).lower() for v in args.values()):
            return GateDecision(
                verdict="FORBIDDEN",
                rule_triggered="RULE_NO_DESTRUCTIVE_ACTIONS",
                reason="Destructive actions (DELETE) are prohibited.",
            )

        # 4. Check claim policy verdict if action is a claim submission
        if tool_name in ("file_claim_web", "submit_claim") or (
            tool_name == "browser_click" and "submit" in str(args.get("selector_or_text", "")).lower()
        ):
            if claim:
                # If claim is REJECT, submitting it is FORBIDDEN
                if claim.verdict == "REJECT":
                    return GateDecision(
                        verdict="FORBIDDEN",
                        rule_triggered=f"POLICY_{claim.clauses_triggered[0] if claim.clauses_triggered else 'REJECT'}",
                        reason=f"Submitting rejected claim #{claim.claim_id} is prohibited: {claim.notes}",
                    )

                # If claim is NEEDS_APPROVAL and not yet approved by human
                if claim.verdict == "NEEDS_APPROVAL" and not getattr(claim, "human_approved", False):
                    return GateDecision(
                        verdict="NEEDS_APPROVAL",
                        rule_triggered="POLICY_NEEDS_APPROVAL",
                        reason=f"Claim #{claim.claim_id} requires human approval before submission.",
                    )

                # High-value auto-approve block (P10)
                if claim.amount_inr > 10000.0 and not getattr(claim, "human_approved", False):
                    return GateDecision(
                        verdict="NEEDS_APPROVAL",
                        rule_triggered="POLICY_P10",
                        reason=f"Claim #{claim.claim_id} amount exceeds ₹10,000 threshold, requiring human signoff.",
                    )

        return GateDecision(verdict="ALLOW", rule_triggered=None, reason="Action permitted.")
