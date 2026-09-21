"""Minimal email sender.

If SMTP_HOST is configured, sends via SMTP (in a worker thread so we don't block
the event loop). Otherwise logs the message — this keeps local dev and tests fully
functional without an email provider, and password-reset/verification links are
visible in the server logs.
"""
import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def _send_smtp(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        if settings.SMTP_STARTTLS:
            server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


async def send_email(to: str, subject: str, body: str) -> None:
    """Best-effort send. Never raises to the caller — a failed email must not
    break registration or leak (via error timing) whether an account exists."""
    if not settings.SMTP_HOST:
        # The body carries live verification and password-reset links. In
        # development, reading that link out of the console IS the delivery
        # mechanism, so the body is logged in full. With DEBUG off — the case
        # ALLOW_NO_SMTP permits — it would instead sit in clear text in whatever
        # ships the logs, so only the envelope is recorded.
        if settings.DEBUG:
            # Accepted, not overlooked: CodeQL flags this line, and the reason
            # and expiry are recorded in .github/codeql-allowlist.json.
            #
            # The body holds a verification or password-reset link, and in
            # development the console is the mail transport — there is no other
            # way to complete either flow locally. DEBUG defaults to False and
            # is what the app treats as "this is a real deployment"; it also
            # gates /docs and the cookie checks in main.py. Nothing forbids
            # setting it True in production, so this is exactly as safe as that
            # switch: turning it on there exposes the API docs and relaxes the
            # cookie guards long before it reaches this line.
            logger.info("[email disabled] To: %s | Subject: %s\n%s", to, subject, body)
        else:
            logger.info(
                "[email disabled] To: %s | Subject: %s | body withheld (DEBUG off)",
                to,
                subject,
            )
        return
    try:
        await asyncio.to_thread(_send_smtp, to, subject, body)
    except Exception:
        logger.exception("Failed to send email to %s", to)
