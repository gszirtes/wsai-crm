from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import ServiceAccount, User
from schemas import ServiceAccountCreate, ServiceAccountOut, ServiceAccountCreated, ServiceAccountUpdate
from auth import require_role, generate_api_key, hash_api_key

router = APIRouter(prefix="/api/service-accounts", tags=["service-accounts"])


@router.get("", response_model=list[ServiceAccountOut], summary="List service accounts",
           description="List all API-key principals (for MCP/agent access, Phase 6). Never returns the key or its hash. Admin only.")
def list_service_accounts(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    return db.query(ServiceAccount).order_by(ServiceAccount.created_at.desc()).all()


@router.post("", response_model=ServiceAccountCreated, summary="Create a service account",
            description="Generates a new API key and returns it once, in plaintext, in this response only -- it is never retrievable again (only a SHA-256 hash is stored). The account is plugged into the same role/capability model as a human user: `role` determines exactly what it can do via require_role/require_capability, identically to a User. Admin only.")
def create_service_account(payload: ServiceAccountCreate, db: Session = Depends(get_db),
                           admin: User = Depends(require_role("admin"))):
    raw_key = generate_api_key()
    sa = ServiceAccount(name=payload.name, role=payload.role,
                        key_hash=hash_api_key(raw_key), created_by=admin.id)
    db.add(sa)
    db.commit()
    db.refresh(sa)
    return ServiceAccountCreated(**ServiceAccountOut.model_validate(sa).model_dump(), api_key=raw_key)


@router.patch("/{service_account_id}", response_model=ServiceAccountOut, summary="Update a service account",
             description="Change role and/or active. Setting active=false revokes the key without deleting the row, so EventLog rows logged by this account (actor_type=\"service\") stay attributable. Admin only.")
def update_service_account(service_account_id: str, payload: ServiceAccountUpdate, db: Session = Depends(get_db),
                           _: User = Depends(require_role("admin"))):
    sa = db.query(ServiceAccount).filter(ServiceAccount.id == service_account_id).first()
    if not sa:
        raise HTTPException(status_code=404, detail="Service account not found")
    if payload.role is not None:
        sa.role = payload.role
    if payload.active is not None:
        sa.active = payload.active
    db.commit()
    db.refresh(sa)
    return sa


@router.delete("/{service_account_id}", summary="Delete a service account",
              description="Hard delete. Prefer PATCH active=false if you want EventLog rows this account logged to stay attributable by name. Admin only.")
def delete_service_account(service_account_id: str, db: Session = Depends(get_db),
                           _: User = Depends(require_role("admin"))):
    sa = db.query(ServiceAccount).filter(ServiceAccount.id == service_account_id).first()
    if not sa:
        raise HTTPException(status_code=404, detail="Service account not found")
    db.delete(sa)
    db.commit()
    return {"success": True}
