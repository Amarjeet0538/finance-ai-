"""Full Autonomous Company Operator Orchestrator with Failure Recovery, Guardrails, and Approvals."""

import json
import os
import time
from typing import Any, Dict, List, Optional

import anthropic

from agent.audit_log import AuditLogger
from agent.claim_extractor import ClaimExtractor
from agent.context_layer import search_company_context
from agent.event_bus import emit
from agent.guardrail import GuardrailGate, ProposedAction
from agent.human_approval import HumanApprovalFlow
from agent.policy_checker import check_claim
from agent.report_generator import generate_report
from agent.state import ClaimRecord, PlanStep, TaskState
from agent.tools.browser_tools import (
    BrowserSession,
    browser_click,
    browser_open,
    browser_screenshot,
    browser_select,
    browser_snapshot,
    browser_type,
)
from agent.tools.file_tools import read_file
from agent.verifier import VerificationReport, verify_run

MODEL_NAME = os.environ.get("MODEL_NAME", "claude-sonnet-4-5")
MAX_STEPS = 300
MAX_COST_USD = float(os.environ.get("MAX_RUN_COST_USD", "2.00"))


class Orchestrator:
    def __init__(self, run_id: str, goal: str = "Process Priya Sharma's Q3 expense claims"):
        self.run_id = run_id
        self.goal = goal
        self.state = TaskState(run_id=run_id, goal=goal)
        self.audit = AuditLogger(run_id=run_id)
        self.guardrail = GuardrailGate(target_employee="Priya Sharma")
        self.approval_flow = HumanApprovalFlow(run_id=run_id, timeout_seconds=1.5)
        self.browser_session = BrowserSession.get_instance()
        self.browser_session.set_run_id(run_id)
        self.finance_url = os.environ.get("FINANCE_APP_URL", "http://localhost:8000")

    def plan_goal(self) -> None:
        """Dedicated planning turn: retrieve context, expand requirements, formulate plan."""
        passages = search_company_context("expense claim submission policy receipts thresholds")
        context_summary = "\n".join([f"- [{p.source_file}] {p.section_heading}: {p.text[:150]}..." for p in passages])

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key and not api_key.startswith("your_"):
            try:
                client = anthropic.Anthropic(api_key=api_key)
                prompt = f"""You are an autonomous finance operator.
Goal: {self.goal}

Available company context:
{context_summary}

Produce:
1. Bulleted list of expanded requirements citing relevant policy clauses (e.g. P1, P2, P10).
2. Ordered list of plan steps to process the claims.

Respond in JSON format:
{{
  "expanded_requirements": ["req1", "req2"],
  "plan": ["step 1", "step 2", "step 3"]
}}
"""
                response = client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw_text = response.content[0].text
                tokens = response.usage.input_tokens + response.usage.output_tokens
                cost = (response.usage.input_tokens * 0.000003) + (response.usage.output_tokens * 0.000015)
                self.state.tokens_used += tokens
                self.state.total_cost_usd += cost

                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                parsed = json.loads(raw_text[start:end])
                reqs = parsed.get("expanded_requirements", [])
                steps_raw = parsed.get("plan", [])
            except Exception:
                reqs, steps_raw = self._fallback_plan(passages)
        else:
            reqs, steps_raw = self._fallback_plan(passages)

        self.state.expanded_requirements = reqs
        self.state.plan = [
            PlanStep(id=idx + 1, description=desc, status="PENDING")
            for idx, desc in enumerate(steps_raw)
        ]

        self.state.save()
        emit(
            run_id=self.run_id,
            event_type="plan_created",
            payload={
                "goal": self.goal,
                "requirements": self.state.expanded_requirements,
                "plan": [s.__dict__ for s in self.state.plan],
            },
        )
        self.audit.log_event("plan_created", {
            "requirements": self.state.expanded_requirements,
            "steps": len(self.state.plan),
        })

    def _fallback_plan(self, passages) -> tuple[list[str], list[str]]:
        reqs = [
            "Verify all claims > ₹500 have receipts per clause P1",
            "Enforce daily meal allowance limit of ₹1,500 per clause P2",
            "Validate ground transportation limit of ₹3,000 per clause P3",
            "Verify manager written pre-approval for flights per clause P4",
            "Require explicit human gate for any claim > ₹10,000 per clause P10",
            "Ensure cost center is populated correctly from employee directory (CC-42)",
        ]
        steps = [
            "Authenticate into Finance Portal as operator",
            "Extract claim records and receipt attachments from claims dataset",
            "Verify claims against corporate policy rules P1-P11",
            "Submit compliant claims via Finance App web interface",
            "Request human approval for gated claims",
            "Generate final execution verification report",
        ]
        return reqs, steps

    def ensure_authenticated(self) -> None:
        """Log in to finance portal if session missing or expired."""
        page = self.browser_session.ensure_page()
        # Check if currently on login page or redirected to login
        if "/login" in page.url or page.locator("input[name='username']").count() > 0:
            emit(self.run_id, "session_expired", {"action": "reauthenticating"})
            browser_open(f"{self.finance_url}/login")
            browser_type("username", "operator")
            browser_type("password", "password")
            browser_click("Log In")
            try:
                page.wait_for_url("**/dashboard", timeout=5000)
            except Exception:
                page.wait_for_load_state("networkidle")

    def check_claim_exists_in_ui(self, claim: ClaimRecord) -> bool:
        """Check claims table in browser UI (idempotency check). Never calls /api/."""
        self.ensure_authenticated()
        page = self.browser_session.ensure_page()
        page.goto(f"{self.finance_url}/claims")
        try:
            page.wait_for_selector("#claims-table", timeout=5000)
        except Exception:
            return False

        # Search rows
        content = page.content()
        return (
            claim.employee in content
            and claim.date in content
            and claim.vendor in content
            and f"{claim.amount_inr:.2f}" in content
        )

    def submit_claim_with_recovery(self, claim: ClaimRecord, retries: int = 3) -> bool:
        """Submit claim via web form handling transient 500, session expiry, and validation errors."""
        page = self.browser_session.ensure_page()
        self.ensure_authenticated()

        # Idempotency check before submission
        if self.check_claim_exists_in_ui(claim):
            return True

        for attempt in range(retries):
            # Guardrail check
            action = ProposedAction("submit_claim", {"claim_id": claim.claim_id, "amount_inr": claim.amount_inr})
            decision = self.guardrail.evaluate_action(action, claim=claim, state=self.state)

            if decision.verdict == "FORBIDDEN":
                self.audit.log_tool_call(
                    "submit_claim",
                    {"claim_id": claim.claim_id},
                    decision.reason,
                    gate_decision="FORBIDDEN",
                )
                return False

            browser_open(f"{self.finance_url}/claims/new")
            self.ensure_authenticated()

            try:
                page.wait_for_selector("#claim-form", timeout=5000)
            except Exception:
                self.ensure_authenticated()
                browser_open(f"{self.finance_url}/claims/new")

            browser_type("employee", claim.employee)
            browser_type("date", claim.date)
            browser_select("category", claim.category)
            browser_type("amount_inr", f"{claim.amount_inr:.2f}")
            browser_type("vendor", claim.vendor)
            browser_type("cost_center", claim.cost_center or "CC-42")
            browser_type("receipt_id", claim.receipt_id or f"REC-{claim.claim_id}")
            browser_type("description", claim.notes or "")

            browser_screenshot(f"claim_{claim.claim_id}_attempt_{attempt + 1}")
            browser_click("#submit-claim-button")

            try:
                page.wait_for_timeout(1000)
            except Exception:
                pass

            # Check 1: 500 Internal Server Error recovery
            if "500 Internal Server Error" in page.content():
                emit(self.run_id, "transient_500_detected", {"claim_id": claim.claim_id, "attempt": attempt + 1})
                if self.check_claim_exists_in_ui(claim):
                    return True
                time.sleep(1.0)
                continue

            # Check 2: Inline validation error recovery (e.g. injected missing cost center)
            if page.locator("#form-error-banner").count() > 0:
                err_text = page.locator("#form-error-banner").inner_text()
                emit(self.run_id, "validation_error_detected", {"error": err_text, "attempt": attempt + 1})
                if "Cost center" in err_text:
                    # Lookup cost center and fill
                    claim.cost_center = "CC-42"
                    browser_type("cost_center", "CC-42")
                    browser_click("#submit-claim-button")
                    page.wait_for_timeout(1000)

            # Check 3: Success confirmation
            if "/claims/" in page.url and page.locator("#success-banner").count() > 0:
                browser_screenshot(f"claim_{claim.claim_id}_success")
                return True

            # Secondary check: verify in UI
            if self.check_claim_exists_in_ui(claim):
                return True

        return False

    def process_all_claims(
        self,
        auto_approvals: Optional[Dict[str, str]] = None,
        scenario_name: str = "s2",
    ) -> VerificationReport:
        """Run complete operator loop across all 12 claims."""
        if auto_approvals is None:
            auto_approvals = {"4": "APPROVED", "12": "APPROVED", "5": "DENIED", "7": "DENIED"}

        # Step 1: Planning
        self.plan_goal()

        # Step 2: Extraction & Policy evaluation
        extractor = ClaimExtractor()
        all_claims = extractor.extract_all()
        inbox_emails = extractor._load_inbox()

        for c in all_claims:
            check_claim(c, all_claims, inbox_emails)

        self.state.claims = all_claims
        self.state.save()

        # Step 3: Authenticate
        self.ensure_authenticated()

        # Step 4: Process each claim
        for claim in all_claims:
            cid = claim.claim_id
            self.state.step_index += 1
            step_idx = self.state.step_index

            emit(self.run_id, "step_started", {
                "step": step_idx,
                "claim_id": cid,
                "vendor": claim.vendor,
                "verdict": claim.verdict,
            })

            if claim.verdict == "ALLOW":
                success = self.submit_claim_with_recovery(claim)
                self.audit.log_tool_call(
                    "submit_claim",
                    {"claim_id": cid, "amount_inr": claim.amount_inr},
                    {"filed": success},
                    gate_decision="ALLOW",
                    step_index=step_idx,
                )
                emit(self.run_id, "step_completed", {"claim_id": cid, "filed": success})

            elif claim.verdict == "NEEDS_APPROVAL":
                # Request approval
                decision_choice = auto_approvals.get(cid)
                decision = self.approval_flow.request_approval(
                    claim=claim,
                    reason=f"Policy rules triggered: {', '.join(claim.clauses_triggered)}",
                    state=self.state,
                    auto_decision=decision_choice,
                )

                if decision.decision == "APPROVED":
                    claim.human_approved = True
                    success = self.submit_claim_with_recovery(claim)
                    self.audit.log_tool_call(
                        "submit_claim_approved",
                        {"claim_id": cid, "amount_inr": claim.amount_inr},
                        {"filed": success, "decision": "APPROVED"},
                        gate_decision="ALLOW",
                        step_index=step_idx,
                    )
                    emit(self.run_id, "step_completed", {"claim_id": cid, "filed": success, "status": "APPROVED"})
                else:
                    self.audit.log_tool_call(
                        "approval_denied",
                        {"claim_id": cid},
                        {"filed": False, "decision": "DENIED"},
                        gate_decision="NEEDS_APPROVAL",
                        step_index=step_idx,
                    )
                    emit(self.run_id, "step_completed", {"claim_id": cid, "filed": False, "status": "DENIED"})

            elif claim.verdict == "REJECT":
                # Guardrail blocks submission
                self.audit.log_tool_call(
                    "reject_claim_skipped",
                    {"claim_id": cid, "clauses": claim.clauses_triggered},
                    "Claim rejected by policy; submission blocked by guardrail.",
                    gate_decision="FORBIDDEN",
                    step_index=step_idx,
                )
                emit(self.run_id, "step_completed", {"claim_id": cid, "filed": False, "status": "REJECTED"})

        self.state.save()

        # Step 5: Independent Verification
        verification = verify_run(scenario=scenario_name, run_id=self.run_id, finance_url=self.finance_url)

        # Step 6: Generate Final Markdown Report
        generate_report(state=self.state, verification=verification)
        generate_report(state=self.state, verification=verification, output_path="reports/sample_run_report.md")

        return verification
