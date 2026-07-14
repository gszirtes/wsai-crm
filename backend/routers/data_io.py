import csv
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Contact, Company, Deal, Project, User
from auth import get_current_user, require_write

router = APIRouter(prefix="/api", tags=["data"])

VALID_CONTACT_STATUSES = {"lead", "prospect", "customer", "inactive"}


def _csv_response(rows, fieldnames, filename):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/contacts.csv")
def export_contacts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = []
    for c in db.query(Contact).all():
        rows.append({
            "first_name": c.first_name, "last_name": c.last_name, "email": c.email,
            "phone": c.phone, "title": c.title, "status": c.status,
            "company": c.company.name if c.company else "",
        })
    return _csv_response(rows,
        ["first_name", "last_name", "email", "phone", "title", "status", "company"],
        "contacts.csv")


@router.get("/export/companies.csv")
def export_companies(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = [{
        "name": c.name, "industry": c.industry, "website": c.website,
        "email": c.email, "phone": c.phone, "size": c.size, "address": c.address,
    } for c in db.query(Company).all()]
    return _csv_response(rows,
        ["name", "industry", "website", "email", "phone", "size", "address"],
        "companies.csv")


@router.get("/export/deals.csv")
def export_deals(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = [{
        "title": d.title, "value": d.value, "currency": d.currency,
        "stage": d.stage, "probability": d.probability,
    } for d in db.query(Deal).all()]
    return _csv_response(rows,
        ["title", "value", "currency", "stage", "probability"], "deals.csv")


@router.get("/export/projects.csv")
def export_projects(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = [{
        "name": p.name, "status": p.status, "priority": p.priority,
        "budget": p.budget, "estimated_hours": p.estimated_hours,
    } for p in db.query(Project).all()]
    return _csv_response(rows,
        ["name", "status", "priority", "budget", "estimated_hours"], "projects.csv")


@router.post("/import/contacts")
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
                comp = Company(name=cname, owner_id=user.id)
                db.add(comp); db.commit(); db.refresh(comp)
                companies[cname.lower()] = comp.id
                company_id = comp.id
        c = Contact(
            first_name=first, last_name=row.get("last_name"),
            email=email, phone=row.get("phone"),
            title=row.get("title"), status=status,
            company_id=company_id, owner_id=user.id,
        )
        db.add(c); created += 1
    db.commit()
    return {"created": created, "errors": errors}
