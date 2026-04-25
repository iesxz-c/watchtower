import os
import yaml
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class TargetConfig(BaseModel):
    name: str
    url: str
    method: str = "GET"
    expected_status: int = 200
    timeout_s: int = 10
    interval_s: int = 60
    enabled: bool = True
    headers: Dict[str, str] = Field(default_factory=dict)

class LogSourceConfig(BaseModel):
    path: str
    service_name: str
    error_threshold: int = 5
    window_minutes: int = 5

class FrontendConfig(BaseModel):
    error_threshold: int = 10
    window_minutes: int = 5
    cooldown_minutes: int = 30

class AlertsConfig(BaseModel):
    email: str
    cooldown_minutes: int = 30

class SmtpConfig(BaseModel):
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    from_email: str = Field(alias="from", default="WatchTower Alerts <alerts@watchtower.dev>")

class MonitoringConfig(BaseModel):
    targets: List[TargetConfig] = Field(default_factory=list)

class YamlConfig(BaseModel):
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    log_sources: List[LogSourceConfig] = Field(default_factory=list)
    frontend: FrontendConfig = Field(default_factory=FrontendConfig)
    alerts: AlertsConfig
    smtp: SmtpConfig

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=os.path.join(os.path.dirname(__file__), "..", ".env"), env_file_encoding='utf-8', extra='ignore')
    
    database_url: str = "sqlite:///./watchtower.db"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    alert_email: str = "akashiyu18@gmail.com"
    watchtower_ingest_key: str = "wt_changeme_secret_key"
    secret_key: str = "change_this_secret"
    yaml_config_path: str = os.path.join(os.path.dirname(__file__), "..", "config.yaml")

@lru_cache()
def get_settings() -> Settings:
    return Settings()

@lru_cache()
def get_yaml_config() -> YamlConfig:
    settings = get_settings()
    if not os.path.exists(settings.yaml_config_path):
        raise FileNotFoundError(f"Config file not found: {settings.yaml_config_path}")
        
    with open(settings.yaml_config_path, "r") as f:
        data = yaml.safe_load(f)
        
    def replace_env(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: replace_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_env(v) for v in obj]
        elif isinstance(obj, str):
            for key, val in os.environ.items():
                obj = obj.replace(f"${{{key}}}", val)
            obj = obj.replace("${SMTP_HOST}", settings.smtp_host)
            obj = obj.replace("${SMTP_USER}", settings.smtp_user)
            obj = obj.replace("${SMTP_PASS}", settings.smtp_pass)
            obj = obj.replace("${ALERT_EMAIL}", settings.alert_email)
            return obj
        return obj
        
    data = replace_env(data)
    return YamlConfig(**data)
