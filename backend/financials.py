from capabilities import has_capability

# The plan's money-field list (BL-3): Deal.value, Project.budget/hourly_rate,
# Milestone.amount (Phase 4).
DEAL_MONEY_FIELDS = ("value",)
PROJECT_MONEY_FIELDS = ("budget", "hourly_rate")
MILESTONE_MONEY_FIELDS = ("amount",)

# Plan 4.2: reports never sum across currencies -- every money aggregate is
# broken out per currency instead. Fixed pair (matches schemas.Currency), not
# open-ended, so aggregation code can always report a full {EUR, HUF} shape.
CURRENCIES = ("EUR", "HUF")


def zero_by_currency() -> dict:
    return {c: 0.0 for c in CURRENCIES}


def add_currency(bucket: dict, currency: str, amount: float):
    """Add `amount` into `bucket[currency]` if `currency` is one we track,
    silently dropping anything else -- shared by every per-currency
    aggregation loop (dashboard.py, reports.py) instead of each hand-rolling
    the same `if currency in bucket: bucket[currency] += amount` check."""
    if currency in bucket:
        bucket[currency] += amount


def can_view_financials(db, user) -> bool:
    return has_capability(db, user.role, "view_financials")


def _mask(db, user, out, fields, can_view=None):
    """Null out `fields` on an already-built *Out Pydantic instance (never
    on the ORM entity -- setting an ORM-mapped attribute to None would mark
    it dirty and risk flushing the change to the DB). Both DealOut.value and
    ProjectOut.budget/hourly_rate are already Optional[float] in schemas.py,
    so assigning None is a valid value for the field, not a type violation.

    `can_view` lets a caller hoist can_view_financials() once for a whole
    list/loop instead of re-querying the AppSetting-backed capability matrix
    per row; pass None (the default) for single-row call sites where that
    doesn't matter.
    """
    if can_view is None:
        can_view = can_view_financials(db, user)
    if not can_view:
        for f in fields:
            setattr(out, f, None)
    return out


def mask_deal_out(db, user, out, can_view=None):
    return _mask(db, user, out, DEAL_MONEY_FIELDS, can_view)


def mask_project_out(db, user, out, can_view=None):
    return _mask(db, user, out, PROJECT_MONEY_FIELDS, can_view)


def mask_milestone_out(db, user, out, can_view=None):
    return _mask(db, user, out, MILESTONE_MONEY_FIELDS, can_view)
