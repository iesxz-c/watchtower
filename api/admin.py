from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

from watchtower.core.database import get_db
from watchtower.core.models import Incident, IncidentEvent

router = APIRouter(prefix="/admin", tags=["admin"])

class ResolveStaleRequest(BaseModel):
    older_than_hours: int
    source_type: str

@router.post("/resolve-stale-incidents")
def resolve_stale_incidents(req: ResolveStaleRequest, db: Session = Depends(get_db)):
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=req.older_than_hours)
    
    # SQLite datetime comparison is easiest if we use naive UTC strings or objects properly,
    # but SQLAlchemy with func.now() and DateTime might handle it.
    # To be safe, we fetch all OPEN incidents of this source type and check in python.
    
    stale_incidents = db.query(Incident).filter(
        Incident.state == "OPEN",
        Incident.source_type == req.source_type
    ).all()
    
    resolved_count = 0
    now = datetime.now(timezone.utc)
    
    for inc in stale_incidents:
        fs = inc.first_seen
        if fs.tzinfo is None:
            fs = fs.replace(tzinfo=timezone.utc)
            
        if fs < cutoff_time:
            # Resolve it
            inc.state = "RESOLVED"
            inc.resolved_at = now
            
            # Add audit event
            audit_event = IncidentEvent(
                incident_id=inc.id,
                event_type="RESOLVED",
                detail_json={"message": "Manually resolved - stale test data"}
            )
            db.add(audit_event)
            resolved_count += 1
            
    db.commit()
    return {"status": "success", "resolved_count": resolved_count}
