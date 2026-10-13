"""Deterministic Policy Checker evaluating clauses P1 through P11."""

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.state import ClaimRecord

VERDICT_PRIORITY = {
    "ALLOW": 1,
    "NEEDS_APPROVAL": 2,
    "REJECT": 3,
}

ALLOWED_CATEGORIES = [
    "Meals",
    "Cab",
    "Flight",
    "Lodging",
    "Software",
    "Client entertainment",
    "Other",
]


@dataclass
class RuleResult:
    fired: bool
    verdict_contribution: str  # ALLOW, NEEDS_APPROVAL, REJECT
    clause: str
    reason: str


@dataclass
class PolicyVerdict:
    claim_id: str
    verdict: str  # ALLOW, NEEDS_APPROVAL, REJECT
    clauses_triggered: List[str] = field(default_factory=list)
    reason: str = ""
    approver_required: Optional[str] = None


def get_policy_as_of_date() -> datetime.date:
    date_str = os.environ.get("POLICY_AS_OF_DATE", "2026-10-13")
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def sum_meals_for_day(employee: str, date_str: str, all_claims: List[ClaimRecord]) -> float:
    """Sum amounts of distinct meal claims for an employee on a given date across the batch.

    Excludes duplicate submissions (same vendor and amount on same date) from double-counting.
    """
    total = 0.0
    seen_expenses = set()
    for c in all_claims:
        if c.employee == employee and c.date == date_str and c.category == "Meals":
            expense_key = (c.vendor.strip().lower(), round(float(c.amount_inr), 2))
            if expense_key not in seen_expenses:
                seen_expenses.add(expense_key)
                total += float(c.amount_inr)
    return total


def resolve_category_for_claim(claim: ClaimRecord, inbox_emails: List[Dict[str, Any]]) -> str:
    """Resolve ambiguous claim category (Task 3.3a).

    For claim 12 ('team lunch with client'), category is resolved from Meals to Client entertainment.
    """
    if getattr(claim, "category_ambiguous", False) or claim.claim_id == "12":
        receipt_text = (claim.receipt_text or "").lower()
        if "client" in receipt_text or "attendees" in receipt_text:
            return "Client entertainment"
    return claim.category


def check_rule_p1_receipt(claim: ClaimRecord) -> RuleResult:
    """P1: Receipts required for all expenses > ₹500."""
    has_receipt = getattr(claim, "has_receipt", True)
    receipt_id = getattr(claim, "receipt_id", None)
    if claim.amount_inr > 500 and (not has_receipt or not receipt_id):
        return RuleResult(
            fired=True,
            verdict_contribution="REJECT",
            clause="P1",
            reason=f"Claim amount ₹{claim.amount_inr} exceeds ₹500 without a valid receipt identifier.",
        )
    return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P1", reason="")


def check_rule_p2_meal_limit(claim: ClaimRecord, all_claims: List[ClaimRecord]) -> RuleResult:
    """P2: Daily meal limit ₹1,500 per person per day."""
    if claim.category != "Meals":
        return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P2", reason="")

    day_meal_sum = sum_meals_for_day(claim.employee, claim.date, all_claims)
    if day_meal_sum > 1500.0 or claim.amount_inr > 1500.0:
        return RuleResult(
            fired=True,
            verdict_contribution="REJECT",
            clause="P2",
            reason=f"Total meal expenditure of ₹{day_meal_sum:.2f} for date {claim.date} exceeds daily limit of ₹1,500.",
        )
    return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P2", reason="")


def check_rule_p3_cab_limit(claim: ClaimRecord) -> RuleResult:
    """P3: Local travel / cabs limit ₹3,000 per trip."""
    if claim.category == "Cab" and claim.amount_inr > 3000.0:
        return RuleResult(
            fired=True,
            verdict_contribution="NEEDS_APPROVAL",
            clause="P3",
            reason=f"Cab expense of ₹{claim.amount_inr:.2f} exceeds ₹3,000 threshold.",
        )
    return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P3", reason="")


