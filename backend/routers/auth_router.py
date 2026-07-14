import os
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import RegisterRequest, LoginRequest, UserOut
from auth import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    set_auth_cookies, get_current_user, get_jwt_secret, JWT_ALGORITHM,
)
from rate_limit import limiter
import jwt

router = APIRouter(prefix="/api/auth", tags=["auth"])

ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "false").lower() == "true"


@router.post("/register", response_model=UserOut)
@limiter.limit("3/minute")
def register(request: Request, payload: RegisterRequest, response: Response,
             db: Session = Depends(get_db)):
    if not ALLOW_REGISTRATION:
        raise HTTPException(status_code=403,
                            detail="Registration is disabled. Contact an administrator.")
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        role="user",
        auth_provider="local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    at = create_access_token(user.id, user.email)
    rt = create_refresh_token(user.id)
    set_auth_cookies(response, at, rt)
    return user


@router.post("/login", response_model=UserOut)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, response: Response,
          db: Session = Depends(get_db)):
    email = payload.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash or ""):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.active:
        raise HTTPException(status_code=403, detail="Account disabled")
    at = create_access_token(user.id, user.email)
    rt = create_refresh_token(user.id)
    set_auth_cookies(response, at, rt)
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"success": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/refresh")
@limiter.limit("10/minute")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        at = create_access_token(user.id, user.email)
        rt = create_refresh_token(user.id)
        set_auth_cookies(response, at, rt)
        return {"success": True}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
