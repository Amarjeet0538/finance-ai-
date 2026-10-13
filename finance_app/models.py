"""SQLAlchemy models for the Mock Finance Web Application."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """User account model for authentication."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.username} (admin={self.is_admin})>"


class ExpenseClaim(Base):
    """Expense claim filed by or on behalf of an employee."""
    __tablename__ = "expense_claims"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    employee = Column(String(150), nullable=False, index=True)
    date = Column(String(20), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    amount_inr = Column(Float, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    vendor = Column(String(150), nullable=False)
    description = Column(Text, default="", nullable=False)
    cost_center = Column(String(50), nullable=False)
    receipt_id = Column(String(100), nullable=True)
    status = Column(String(50), default="SUBMITTED", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    receipts = relationship("Receipt", back_populates="claim", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ExpenseClaim #{self.id} {self.employee}: {self.category} ₹{self.amount_inr}>"


class Receipt(Base):
    """Associated receipt metadata or content."""
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("expense_claims.id", ondelete="CASCADE"), nullable=True)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)

    claim = relationship("ExpenseClaim", back_populates="receipts")

    def __repr__(self) -> str:
        return f"<Receipt {self.filename} for Claim {self.claim_id}>"
