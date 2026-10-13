"""File exploration and inspection tools."""

import csv
import json
from pathlib import Path
from typing import Optional

from agent.tools.schemas import ToolResult


def list_files(dir_path: str = ".") -> ToolResult:
    """List files and subdirectories under the specified path."""
    try:
        p = Path(dir_path)
        if not p.exists():
            return ToolResult(ok=False, error=f"Path not found: {dir_path}")
        if not p.is_dir():
            return ToolResult(ok=False, error=f"Path is not a directory: {dir_path}")

        files = [
            str(item.relative_to(p))
            for item in sorted(p.iterdir())
            if not item.name.startswith(".")
        ]
        return ToolResult(ok=True, data={"files": files, "count": len(files)})
    except Exception as e:
        return ToolResult(ok=False, error=f"Error listing files: {str(e)}")


def read_file(file_path: str) -> ToolResult:
    """Read contents of a file (CSV, JSON, Markdown, or plain text)."""
    try:
        p = Path(file_path)
        if not p.exists():
            return ToolResult(ok=False, error=f"File not found: {file_path}")
        if p.is_dir():
            return ToolResult(ok=False, error=f"Path is a directory, not a file: {file_path}")

        suffix = p.suffix.lower()

        if suffix == ".json":
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ToolResult(ok=True, data={"content": data, "format": "json", "source": file_path})

        elif suffix == ".csv":
            with open(p, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            return ToolResult(ok=True, data={"rows": rows, "count": len(rows), "format": "csv", "source": file_path})

        else:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            return ToolResult(ok=True, data={"content": text, "format": "text", "source": file_path})

    except Exception as e:
        return ToolResult(ok=False, error=f"Error reading file {file_path}: {str(e)}")
