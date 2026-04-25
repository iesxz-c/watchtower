import os
import re
import logging
from datetime import datetime, timezone
from watchtower.core.database import SessionLocal
from watchtower.core.models import BackendErrorEvent
from watchtower.core.config import get_yaml_config
from watchtower.services.normalizer import NormalizedEvent
from watchtower.services.dedup import generate_fingerprint
from watchtower.core.enums import SourceType, Severity
from .incident_engine import process_event

logger = logging.getLogger(__name__)

ERROR_PATTERN = re.compile(r'(ERROR|Exception|Traceback)', re.IGNORECASE)

def parse_log_file(file_path: str, service_name: str, db):
    if not os.path.exists(file_path):
        logger.warning(f"Log file not found: {file_path}")
        return 0

    error_count = 0
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()[-1000:]
            for line in lines:
                if ERROR_PATTERN.search(line):
                    error_count += 1
                    if error_count <= 5:
                        fp = generate_fingerprint(service_name, "LogMatch", line[:100])
                        event = BackendErrorEvent(
                            source_file=file_path,
                            service_name=service_name,
                            error_type="LogMatch",
                            message=line[:255],
                            fingerprint=fp,
                            raw_line=line
                        )
                        db.add(event)
        db.commit()
    except Exception as e:
        logger.error(f"Error reading log file {file_path}: {e}")
        
    return error_count

def run_log_parser_scan():
    logger.info("Running log parser scan...")
    db = SessionLocal()
    try:
        yaml_config = get_yaml_config()
        for log_source in yaml_config.log_sources:
            count = parse_log_file(log_source.path, log_source.service_name, db)
            
            fingerprint = generate_fingerprint("BACKEND", log_source.service_name)
            is_recovery = count < log_source.error_threshold
            
            if not is_recovery or count == 0:
                event = NormalizedEvent(
                    source_type=SourceType.BACKEND,
                    source_id=log_source.service_name,
                    fingerprint=fingerprint,
                    title=f"Backend Error Spike: {log_source.service_name}",
                    severity=Severity.CRITICAL,
                    message=f"{count} errors detected in log window (threshold: {log_source.error_threshold})",
                    is_recovery=is_recovery,
                    metadata={"service": log_source.service_name, "error_count": count},
                    timestamp=datetime.now(timezone.utc)
                )
                process_event(event, db)
    finally:
        db.close()
