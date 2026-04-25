from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

class MonitorTarget(Base):
    __tablename__ = "monitor_targets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    method = Column(String, default="GET")
    headers_json = Column(JSON, default=dict)
    expected_status = Column(Integer, default=200)
    timeout_s = Column(Integer, default=10)
    interval_s = Column(Integer, default=60)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class EndpointCheckResult(Base):
    __tablename__ = "endpoint_check_results"
    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("monitor_targets.id"), index=True)
    status = Column(String, nullable=False) # UP/DOWN
    http_code = Column(Integer, nullable=True)
    error_class = Column(String, nullable=True)
    response_ms = Column(Float, nullable=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())

class BackendErrorEvent(Base):
    __tablename__ = "backend_error_events"
    id = Column(Integer, primary_key=True, index=True)
    source_file = Column(String, nullable=False)
    service_name = Column(String, nullable=False)
    error_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    fingerprint = Column(String, index=True, nullable=False)
    stack = Column(Text, nullable=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())
    raw_line = Column(Text, nullable=True)

class FrontendErrorEvent(Base):
    __tablename__ = "frontend_error_events"
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String, nullable=False)
    environment = Column(String, nullable=True)
    release_version = Column(String, nullable=True)
    url = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    error_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    stack = Column(Text, nullable=True)
    api_context_json = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False) # unique fingerprint
    source_type = Column(String, nullable=False) # ENDPOINT, BACKEND, FRONTEND
    source_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    state = Column(String, nullable=False, default="OPEN")
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, default=dict)

    events = relationship("IncidentEvent", back_populates="incident", cascade="all, delete-orphan")
    deliveries = relationship("AlertDelivery", back_populates="incident", cascade="all, delete-orphan")

class IncidentEvent(Base):
    __tablename__ = "incident_events"
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), index=True)
    event_type = Column(String, nullable=False) # OPENED/UPDATED/RESOLVED
    detail_json = Column(JSON, default=dict)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())
    
    incident = relationship("Incident", back_populates="events")

class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), index=True)
    alert_type = Column(String, nullable=False) # FAILURE/RECOVERY
    recipient = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    success = Column(Boolean, default=False)
    error_msg = Column(Text, nullable=True)

    incident = relationship("Incident", back_populates="deliveries")
