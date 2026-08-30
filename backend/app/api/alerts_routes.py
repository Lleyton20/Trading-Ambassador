"""
Recent price-in-zone alerts. This is what the dashboard polls to show
alerts in-page - see app/alerts/watcher.py for how they're produced.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import Alert
from app.schemas.alerts import AlertOut

router = APIRouter()


@router.get("/alerts/recent", response_model=list[AlertOut])
def get_recent_alerts(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(select(Alert).order_by(Alert.triggered_at.desc()).limit(limit)).all()
    return [AlertOut(**{c.name: getattr(row, c.name) for c in Alert.__table__.columns}) for row in rows]
