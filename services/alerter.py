import smtplib
from email.message import EmailMessage
import logging
from jinja2 import Environment, FileSystemLoader
from watchtower.core.config import get_settings, get_yaml_config
from watchtower.core.enums import AlertType
import os

logger = logging.getLogger(__name__)

def send_alert_email(recipient: str, subject: str, html_content: str):
    settings = get_settings()
    if not settings.smtp_host:
        logger.warning("SMTP_HOST not configured. Skipping email alert.")
        return False

    try:
        yaml_config = get_yaml_config()
        from_email = yaml_config.smtp.from_email
    except Exception:
        from_email = "WatchTower Alerts <alerts@watchtower.dev>"

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = recipient
    msg.set_content("Please enable HTML to view this alert.")
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user and settings.smtp_pass:
                server.login(settings.smtp_user, settings.smtp_pass)
            server.send_message(msg)
        logger.info(f"Alert email sent to {recipient}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        return False

def render_template(template_name: str, **context) -> str:
    templates_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template(template_name)
    return template.render(**context)

def dispatch_alert(alert_type: AlertType, incident, target_or_error_info=None):
    settings = get_settings()
    recipient = settings.alert_email

    if alert_type == AlertType.FAILURE:
        subject = f"[WatchTower] {incident.severity} - {incident.title}"
        html_content = render_template('email_failure.html', incident=incident, info=target_or_error_info)
    else:
        subject = f"[WatchTower] RECOVERY - {incident.title}"
        html_content = render_template('email_recovery.html', incident=incident, info=target_or_error_info)

    return send_alert_email(recipient, subject, html_content)
