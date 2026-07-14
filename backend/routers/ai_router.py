from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import (Contact, Company, Deal, Project, Activity, User, AICommandLog)
from schemas import AICommandRequest
from auth import get_current_user, require_write
from ai_service import get_openrouter_key, get_model, run_ai_command

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _build_context(db: Session) -> str:
    c = db.query(func.count(Contact.id)).scalar()
    co = db.query(func.count(Company.id)).scalar()
    d = db.query(func.count(Deal.id)).scalar()
    p = db.query(func.count(Project.id)).scalar()
    return f"Contacts: {c}, Companies: {co}, Deals: {d}, Projects: {p}."


def _execute(action: str, data: dict, db: Session, user: User):
    created = None
    if action == "create_contact":
        obj = Contact(
            first_name=data.get("first_name") or data.get("name") or "New",
            last_name=data.get("last_name"),
            email=data.get("email"),
            phone=data.get("phone"),
            title=data.get("title"),
            status=data.get("status", "lead"),
            owner_id=user.id,
        )
        db.add(obj); db.commit(); db.refresh(obj)
        created = {"type": "contact", "id": obj.id, "name": f"{obj.first_name} {obj.last_name or ''}".strip()}
    elif action == "create_company":
        obj = Company(
            name=data.get("name") or "New Company",
            industry=data.get("industry"),
            website=data.get("website"),
            phone=data.get("phone"),
            email=data.get("email"),
            owner_id=user.id,
        )
        db.add(obj); db.commit(); db.refresh(obj)
        created = {"type": "company", "id": obj.id, "name": obj.name}
    elif action == "create_deal":
        obj = Deal(
            title=data.get("title") or data.get("name") or "New Deal",
            value=float(data.get("value") or 0),
            currency=data.get("currency", "EUR"),
            stage=data.get("stage", "lead"),
            owner_id=user.id,
        )
        db.add(obj); db.commit(); db.refresh(obj)
        created = {"type": "deal", "id": obj.id, "name": obj.title}
    elif action == "create_project":
        obj = Project(
            name=data.get("name") or data.get("title") or "New Project",
            description=data.get("description"),
            status=data.get("status", "planning"),
            priority=data.get("priority", "medium"),
            owner_id=user.id,
        )
        db.add(obj); db.commit(); db.refresh(obj)
        created = {"type": "project", "id": obj.id, "name": obj.name}
    elif action == "create_activity":
        obj = Activity(
            type=data.get("type", "task"),
            subject=data.get("subject") or data.get("title") or "New Task",
            description=data.get("description"),
            owner_id=user.id,
        )
        db.add(obj); db.commit(); db.refresh(obj)
        created = {"type": "activity", "id": obj.id, "name": obj.subject}
    return created


@router.post("/command")
async def ai_command(payload: AICommandRequest, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    api_key = get_openrouter_key(db)
    if not api_key:
        raise HTTPException(status_code=400,
                            detail="OpenRouter API key not configured. Add it in Settings.")
    model = get_model(db)
    try:
        result = await run_ai_command(api_key, model, payload.command, _build_context(db))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    action = result.get("action", "answer")
    data = result.get("data", {}) or {}
    message = result.get("message", "")

    created = None
    write_actions = {"create_contact", "create_company", "create_deal",
                     "create_project", "create_activity"}
    if action in write_actions:
        if user.role == "guest":
            raise HTTPException(status_code=403, detail="Guests have read-only access")
        created = _execute(action, data, db, user)

    log = AICommandLog(user_id=user.id, command=payload.command, action=action,
                       response=message)
    db.add(log); db.commit()

    return {"action": action, "message": message, "created": created}


@router.get("/history")
def ai_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(AICommandLog).filter(AICommandLog.user_id == user.id) \
        .order_by(AICommandLog.created_at.desc()).limit(20).all()
    return [{"id": r.id, "command": r.command, "action": r.action,
             "response": r.response, "created_at": r.created_at} for r in rows]
