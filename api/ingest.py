from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from watchtower.core.database import get_db
from watchtower.core.schemas import FrontendIngestPayload
from watchtower.core.models import FrontendErrorEvent
from watchtower.core.config import get_settings, get_yaml_config
from watchtower.services.normalizer import NormalizedEvent
from watchtower.services.dedup import generate_fingerprint
from watchtower.core.enums import SourceType, Severity
from watchtower.workers.incident_engine import process_event
import re

router = APIRouter()

def scrub_sensitive_data(payload: FrontendIngestPayload) -> FrontendIngestPayload:
    pattern_kv = re.compile(r'(password|secret|token|key|card)=[^& ]+', re.IGNORECASE)
    pattern_bearer = re.compile(r'Bearer\s+[a-zA-Z0-9\-\._~+/]+=*', re.IGNORECASE)
    pattern_card = re.compile(r'\b\d{16}\b')
    
    def apply_redaction(text: str) -> str:
        if not text:
            return text
        text = pattern_kv.sub(r'\1=[REDACTED]', text)
        text = pattern_bearer.sub(r'Bearer [REDACTED]', text)
        text = pattern_card.sub(r'[REDACTED]', text)
        return text

    if payload.message:
        payload.message = apply_redaction(payload.message)
    if payload.stack:
        payload.stack = apply_redaction(payload.stack)
    if payload.api_context:
        for k, v in payload.api_context.items():
            if isinstance(v, str):
                payload.api_context[k] = apply_redaction(v)
    return payload

@router.post("/ingest/frontend")
async def ingest_frontend_error(
    payload: FrontendIngestPayload,
    x_watchtower_key: str = Header(None),
    db: Session = Depends(get_db)
):
    settings = get_settings()
    if x_watchtower_key != settings.watchtower_ingest_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    payload = scrub_sensitive_data(payload)

    event = FrontendErrorEvent(
        app_id=payload.app_id,
        environment=payload.environment,
        release_version=payload.release_version,
        url=payload.url,
        user_agent=payload.user_agent,
        error_type=payload.error_type,
        message=payload.message,
        stack=payload.stack,
        api_context_json=payload.api_context,
        timestamp=payload.timestamp or datetime.now(timezone.utc)
    )
    db.add(event)
    db.commit()

    fingerprint = generate_fingerprint(payload.app_id, payload.error_type, payload.message[:100])
    
    config = get_yaml_config()
    threshold = config.frontend.error_threshold if hasattr(config.frontend, 'error_threshold') else 10
    window = config.frontend.window_minutes if hasattr(config.frontend, 'window_minutes') else 5
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window)
    
    recent_count = db.query(FrontendErrorEvent).filter(
        FrontendErrorEvent.app_id == payload.app_id,
        FrontendErrorEvent.error_type == payload.error_type,
        FrontendErrorEvent.received_at >= cutoff
    ).count()

    if recent_count >= threshold:
        norm_event = NormalizedEvent(
            source_type=SourceType.FRONTEND,
            source_id=payload.app_id,
            fingerprint=fingerprint,
            title=f"Frontend Error: {payload.error_type} in {payload.app_id}",
            severity=Severity.HIGH,
            message=payload.message,
            metadata={"app_id": payload.app_id, "url": payload.url, "env": payload.environment, "count": recent_count},
            timestamp=datetime.now(timezone.utc)
        )
        process_event(norm_event, db)

    return {"status": "ok"}
