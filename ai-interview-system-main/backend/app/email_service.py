from __future__ import annotations

import os
import smtplib
import threading
import time
from email.message import EmailMessage
from email.utils import formataddr

from dotenv import load_dotenv

from app.services.report_generator import report_generator

# In-memory store for admin email history (can be replaced with DB storage)
_email_history = []
MAX_HISTORY_SIZE = 100

load_dotenv()


SMTP_HOST = os.getenv("SMTP_HOST", os.getenv("SMTP_SERVER", "smtp.gmail.com")).strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("EMAIL_USER", os.getenv("SMTP_USERNAME", os.getenv("SMTP_EMAIL", ""))).strip()
SMTP_PASSWORD = os.getenv("EMAIL_PASS", os.getenv("SMTP_PASSWORD", "")).strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
EMAIL_SENDER = os.getenv("EMAIL_SENDER", SMTP_USERNAME).strip()
ADMIN_REPORT_EMAIL = os.getenv("ADMIN_REPORT_EMAIL", "").strip()


def smtp_ready() -> bool:
    return all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_SENDER])


def _is_pass(total_score: int) -> bool:
    return int(total_score or 0) >= 25


def send_report_email(report: dict) -> bool:
    recipient = (report.get("candidate_email") or "").strip()
    if not recipient or not smtp_ready():
        return False

    candidate_name = report.get("candidate_name", "Candidate")
    total_score = int(report.get("total_score", 0) or 0)
    passed = _is_pass(total_score)
    scores = report.get("scores", {})
    communication = scores.get("communication", "-")
    confidence = scores.get("confidence", "-")
    technical = scores.get("technical", "-")
    performance_label = report.get("performance_label", "Needs Improvement")
    question_scores = report.get("question_scores", [])
    alerts = report.get("alerts", [])
    strengths = report.get("strengths", [])
    weaknesses = report.get("weaknesses", [])
    alert_lines = "\n".join([f"- {item}" for item in alerts]) if alerts else "- No behavior alerts"
    strength_lines = "\n".join([f"- {item}" for item in strengths]) if strengths else "- Consistent participation"
    weakness_lines = "\n".join([f"- {item}" for item in weaknesses]) if weaknesses else "- No major weakness highlighted"
    final_feedback = report.get("final_feedback", "Thank you for completing the interview.")
    question_score_lines = "\n".join(
        [f"Q{item.get('question_number', index)}: {item.get('score', 0)}/{item.get('max_score', 10)}" for index, item in enumerate(question_scores, start=1)]
    ) if question_scores else "- Question scores unavailable"

    if passed:
        subject = "Congratulations! You Passed the Interview"
        body = (
            f"Hello {candidate_name},\n\n"
            "Thank you for attending the interview.\n"
            "Congratulations! You have successfully passed the interview.\n\n"
            f"Total Score: {total_score} / 50\n"
            f"Performance: {performance_label}\n"
            f"Total Questions: {report.get('total_questions', 5)}\n"
            f"Communication Score: {communication}/10\n"
            f"Confidence Score: {confidence}/10\n"
            f"Technical Score: {technical}/10\n\n"
            "Question-wise Scores:\n"
            f"{question_score_lines}\n\n"
            "Strengths:\n"
            f"{strength_lines}\n\n"
            "Positive Feedback:\n"
            f"{final_feedback}\n\n"
            "We will contact you regarding the next steps.\n\n"
            "Best regards,\nAI Interview System"
        )
    else:
        subject = "Interview Result - Thank You for Attending"
        body = (
            f"Hello {candidate_name},\n\n"
            "Thank you for attending the interview.\n"
            "We regret to inform you that you were not selected this time.\n\n"
            "We encourage you to continue improving your skills and apply again in the future. "
            "We wish you all the best in your career journey.\n\n"
            "Best regards,\nAI Interview System"
        )

    alerts_html = "".join([f"<li>{item}</li>" for item in alerts]) if alerts else "<li>No behavior alerts</li>"
    strengths_html = "".join([f"<li>{item}</li>" for item in strengths]) if strengths else "<li>Consistent participation</li>"
    weaknesses_html = "".join([f"<li>{item}</li>" for item in weaknesses]) if weaknesses else "<li>No major weakness highlighted</li>"
    question_scores_html = "".join(
        [
            f"<tr><td style=\"border:1px solid #cbd5e1;padding:8px;\">Q{item.get('question_number', index)}</td><td style=\"border:1px solid #cbd5e1;padding:8px;\">{item.get('score', 0)}/{item.get('max_score', 10)}</td></tr>"
            for index, item in enumerate(question_scores, start=1)
        ]
    ) if question_scores else "<tr><td style=\"border:1px solid #cbd5e1;padding:8px;\">Questions</td><td style=\"border:1px solid #cbd5e1;padding:8px;\">Unavailable</td></tr>"
    if passed:
        html_body = f"""
        <html>
          <body style="font-family:Segoe UI,Arial,sans-serif;color:#0f172a;">
            <h2 style="margin-bottom:8px;">Congratulations!</h2>
            <p>Hello <strong>{candidate_name}</strong>,</p>
            <p>Thank you for attending the interview.</p>
            <p><strong>Congratulations! You have successfully passed the interview.</strong></p>

            <table style="border-collapse:collapse;width:100%;max-width:520px;margin:14px 0;">
              <thead>
                <tr>
                  <th style="border:1px solid #cbd5e1;padding:8px;background:#f8fafc;text-align:left;">Metric</th>
                  <th style="border:1px solid #cbd5e1;padding:8px;background:#f8fafc;text-align:left;">Score</th>
                </tr>
              </thead>
              <tbody>
                <tr><td style="border:1px solid #cbd5e1;padding:8px;">Total Score</td><td style="border:1px solid #cbd5e1;padding:8px;">{total_score}/50</td></tr>
                <tr><td style="border:1px solid #cbd5e1;padding:8px;">Performance</td><td style="border:1px solid #cbd5e1;padding:8px;">{performance_label}</td></tr>
                <tr><td style="border:1px solid #cbd5e1;padding:8px;">Communication</td><td style="border:1px solid #cbd5e1;padding:8px;">{communication}/10</td></tr>
                <tr><td style="border:1px solid #cbd5e1;padding:8px;">Confidence</td><td style="border:1px solid #cbd5e1;padding:8px;">{confidence}/10</td></tr>
                <tr><td style="border:1px solid #cbd5e1;padding:8px;">Technical</td><td style="border:1px solid #cbd5e1;padding:8px;">{technical}/10</td></tr>
              </tbody>
            </table>

            <h3 style="margin:12px 0 6px;">Question-wise Scores</h3>
            <table style="border-collapse:collapse;width:100%;max-width:420px;margin:10px 0 14px;">
              <thead>
                <tr>
                  <th style="border:1px solid #cbd5e1;padding:8px;background:#f8fafc;text-align:left;">Question</th>
                  <th style="border:1px solid #cbd5e1;padding:8px;background:#f8fafc;text-align:left;">Score</th>
                </tr>
              </thead>
              <tbody>{question_scores_html}</tbody>
            </table>

            <h3 style="margin:12px 0 6px;">Strengths</h3>
            <ul>{strengths_html}</ul>

            <h3 style="margin:12px 0 6px;">Positive Feedback</h3>
            <p>{final_feedback}</p>

            <h3 style="margin:12px 0 6px;">Behavior Alerts</h3>
            <ul>{alerts_html}</ul>

            <p><strong>We will contact you regarding the next steps.</strong></p>
          </body>
        </html>
        """
    else:
        html_body = f"""
        <html>
          <body style="font-family:Segoe UI,Arial,sans-serif;color:#0f172a;">
            <h2 style="margin-bottom:8px;">Interview Result</h2>
            <p>Hello <strong>{candidate_name}</strong>,</p>
            <p>Thank you for attending the interview.</p>
            <p><strong>We regret to inform you that you were not selected this time.</strong></p>
            <p>We encourage you to continue improving your skills and apply again in the future. We wish you all the best in your career journey.</p>
          </body>
        </html>
        """

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("AI Interview System", EMAIL_SENDER))
    message["To"] = recipient
    if ADMIN_REPORT_EMAIL:
        message["Cc"] = ADMIN_REPORT_EMAIL
    message.set_content(body)
    message.add_alternative(html_body, subtype="html")
    if passed:
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


