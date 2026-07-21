from datetime import datetime, timedelta, timezone
import json
from sqlalchemy.orm import Session
from utils import get_setting, set_setting

# D7: business-day thresholds, global and admin-configurable, backing the
# lazy auto_unclaimed_lead / auto_awaiting_response notifications (Phase 2)
# and the is_stale flag (Phase 5). Same AppSetting-JSON pattern as the
# capability matrix -- stored value merged over these coded defaults.
DEFAULT_THRESHOLDS = {
    "unassigned_days": 2,
    "awaiting_response_days": 5,
    "stale_days": 14,
}

SETTING_KEY = "sla_thresholds"


def get_thresholds(db: Session) -> dict:
    merged = dict(DEFAULT_THRESHOLDS)
    raw = get_setting(db, SETTING_KEY)
    if raw:
        try:
            stored = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            stored = {}
        for k, v in stored.items():
            if k in DEFAULT_THRESHOLDS:
                try:
                    merged[k] = int(v)
                except (TypeError, ValueError):
                    pass
    return merged


def set_thresholds(db: Session, thresholds: dict):
    merged = get_thresholds(db)
    for k, v in thresholds.items():
        if k in DEFAULT_THRESHOLDS:
            merged[k] = int(v)
    set_setting(db, SETTING_KEY, json.dumps(merged))


def business_days_since(since: datetime, now: datetime = None) -> int:
    """Count weekdays (Mon-Fri) strictly between `since` and `now`, treating
    each as a calendar date -- a simple business-day count with no holiday
    calendar, matching the plan's stated scope (no mention of holidays)."""
    now = now or datetime.now(timezone.utc)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if since >= now:
        return 0
    days = 0
    cur = since.date()
    end_date = now.date()
    while cur < end_date:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            days += 1
    return days
