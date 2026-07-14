from sqlalchemy import func
from sqlalchemy.orm import Session
from models import TimeEntry


def logged_hours_for(db: Session, project_id: str) -> float:
    """Total hours logged for a project across all time entries."""
    return float(db.query(func.coalesce(func.sum(TimeEntry.hours), 0))
                 .filter(TimeEntry.project_id == project_id).scalar())
