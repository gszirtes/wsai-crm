from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import TimeEntry, Project, User
from auth import require_role

router = APIRouter(prefix="/api/reports", tags=["reports"])


def period_start(period: str) -> datetime:
    now = datetime.now(timezone.utc)
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # default: this week (Monday)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/utilization")
def utilization(period: str = "week", db: Session = Depends(get_db),
                _: User = Depends(require_role("manager"))):
    start = period_start(period)
    entries = db.query(TimeEntry).filter(TimeEntry.entry_date >= start).all()
    rates = {p.id: (p.hourly_rate or 0) for p in db.query(Project).all()}

    agg = {}
    for e in entries:
        a = agg.setdefault(e.user_id, {"total": 0.0, "billable": 0.0, "amount": 0.0})
        a["total"] += e.hours or 0
        if e.billable:
            a["billable"] += e.hours or 0
            a["amount"] += (e.hours or 0) * rates.get(e.project_id, 0)

    rows = []
    for u in db.query(User).filter(User.active == True, User.role != "guest").all():
        a = agg.get(u.id, {"total": 0.0, "billable": 0.0, "amount": 0.0})
        rows.append({
            "user_id": u.id, "name": u.name, "role": u.role,
            "total_hours": round(a["total"], 2),
            "billable_hours": round(a["billable"], 2),
            "billable_amount": round(a["amount"], 2),
            "utilization_pct": round((a["billable"] / a["total"] * 100) if a["total"] else 0, 0),
        })
    rows.sort(key=lambda r: r["billable_hours"], reverse=True)

    return {
        "period": period,
        "period_start": start.isoformat(),
        "totals": {
            "total_hours": round(sum(r["total_hours"] for r in rows), 2),
            "billable_hours": round(sum(r["billable_hours"] for r in rows), 2),
            "billable_amount": round(sum(r["billable_amount"] for r in rows), 2),
        },
        "users": rows,
    }
