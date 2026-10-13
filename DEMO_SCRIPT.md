# CenterAlign — 3-Minute Demo Walkthrough Script

## 1. Introduction (30 seconds)
> "CenterAlign is an autonomous company operator that reads unstructured policies, emails, and receipts, evaluates claims deterministically, and executes actions directly in a internal web finance portal through headless browser automation while adhering to strict safety guardrails and human approval gates."

---

## 2. Launching Services & Scenario 1: Happy Path (60 seconds)

### Terminal 1: Launch Finance App & UI
```bash
make run-finance   # Runs on http://localhost:8000
make ui            # Runs on http://localhost:8001
```

### Terminal 2: Run Scenario 1
```bash
make demo
```

### What to show on screen:
1. Open the UI Dashboard at `http://localhost:8001`.
2. **Panel 1 (Goal & Directives):** Show how the raw goal *"Process Priya Sharma's Q3 expense claims"* expands into structured policy requirements citing clauses P1, P2, P10.
3. **Panel 2 (Plan):** Steps update in real time with status badges (`PENDING` -> `IN_PROGRESS` -> `DONE`).
4. **Panel 4 (Live Browser Screenshot):** Auto-refreshes every 2 seconds, displaying the actual Playwright browser filling fields and submitting claims.
5. **Panel 6 (Verification Report):** Shows independent verification passing with 3 ALLOW claims filed and 0 failures.

---

## 3. Scenario 2: Full Mixed Claims & Human Approval Gate (60 seconds)

### Run Scenario 2:
```bash
make demo-all
```

### What to show on screen:
1. **Approval Queue Panel:** Highlight claim 4 (Flight ₹18,500) and claim 12 (Client Entertainment ₹2,800) pausing for human signoff.
2. Explain the policy reasoning:
   - Claim 4 pre-approval email was verified from the inbox, but requires human signoff because it exceeds the ₹10,000 threshold (Clause P10).
   - Claim 12 was ambiguous ("Meals" in CSV, but receipt mentions 4 client attendees from Acme Corp). The operator classified it as **Client entertainment** (Clause P7).
3. Click **Approve** on Claim 4 and Claim 12.
4. Show how the operator resumes, submits the approved claims, and blocks rejected claims (e.g. Claim 11 with alcohol, Claim 10 duplicate, Claim 9 stale date).

---

## 4. Failure Recovery & Guardrails (30 seconds)

### Highlight S3 & S4:
- **Scenario 3 (Failure Recovery):** The operator encounters transient HTTP 500 errors, session timeouts, and missing cost centers. It re-authenticates, performs idempotency checks via the UI, and completes with **zero duplicate submissions**.
- **Scenario 4 (Guardrails):** Even when faced with adversarial prompt injection in emails or receipts, the deterministic code gate strictly blocks unauthorized access to `/admin` and destructive operations.
- **Audit Trail:** Show `reports/audit_<run_id>.jsonl` with cryptographically chained SHA-256 hashes.
