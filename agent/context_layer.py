"""Context retrieval layer for company policies, SOPs, and employee directories."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

CONTEXT_DIR = Path("company_context")


@dataclass
class Passage:
    source_file: str
    section_heading: str
    text: str
    relevance_score: float

    def to_dict(self):
        return asdict(self)


class ContextLayer:
    def __init__(self, context_dir: Path = CONTEXT_DIR):
        self.context_dir = context_dir
        self.passages: List[Passage] = []
        self._load_documents()

    def _load_documents(self) -> None:
        if not self.context_dir.exists():
            return

        # 1. Parse policy.md by sections (clauses)
        policy_path = self.context_dir / "policy.md"
        if policy_path.exists():
            text = policy_path.read_text(encoding="utf-8")
            sections = re.split(r"\n(?=### )", text)
            for sec in sections:
                lines = sec.strip().split("\n")
                heading = lines[0].replace("###", "").strip() if lines else "Policy"
                body = "\n".join(lines[1:]).strip() if len(lines) > 1 else sec.strip()
                self.passages.append(
                    Passage(
                        source_file="policy.md",
                        section_heading=heading,
                        text=f"{heading}\n{body}",
                        relevance_score=0.0,
                    )
                )

        # 2. Parse approvals_matrix.json
        matrix_path = self.context_dir / "approvals_matrix.json"
        if matrix_path.exists():
            matrix_data = json.loads(matrix_path.read_text(encoding="utf-8"))
            for item in matrix_data:
                category = item.get("category", "")
                min_amt = item.get("amount_min", 0)
                max_amt = item.get("amount_max", "No limit")
                approver = item.get("approver_role", "")
                clause = item.get("clause", "")
                desc = f"Category: {category}, Range: ₹{min_amt} to ₹{max_amt}, Approver: {approver}, Clause: {clause}"
                self.passages.append(
                    Passage(
                        source_file="approvals_matrix.json",
                        section_heading=f"Approval Rule: {category} ({clause})",
                        text=desc,
                        relevance_score=0.0,
                    )
                )

        # 3. Parse sop_expense_entry.md
        sop_path = self.context_dir / "sop_expense_entry.md"
        if sop_path.exists():
            sop_text = sop_path.read_text(encoding="utf-8")
            sop_sections = re.split(r"\n(?=## )", sop_text)
            for sec in sop_sections:
                lines = sec.strip().split("\n")
                heading = lines[0].replace("##", "").strip() if lines else "SOP Step"
                body = "\n".join(lines[1:]).strip() if len(lines) > 1 else sec.strip()
                self.passages.append(
                    Passage(
                        source_file="sop_expense_entry.md",
                        section_heading=heading,
                        text=f"{heading}\n{body}",
                        relevance_score=0.0,
                    )
                )

        # 4. Parse employee_directory.json
        emp_path = self.context_dir / "employee_directory.json"
        if emp_path.exists():
            emp_data = json.loads(emp_path.read_text(encoding="utf-8"))
            for emp_name, info in emp_data.items():
                info_text = f"Employee: {emp_name}, Cost Center: {info.get('cost_center')}, Manager: {info.get('manager')}, Email: {info.get('email')}, Dept: {info.get('department')}"
                self.passages.append(
                    Passage(
                        source_file="employee_directory.json",
                        section_heading=f"Employee Record: {emp_name}",
                        text=info_text,
                        relevance_score=0.0,
                    )
                )

    def search(self, query: str, top_k: int = 5) -> List[Passage]:
        """Keyword and token overlap search."""
        query_tokens = set(re.findall(r"\w+", query.lower()))
        if not query_tokens:
            return self.passages[:top_k]

        scored: List[Passage] = []
        for p in self.passages:
            doc_text = f"{p.section_heading} {p.text}".lower()
            doc_tokens = set(re.findall(r"\w+", doc_text))
            overlap = query_tokens.intersection(doc_tokens)

            # Extra weight for exact match of query words or clause tags (e.g. P1, P4)
            exact_bonus = sum(2.0 for token in query_tokens if token in doc_text)
            score = (len(overlap) * 1.5) + exact_bonus

            if score > 0:
                scored.append(
                    Passage(
                        source_file=p.source_file,
                        section_heading=p.section_heading,
                        text=p.text,
                        relevance_score=score,
                    )
                )

        scored.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored[:top_k]


# Global singleton instance
_context_layer = None


def get_context_layer() -> ContextLayer:
    global _context_layer
    if _context_layer is None:
        _context_layer = ContextLayer()
    return _context_layer


def search_company_context(query: str, top_k: int = 5) -> List[Passage]:
    """Top-level functional interface for agent tools and planning."""
    return get_context_layer().search(query, top_k=top_k)
