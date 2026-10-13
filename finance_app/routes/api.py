"""Read-only verifier API routes."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from finance_app.database import get_session
from finance_app.models import ExpenseClaim

router = APIRouter(prefix="/api")


class ClaimResponse(BaseModel):
    id: int
    employee: str
    date: str
    category: str
    amount_inr: float
    vendor: str
    cost_center: str
    receipt_id: Optional[str] = None
    status: str
    created_at: str


@router.get("/claims", response_model=List[ClaimResponse])
async def get_claims_for_verifier(
    employee: Optional[str] = Query(None, description="Employee name to filter by"),
    db: Session = Depends(get_session),
):
    """Read-only claims query endpoint for independent verification only."""
    query = db.query(ExpenseClaim)
    if employee:
        query = query.filter(ExpenseClaim.employee.ilike(f"%{employee.strip()}%"))

    claims = query.order_by(ExpenseClaim.id.asc()).all()

    return [
        ClaimResponse(
            id=c.id,
            employee=c.employee,
            date=c.date,
            category=c.category,
            amount_inr=c.amount_inr,
            vendor=c.vendor,
            cost_center=c.cost_center,
            receipt_id=c.receipt_id,
            status=c.status,
            created_at=c.created_at.isoformat(),
        )
        for c in claims
    ]
