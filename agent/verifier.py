"""Independent Verifier: validates actual finance app records against hand-written ground truth."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

EXPECTED_DIR = Path("tests/expected_outcomes")


@dataclass
class ClaimVerificationResult:
    claim_id: str
    expected_filed: bool
    actual_filed: bool
    result: str  # PASS, FAIL
    details: str
    record_id: Optional[int] = None


@dataclass
class VerificationReport:
    scenario: str
    run_id: str
    overall_result: str  # PASS, FAIL
    pass_count: int = 0
    fail_count: int = 0
    total_checked: int = 0
    results: List[ClaimVerificationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Verifier:
    def __init__(self, finance_url: str = "http://localhost:8000"):
        self.finance_url = finance_url.rstrip("/")

    def verify_scenario(
        self,
        scenario: str,
        run_id: str = "unknown",
        target_employee: str = "Priya Sharma",
    ) -> VerificationReport:
        """Query read-only /api/claims and compare against ground truth JSON."""
        expected_file = EXPECTED_DIR / f"{scenario}_expected.json"
        if not expected_file.exists():
            raise FileNotFoundError(f"Expected outcome file not found: {expected_file}")

        with open(expected_file, "r", encoding="utf-8") as f:
            expected_list: List[Dict[str, Any]] = json.load(f)

        # Call read-only verifier API via fresh clean HTTP client (no agent cookies)
        api_url = f"{self.finance_url}/api/claims"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(api_url, params={"employee": target_employee})
            if resp.status_code != 200:
                raise RuntimeError(f"Verifier API query failed: HTTP {resp.status_code} {resp.text}")
            actual_claims: List[Dict[str, Any]] = resp.json()

        results: List[ClaimVerificationResult] = []
        pass_count = 0
        fail_count = 0
        matched_record_ids = set()

        for exp in expected_list:
            c_id = str(exp["claim_id"])
            exp_filed = exp["expected_filed"]
            exp_amount = float(exp["expected_amount_inr"])
            exp_vendor = str(exp["expected_vendor"]).strip().lower()

            # Find matching actual claim by vendor, amount, excluding already matched records
            matches = [
                a for a in actual_claims
                if a["id"] not in matched_record_ids
                and a["vendor"].strip().lower() == exp_vendor
                and abs(float(a["amount_inr"]) - exp_amount) < 0.05
            ]

            actual_filed = len(matches) > 0
            matching_record = matches[0] if matches else None

            if exp_filed:
                if not actual_filed:
                    results.append(ClaimVerificationResult(
                        claim_id=c_id,
                        expected_filed=True,
                        actual_filed=False,
                        result="FAIL",
                        details=f"Expected claim #{c_id} ({exp['expected_vendor']} ₹{exp_amount}) was NOT filed.",
                    ))
                    fail_count += 1
                else:
                    matched_record_ids.add(matching_record["id"])
                    # Validate fields
                    errors = []
                    if matching_record["category"].lower() != exp["expected_category"].lower():
                        errors.append(f"Category mismatch: expected {exp['expected_category']}, got {matching_record['category']}")

                    if errors:
                        results.append(ClaimVerificationResult(
                            claim_id=c_id,
                            expected_filed=True,
                            actual_filed=True,
                            result="FAIL",
                            details="; ".join(errors),
                            record_id=matching_record["id"],
                        ))
                        fail_count += 1
                    else:
                        results.append(ClaimVerificationResult(
                            claim_id=c_id,
                            expected_filed=True,
                            actual_filed=True,
                            result="PASS",
                            details="Record verified matches ground truth.",
                            record_id=matching_record["id"],
                        ))
                        pass_count += 1
            else:
                if actual_filed:
                    results.append(ClaimVerificationResult(
                        claim_id=c_id,
                        expected_filed=False,
                        actual_filed=True,
                        result="FAIL",
                        details=f"Forbidden/Rejected claim #{c_id} was improperly filed in database!",
                        record_id=matching_record["id"],
                    ))
                    fail_count += 1
                else:
                    results.append(ClaimVerificationResult(
                        claim_id=c_id,
                        expected_filed=False,
                        actual_filed=False,
                        result="PASS",
                        details="Correctly not filed in accordance with policy/gate.",
                    ))
                    pass_count += 1

        overall = "PASS" if fail_count == 0 else "FAIL"

        return VerificationReport(
            scenario=scenario,
            run_id=run_id,
            overall_result=overall,
            pass_count=pass_count,
            fail_count=fail_count,
            total_checked=len(expected_list),
            results=results,
        )


def verify_run(scenario: str, run_id: str, finance_url: str = "http://localhost:8000") -> VerificationReport:
    """Convenience functional interface for independent verification."""
    verifier = Verifier(finance_url=finance_url)
    return verifier.verify_scenario(scenario=scenario, run_id=run_id)
