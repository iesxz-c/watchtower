from enum import Enum

class SourceType(str, Enum):
    ENDPOINT = "ENDPOINT"
    BACKEND = "BACKEND"
    FRONTEND = "FRONTEND"

class IncidentState(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    WARNING = "WARNING"
    INFO = "INFO"

class AlertType(str, Enum):
    FAILURE = "FAILURE"
    RECOVERY = "RECOVERY"

class EventType(str, Enum):
    OPENED = "OPENED"
    UPDATED = "UPDATED"
    RESOLVED = "RESOLVED"
