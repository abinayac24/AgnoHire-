from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formataddr

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()

    smtp_host = os.getenv("SMTP_HOST", os.getenv("SMTP_SERVER", "")).strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME", os.getenv("SMTP_EMAIL", "")).strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    email_sender = os.getenv("EMAIL_SENDER", smtp_username).strip()
    test_recipient = (sys.argv[1] if len(sys.argv) > 1 else email_sender).strip()

    missing = []
    if not smtp_host:
        missing.append("SMTP_HOST")
    if not smtp_username:
        missing.append("SMTP_USERNAME")
    if not smtp_password:
        missing.append("SMTP_PASSWORD")
    if not email_sender:
        missing.append("EMAIL_SENDER")
    if not test_recipient:
        missing.append("test recipient argument or EMAIL_SENDER")

    if missing:
        print("Email test cannot run. Missing settings:")
        for item in missing:
            print(f"- {item}")
        return 1

    message = EmailMessage()
    message["Subject"] = "Your AI Interview Report"
    message["From"] = formataddr(("AI Interview System", email_sender))
    message["To"] = test_recipient
    message.set_content(
        "This is a successful SMTP test from the AI Interview System.\n\n"
        "If you received this, your email configuration is working."
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            if smtp_use_tls:
                server.starttls()
                server.ehlo()
            server.login(smtp_username, smtp_password)
            server.send_message(message)
        print(f"Email test sent successfully to {test_recipient}")
        return 0
    except Exception as exc:
        print(f"Email test failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