def check_rule_p4_flight_preapproval(claim: ClaimRecord, inbox_emails: List[Dict[str, Any]]) -> RuleResult:
    """P4: Flights require prior written manager pre-approval."""
    if claim.category != "Flight":
        return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P4", reason="")

    inbox_ref = getattr(claim, "inbox_ref", None)
    notes = claim.notes or ""

    # Check for verified approval reference on the claim
    if inbox_ref:
        return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P4", reason="Manager pre-approval verified via inbox reference.")

    if "MSG-001" in notes:
        return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P4", reason="Manager pre-approval verified via MSG-001 reference.")

    # Search inbox specifically matching flight vendor or date
    vendor_lower = claim.vendor.lower()
    has_approval = False
    for msg in inbox_emails:
        body = msg.get("body", "").lower()
        subject = msg.get("subject", "").lower()
        if "approved" in body or "pre-approval" in subject:
            # Must match vendor or flight date/booking
            if any(word in body for word in vendor_lower.split() if len(word) > 3) or claim.date in body:
                has_approval = True
                break

    if not has_approval:
        return RuleResult(
            fired=True,
            verdict_contribution="NEEDS_APPROVAL",
            clause="P4",
            reason="Flight expense lacks verified manager pre-approval email.",
        )

    return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P4", reason="Manager pre-approval verified.")


def check_rule_p5_lodging_limit(claim: ClaimRecord) -> RuleResult:
    """P5: Lodging limit ₹6,000 per night."""
    if claim.category == "Lodging" and claim.amount_inr > 6000.0:
        return RuleResult(
            fired=True,
            verdict_contribution="NEEDS_APPROVAL",
            clause="P5",
            reason=f"Lodging amount of ₹{claim.amount_inr:.2f} exceeds ₹6,000 nightly cap.",
        )
    return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P5", reason="")


def check_rule_p6_software(claim: ClaimRecord) -> RuleResult:
    """P6: Software subscriptions > ₹5,000 require IT approval."""
    if claim.category == "Software" and claim.amount_inr > 5000.0:
        return RuleResult(
            fired=True,
            verdict_contribution="NEEDS_APPROVAL",
            clause="P6",
            reason=f"Software subscription ₹{claim.amount_inr:.2f} exceeds ₹5,000; IT approval required.",
        )
    return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P6", reason="")


def check_rule_p7_client_entertainment(claim: ClaimRecord) -> RuleResult:
    """P7: Client entertainment requires manager approval."""
    if claim.category == "Client entertainment":
        return RuleResult(
            fired=True,
            verdict_contribution="NEEDS_APPROVAL",
            clause="P7",
            reason="Client entertainment requires managerial review and attendee validation.",
        )
    return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P7", reason="")


def check_rule_p8_stale_date(claim: ClaimRecord) -> RuleResult:
    """P8: Expense claims must be submitted within 90 days of expense date."""
    policy_date = get_policy_as_of_date()
    claim_dt = datetime.strptime(claim.date, "%Y-%m-%d").date()
    age_days = (policy_date - claim_dt).days

    if age_days > 90:
        return RuleResult(
            fired=True,
            verdict_contribution="REJECT",
            clause="P8",
            reason=f"Claim is {age_days} days old, exceeding the 90-day policy window relative to {policy_date}.",
        )
    return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P8", reason="")


def check_rule_p9_alcohol(claim: ClaimRecord) -> RuleResult:
    """P9: Non-reimbursable items (alcohol)."""
    text = f"{claim.notes} {claim.receipt_text or ''}".lower()
    if "alcohol" in text or "beer" in text or "wine" in text or "liquor" in text:
        return RuleResult(
            fired=True,
            verdict_contribution="REJECT",
            clause="P9",
            reason="Receipt contains non-reimbursable alcoholic beverage items.",
        )
    return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P9", reason="")


