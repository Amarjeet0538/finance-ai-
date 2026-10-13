"""Standard schemas and models for tool execution results."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Standardized result returned by all operator tools."""
    ok: bool = Field(..., description="Whether the tool execution succeeded")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured execution payload")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
        }
