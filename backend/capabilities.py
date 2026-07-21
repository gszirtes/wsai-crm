import json
from sqlalchemy.orm import Session
from utils import get_setting, set_setting

# Bounded, fixed set of capabilities the admin can toggle per role. Deliberately
# NOT a general policy engine -- adding a new capability is a code change (new
# entry here + a require_capability("...") call where it matters), not a data
# change. manage_users/configure_permissions are NOT in this set: they are
# fixed to admin, enforced via require_role("admin"), and never configurable.
ALL_CAPABILITIES = (
    "view_financials",
    "manage_deals",
    "manage_projects",
    "invite_members",
    "set_visibility",
    "reassign_owner",
    "view_all_reports",
)

# Coded fallback, used whenever the "role_capabilities" AppSetting is absent
# or incomplete (fresh install, or a role/capability added after the admin
# last saved). Values here mirror the plan's capability table (D6 for
# view_financials); set_visibility=True and view_all_reports=False for `user`
# are this implementation's own reading where the plan left the default
# unstated for those two cells (both other user-role cells were explicit) --
# flagged for confirmation, trivially changed via the admin UI either way.
DEFAULT_CAPABILITIES = {
    "admin": {c: True for c in ALL_CAPABILITIES},
    "manager": {c: True for c in ALL_CAPABILITIES},
    "user": {
        "view_financials": True,
        "manage_deals": True,
        "manage_projects": True,
        "invite_members": True,
        "set_visibility": True,
        "reassign_owner": False,
        "view_all_reports": False,
    },
    "guest": {c: False for c in ALL_CAPABILITIES},
}

SETTING_KEY = "role_capabilities"


def get_capability_matrix(db: Session) -> dict:
    """Effective capability matrix: stored JSON merged over the coded
    defaults, so a partially-saved or pre-upgrade matrix still has every
    role/capability covered rather than KeyError-ing or silently denying."""
    merged = {role: dict(caps) for role, caps in DEFAULT_CAPABILITIES.items()}
    raw = get_setting(db, SETTING_KEY)
    if raw:
        try:
            stored = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            stored = {}
        for role, caps in stored.items():
            if role in merged and isinstance(caps, dict):
                merged[role].update({k: bool(v) for k, v in caps.items() if k in ALL_CAPABILITIES})
    return merged


def set_capability_matrix(db: Session, matrix: dict):
    set_setting(db, SETTING_KEY, json.dumps(matrix))


def has_capability(db: Session, role: str, capability: str) -> bool:
    return bool(get_capability_matrix(db).get(role, {}).get(capability, False))


# ---------- Object visibility default (D5) ----------
DEFAULT_VISIBILITY_KEY = "default_visibility"


def get_default_visibility(db: Session) -> str:
    """Org-wide default for new Deal/Project.visibility (D5: public unless
    the admin has changed it)."""
    return get_setting(db, DEFAULT_VISIBILITY_KEY) or "public"


def set_default_visibility(db: Session, value: str):
    set_setting(db, DEFAULT_VISIBILITY_KEY, value)
