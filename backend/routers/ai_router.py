from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import (Contact, Company, Deal, Project, Activity, User, AICommandLog)
from schemas import AICommandRequest
from auth import get_current_user, require_write
from ai_service import get_openrouter_key, get_model, run_ai_command
from utils import log_event, owner_id_for
from capabilities import has_capability, get_default_visibility
from membership import add_member

router = APIRouter(prefix="/api/ai", tags=["ai"])

VALID_CONTACT_STATUSES = {"lead", "prospect", "customer", "inactive"}
VALID_DEAL_STAGES = {"lead", "qualified", "proposal", "negotiation", "won", "lost"}
VALID_PROJECT_STATUSES = {"planning", "active", "on_hold", "completed", "cancelled"}
VALID_PRIORITIES = {"low", "medium", "high"}
VALID_ACTIVITY_TYPES = {"call", "email", "meeting", "task", "note"}


def _build_context(db: Session) -> str:
    c = db.query(func.count(Contact.id)).scalar()
    co = db.query(func.count(Company.id)).scalar()
    d = db.query(func.count(Deal.id)).scalar()
    p = db.query(func.count(Project.id)).scalar()
    return f"Contacts: {c}, Companies: {co}, Deals: {d}, Projects: {p}."


def _execute(action: str, data: dict, db: Session, user: User):
    created = None
    if action == "create_contact":
        status = data.get("status", "lead")
        if status not in VALID_CONTACT_STATUSES:
            status = "lead"
        obj = Contact(
            first_name=data.get("first_name") or data.get("name") or "New",
            last_name=data.get("last_name"),
            email=data.get("email"),
            phone=data.get("phone"),
            title=data.get("title"),
            status=status,
            owner_id=owner_id_for(user),
        )
        db.add(obj); db.commit(); db.refresh(obj)
        log_event(db, "contact", obj.id, "created", user); db.commit()
        created = {"type": "contact", "id": obj.id, "name": f"{obj.first_name} {obj.last_name or ''}".strip()}
    elif action == "create_company":
        obj = Company(
            name=data.get("name") or data.get("title") or "New Company",
            industry=data.get("industry"),
            website=data.get("website"),
            phone=data.get("phone"),
            email=data.get("email"),
            owner_id=owner_id_for(user),
        )
        db.add(obj); db.commit(); db.refresh(obj)
        log_event(db, "company", obj.id, "created", user); db.commit()
        created = {"type": "company", "id": obj.id, "name": obj.name}
    elif action == "create_deal":
        stage = data.get("stage", "lead")
        if stage not in VALID_DEAL_STAGES:
            stage = "lead"
        try:
            value = float(data.get("value") or 0)
        except (TypeError, ValueError):
            value = 0
        obj = Deal(
            title=data.get("title") or data.get("name") or "New Deal",
            value=value,
            currency=data.get("currency", "EUR"),
            stage=stage,
            owner_id=owner_id_for(user),
            visibility=get_default_visibility(db),
        )
        db.add(obj); db.commit(); db.refresh(obj)
        log_event(db, "deal", obj.id, "created", user)
        if isinstance(user, User):
            add_member(db, "deal", obj.id, user.id, added_by=user)
        db.commit()
        created = {"type": "deal", "id": obj.id, "name": obj.title}
    elif action == "create_project":
        status = data.get("status", "planning")
        if status not in VALID_PROJECT_STATUSES:
            status = "planning"
        priority = data.get("priority", "medium")
        if priority not in VALID_PRIORITIES:
            priority = "medium"
        obj = Project(
            name=data.get("name") or data.get("title") or "New Project",
            description=data.get("description"),
            status=status,
            priority=priority,
            owner_id=owner_id_for(user),
            visibility=get_default_visibility(db),
        )
        db.add(obj); db.commit(); db.refresh(obj)
        log_event(db, "project", obj.id, "created", user)
        if isinstance(user, User):
            add_member(db, "project", obj.id, user.id, added_by=user)
        db.commit()
        created = {"type": "project", "id": obj.id, "name": obj.name}
    elif action == "create_activity":
        atype = data.get("type", "task")
        if atype not in VALID_ACTIVITY_TYPES:
            atype = "task"
        obj = Activity(
            type=atype,
            subject=data.get("subject") or data.get("title") or "New Task",
            description=data.get("description"),
            owner_id=owner_id_for(user),
        )
        db.add(obj); db.commit(); db.refresh(obj)
        log_event(db, "activity", obj.id, "created", user); db.commit()
        created = {"type": "activity", "id": obj.id, "name": obj.subject}
    return created


CAPABILITY_BY_ACTION = {"create_deal": "manage_deals", "create_project": "manage_projects"}


@router.post("/command", summary="Run an AI command",
            description="Send free-form text to the configured OpenRouter model, which returns a structured {action, data, message}. Enum fields in `data` are re-validated server-side before any write (never trusted from the LLM). Write actions (create_*) are blocked for guests; create_deal/create_project additionally require manage_deals/manage_projects, same as the direct API -- the capability matrix is the deciding layer regardless of which surface triggers the write.")
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
        required_cap = CAPABILITY_BY_ACTION.get(action)
        if required_cap and not has_capability(db, user.role, required_cap):
            raise HTTPException(status_code=403, detail=f"Missing capability: {required_cap}")
        created = _execute(action, data, db, user)

    log = AICommandLog(user_id=owner_id_for(user), command=payload.command, action=action,
                       response=message)
    db.add(log); db.commit()

    return {"action": action, "message": message, "created": created}


@router.get("/history", summary="Get AI command history", description="List the current user's own last 20 AI commands and their outcomes.")
def ai_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(AICommandLog).filter(AICommandLog.user_id == user.id) \
        .order_by(AICommandLog.created_at.desc()).limit(20).all()
    return [{"id": r.id, "command": r.command, "action": r.action,
             "response": r.response, "created_at": r.created_at} for r in rows]
