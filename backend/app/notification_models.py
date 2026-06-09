"""
Notification system — fire-and-forget webhook / email notifications
after collection completes.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx
from sqlalchemy import Column, String, Text, Boolean, DateTime
from sqlalchemy.orm import Session

from app.database import Base

logger = logging.getLogger(__name__)


class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    channel = Column(String, nullable=False)  # "webhook" | "email"
    webhook_url = Column(String, nullable=True)
    email_to = Column(String, nullable=True)
    trigger_on_new = Column(Boolean, default=True)  # fire when items_new > 0
    trigger_on_failure = Column(Boolean, default=False)  # fire when collection fails
    is_active = Column(Boolean, default=True)
    last_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


def init_notification_tables(engine):
    """Create notification tables if not exists."""
    Base.metadata.create_all(engine)
    logger.info("Notification tables initialized")


class NotificationSender:
    """Fire-and-forget sender for collection notifications."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def send(self, event_type: str, payload: dict):
        """Check active notification configs and dispatch fire-and-forget."""
        db: Session = self.session_factory()
        try:
            configs = db.query(NotificationConfig).filter(
                NotificationConfig.is_active == True
            ).all()

            for cfg in configs:
                should_fire = False
                if event_type == "new_items" and cfg.trigger_on_new:
                    should_fire = True
                elif event_type == "failure" and cfg.trigger_on_failure:
                    should_fire = True

                if not should_fire:
                    continue

                if cfg.channel == "webhook" and cfg.webhook_url:
                    self._send_webhook_async(cfg, payload)
                elif cfg.channel == "email" and cfg.email_to:
                    self._send_email_async(cfg, payload)

                cfg.last_sent_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as exc:
            logger.warning("Notification dispatch failed (non-blocking): %s", exc)
        finally:
            db.close()

    def _send_webhook_async(self, cfg: NotificationConfig, payload: dict):
        """Fire webhook in a background task."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._post_webhook(cfg.webhook_url, payload))
            else:
                asyncio.run(self._post_webhook(cfg.webhook_url, payload))
        except RuntimeError:
            asyncio.run(self._post_webhook(cfg.webhook_url, payload))

    async def _post_webhook(self, url: str, payload: dict):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json=payload)
        except Exception as exc:
            logger.warning("Webhook delivery failed for %s: %s", url, exc)

    def _send_email_async(self, cfg: NotificationConfig, payload: dict):
        """Send email via SMTP. Reads SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS
        from environment variables. Falls back to logging-only if not configured."""
        import os
        smtp_host = os.environ.get("SMTP_HOST", "")
        if not smtp_host:
            logger.info(
                "Email notification logged (SMTP not configured): to=%s, subject=%s",
                cfg.email_to,
                payload.get("subject", "GatherInfo Notification"),
            )
            return

        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")
        smtp_from = os.environ.get("SMTP_FROM", smtp_user or "gatherinfo@localhost")
        use_tls = os.environ.get("SMTP_TLS", "1") == "1"

        subject = payload.get("subject", "GatherInfo Notification")
        body = payload.get("body", json.dumps(payload, ensure_ascii=False))

        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = cfg.email_to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            if use_tls:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)

            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)

            server.sendmail(smtp_from, cfg.email_to, msg.as_string())
            server.quit()
            logger.info("Email sent to %s via %s:%s", cfg.email_to, smtp_host, smtp_port)
        except Exception as exc:
            logger.warning("Email delivery failed for %s: %s", cfg.email_to, exc)
