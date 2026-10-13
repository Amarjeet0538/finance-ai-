
"""Authentication routes and session management for Finance App."""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from finance_app.database import get_session
from finance_app.models import User
from finance_app.seed import verify_password

router = APIRouter()
templates = Jinja2Templates(directory="finance_app/templates")

SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "centralign-dev-secret-key-35410")


def get_session_ttl() -> int:
    """Return effective session TTL in seconds, factoring in fault injection."""
    if os.environ.get("INJECT_SESSION_EXPIRY", "0") == "1":
        return 5  # Accelerated expiry for testing recovery
    return int(os.environ.get("SESSION_TTL_SECONDS", "300"))


def sign_payload(payload_str: str) -> str:
    """Create HMAC-SHA256 signature for payload string."""
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_session_token(username: str, is_admin: bool) -> str:
    """Create signed base64 session token with timestamp."""
    data = {
        "username": username,
        "is_admin": is_admin,
        "issued_at": int(time.time()),
    }
    raw = json.dumps(data)
    sig = sign_payload(raw)
    combined = f"{raw}.{sig}"
    return base64.urlsafe_b64encode(combined.encode("utf-8")).decode("utf-8")


def decode_session_token(token: Optional[str]) -> Optional[dict]:
    """Decode and validate session token, checking signature and expiration."""
    if not token:
        return None
    try:
        combined = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        if "." not in combined:
            return None
        raw, sig = combined.rsplit(".", 1)
        if not hmac.compare_digest(sign_payload(raw), sig):
            return None
        data = json.loads(raw)
        ttl = get_session_ttl()
        if time.time() - data.get("issued_at", 0) > ttl:
            return None  # Expired
        return data
    except Exception:
        return None


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_session),
) -> Optional[User]:
    """Return current User if session valid, else None."""
    token = request.cookies.get("session_token")
    data = decode_session_token(token)
    if not data:
        return None
    return db.query(User).filter_by(username=data["username"]).first()


def require_auth(
    request: Request,
    db: Session = Depends(get_session),
) -> User:
    """Dependency that requires valid active session, redirects to /login if absent."""
    user = get_current_user_optional(request, db)
    if not user:
        raise AuthRequiredException()
    return user


class AuthRequiredException(Exception):
    pass


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_session)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"user": None, "error": None},
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    user = db.query(User).filter_by(username=username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "user": None,
                "username": username,
                "error": "Invalid username or password.",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    token = create_session_token(username=user.username, is_admin=user.is_admin)
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=get_session_ttl(),
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("session_token")
    return response
