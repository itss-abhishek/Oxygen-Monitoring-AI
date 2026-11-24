"""
test_auth_policy.py — Comprehensive Automated Test Suite for OxySense Authentication Policy
Validates institutional domain restrictions (@iilm.edu), OTP lifecycle, role-based access control,
bootstrap protection, Viewer restrictions, and ESP32 hardware authentication separation.
"""

import pytest
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash
from backend.app import app
from backend.models import db, User, EmailOTP, Alert
from backend.auth import (
    validate_institutional_email,
    generate_secure_otp,
    hash_otp,
    verify_otp_hash,
    ALLOWED_DOMAIN
)
from backend.bootstrap_admin import bootstrap_main_admin


@pytest.fixture
def auth_client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_domain_validator():
    """Requirement 1: Only email addresses ending exactly with @iilm.edu can register."""
    assert validate_institutional_email("student@iilm.edu") is True
    assert validate_institutional_email("dr.sharma@iilm.edu") is True
    assert validate_institutional_email("nurse_priya@iilm.edu") is True

    # Rejections
    assert validate_institutional_email("hacker@gmail.com") is False
    assert validate_institutional_email("user@iilm.edu.com") is False
    assert validate_institutional_email("user@fake-iilm.edu") is False
    assert validate_institutional_email("iilm.edu") is False
    assert validate_institutional_email("") is False
    assert validate_institutional_email(None) is False


