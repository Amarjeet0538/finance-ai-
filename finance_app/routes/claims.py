"""Expense claims filing and listing routes."""

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from finance_app.database import get_session
from finance_app.models import ExpenseClaim, User
from finance_app.routes.auth import require_auth

router = APIRouter()
templates = Jinja2Templates(directory="finance_app/templates")


def get_policy_as_of_date() -> str:
    """Read pinned reference date from environment."""
    return os.environ.get("POLICY_AS_OF_DATE", "2026-10-13")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: User = Depends(require_auth),
):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": current_user},
    )


@router.get("/claims", response_class=HTMLResponse)
async def list_claims(
    request: Request,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_session),
):
    claims = db.query(ExpenseClaim).order_by(ExpenseClaim.id.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="claims_list.html",
        context={"user": current_user, "claims": claims},
    )


@router.get("/claims/new", response_class=HTMLResponse)
async def new_claim_page(
    request: Request,
    current_user: User = Depends(require_auth),
):
    return templates.TemplateResponse(
        request=request,
        name="new_claim.html",
        context={
            "user": current_user,
            "error": None,
            "employee": "Priya Sharma",
            "date": "",
            "category": "",
            "amount_inr": "",
            "vendor": "",
            "cost_center": "",
            "receipt_id": "",
            "description": "",
        },
    )


@router.post("/claims/new", response_class=HTMLResponse)
async def submit_claim(
    request: Request,
    employee: str = Form(...),
    date: str = Form(...),
    category: str = Form(...),
    amount_inr: str = Form(...),
    vendor: str = Form(...),
    cost_center: Optional[str] = Form(None),
    receipt_id: Optional[str] = Form(None),
    description: Optional[str] = Form(""),
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_session),
):
    def render_error(err_msg: str):
        return templates.TemplateResponse(
            request=request,
            name="new_claim.html",
            context={
                "user": current_user,
                "error": err_msg,
                "employee": employee,
                "date": date,
                "category": category,
                "amount_inr": amount_inr,
                "vendor": vendor,
                "cost_center": cost_center or "",
                "receipt_id": receipt_id or "",
                "description": description or "",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # 1. Cost center validation
    if not cost_center or not cost_center.strip():
        return render_error("Cost center is required.")

    # 2. Numeric amount validation
    try:
        amount_val = float(amount_inr)
        if amount_val <= 0:
            return render_error("Amount must be a positive number.")
    except (ValueError, TypeError):
        return render_error("Amount must be a positive number.")

    # 3. Future date validation (against POLICY_AS_OF_DATE)
    policy_date_str = get_policy_as_of_date()
    try:
        claim_dt = datetime.strptime(date, "%Y-%m-%d").date()
        policy_dt = datetime.strptime(policy_date_str, "%Y-%m-%d").date()
        if claim_dt > policy_dt:
            return render_error(f"Date cannot be in the future (after {policy_date_str}).")
    except ValueError:
        return render_error("Invalid date format. Expected YYYY-MM-DD.")

    # 4. Duplicate claim detection
    existing_claim = db.query(ExpenseClaim).filter_by(
        employee=employee.strip(),
        date=date.strip(),
        vendor=vendor.strip(),
        amount_inr=amount_val,
    ).first()

    if existing_claim:
        return render_error("Duplicate claim: an identical claim has already been filed for this employee on this date.")

    # Create and persist claim
    claim = ExpenseClaim(
        employee=employee.strip(),
        date=date.strip(),
        category=category.strip(),
        amount_inr=amount_val,
        currency="INR",
        vendor=vendor.strip(),
        description=description.strip() if description else "",
        cost_center=cost_center.strip(),
        receipt_id=receipt_id.strip() if receipt_id else None,
        status="SUBMITTED",
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    return RedirectResponse(
        url=f"/claims/{claim.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/claims/{claim_id}", response_class=HTMLResponse)
async def view_claim_detail(
    request: Request,
    claim_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_session),
):
    claim = db.query(ExpenseClaim).filter_by(id=claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    return templates.TemplateResponse(
        request=request,
        name="claim_detail.html",
        context={"user": current_user, "claim": claim},
    )
