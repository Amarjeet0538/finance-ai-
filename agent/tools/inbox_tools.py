"""Email inbox search and inspection tools."""

import json
from pathlib import Path
from typing import Any, Dict, List

from agent.tools.schemas import ToolResult

DEFAULT_INBOX_PATH = Path("company_context/inbox_export.json")


def read_inbox(query: str, inbox_path: str = str(DEFAULT_INBOX_PATH)) -> ToolResult:
    """Search company emails by keyword across sender, recipient, subject, and body."""
    try:
        p = Path(inbox_path)
        if not p.exists():
            return ToolResult(ok=False, error=f"Inbox file not found: {inbox_path}")

        with open(p, "r", encoding="utf-8") as f:
            emails: List[Dict[str, Any]] = json.load(f)

        query_terms = query.lower().split()
        matches = []

        for msg in emails:
            searchable_text = " ".join([
                msg.get("id", ""),
                msg.get("sender", ""),
                msg.get("recipient", ""),
                msg.get("subject", ""),
                msg.get("body", ""),
                " ".join(msg.get("labels", [])),
            ]).lower()

            # Score by number of matched terms
            score = sum(1 for term in query_terms if term in searchable_text)
            if score > 0 or not query_terms:
                matches.append((score, msg))

        # Sort descending by match score
        matches.sort(key=lambda x: x[0], reverse=True)
        results = [m[1] for m in matches]

        return ToolResult(
            ok=True,
            data={
                "query": query,
                "matches": results,
                "total_found": len(results),
            },
        )
    except Exception as e:
        return ToolResult(ok=False, error=f"Error reading inbox: {str(e)}")
