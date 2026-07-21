from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserOut, UserUpdate, RegisterRequest, LocaleUpdate
from auth import get_current_user, require_role, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut],
           summary="List users", description="List all users, newest first. Admin only.")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserOut,
            summary="Create a user", description="Admin-created account with an explicit role. Admin only.")
def create_user(payload: RegisterRequest, db: Session = Depends(get_db),
                admin: User = Depends(require_role("admin"))):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(payload.password),
                name=payload.name, role=payload.role or "user", auth_provider="local")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut,
           summary="Update a user", description="Update name/role/locale/active/password. Admin only; an admin cannot demote or deactivate themself.")
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db),
                admin: User = Depends(require_role("admin"))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.name is not None:
        user.name = payload.name
    if payload.role is not None:
        if user.id == admin.id and payload.role != "admin":
            raise HTTPException(status_code=400, detail="You cannot change your own admin role")
        user.role = payload.role
    if payload.locale is not None:
        user.locale = payload.locale
    if payload.active is not None:
        if user.id == admin.id and payload.active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate yourself")
        user.active = payload.active
    if payload.password:
        user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", summary="Delete a user", description="Admin only; an admin cannot delete themself.")
def delete_user(user_id: str, db: Session = Depends(get_db),
                admin: User = Depends(require_role("admin"))):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"success": True}


@router.get("/directory", summary="List users for a teammate picker",
           description="Minimal id/name/email/active for every user, available to any authenticated user (not admin-only like GET /api/users, which returns full profiles including role/auth_provider) -- just enough to populate an invite-a-member picker.")
def list_directory(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [{"id": u.id, "name": u.name, "email": u.email, "active": u.active}
            for u in db.query(User).order_by(User.name).all()]


@router.put("/me/locale", response_model=UserOut,
           summary="Update own locale", description="Set the current user's UI language (en/hu). Any authenticated user.")
def update_my_locale(payload: LocaleUpdate, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    user.locale = payload.locale
    db.commit()
    db.refresh(user)
    return user
