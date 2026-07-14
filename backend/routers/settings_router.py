from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import SettingUpdate
from auth import require_role
from ai_service import get_setting, set_setting, encrypt_value, get_model

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    key = get_setting(db, "openrouter_api_key")
    return {
        "openrouter_configured": bool(key),
        "openrouter_model": get_model(db),
    }


@router.put("")
def update_settings(payload: SettingUpdate, db: Session = Depends(get_db),
                    _: User = Depends(require_role("admin"))):
    if payload.openrouter_api_key:
        set_setting(db, "openrouter_api_key", encrypt_value(payload.openrouter_api_key))
    if payload.openrouter_model:
        set_setting(db, "openrouter_model", payload.openrouter_model)
    return {
        "openrouter_configured": bool(get_setting(db, "openrouter_api_key")),
        "openrouter_model": get_model(db),
    }