def test_registration_request_otp_rejects_non_iilm(auth_client):
    """Requirement 1 & 2: Public registration rejects non-@iilm.edu emails."""
    res = auth_client.post("/api/auth/register-request-otp", json={
        "email": "intruder@external.com",
        "full_name": "Intruder"
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "@iilm.edu" in data["error"]


def test_registration_request_otp_success_and_expiry(auth_client):
    """Requirement 3 & 4: Secure 6-digit OTP created with 10-minute expiry."""
    with app.app_context():
        EmailOTP.query.filter_by(email="researcher@iilm.edu").delete()
        db.session.commit()

    res = auth_client.post("/api/auth/register-request-otp", json={
        "email": "researcher@iilm.edu",
        "full_name": "Dr. Researcher"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    with app.app_context():
        otp_rec = EmailOTP.query.filter_by(email="researcher@iilm.edu").order_by(EmailOTP.id.desc()).first()
        assert otp_rec is not None
        assert otp_rec.is_used is False
        # Expiry is set to ~10 minutes in the future
        diff = (otp_rec.expires_at - otp_rec.created_at).total_seconds()
        assert 590 <= diff <= 610


def test_registration_verify_otp_assigns_viewer_role(auth_client):
    """Requirement 5 & 6: Verification assigns VIEWER role automatically; ignores client role override."""
    with app.app_context():
        EmailOTP.query.filter_by(email="clinical.staff@iilm.edu").delete()
        User.query.filter_by(email="clinical.staff@iilm.edu").delete()
        db.session.commit()

    # Step 1: Request OTP
    auth_client.post("/api/auth/register-request-otp", json={
        "email": "clinical.staff@iilm.edu",
        "full_name": "Staff Member"
    })

    # Retrieve OTP directly for verification test
    with app.app_context():
        raw_otp = "842915"
        otp_rec = EmailOTP.query.filter_by(email="clinical.staff@iilm.edu").order_by(EmailOTP.id.desc()).first()
        otp_rec.otp_hash = hash_otp(raw_otp, app.secret_key)
        db.session.commit()

    # Step 2: Submit verification with malicious attempt to request ADMIN role
    res = auth_client.post("/api/auth/register-verify-otp", json={
        "email": "clinical.staff@iilm.edu",
        "otp": "842915",
        "password": "SecurePassword123",
        "full_name": "Staff Member",
        "role": "ADMIN"  # Malicious attempt
    })
    assert res.status_code == 200
    user_data = res.get_json()["user"]
    # Policy 5 & 6 enforced: role is strictly VIEWER
    assert user_data["role"] == "VIEWER"
    assert user_data["is_main_admin"] is False
    assert user_data["is_verified"] is True

    with app.app_context():
        # Policy 4 enforced: OTP marked as used (cannot be reused)
        used_otp = EmailOTP.query.filter_by(email="clinical.staff@iilm.edu").order_by(EmailOTP.id.desc()).first()
        assert used_otp.is_used is True

    # Attempting to reuse the OTP must fail
    res_reuse = auth_client.post("/api/auth/register-verify-otp", json={
        "email": "clinical.staff@iilm.edu",
        "otp": "842915",
        "password": "AnotherPassword123"
    })
    assert res_reuse.status_code == 400


def test_main_admin_bootstrap_one_time(auth_client):
    """Requirement 7: First admin created through secure bootstrap; subsequent bootstrap blocked."""
    with app.app_context():
        User.query.delete()
        db.session.commit()

        success_first = bootstrap_main_admin("head.biomed@iilm.edu", "Head Admin", "AdminPass@2026")
        assert success_first is True

        admin_user = User.query.filter_by(email="head.biomed@iilm.edu").first()
        assert admin_user.is_main_admin is True
        assert admin_user.role == "MAIN_ADMIN"

        # Second bootstrap attempt must abort
        success_second = bootstrap_main_admin("second.admin@iilm.edu", "Second Admin", "SecondPass@2026")
        assert success_second is False

        # Restore admin@iilm.edu for other tests
        User.query.delete()
        bootstrap_main_admin("admin@iilm.edu", "Main Administrator", "Admin@IILM2026")
        db.session.commit()


def test_role_promotion_permissions(auth_client):
    """Requirement 8 & 9: Only Main Admin can promote to Admin. Other Admins cannot change Admin roles."""
    with app.app_context():
        # Setup Main Admin
        main_adm = User.query.filter_by(is_main_admin=True).first()
        if not main_adm:
            bootstrap_main_admin("admin@iilm.edu", "Main Administrator", "Admin@IILM2026")
            main_adm = User.query.filter_by(is_main_admin=True).first()
        main_adm_id = main_adm.id

        # Setup standard Admin
        sub_adm = User.query.filter_by(email="sub.admin@iilm.edu").first()
        if not sub_adm:
            sub_adm = User(
                email="sub.admin@iilm.edu",
                full_name="Sub Admin",
                password_hash="dummy",
                role="ADMIN",
                is_main_admin=False,
                is_verified=True,
                status="ACTIVE"
            )
            db.session.add(sub_adm)

        # Setup standard Viewer
        viewer = User.query.filter_by(email="regular.viewer@iilm.edu").first()
        if not viewer:
            viewer = User(
                email="regular.viewer@iilm.edu",
                full_name="Regular Viewer",
                password_hash="dummy",
                role="VIEWER",
                is_main_admin=False,
                is_verified=True,
                status="ACTIVE"
            )
            db.session.add(viewer)
        else:
            viewer.role = "VIEWER"

        db.session.commit()
        viewer_id = viewer.id
        sub_adm_id = sub_adm.id

    # 1. Standard Admin attempts to promote Viewer -> Must get 403 Forbidden!
    with auth_client.session_transaction() as sess:
        sess["user_id"] = sub_adm_id
        sess["user"] = {"id": sub_adm_id, "role": "ADMIN", "is_main_admin": False}

    res_sub = auth_client.post(f"/api/admin/users/{viewer_id}/role", json={"role": "ADMIN"})
    assert res_sub.status_code == 403
    assert "Only the Main Administrator" in res_sub.get_json()["error"]

    # 2. Main Admin promotes Viewer -> Allowed (200 OK)
    with auth_client.session_transaction() as sess:
        sess["user_id"] = main_adm_id
        sess["user"] = {"id": main_adm_id, "role": "MAIN_ADMIN", "is_main_admin": True}

    res_main = auth_client.post(f"/api/admin/users/{viewer_id}/role", json={"role": "ADMIN"})
    assert res_main.status_code == 200
    assert res_main.get_json()["user"]["role"] == "ADMIN"


def test_viewer_permission_enforcement_on_backend(auth_client):
    """Requirement 10 & 11: Viewers can read telemetry, but cannot modify data or acknowledge alerts."""
    with app.app_context():
        viewer = User(
            email="nurse.viewer@iilm.edu",
            full_name="Nurse Viewer",
            password_hash="dummy",
            role="VIEWER",
            is_main_admin=False,
            is_verified=True,
            status="ACTIVE"
        )
        db.session.add(viewer)
        # Seed an alert
        test_alert = Alert(cylinder_id="CYL-ICU-101", alert_type="WARNING", message="Test Warning")
        db.session.add(test_alert)
        db.session.commit()
        v_id = viewer.id
        alert_id = test_alert.id

    # Authenticate as Viewer
    with auth_client.session_transaction() as sess:
        sess["user_id"] = v_id
        sess["user"] = {"id": v_id, "role": "VIEWER", "is_main_admin": False}

    # 1. Viewer CAN read overview & alerts
    res_overview = auth_client.get("/api/overview")
    assert res_overview.status_code == 200
    res_alerts = auth_client.get("/api/alerts")
    assert res_alerts.status_code == 200

    # 2. Viewer CANNOT acknowledge alerts (Backend 403)
    res_ack = auth_client.post("/api/alerts/acknowledge", json={"alert_id": f"ALT-{alert_id}"})
    assert res_ack.status_code == 403
    assert "Viewers cannot acknowledge alerts" in res_ack.get_json()["error"]

    # 3. Viewer CANNOT trigger simulation scenarios (Backend 403)
    res_sim = auth_client.post("/api/simulation/scenario", json={"scenario": "LOW_PRESSURE"})
    assert res_sim.status_code == 403
    assert "Viewers cannot trigger simulation" in res_sim.get_json()["error"]

    # 4. Viewer CANNOT modify settings (Backend 403)
    res_set = auth_client.post("/api/settings", json={"warning_threshold_bar": 45.0})
    assert res_set.status_code == 403
    assert "Viewers cannot modify system settings" in res_set.get_json()["error"]

    # 5. Viewer CANNOT access User Management (Backend 403)
    res_users = auth_client.get("/api/admin/users")
    assert res_users.status_code == 403


def test_esp32_hardware_key_separate_authentication(auth_client):
    """Requirement 14: Keep ESP32 device authentication separate from browser login."""
    payload = {
        "cylinders": [{"cylinder_id": "CYL-ICU-101", "pressure_bar": 150.0, "flow_lpm": 2.0}]
    }

    # Turn off test bypass to verify hardware key requirement
    app.config["TESTING"] = False
    try:
        # 1. Ingestion without key -> 401 Unauthorized
        res_no_key = auth_client.post("/api/telemetry/hardware-ingest", json=payload)
        assert res_no_key.status_code == 401

        # 2. Ingestion with wrong key -> 401 Unauthorized
        res_wrong_key = auth_client.post(
            "/api/telemetry/hardware-ingest",
            json=payload,
            headers={"X-ESP32-DEVICE-KEY": "wrong-key"}
        )
        assert res_wrong_key.status_code == 401

        # 3. Ingestion with correct key -> 200 OK
        res_correct = auth_client.post(
            "/api/telemetry/hardware-ingest",
            json=payload,
            headers={"X-ESP32-DEVICE-KEY": "oxysense-esp32-secure-token-2026"}
        )
        assert res_correct.status_code == 200
        assert res_correct.get_json()["success"] is True
    finally:
        app.config["TESTING"] = True
