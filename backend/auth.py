"""
backend/auth.py — Authentication, Authorization, Institutional Policy, and OTP Engine
IoT-Enabled Smart Oxygen Cylinder Monitoring System with AI-Driven Healthcare Recommendations.
"""

import os
import re
import time
import secrets
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, session, current_app
from backend.models import db, User, EmailOTP

ALLOWED_DOMAIN = "@iilm.edu"
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@iilm\.edu$", re.IGNORECASE)

# In-memory rate limiting stores
# Structure: { key: [timestamps] }
_RATE_LIMIT_STORE = {
    "otp_request": {},
    "login_failed": {}
}


def is_rate_limited(bucket: str, key: str, max_requests: int, window_seconds: int) -> bool:
    """Sliding-window rate limiter."""
    now = time.time()
    store = _RATE_LIMIT_STORE.setdefault(bucket, {})
    timestamps = store.get(key, [])
    # Filter out timestamps outside window
    timestamps = [t for t in timestamps if now - t < window_seconds]
    if len(timestamps) >= max_requests:
        store[key] = timestamps
        return True
    timestamps.append(now)
    store[key] = timestamps
    return False


def validate_institutional_email(email: str) -> bool:
    """Enforces registration strictly for emails ending with @iilm.edu."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip().lower()
    return bool(EMAIL_REGEX.match(email))


def generate_secure_otp() -> str:
    """Generates a cryptographically strong 6-digit numeric OTP."""
    return f"{secrets.randbelow(900000) + 100000}"


def hash_otp(otp: str, secret_key: str = None) -> str:
    """Hashes OTP with SHA-256 and secret salt."""
    secret = secret_key or os.environ.get("FLASK_SECRET_KEY", "oxysense-otp-secret-salt-2026")
    return hashlib.sha256(f"{otp}:{secret}".encode("utf-8")).hexdigest()


def verify_otp_hash(otp: str, stored_hash: str, secret_key: str = None) -> bool:
    """Constant-time verification of OTP against stored hash."""
    computed = hash_otp(otp, secret_key)
    return secrets.compare_digest(computed, stored_hash)


def send_otp_email(to_email: str, otp_code: str, full_name: str = "Colleague"):
    """
    Sends 6-digit OTP verification email via SMTP if configured.
    Falls back to secure console logging in developer/offline environments.
    Returns (sent_via_smtp: bool, status_message: str).
    """
    mail_server = os.environ.get("MAIL_SERVER")
    mail_username = os.environ.get("MAIL_USERNAME")
    mail_password = os.environ.get("MAIL_PASSWORD")
    mail_port = int(os.environ.get("MAIL_PORT", 587))
    mail_sender = os.environ.get("MAIL_DEFAULT_SENDER", f"OxySense Security <no-reply{ALLOWED_DOMAIN}>")
    use_tls = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")

    subject = f"OxySense Verification Code: {otp_code}"
    body_text = f"""
Hello {full_name},

Your 6-digit verification code for OxySense IoT Oxygen Cylinder Monitoring is:

    {otp_code}

This code expires in 10 minutes and can only be used once.
If you did not request this verification, please ignore this email.

Institutional Security Team
OxySense @ IILM University
"""

    # If SMTP is configured, attempt delivery
    if mail_server and mail_username and mail_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = mail_sender
            msg["To"] = to_email

            part = MIMEText(body_text, "plain")
            msg.attach(part)

            with smtplib.SMTP(mail_server, mail_port, timeout=8) as server:
                if use_tls:
                    server.starttls()
                server.login(mail_username, mail_password)
                server.sendmail(mail_sender, [to_email], msg.as_string())
            print(f"[OxySense Auth] OTP email successfully dispatched to {to_email}", flush=True)
            return True, "Email successfully sent via SMTP"
        except Exception as smtp_err:
            print(f"[OxySense Auth] SMTP dispatch failed: {smtp_err}. Falling back to console banner.", flush=True)

    # Secure developer console output
    print("=" * 68, flush=True)
    print(f"  [OXYSENSE SECURE OTP DISPATCH] -> {to_email}", flush=True)
    print(f"  VERIFICATION CODE : {otp_code}", flush=True)
    print(f"  EXPIRES IN        : 10 MINUTES (SINGLE-USE)", flush=True)
    print("=" * 68, flush=True)
    return False, "SMTP not configured. Using development console OTP."


def get_current_user():
    """Retrieves authenticated user from active session."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.filter_by(id=user_id, status="ACTIVE").first()


def login_required(f):
    """Decorator requiring an active user session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({
                "success": False,
                "error": "Authentication required. Please sign in with your @iilm.edu account."
            }), 401
        return f(*args, **kwargs)
    return decorated_function


def role_required(allowed_roles: list):
    """Decorator requiring specific role(s) (e.g. ['ADMIN', 'MAIN_ADMIN'])."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({
                    "success": False,
                    "error": "Authentication required."
                }), 401
            if user.role not in allowed_roles and not user.is_main_admin:
                return jsonify({
                    "success": False,
                    "error": f"Access denied. Required role: {', '.join(allowed_roles)}. Your role: {user.role}."
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def main_admin_required(f):
    """Decorator requiring Main Admin privileges exclusively."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({
                "success": False,
                "error": "Authentication required."
            }), 401
        if not user.is_main_admin:
            return jsonify({
                "success": False,
                "error": "Access denied. Only the Main Administrator can modify Admin privileges."
            }), 403
        return f(*args, **kwargs)
    return decorated_function


def verify_esp32_key(req) -> bool:
    """Validates hardware API token from ESP32 headers."""
    expected_key = os.environ.get("ESP32_API_KEY", "oxysense-esp32-secure-token-2026")
    provided_key = req.headers.get("X-ESP32-DEVICE-KEY") or req.headers.get("X-API-KEY")
    if not provided_key and req.headers.get("Authorization"):
        auth_hdr = req.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            provided_key = auth_hdr.split("Bearer ", 1)[1].strip()
    return bool(provided_key and secrets.compare_digest(provided_key, expected_key))
