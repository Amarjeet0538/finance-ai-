"""Main FastAPI application for Mock Finance Portal with failure injection support."""

import asyncio
import os
import time
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from finance_app.database import init_db
from finance_app.routes.admin import router as admin_router
from finance_app.routes.api import router as api_router
from finance_app.routes.auth import AuthRequiredException, router as auth_router
from finance_app.routes.claims import router as claims_router

app = FastAPI(title="CenterAlign Mock Finance Portal")

# Mount static files
app.mount("/static", StaticFiles(directory="finance_app/static"), name="static")

# State for one-shot failure injections
injection_state = {
    "transient_500_fired": False,
    "validation_error_fired": False,
    "slow_page_fired": False,
}


def reset_injections() -> None:
    """Reset injection flags."""
    injection_state["transient_500_fired"] = False
    injection_state["validation_error_fired"] = False
    injection_state["slow_page_fired"] = False


@app.middleware("http")
async def failure_injection_middleware(request: Request, call_next):
    # 1. Transient 500 Injection on POST /claims/new
    if os.environ.get("INJECT_TRANSIENT_500", "0") == "1":
        if request.method == "POST" and request.url.path == "/claims/new":
            if not injection_state["transient_500_fired"]:
                injection_state["transient_500_fired"] = True
                return HTMLResponse(
                    "<h1>500 Internal Server Error</h1><p>Transient upstream failure injected for testing recovery.</p>",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    # 2. Slow Page Injection (adds 5s latency)
    if os.environ.get("INJECT_SLOW_PAGE", "0") == "1":
        if request.url.path in ("/claims", "/claims/new") and not injection_state["slow_page_fired"]:
            injection_state["slow_page_fired"] = True
            await asyncio.sleep(5)

    # 3. Validation Error Injection: on first POST /claims/new, alter form data or trigger error
    if os.environ.get("INJECT_VALIDATION_ERROR", "0") == "1":
        if request.method == "POST" and request.url.path == "/claims/new":
            if not injection_state["validation_error_fired"]:
                injection_state["validation_error_fired"] = True
                # Read form and return 422 with stripped cost center
                from fastapi.templating import Jinja2Templates
                templates = Jinja2Templates(directory="finance_app/templates")
                form = await request.form()
                return templates.TemplateResponse(
                    request=request,
                    name="new_claim.html",
                    context={
                        "user": {"username": "operator"},
                        "error": "Cost center is required.",
                        "employee": form.get("employee", ""),
                        "date": form.get("date", ""),
                        "category": form.get("category", ""),
                        "amount_inr": form.get("amount_inr", ""),
                        "vendor": form.get("vendor", ""),
                        "cost_center": "",
                        "receipt_id": form.get("receipt_id", ""),
                        "description": form.get("description", ""),
                    },
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

    return await call_next(request)


@app.exception_handler(AuthRequiredException)
async def auth_required_handler(request: Request, exc: AuthRequiredException):
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


# Register routes
app.include_router(auth_router)
app.include_router(claims_router)
app.include_router(admin_router)
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse)
async def root_index():
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)


@app.on_event("startup")
def on_startup():
    init_db()
