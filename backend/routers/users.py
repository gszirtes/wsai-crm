from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserOut, UserUpdate, RegisterRequest
from auth import get_current_user, require_role, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])

VALID_ROLES = {"admin", "manager", "user", "guest"}


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserOut)
def create_user(payload: RegisterRequest, db: Session = Depends(get_db),
                admin: User = Depends(require_role("admin"))):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    role = payload.role if payload.role in VALID_ROLES else "user"
    user = User(email=email, password_hash=hash_password(payload.password),
                name=payload.name, role=role, auth_provider="local")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db),
                admin: User = Depends(require_role("admin"))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.name is not None:
        user.name = payload.name
    if payload.role is not None and payload.role in VALID_ROLES:
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


@router.delete("/{user_id}")
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


@router.put("/me/locale", response_model=UserOut)
def update_my_locale(payload: dict, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    locale = payload.get("locale")
    if locale in ("en", "hu"):
        user.locale = locale
        db.commit()
        db.refresh(user)
    return user
