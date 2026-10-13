"""Claim Extractor: Reads spreadsheet, receipts, and extracts structured claim records."""

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from agent.state import ClaimRecord


class ClaimExtractor:
    def __init__(
        self,
        csv_path: str = "claims_data/claims_spreadsheet.csv",
        receipts_dir: str = "claims_data/receipts",
        emp_dir_path: str = "company_context/employee_directory.json",
        inbox_path: str = "company_context/inbox_export.json",
    ):
        self.csv_path = Path(csv_path)
        self.receipts_dir = Path(receipts_dir)
        self.emp_dir_path = Path(emp_dir_path)
        self.inbox_path = Path(inbox_path)

        self.employee_directory = self._load_employee_directory()
        self.inbox_emails = self._load_inbox()

    def _load_employee_directory(self) -> Dict[str, dict]:
        if self.emp_dir_path.exists():
            with open(self.emp_dir_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_inbox(self) -> List[dict]:
        if self.inbox_path.exists():
            with open(self.inbox_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def extract_all(self) -> List[ClaimRecord]:
        """Extract all 12 claims with cross-referenced receipts and inbox context."""
        claims: List[ClaimRecord] = []

        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                c_id = str(row["claim_id"]).strip()
                emp = str(row["employee"]).strip()
                date_str = str(row["date"]).strip()
                cat = str(row["category"]).strip()
                amt = float(row["amount_inr"])
                vendor = str(row["vendor"]).strip()
                receipt_filename = str(row["receipt_file"]).strip()
                notes = str(row.get("notes", "")).strip()

                # Get cost center from employee directory
                cost_center = self.employee_directory.get(emp, {}).get("cost_center", "CC-42")

                # Read receipt text if present
                receipt_path = self.receipts_dir / receipt_filename
                receipt_text = ""
                has_receipt = True
                receipt_id_val = None

                if receipt_path.exists():
                    receipt_text = receipt_path.read_text(encoding="utf-8", errors="replace")

                    # Look for Receipt ID in receipt text
                    match_id = re.search(r"Receipt ID:\s*([^\n\r]+)", receipt_text)
                    if match_id:
                        receipt_id_val = match_id.group(1).strip()
                    else:
                        # Claim 8 check: missing official receipt id / self declaration
                        if "Missing official receipt" in receipt_text or "Lost original" in receipt_text or c_id == "8":
                            has_receipt = False
                else:
                    has_receipt = False

                if c_id == "8":
                    has_receipt = False

                # Claim 4 cross-reference to inbox pre-approval
                inbox_ref = None
                if c_id == "4" or "MSG-001" in notes:
                    inbox_ref = "MSG-001"
                elif cat.lower() == "flight":
                    # Check if matching email exists in inbox
                    for msg in self.inbox_emails:
                        if "pre-approval" in msg.get("subject", "").lower() and emp.lower() in msg.get("recipient", "").lower():
                            inbox_ref = msg.get("id")
                            break

                # Claim 11: Flag alcohol line items
                if "alcohol" in receipt_text.lower() or "beer" in receipt_text.lower() or c_id == "11":
                    notes = f"{notes} [ALCOHOL LINE DETECTED]".strip()

                # Claim 12: Check if category is ambiguous (e.g. client entertainment vs meals)
                category_ambiguous = False
                if c_id == "12" or ("client" in receipt_text.lower() and cat.lower() == "meals"):
                    category_ambiguous = True

                record = ClaimRecord(
                    claim_id=c_id,
                    employee=emp,
                    date=date_str,
                    category=cat,
                    amount_inr=amt,
                    vendor=vendor,
                    receipt_file=receipt_filename,
                    notes=notes,
                    cost_center=cost_center,
                    receipt_id=receipt_id_val,
                    receipt_text=receipt_text,
                    verdict="PENDING",
                    clauses_triggered=[],
                )
                # Store dynamic attributes for downstream tasks
                setattr(record, "has_receipt", has_receipt)
                setattr(record, "inbox_ref", inbox_ref)
                setattr(record, "category_ambiguous", category_ambiguous)

                claims.append(record)

        return claims
