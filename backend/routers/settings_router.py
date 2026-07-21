from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import SettingUpdate, CapabilityMatrix, ThresholdSettings
from auth import require_role
from ai_service import get_setting, set_setting, encrypt_value, get_model
from capabilities import (get_capability_matrix, set_capability_matrix,
                          get_default_visibility, set_default_visibility)
from thresholds import get_thresholds, set_thresholds

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", summary="Get settings",
           description="Whether an OpenRouter API key is configured (never returns the key itself), the current AI model, and the org-wide default visibility for new deals/projects. Admin only.")
def get_settings(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    key = get_setting(db, "openrouter_api_key")
    return {
        "openrouter_configured": bool(key),
        "openrouter_model": get_model(db),
        "default_visibility": get_default_visibility(db),
    }


@router.put("", summary="Update settings",
           description="Set the OpenRouter API key (stored Fernet-encrypted), model, and/or the org-wide default visibility for new deals/projects (D5). Admin only.")
def update_settings(payload: SettingUpdate, db: Session = Depends(get_db),
                    _: User = Depends(require_role("admin"))):
    if payload.openrouter_api_key:
        set_setting(db, "openrouter_api_key", encrypt_value(payload.openrouter_api_key))
    if payload.openrouter_model:
        set_setting(db, "openrouter_model", payload.openrouter_model)
    if payload.default_visibility:
        set_default_visibility(db, payload.default_visibility)
    return {
        "openrouter_configured": bool(get_setting(db, "openrouter_api_key")),
        "openrouter_model": get_model(db),
        "default_visibility": get_default_visibility(db),
    }


@router.get("/capabilities", response_model=CapabilityMatrix, summary="Get capability matrix",
           description="Effective per-role capability matrix -- stored settings merged over coded defaults, so every role/capability is always present. manage_users/configure_permissions are not part of this: those stay fixed to admin. Admin only.")
def get_capabilities(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    return get_capability_matrix(db)


@router.put("/capabilities", response_model=CapabilityMatrix, summary="Update capability matrix",
           description="Full replace of the per-role capability matrix (all 4 roles x 7 capabilities required). Admin only.")
def update_capabilities(payload: CapabilityMatrix, db: Session = Depends(get_db),
                        _: User = Depends(require_role("admin"))):
    set_capability_matrix(db, payload.model_dump())
    return get_capability_matrix(db)


@router.get("/thresholds", response_model=ThresholdSettings, summary="Get SLA thresholds",
           description="Business-day thresholds (D7) backing the unassigned-lead / awaiting-response reminders and the future is_stale flag. Admin only.")
def get_sla_thresholds(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    return get_thresholds(db)


@router.put("/thresholds", response_model=ThresholdSettings, summary="Update SLA thresholds",
           description="Set all three business-day thresholds (D7). Admin only.")
def update_sla_thresholds(payload: ThresholdSettings, db: Session = Depends(get_db),
                          _: User = Depends(require_role("admin"))):
    set_thresholds(db, payload.model_dump())
    return get_thresholds(db)
