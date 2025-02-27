import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from typing import Any, Dict
from sqlalchemy.orm import Session
from ..services.settings_service import SettingsService
from ..utils.exceptions import EmailException
from ..utils.decorators import retry_on_exception

# Setup Jinja2 environment
template_dir = Path(__file__).parent.parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))


@retry_on_exception()
def send_email_report(
    subject: str, template_name: str, data: Dict[str, Any], db: Session
):
    """Send email using template and database configuration"""
    try:
        # Get email settings from database
        settings = SettingsService.get_settings(db)
        email_config = settings.email_config

        # Create message
        msg = MIMEMultipart()
        msg["From"] = email_config["email_sender"]
        msg["To"] = email_config["email_receiver"]
        msg["Subject"] = subject

        # Render template
        template = jinja_env.get_template(template_name)
        html_content = template.render(**data)
        msg.attach(MIMEText(html_content, "html"))

        # Create SMTP connection
        with smtplib.SMTP(
            email_config["smtp_server"], email_config["smtp_port"]
        ) as server:
            server.starttls()
            server.login(email_config["email_sender"], email_config["email_password"])
            server.send_message(msg)

        logger.info(f"Email sent successfully to {email_config['email_receiver']}")
        return True

    except Exception as e:
        error_msg = f"Error sending email: {str(e)}"
        logger.error(error_msg)
        raise EmailException(error_msg)
