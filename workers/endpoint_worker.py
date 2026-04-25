import httpx
import logging
import asyncio
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from watchtower.core.database import SessionLocal
from watchtower.core.models import MonitorTarget, EndpointCheckResult
from watchtower.services.normalizer import NormalizedEvent
from watchtower.services.dedup import generate_fingerprint
from watchtower.core.enums import SourceType, Severity
from .incident_engine import process_event

logger = logging.getLogger(__name__)

async def check_target(target: MonitorTarget, db: Session):
    async with httpx.AsyncClient(timeout=target.timeout_s) as client:
        start_time = datetime.now(timezone.utc)
        status = "UP"
        http_code = None
        error_class = None
        response_ms = None

        try:
            response = await client.request(
                method=target.method,
                url=target.url,
                headers=target.headers_json
            )
            response_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            http_code = response.status_code
            if response.status_code != target.expected_status:
                status = "DOWN"
                error_class = f"HTTP_{response.status_code}"
        except httpx.ConnectTimeout:
            status = "DOWN"
            error_class = "ConnectTimeout"
        except httpx.ReadTimeout:
            status = "DOWN"
            error_class = "ReadTimeout"
        except httpx.RequestError as e:
            status = "DOWN"
            error_class = type(e).__name__
            
        result = EndpointCheckResult(
            target_id=target.id,
            status=status,
            http_code=http_code,
            error_class=error_class,
            response_ms=response_ms
        )
        db.add(result)
        db.commit()

        # Send to incident engine
        fingerprint = generate_fingerprint("ENDPOINT", target.id)
        
        event = NormalizedEvent(
            source_type=SourceType.ENDPOINT,
            source_id=str(target.id),
            fingerprint=fingerprint,
            title=f"Endpoint Check Failed: {target.name}",
            severity=Severity.HIGH,
            message=f"Status: {status}, Code: {http_code}, Error: {error_class}",
            is_recovery=(status == "UP"),
            metadata={"target_name": target.name, "url": target.url, "response_ms": response_ms},
            timestamp=datetime.now(timezone.utc)
        )
        
        process_event(event, db)

async def run_endpoint_checks():
    logger.info("Running endpoint checks...")
    db = SessionLocal()
    try:
        targets = db.query(MonitorTarget).filter(MonitorTarget.enabled == True).all()
        tasks = [check_target(target, db) for target in targets]
        await asyncio.gather(*tasks)
    finally:
        db.close()
