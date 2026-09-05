"""Email service for CLPZ.

Uses Resend (free tier: 3,000 emails/month) for transactional email.
Falls back to console logging when Resend is not configured.

Environment variables:
    RESEND_API_KEY: Resend API key (required for production)
    CLPZ_FROM_EMAIL: Sender email address (default: noreply@clpz.com)
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("clpz.email")

_resend_client = None
_from_email = os.getenv("CLPZ_FROM_EMAIL", "noreply@clpz.com")


def _get_client():
    """Lazily initialize Resend client."""
    global _resend_client
    if _resend_client is not None:
        return _resend_client
    
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("RESEND_API_KEY not set. Emails will be logged to console only.")
        return None
    
    try:
        import resend
        resend.api_key = api_key
        _resend_client = resend
        return _resend_client
    except ImportError:
        logger.warning("resend package not installed. Emails will be logged to console only.")
        return None


def send_verification_email(to_email: str, code: str, purpose: str = "signup") -> bool:
    """Send a verification code email. Returns True if sent successfully."""
    client = _get_client()
    
    subject = "CLPZ - Verify your email" if purpose == "signup" else "CLPZ - Password Reset Code"
    html = f"""
    <div style="font-family: sans-serif; max-width: 400px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1a1a1a;">{subject}</h2>
        <p style="color: #666; font-size: 14px;">Your verification code is:</p>
        <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #efa93a; 
                    text-align: center; padding: 20px; background: #f9f9f9; border-radius: 8px;
                    margin: 16px 0;">{code}</div>
        <p style="color: #666; font-size: 13px;">This code expires in 15 minutes.</p>
        <p style="color: #999; font-size: 12px;">If you didn't request this, ignore this email.</p>
    </div>
    """
    
    if client is None:
        # Development fallback: log to console
        logger.info(f"[CLPZ EMAIL] To: {to_email} | Subject: {subject} | Code: {code}")
        sep = "=" * 50
        print()
        print(sep)
        print("CLPZ VERIFICATION CODE")
        print("To:", to_email)
        print("Code:", code)
        print(sep)
        return True
    
    try:
        client.Emails.send({
            "from": f"CLPZ <{_from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html,
        })
        logger.info(f"Verification email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {to_email}: {e}")
        # Fall back to console
        logger.info(f"[CLPZ EMAIL FALLBACK] To: {to_email} | Code: {code}")
        return False


def send_password_reset_email(to_email: str, code: str) -> bool:
    """Send a password reset code email."""
    return send_verification_email(to_email, code, purpose="reset")
