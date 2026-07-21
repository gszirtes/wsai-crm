import csv
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Contact, Company, Deal, Project, User
from auth import get_current_user, require_write
from utils import log_event, owner_id_for
from visibility import visibility_filter
from financials import can_view_financials

router = APIRouter(prefix="/api", tags=["data"])

VALID_CONTACT_STATUSES = {"lead", "prospect", "customer", "inactive"}

_FORMULA_LEAD_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value):
    """Neutralize CSV/spreadsheet formula injection (CWE-1236): a cell whose
    first character is =/+/-/@ (or a leading tab/CR) is interpreted as a
    formula by Excel/Sheets when the export is opened there. Prefixing with
    a single quote forces it to be read as literal text instead."""
    if isinstance(value, str) and value.startswith(_FORMULA_LEAD_CHARS):
        return "'" + value
    return value


def _csv_response(rows, fieldnames, filename):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: _csv_safe(v) for k, v in r.items()})
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/contacts.csv", summary="Export contacts as CSV", description="Download all contacts as a CSV file. Any authenticated user, including guests -- there is no admin/manager gate on bulk export.")
def export_contacts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = []
    for c in db.query(Contact).options(joinedload(Contact.company)).all():
        rows.append({
            "first_name": c.first_name, "last_name": c.last_name, "email": c.email,
            "phone": c.phone, "title": c.title, "status": c.status,
            "company": c.company.name if c.company else "",
        })
    return _csv_response(rows,
        ["first_name", "last_name", "email", "phone", "title", "status", "company"],
        "contacts.csv")


@router.get("/export/companies.csv", summary="Export companies as CSV", description="Download all companies as a CSV file. Any authenticated user, including guests.")
def export_companies(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = [{
        "name": c.name, "industry": c.industry, "website": c.website,
        "email": c.email, "phone": c.phone, "size": c.size, "address": c.address,
    } for c in db.query(Company).all()]
    return _csv_response(rows,
        ["name", "industry", "website", "email", "phone", "size", "address"],
        "companies.csv")


@router.get("/export/deals.csv", summary="Export deals as CSV",
           description="Download visibility-scoped deals as a CSV file (private ones the caller can't see are excluded). Blocked for guests -- unlike the other three exports, which have no role gate at all (a pre-existing gap the plan flags), this one and projects.csv now require write access. `value` column is blank without view_financials.")
def export_deals(db: Session = Depends(get_db), user: User = Depends(require_write)):
    can_see_money = can_view_financials(db, user)
    rows = [{
        "title": d.title, "value": d.value if can_see_money else "", "currency": d.currency,
        "stage": d.stage, "probability": d.probability,
    } for d in db.query(Deal).filter(visibility_filter(db, Deal, "deal", user)).all()]
    return _csv_response(rows,
        ["title", "value", "currency", "stage", "probability"], "deals.csv")


@router.get("/export/projects.csv", summary="Export projects as CSV",
           description="Download visibility-scoped projects as a CSV file (private ones the caller can't see are excluded). Blocked for guests, same as deals.csv. `budget` column is blank without view_financials.")
def export_projects(db: Session = Depends(get_db), user: User = Depends(require_write)):
    can_see_money = can_view_financials(db, user)
    rows = [{
        "name": p.name, "status": p.status, "priority": p.priority,
        "budget": p.budget if can_see_money else "", "estimated_hours": p.estimated_hours,
    } for p in db.query(Project).filter(visibility_filter(db, Project, "project", user)).all()]
    return _csv_response(rows,
        ["name", "status", "priority", "budget", "estimated_hours"], "projects.csv")


@router.post("/import/contacts", summary="Import contacts from CSV",
            description="Bulk-create contacts from a .csv upload. Unknown company names are auto-created; rows with a duplicate email (existing or within the file) are skipped and reported as errors, not failed outright.")
async def import_contacts(file: UploadFile = File(...), db: Session = Depends(get_db),
                          user: User = Depends(require_write)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    created = 0
    errors = []
    companies = {c.name.lower(): c.id for c in db.query(Company).all()}
    existing_emails = {c.email.lower() for c in db.query(Contact).filter(Contact.email != None).all()}
    seen_emails = set()
    for i, row in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        first = row.get("first_name") or row.get("firstname") or row.get("name")
        if not first:
            errors.append(f"Row {i}: missing first_name")
            continue
        email = row.get("email")
        if email:
            email_lower = email.lower()
            if email_lower in existing_emails or email_lower in seen_emails:
                errors.append(f"Row {i}: duplicate email '{email}' - skipped")
                continue
            seen_emails.add(email_lower)
        status = row.get("status") or "lead"
        if status not in VALID_CONTACT_STATUSES:
            status = "lead"
        company_id = None
        cname = row.get("company")
        if cname:
            company_id = companies.get(cname.lower())
            if not company_id:
                comp = Company(name=cname, owner_id=owner_id_for(user))
                db.add(comp); db.flush()
                log_event(db, "company", comp.id, "created", user)
                companies[cname.lower()] = comp.id
                company_id = comp.id
        c = Contact(
            first_name=first, last_name=row.get("last_name"),
            email=email, phone=row.get("phone"),
            title=row.get("title"), status=status,
            company_id=company_id, owner_id=owner_id_for(user),
        )
        db.add(c); db.flush()
        log_event(db, "contact", c.id, "created", user)
        created += 1
    db.commit()
    return {"created": created, "errors": errors}