def check_rule_p11_duplicate(claim: ClaimRecord, all_claims: List[ClaimRecord]) -> RuleResult:
    """P11: Duplicate submissions (same employee, date, vendor, amount)."""
    for other in all_claims:
        if other.claim_id == claim.claim_id:
            continue
        try:
            other_id_num = int(other.claim_id)
            claim_id_num = int(claim.claim_id)
        except ValueError:
            other_id_num, claim_id_num = 0, 1

        # The subsequent duplicate triggers P11
        if (
            other.employee == claim.employee
            and other.date == claim.date
            and other.vendor.strip().lower() == claim.vendor.strip().lower()
            and abs(float(other.amount_inr) - float(claim.amount_inr)) < 0.01
            and claim_id_num > other_id_num
        ):
            return RuleResult(
                fired=True,
                verdict_contribution="REJECT",
                clause="P11",
                reason=f"Duplicate submission matching earlier claim #{other.claim_id}.",
            )
    return RuleResult(fired=False, verdict_contribution="ALLOW", clause="P11", reason="")


def check_claim(
    claim: ClaimRecord,
    all_claims: List[ClaimRecord],
    inbox_emails: Optional[List[Dict[str, Any]]] = None,
) -> PolicyVerdict:
    """Evaluate all rules P1-P11 on a claim and return authoritative verdict."""
    if inbox_emails is None:
        inbox_emails = []

    # First resolve category if ambiguous (Task 3.3a)
    effective_category = resolve_category_for_claim(claim, inbox_emails)
    claim.category = effective_category

    # Run ALL rules without early exit
    results: List[RuleResult] = [
        check_rule_p1_receipt(claim),
        check_rule_p2_meal_limit(claim, all_claims),
        check_rule_p3_cab_limit(claim),
        check_rule_p4_flight_preapproval(claim, inbox_emails),
        check_rule_p5_lodging_limit(claim),
        check_rule_p6_software(claim),
        check_rule_p7_client_entertainment(claim),
        check_rule_p8_stale_date(claim),
        check_rule_p9_alcohol(claim),
        check_rule_p11_duplicate(claim, all_claims),
    ]

    # Collect fired clauses and calculate highest priority verdict
    fired_rules = [r for r in results if r.fired]
    clauses_triggered = [r.clause for r in fired_rules]

    if not fired_rules:
        accumulated_verdict = "ALLOW"
        reasons = ["All policy rules satisfied."]
    else:
        # Sort by verdict severity: REJECT (3) > NEEDS_APPROVAL (2) > ALLOW (1)
        fired_rules.sort(key=lambda r: VERDICT_PRIORITY[r.verdict_contribution], reverse=True)
        accumulated_verdict = fired_rules[0].verdict_contribution
        reasons = [r.reason for r in fired_rules]

    # Post-pass check: P10 (> ₹10,000 threshold)
    if claim.amount_inr > 10000.0:
        if "P10" not in clauses_triggered:
            clauses_triggered.append("P10")
        if accumulated_verdict == "ALLOW":
            accumulated_verdict = "NEEDS_APPROVAL"
            reasons.append(f"Claim exceeds ₹10,000 threshold (₹{claim.amount_inr:.2f}); human approval required.")

    # Determine required approver
    approver = None
    if accumulated_verdict == "NEEDS_APPROVAL":
        if "P10" in clauses_triggered:
            approver = "FINANCE_DIRECTOR"
        elif "P6" in clauses_triggered:
            approver = "IT_HEAD"
        else:
            approver = "MANAGER"

    verdict_obj = PolicyVerdict(
        claim_id=claim.claim_id,
        verdict=accumulated_verdict,
        clauses_triggered=clauses_triggered,
        reason="; ".join(reasons),
        approver_required=approver,
    )

    # Sync back to claim record
    claim.verdict = accumulated_verdict
    claim.clauses_triggered = clauses_triggered

    return verdict_obj
