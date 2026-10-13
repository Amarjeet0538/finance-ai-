# SOP: Standard Operating Procedure for Expense Claim Entry

**Procedure ID:** SOP-FIN-004  
**Title:** Web-Based Expense Claim Submission  
**Target Application:** CenterAlign Finance Portal (`http://localhost:8000`)

---

## 1. Authentication
1. Navigate to `/login`.
2. Input operator credentials (`username: operator`, `password: password`).
3. Verify redirection to `/dashboard`.

## 2. Navigation to Filing Interface
1. From the navigation bar or dashboard, click **"File New Claim"** (URL: `/claims/new`).

## 3. Field Entry Sequence
All required fields marked with `*` must be completed in the following order:

1. **Employee Name**: Full legal name as recorded in the employee directory (e.g. `Priya Sharma`).
2. **Claim Date**: Date of transaction in `YYYY-MM-DD` format. Must not be a future date relative to `POLICY_AS_OF_DATE`.
3. **Category**: Select the matching category from the dropdown:
   - `Meals`
   - `Cab`
   - `Flight`
   - `Lodging`
   - `Software`
   - `Client entertainment`
   - `Other`
4. **Amount (INR)**: Numerical amount in Indian Rupees (without currency symbols or commas).
5. **Vendor / Merchant**: Name of the issuing business / establishment.
6. **Cost Center**:
   - Query the `employee_directory.json` to find the employee's assigned cost center.
   - For `Priya Sharma`, the assigned cost center is **`CC-42`**.
   - Failure to provide this field will result in form rejection.
7. **Receipt Identifier**: Enter receipt code (e.g., `REC-01`) or leave blank if unavailable.
8. **Business Justification**: State purpose of expenditure, project, or client context.

## 4. Submission & Verification
1. Click **"Submit Claim"**.
2. Verify redirection to `/claims/<id>` and verify confirmation message: `"Claim Filed Successfully!"`.
3. Record the generated claim ID in the audit log.
