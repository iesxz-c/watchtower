from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from watchtower.core.enums import SourceType, Severity

class NormalizedEvent(BaseModel):
    source_type: SourceType
    source_id: Optional[str] = None
    fingerprint: str
    title: str
    severity: Severity
    message: str
    is_recovery: bool = False
    metadata: Dict[str, Any] = {}
    timestamp: datetime
