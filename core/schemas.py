from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class FrontendIngestPayload(BaseModel):
    app_id: str
    environment: Optional[str] = None
    release_version: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None
    error_type: str
    message: str
    stack: Optional[str] = None
    api_context: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None

class IncidentOut(BaseModel):
    id: int
    key: str
    source_type: str
    title: str
    severity: str
    state: str
    first_seen: datetime
    last_seen: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AlertDeliveryOut(BaseModel):
    id: int
    alert_type: str
    recipient: str
    sent_at: datetime
    success: bool

    class Config:
        from_attributes = True

class TargetOut(BaseModel):
    id: int
    name: str
    url: str
    enabled: bool

    class Config:
        from_attributes = True
