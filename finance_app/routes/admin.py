"""Admin routes (Forbidden Zone for normal operator)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from finance_app.models import User
from finance_app.routes.auth import require_auth

router = APIRouter()
templates = Jinja2Templates(directory="finance_app/templates")


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    current_user: User = Depends(require_auth),
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative privileges required to access this resource.",
        )

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"user": current_user},
    )
