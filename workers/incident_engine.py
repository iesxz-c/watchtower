import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from watchtower.core.models import Incident, IncidentEvent, AlertDelivery
from watchtower.services.normalizer import NormalizedEvent
from watchtower.core.enums import IncidentState, EventType, AlertType
from watchtower.services.alerter import dispatch_alert
from watchtower.core.config import get_yaml_config

logger = logging.getLogger(__name__)

def process_event(event: NormalizedEvent, db: Session):
    incident = db.query(Incident).filter(Incident.key == event.fingerprint).first()

    if event.is_recovery:
        if incident and incident.state == IncidentState.OPEN:
            # Resolve incident
            incident.state = IncidentState.RESOLVED
            incident.resolved_at = datetime.now(timezone.utc)
            db.commit()

            incident_event = IncidentEvent(
                incident_id=incident.id,
                event_type=EventType.RESOLVED,
                detail_json={"message": "System recovered"}
            )
            db.add(incident_event)
            db.commit()

            # Trigger recovery alert
            success = dispatch_alert(AlertType.RECOVERY, incident, event.metadata)
            delivery = AlertDelivery(
                incident_id=incident.id,
                alert_type=AlertType.RECOVERY,
                recipient=get_yaml_config().alerts.email,
                success=success
            )
            db.add(delivery)
            db.commit()
        return

    # It's a failure event
    if not incident:
        # Create new incident
        incident = Incident(
            key=event.fingerprint,
            source_type=event.source_type,
            source_id=event.source_id,
            title=event.title,
            severity=event.severity,
            state=IncidentState.OPEN,
            metadata_json=event.metadata
        )
        db.add(incident)
        db.commit()

        incident_event = IncidentEvent(
            incident_id=incident.id,
            event_type=EventType.OPENED,
            detail_json={"message": event.message}
        )
        db.add(incident_event)
        db.commit()

        config = get_yaml_config()
        cooldown = config.alerts.cooldown_minutes if hasattr(config.alerts, 'cooldown_minutes') else 30
        
        last_delivery = db.query(AlertDelivery).filter(
            AlertDelivery.incident_id == incident.id,
            AlertDelivery.alert_type == AlertType.FAILURE
        ).order_by(AlertDelivery.sent_at.desc()).first()

        if not last_delivery or (datetime.now(timezone.utc).replace(tzinfo=None) - last_delivery.sent_at.replace(tzinfo=None)) > timedelta(minutes=cooldown):
            success = dispatch_alert(AlertType.FAILURE, incident, event.metadata)
            delivery = AlertDelivery(
                incident_id=incident.id,
                alert_type=AlertType.FAILURE,
                recipient=config.alerts.email,
                success=success
            )
            db.add(delivery)
        db.commit()
    else:
        # Update existing incident
        incident.last_seen = datetime.now(timezone.utc)
        if incident.state == IncidentState.RESOLVED:
            # Reopen
            incident.state = IncidentState.OPEN
            incident.resolved_at = None
            db.commit()

            incident_event = IncidentEvent(
                incident_id=incident.id,
                event_type=EventType.OPENED,
                detail_json={"message": "Incident Reopened: " + event.message}
            )
            db.add(incident_event)
            db.commit()
            
            config = get_yaml_config()
            cooldown = config.alerts.cooldown_minutes if hasattr(config.alerts, 'cooldown_minutes') else 30
            
            last_delivery = db.query(AlertDelivery).filter(
                AlertDelivery.incident_id == incident.id,
                AlertDelivery.alert_type == AlertType.FAILURE
            ).order_by(AlertDelivery.sent_at.desc()).first()

            if not last_delivery or (datetime.now(timezone.utc).replace(tzinfo=None) - last_delivery.sent_at.replace(tzinfo=None)) > timedelta(minutes=cooldown):
                success = dispatch_alert(AlertType.FAILURE, incident, event.metadata)
                delivery = AlertDelivery(
                    incident_id=incident.id,
                    alert_type=AlertType.FAILURE,
                    recipient=config.alerts.email,
                    success=success
                )
                db.add(delivery)
            db.commit()
        else:
            db.commit()
            config = get_yaml_config()
            cooldown = config.alerts.cooldown_minutes if hasattr(config.alerts, 'cooldown_minutes') else 30
            
            last_delivery = db.query(AlertDelivery).filter(
                AlertDelivery.incident_id == incident.id,
                AlertDelivery.alert_type == AlertType.FAILURE
            ).order_by(AlertDelivery.sent_at.desc()).first()

            if not last_delivery or (datetime.now(timezone.utc).replace(tzinfo=None) - last_delivery.sent_at.replace(tzinfo=None)) > timedelta(minutes=cooldown):
                success = dispatch_alert(AlertType.FAILURE, incident, event.metadata)
                delivery = AlertDelivery(
                    incident_id=incident.id,
                    alert_type=AlertType.FAILURE,
                    recipient=config.alerts.email,
                    success=success
                )
                db.add(delivery)
            db.commit()
