"""Cryptographically chained append-only audit logger."""

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class AuditLogger:
    def __init__(self, run_id: str, log_dir: str = "reports"):
        self.run_id = run_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"audit_{run_id}.jsonl"
        self._lock = threading.Lock()
        self._last_hash = "GENESIS_000000000000000000000000000000000000000000000000000000000000"
        self._secrets = self._gather_secrets_to_redact()

    def _gather_secrets_to_redact(self) -> list[str]:
        """Collect sensitive environment variables for redaction."""
        secrets = []
        for k in ("ANTHROPIC_API_KEY", "SESSION_SECRET_KEY"):
            val = os.environ.get(k)
            if val and len(val) > 4:
                secrets.append(val)
        return secrets

    def _redact_text(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "[REDACTED]")
        return text

    def _redact_obj(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self._redact_text(obj)
        elif isinstance(obj, dict):
            return {k: self._redact_obj(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._redact_obj(i) for i in obj]
        return obj

    def log_entry(self, entry: Dict[str, Any]) -> str:
        with self._lock:
            ts = datetime.now(timezone.utc).isoformat()
            entry["timestamp"] = ts
            entry["run_id"] = self.run_id
            entry["prev_hash"] = self._last_hash

            redacted_entry = self._redact_obj(entry)
            raw_serialized = json.dumps(redacted_entry, sort_keys=True)
            current_hash = hashlib.sha256(raw_serialized.encode("utf-8")).hexdigest()
            redacted_entry["hash"] = current_hash
            self._last_hash = current_hash

            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(redacted_entry) + "\n")

            return current_hash

    def log_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result_summary: Any,
        gate_decision: str = "ALLOW",
        step_index: int = 0,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
    ) -> str:
        return self.log_entry({
            "type": "tool_call",
            "tool_name": tool_name,
            "arguments": arguments,
            "result_summary": result_summary,
            "gate_decision": gate_decision,
            "step_index": step_index,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        })

    def log_event(
        self,
        event_type: str,
        detail: Dict[str, Any],
        step_index: int = 0,
    ) -> str:
        return self.log_entry({
            "type": "system_event",
            "event_type": event_type,
            "detail": detail,
            "step_index": step_index,
        })
