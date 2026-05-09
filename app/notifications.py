"""
Email notification system for server errors and critical events.
Sends alerts to admin email configured in .env
"""
import os
import traceback
from typing import Optional
import resend

resend.api_key = os.environ.get("RESEND_API_KEY", "")

def send_admin_alert(subject: str, body: str, error: Optional[Exception] = None):
    """
    Send an email alert to the admin about a critical server event.

    Args:
        subject: Email subject line
        body: Main message body
        error: Optional exception to include in the email
    """
    admin_email = os.environ.get("ADMIN_EMAIL")
    server_from = os.environ.get("SERVER_FROM_EMAIL", "API Server <apiserver@api.novaroma-homelab.uk>")

    if not admin_email:
        print(f"[ALERT] {subject}: {body}")
        if error:
            print(f"[ERROR] {error}")
        return

    # Build email HTML
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #dc3545;">🚨 API Gateway Alert</h2>
            <h3>{subject}</h3>
            <p>{body}</p>
    """

    if error:
        error_details = traceback.format_exception(type(error), error, error.__traceback__)
        error_text = "".join(error_details)
        html_body += f"""
            <div style="background: #f8f9fa; padding: 15px; margin-top: 20px; border-left: 4px solid #dc3545;">
                <h4 style="margin-top: 0;">Error Details:</h4>
                <pre style="white-space: pre-wrap; word-wrap: break-word;">{error_text}</pre>
            </div>
        """

    html_body += """
            <hr style="margin-top: 30px;">
            <p style="color: #666; font-size: 12px;">
                This is an automated alert from your API Gateway at api.novaroma-homelab.uk
            </p>
        </body>
    </html>
    """

    try:
        params = {
            "from": server_from,
            "to": [admin_email],
            "subject": f"[API Gateway] {subject}",
            "html": html_body
        }
        resend.Emails.send(params)
        print(f"[ALERT SENT] {subject}")
    except Exception as e:
        print(f"[FAILED TO SEND ALERT] {subject}: {e}")
        print(f"[ORIGINAL ERROR] {body}")
        if error:
            print(f"[ERROR DETAILS] {error}")


def notify_startup_error(error: Exception):
    """Send notification when server fails to start"""
    send_admin_alert(
        subject="Server Startup Failed",
        body="The API Gateway failed to start. Please check the server logs and fix the issue.",
        error=error
    )


def notify_startup_success():
    """Send notification when server starts successfully"""
    send_admin_alert(
        subject="Server Started Successfully",
        body="The API Gateway has started successfully and is ready to accept requests."
    )


def notify_critical_error(error: Exception, context: str = ""):
    """Send notification for critical runtime errors"""
    body = f"A critical error occurred in the API Gateway."
    if context:
        body += f"\n\nContext: {context}"

    send_admin_alert(
        subject="Critical Runtime Error",
        body=body,
        error=error
    )
