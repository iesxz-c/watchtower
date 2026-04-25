from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
from watchtower.core.database import get_db
from watchtower.core.models import MonitorTarget, EndpointCheckResult, Incident
import os

router = APIRouter()
templates_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
templates = Jinja2Templates(directory=templates_dir)

@router.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="status.html",
        context={"request": request}
    )

@router.get("/status/data")
async def status_data(db: Session = Depends(get_db)):
    targets = db.query(MonitorTarget).all()
    
    # Get monitoring start date
    first_check = db.query(EndpointCheckResult).order_by(EndpointCheckResult.checked_at.asc()).first()
    monitoring_started_at = first_check.checked_at.isoformat() if first_check else now.isoformat()

    now = datetime.now(timezone.utc)
    ninety_days_ago = now - timedelta(days=89) # 90 days total including today
    ninety_days_ago_start = ninety_days_ago.replace(hour=0, minute=0, second=0, microsecond=0)
    
    seven_days_ago_start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)

    services_data = []
    global_status = "operational"
    down_count = 0

    for target in targets:
        # Get current status
        latest_check = db.query(EndpointCheckResult).filter(
            EndpointCheckResult.target_id == target.id
        ).order_by(EndpointCheckResult.checked_at.desc()).first()
        
        current_status = "operational"
        if latest_check and latest_check.status != "UP":
            current_status = "outage"
            down_count += 1
        elif not latest_check:
            current_status = "unknown"

        # Get last 90 days checks
        checks = db.query(EndpointCheckResult).filter(
            EndpointCheckResult.target_id == target.id,
            EndpointCheckResult.checked_at >= ninety_days_ago_start
        ).all()

        # Bucket by day
        # Create an empty dictionary for the last 90 days
        daily_buckets = {}
        for i in range(90):
            day_date = (now - timedelta(days=89-i)).strftime('%Y-%m-%d')
            daily_buckets[day_date] = {"total": 0, "down": 0}

        total_checks_90d = 0
        up_checks_90d = 0
        total_checks_7d = 0
        up_checks_7d = 0

        for check in checks:
            # check.checked_at might be naive or aware, assume UTC
            # ensure it has tzinfo to format
            dt = check.checked_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            day_str = dt.strftime('%Y-%m-%d')
            
            if day_str in daily_buckets:
                daily_buckets[day_str]["total"] += 1
                if check.status != "UP":
                    daily_buckets[day_str]["down"] += 1
                else:
                    up_checks_90d += 1
                    if dt >= seven_days_ago_start:
                        up_checks_7d += 1
                total_checks_90d += 1
                if dt >= seven_days_ago_start:
                    total_checks_7d += 1

        # Calculate uptime %
        if total_checks_90d > 0:
            uptime_percentage_90d = round((up_checks_90d / total_checks_90d) * 100, 1)
        else:
            uptime_percentage_90d = 0.0
            
        if total_checks_7d > 0:
            uptime_percentage_7d = round((up_checks_7d / total_checks_7d) * 100, 1)
        else:
            uptime_percentage_7d = 0.0

        daily_bars = []
        for day_str, counts in daily_buckets.items():
            total = counts["total"]
            down = counts["down"]
            
            status_val = "nodata"
            downtime_minutes = 0
            if total > 0:
                if down == 0:
                    status_val = "good"
                elif down < (total / 2.0):
                    status_val = "partial"
                else:
                    status_val = "bad"
                
                # Assume 1 check = 1 minute
                downtime_minutes = down
                
            daily_bars.append({
                "date": day_str,
                "status": status_val,
                "outage_count": down,
                "downtime_minutes": downtime_minutes
            })

        services_data.append({
            "name": target.name,
            "url": target.url,
            "current_status": current_status,
            "uptime_percentage_7d": uptime_percentage_7d,
            "uptime_percentage_90d": uptime_percentage_90d,
            "daily_bars": daily_bars
        })

    # Global status calculation
    if len(targets) > 0:
        if down_count == len(targets):
            global_status = "outage"
        elif down_count > 0:
            global_status = "degraded"

    # Fetch Incidents
    incidents = db.query(Incident).filter(
        Incident.first_seen >= ninety_days_ago_start
    ).order_by(Incident.first_seen.desc()).limit(20).all()

    def format_duration(minutes):
        if minutes < 60:
            return f"{minutes} mins"
        elif minutes < 1440: # 24 hours
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours} hours {mins} mins"
        else:
            days = minutes // 1440
            hours = (minutes % 1440) // 60
            return f"{days} days {hours} hours"

    incidents_data = []
    for inc in incidents:
        first_seen_str = inc.first_seen.strftime('%Y-%m-%d %H:%M:%S') if inc.first_seen else "Unknown"
        resolved_at_str = inc.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if inc.resolved_at else "Ongoing"
        
        duration_minutes = "Ongoing"
        if inc.first_seen and inc.resolved_at:
            delta = inc.resolved_at - inc.first_seen
            duration_minutes = format_duration(int(delta.total_seconds() / 60))
        elif inc.first_seen:
            # If still open, calculate duration until now
            dt_fs = inc.first_seen
            if dt_fs.tzinfo is None:
                dt_fs = dt_fs.replace(tzinfo=timezone.utc)
            delta = now - dt_fs
            duration_minutes = f"Ongoing ({format_duration(int(delta.total_seconds() / 60))})"
            
        incidents_data.append({
            "title": inc.title,
            "state": inc.state,
            "source_type": inc.source_type,
            "first_seen": first_seen_str,
            "resolved_at": resolved_at_str,
            "duration_minutes": duration_minutes
        })

    return JSONResponse(content={
        "overall_status": global_status,
        "services": services_data,
        "incidents": incidents_data,
        "monitoring_started_at": monitoring_started_at,
        "generated_at": now.isoformat()
    })
