"""Structured state definitions for autonomous company operator runs."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PlanStep:
    id: int
    description: str
    status: str = "PENDING"  # PENDING, IN_PROGRESS, DONE, FAILED, SKIPPED
    error: Optional[str] = None


@dataclass
class ClaimRecord:
    claim_id: str
    employee: str
    date: str
    category: str
    amount_inr: float
    vendor: str
    receipt_file: str
    notes: str = ""
    cost_center: str = "CC-42"
    receipt_id: Optional[str] = None
    receipt_text: str = ""
    verdict: str = "PENDING"  # ALLOW, NEEDS_APPROVAL, REJECT
    clauses_triggered: List[str] = field(default_factory=list)
    human_approved: bool = False
    filed_claim_id: Optional[int] = None
    filing_error: Optional[str] = None


@dataclass
class ApprovalRequest:
    claim_id: str
    employee: str
    amount_inr: float
    reason: str
    clauses: List[str]
    evidence_summary: str
    status: str = "PENDING"  # PENDING, APPROVED, DENIED


@dataclass
class EvidenceBundle:
    claim_id: str
    items: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TaskState:
    run_id: str
    goal: str
    expanded_requirements: List[str] = field(default_factory=list)
    plan: List[PlanStep] = field(default_factory=list)
    claims: List[ClaimRecord] = field(default_factory=list)
    pending_approvals: List[ApprovalRequest] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    step_index: int = 0
    retry_counts: Dict[str, int] = field(default_factory=dict)
    tokens_used: int = 0
    total_cost_usd: float = 0.0
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskState":
        plan_steps = [PlanStep(**p) for p in data.get("plan", [])]
        claims = [ClaimRecord(**c) for c in data.get("claims", [])]
        approvals = [ApprovalRequest(**a) for a in data.get("pending_approvals", [])]

        return cls(
            run_id=data["run_id"],
            goal=data["goal"],
            expanded_requirements=data.get("expanded_requirements", []),
            plan=plan_steps,
            claims=claims,
            pending_approvals=approvals,
            evidence=data.get("evidence", {}),
            step_index=data.get("step_index", 0),
            retry_counts=data.get("retry_counts", {}),
            tokens_used=data.get("tokens_used", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            last_error=data.get("last_error"),
        )

    def save(self, reports_dir: str = "reports") -> Path:
        """Persist state snapshot to reports/state_<run_id>.json."""
        out_dir = Path(reports_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / f"state_{self.run_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return file_path

    @classmethod
    def load(cls, run_id: str, reports_dir: str = "reports") -> Optional["TaskState"]:
        file_path = Path(reports_dir) / f"state_{run_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def compact_summary(self) -> str:
        """Compact summary of task progress suitable for LLM prompt context (< 800 tokens)."""
        lines = [
            f"GOAL: {self.goal}",
            f"RUN ID: {self.run_id} | STEP: {self.step_index} | TOKENS: {self.tokens_used} | COST: ${self.total_cost_usd:.4f}",
            "PLAN PROGRESS:",
        ]
        for step in self.plan:
            status_badge = f"[{step.status}]"
            err = f" (Error: {step.error})" if step.error else ""
            lines.append(f"  {step.id}. {status_badge} {step.description}{err}")

        if self.claims:
            counts = {}
            for c in self.claims:
                counts[c.verdict] = counts.get(c.verdict, 0) + 1
            lines.append(f"CLAIMS SUMMARY: {len(self.claims)} total claims {counts}")

        if self.last_error:
            lines.append(f"LAST RECOVERABLE ERROR: {self.last_error}")

        return "\n".join(lines)
