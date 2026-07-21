from dotenv import load_dotenv
load_dotenv()

import os
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi.errors import RateLimitExceeded

from database import SessionLocal
from models import User, Company, Contact, Deal, Project, Activity
from auth import hash_password
from rate_limit import limiter
from routers import (auth_router, users, companies, contacts, deals, projects,
                     activities, dashboard, ai_router, settings_router, data_io,
                     reports, notifications, event_logs, service_accounts)

app = FastAPI(title="wespeak.ai CRM")

app.state.limiter = limiter


# Every error response (HTTPException, Pydantic validation, rate limiting)
# gets the same envelope: {detail, status_code, path}. `detail` keeps its
# existing shape (string for HTTPException, list-of-{loc,msg,type} for
# validation errors) since the frontend's formatApiError() already reads
# response.data.detail and handles both shapes -- this only adds fields, it
# doesn't change what's already there. status_code/path are new, so a
# machine caller (an MCP agent, eventually) always has a uniform way to read
# an error regardless of which of these three paths produced it.
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                        content={"detail": exc.detail, "status_code": exc.status_code,
                                 "path": request.url.path})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422,
                        content={"detail": exc.errors(), "status_code": 422,
                                 "path": request.url.path})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429,
                        content={"detail": f"Rate limit exceeded: {exc.detail}",
                                 "status_code": 429, "path": request.url.path})

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Total-Count"],
)

app.include_router(auth_router.router)
app.include_router(users.router)
app.include_router(companies.router)
app.include_router(contacts.router)
app.include_router(deals.router)
app.include_router(projects.router)
app.include_router(activities.router)
app.include_router(dashboard.router)
app.include_router(ai_router.router)
app.include_router(settings_router.router)
app.include_router(data_io.router)
app.include_router(reports.router)
app.include_router(notifications.router)
app.include_router(event_logs.router)
app.include_router(service_accounts.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "wespeak-crm"}


def seed():
    # Schema is owned by Alembic (see backend/alembic/) — `alembic upgrade head`
    # runs before the app starts (Docker entrypoint / pytest fixtures), so by
    # the time seed() runs here the tables already exist at the right shape.
    db = SessionLocal()
    try:
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@wespeak.ai")
        admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(email=admin_email, password_hash=hash_password(admin_password),
                         name="Admin", role="admin", auth_provider="local")
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # Demo users for each role
        demo_users = [
            ("manager@wespeak.ai", "manager123", "Kata Manager", "manager"),
            ("user@wespeak.ai", "user123", "Bela User", "user"),
            ("guest@wespeak.ai", "guest123", "Guest Viewer", "guest"),
        ]
        for email, pw, name, role in demo_users:
            if not db.query(User).filter(User.email == email).first():
                db.add(User(email=email, password_hash=hash_password(pw), name=name,
                            role=role, auth_provider="local"))
        db.commit()

        # Seed sample CRM data once
        if db.query(Company).count() == 0:
            now = datetime.now(timezone.utc)
            acme = Company(name="Acme Analytics", industry="SaaS", website="acme.ai",
                           email="hello@acme.ai", size="50-200", owner_id=admin.id,
                           notes="Interested in AI strategy consulting.")
            nord = Company(name="Nordic Retail Group", industry="Retail",
                           website="nordicretail.eu", size="200-1000", owner_id=admin.id)
            magyar = Company(name="Magyar Telekom", industry="Telecom",
                             website="telekom.hu", size="1000+", owner_id=admin.id)
            db.add_all([acme, nord, magyar]); db.commit()

            c1 = Contact(first_name="Anna", last_name="Kovacs", email="anna@acme.ai",
                         title="CTO", status="customer", company_id=acme.id, owner_id=admin.id,
                         phone="+36 30 111 2222", tags=["decision-maker", "ai"])
            c2 = Contact(first_name="Peter", last_name="Nagy", email="peter@nordicretail.eu",
                         title="Head of Data", status="prospect", company_id=nord.id, owner_id=admin.id)
            c3 = Contact(first_name="Eszter", last_name="Szabo", email="eszter@telekom.hu",
                         title="Innovation Lead", status="lead", company_id=magyar.id, owner_id=admin.id)
            db.add_all([c1, c2, c3]); db.commit()

            db.add_all([
                Deal(title="AI Strategy Workshop", value=15000, currency="EUR", stage="proposal",
                     probability=55, company_id=acme.id, contact_id=c1.id, owner_id=admin.id,
                     expected_close=now + timedelta(days=20)),
                Deal(title="LLM Chatbot Build", value=42000, currency="EUR", stage="negotiation",
                     probability=75, company_id=nord.id, contact_id=c2.id, owner_id=admin.id,
                     expected_close=now + timedelta(days=40)),
                Deal(title="Data Platform Audit", value=8000, currency="EUR", stage="qualified",
                     probability=30, company_id=magyar.id, contact_id=c3.id, owner_id=admin.id),
                Deal(title="RAG Pilot", value=25000, currency="EUR", stage="won",
                     probability=100, company_id=acme.id, contact_id=c1.id, owner_id=admin.id),
            ])
            db.add_all([
                Project(name="Acme AI Roadmap", description="12-week AI transformation roadmap.",
                        status="active", priority="high", budget=30000, company_id=acme.id,
                        contact_id=c1.id, owner_id=admin.id, start_date=now,
                        end_date=now + timedelta(days=84)),
                Project(name="Nordic Chatbot MVP", description="Customer support LLM assistant.",
                        status="planning", priority="medium", budget=42000, company_id=nord.id,
                        owner_id=admin.id),
            ])
            db.add_all([
                Activity(type="call", subject="Discovery call with Anna", completed=True,
                         contact_id=c1.id, owner_id=admin.id),
                Activity(type="meeting", subject="Proposal review", contact_id=c2.id,
                         owner_id=admin.id, due_date=now + timedelta(days=2)),
                Activity(type="task", subject="Prepare RAG architecture doc",
                         owner_id=admin.id, due_date=now + timedelta(days=5)),
            ])
            db.commit()
    finally:
        db.close()


# seed() is invoked as a one-time bootstrap step (Docker entrypoint.sh, or
# manually via `python -c "from server import seed; seed()"` for local dev),
# not as a FastAPI startup hook: with multiple uvicorn workers, each worker
# would otherwise race the others through the same insert-if-missing checks.
