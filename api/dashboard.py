from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from watchtower.core.database import get_db
from watchtower.core.models import MonitorTarget, Incident, AlertDelivery, FrontendErrorEvent, EndpointCheckResult, BackendErrorEvent
from sqlalchemy import func
from watchtower.core.enums import IncidentState
import os

router = APIRouter()
templates_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
templates = Jinja2Templates(directory=templates_dir)

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    targets = db.query(MonitorTarget).all()
    
    recent_incidents = db.query(Incident).order_by(Incident.last_seen.desc()).limit(20).all()
    recent_deliveries = db.query(AlertDelivery).order_by(AlertDelivery.sent_at.desc()).limit(10).all()
    
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    frontend_events_count = db.query(FrontendErrorEvent).filter(FrontendErrorEvent.received_at >= one_hour_ago).count()
    backend_events_count = db.query(BackendErrorEvent).filter(BackendErrorEvent.occurred_at >= one_hour_ago).count()
    open_incidents_count = db.query(Incident).filter(Incident.state == IncidentState.OPEN).count()
    resolved_today_count = db.query(Incident).filter(
        Incident.state == IncidentState.RESOLVED,
        Incident.resolved_at >= today_start
    ).count()
    alerts_sent_today = db.query(AlertDelivery).filter(AlertDelivery.sent_at >= today_start).count()

    last_checked_dict = {}
    target_status_dict = {}
    for target in targets:
        latest_check = db.query(EndpointCheckResult).filter(EndpointCheckResult.target_id == target.id).order_by(EndpointCheckResult.checked_at.desc()).first()
        if latest_check:
            last_checked_dict[target.id] = latest_check.checked_at
            target_status_dict[target.id] = latest_check.status
        else:
            last_checked_dict[target.id] = None
            target_status_dict[target.id] = "UNKNOWN"

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
        "request": request,
        "targets": targets,
        "last_checked_dict": last_checked_dict,
        "target_status_dict": target_status_dict,
        "incidents": recent_incidents,
        "deliveries": recent_deliveries,
        "frontend_events_count": frontend_events_count,
        "backend_events_count": backend_events_count,
        "open_incidents_count": open_incidents_count,
        "resolved_today_count": resolved_today_count,
        "alerts_sent_today": alerts_sent_today
    })