def send_report_email_async(report: dict, on_success=None, on_failure=None) -> None:
    schedule_report_email_async(report=report, delay_seconds=0, on_success=on_success, on_failure=on_failure)


def schedule_report_email_async(report: dict, delay_seconds: int, on_success=None, on_failure=None) -> None:
    def _runner():
        try:
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            sent = send_report_email(report)
            if sent and callable(on_success):
                on_success()
            if not sent and callable(on_failure):
                on_failure("email_not_sent_or_not_configured")
        except Exception:
            if callable(on_failure):
                on_failure("smtp_send_failed")
            return

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()


def send_personalized_email(recipients: list[str], subject: str, message: str, sent_by: str = "Admin") -> dict:
    """Send a personalized/manual email to one or more recipients.

    Args:
        recipients: List of email addresses
        subject: Email subject line
        message: Plain text message body
        sent_by: Identifier of the admin sending the email

    Returns:
        dict with success status, recipients, and any error message
    """
    from datetime import datetime

    if not smtp_ready():
        return {"success": False, "error": "Email service not configured", "recipients": recipients}

    if not recipients or not subject or not message:
        return {"success": False, "error": "Missing required fields", "recipients": recipients}

    # Validate recipient emails
    valid_recipients = []
    for email in recipients:
        email = email.strip()
        if email and "@" in email and "." in email.split("@")[-1]:
            valid_recipients.append(email)

    if not valid_recipients:
        return {"success": False, "error": "No valid recipient emails provided", "recipients": recipients}

    try:
        email_message = EmailMessage()
        email_message["Subject"] = subject
        email_message["From"] = formataddr(("AI Interview System (Admin)", EMAIL_SENDER))
        email_message["To"] = ", ".join(valid_recipients)
        email_message.set_content(message)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            if SMTP_USE_TLS:
                server.starttls()
                server.ehlo()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(email_message)

        # Log successful email
        _log_email_history(
            recipients=valid_recipients,
            subject=subject,
            sent_by=sent_by,
            status="success",
            error_message=""
        )

        return {"success": True, "recipients": valid_recipients, "error": None}

    except Exception as e:
        error_msg = str(e)
        # Log failed email
        _log_email_history(
            recipients=valid_recipients,
            subject=subject,
            sent_by=sent_by,
            status="failed",
            error_message=error_msg
        )
        return {"success": False, "recipients": valid_recipients, "error": error_msg}


def _log_email_history(recipients: list[str], subject: str, sent_by: str, status: str, error_message: str = ""):
    """Log an email to the history store."""
    from datetime import datetime

    entry = {
        "id": f"{datetime.utcnow().timestamp()}-{len(_email_history)}",
        "recipients": ", ".join(recipients),
        "subject": subject[:200],  # Limit subject length
        "sent_by": sent_by,
        "sent_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "status": status,
        "error_message": error_message[:500] if error_message else ""
    }

    _email_history.insert(0, entry)

    # Keep history size limited
    while len(_email_history) > MAX_HISTORY_SIZE:
        _email_history.pop()


def get_email_history(limit: int = 50) -> list[dict]:
    """Get the email history, most recent first."""
    return _email_history[:limit]


def clear_email_history():
    """Clear all email history. Admin only operation."""
    global _email_history
    _email_history = []
