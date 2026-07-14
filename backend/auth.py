import os
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User

JWT_ALGORITHM = "HS256"

ROLE_LEVELS = {"guest": 0, "user": 1, "manager": 2, "admin": 3}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"


def set_auth_cookies(response, access_token: str, refresh_token: str):
    response.set_cookie(key="access_token", value=access_token, httponly=True,
                        secure=COOKIE_SECURE, samesite="lax", max_age=43200, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True,
                        secure=COOKIE_SECURE, samesite="lax", max_age=604800, path="/")


def _extract_token(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if not user or not user.active:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(min_role: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if ROLE_LEVELS.get(user.role, 0) < ROLE_LEVELS.get(min_role, 0):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


def require_write(user: User = Depends(get_current_user)) -> User:
    # Guests are read-only
    if user.role == "guest":
        raise HTTPException(status_code=403, detail="Guests have read-only access")
    return user
