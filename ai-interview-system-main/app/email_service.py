from __future__ import annotations

import os
import smtplib
import threading
from email.message import EmailMessage
from email.utils import formataddr

from dotenv import load_dotenv

from app.services.report_generator import report_generator


load_dotenv()


SMTP_HOST = os.getenv("SMTP_HOST", os.getenv("SMTP_SERVER", "")).strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", os.getenv("SMTP_EMAIL", "")).strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
EMAIL_SENDER = os.getenv("EMAIL_SENDER", SMTP_USERNAME).strip()


def smtp_ready() -> bool:
    return all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_SENDER])


def send_report_email(report: dict) -> bool:
    recipient = (report.get("candidate_email") or "").strip()
    if not recipient or not smtp_ready():
        return False

    subject = "Your AI Interview Report"
    body = (
        f"Hello {report['candidate_name']},\n\n"
        "Your AI interview report is attached.\n\n"
        f"Overall Score: {report['overall_score']}%\n"
        f"Mode: {report['mode']}\n\n"
        "Thank you for completing the interview."
    )
    html_body = f"""
    <html>
      <body style="font-family:Segoe UI,Arial,sans-serif;color:#0f172a;">
        <h2>AI Interview Report</h2>
        <p>Hello <strong>{report['candidate_name']}</strong>,</p>
        <p>Your AI interview report is attached.</p>
        <p><strong>Overall Score:</strong> {report['overall_score']}%</p>
        <p><strong>Mode:</strong> {report['mode']}</p>
      </body>
    </html>
    """

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("AI Interview System", EMAIL_SENDER))
    message["To"] = recipient
    message.set_content(body)
    message.add_alternative(html_body, subtype="html")
    message.add_attachment(
        report_generator.generate_pdf(report),
        maintype="application",
        subtype="pdf",
        filename="Interview_Report.pdf",
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        if SMTP_USE_TLS:
            server.starttls()
            server.ehlo()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message)

    return True


def send_report_email_async(report: dict, on_success=None) -> None:
    def _runner():
        try:
            sent = send_report_email(report)
            if sent and callable(on_success):
                on_success()
        except Exception:
            return

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
