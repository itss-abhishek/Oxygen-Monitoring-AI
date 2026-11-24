"""
backend/app.py — Flask REST API Server for OxySense Web Dashboard.
"""

import os
import io
import csv
import json
import time
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request, render_template, Response, send_file, session, has_app_context
from werkzeug.security import generate_password_hash, check_password_hash
from backend.simulation_engine import telemetry_instance, generate_ai_insights
from backend.mock_data import MOCK_CYLINDERS
from backend.models import db, Cylinder, Telemetry, Alert, User, EmailOTP
from backend.database import init_db, prune_telemetry_older_than
from backend.auth import (
    ALLOWED_DOMAIN,
    validate_institutional_email,
    generate_secure_otp,
    hash_otp,
    verify_otp_hash,
    send_otp_email,
    get_current_user,
    login_required,
    role_required,
    main_admin_required,
    verify_esp32_key,
    is_rate_limited
)

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "..", "static")
)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "oxysense-demo-secret-key-2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"

# Initialize SQLite database (oxygen_monitoring.db) and demonstration fleet models
init_db(app)


# ---------------------------------------------------------------------------
# Page Route
# ---------------------------------------------------------------------------

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    traceback.print_exc()
    return jsonify({"success": False, "error": str(e)}), 500

@app.route("/")
def index():
    return render_template("index.html")

# ---------------------------------------------------------------------------
# Institutional Authentication Endpoints (@iilm.edu)
# ---------------------------------------------------------------------------

@app.route("/api/auth/register-request-otp", methods=["POST"])
def auth_register_request_otp():
    """Step 1: Request 6-digit OTP for institutional email self-registration."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    full_name = (data.get("full_name") or data.get("name") or "").strip()

    if not validate_institutional_email(email):
        return jsonify({
            "success": False,
            "error": f"Registration policy violation: Only institutional emails ending with '{ALLOWED_DOMAIN}' are permitted."
        }), 400

    if not full_name:
        return jsonify({"success": False, "error": "Please provide your full name."}), 400

    # Check if active verified account already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user.is_verified:
        return jsonify({
            "success": False,
            "error": "An account with this institutional email already exists. Please sign in."
        }), 409

    # Rate limiting: max 3 requests per 10 minutes per email
    client_ip = request.remote_addr or "client"
    if is_rate_limited("otp_request", f"{email}:{client_ip}", max_requests=3, window_seconds=600):
        return jsonify({
            "success": False,
            "error": "Too many OTP requests. Please wait 10 minutes before requesting another verification code."
        }), 429

    # Invalidate previous unused OTPs for this email
    EmailOTP.query.filter_by(email=email, is_used=False).update({"is_used": True})

    otp_code = generate_secure_otp()
    otp_record = EmailOTP(
        email=email,
        otp_hash=hash_otp(otp_code, app.secret_key),
        purpose="REGISTRATION",
        attempts=0,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        is_used=False
    )
    db.session.add(otp_record)
    db.session.commit()

    sent_via_smtp, smtp_msg = send_otp_email(email, otp_code, full_name)

    response_payload = {
        "success": True,
        "email": email,
        "sent_via_smtp": sent_via_smtp
    }
    if sent_via_smtp:
        response_payload["message"] = f"A secure 6-digit verification code has been dispatched to {email}. Valid for 10 minutes."
    else:
        response_payload["message"] = f"SMTP offline: verification code is {otp_code}."
        response_payload["dev_otp"] = otp_code

    return jsonify(response_payload)


@app.route("/api/auth/register-verify-otp", methods=["POST"])
def auth_register_verify_otp():
    """Step 2: Verify 6-digit OTP and complete password setup (auto-assigns VIEWER role)."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    otp = (data.get("otp") or "").strip()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or data.get("name") or "").strip()

    if not validate_institutional_email(email):
        return jsonify({"success": False, "error": f"Invalid email domain. Must end with '{ALLOWED_DOMAIN}'."}), 400

    if len(otp) != 6 or not otp.isdigit():
        return jsonify({"success": False, "error": "Verification code must be exactly 6 digits."}), 400

    if len(password) < 8:
        return jsonify({"success": False, "error": "Password must be at least 8 characters long."}), 400

    # Retrieve latest active OTP for this email
    otp_record = EmailOTP.query.filter_by(email=email, is_used=False).order_by(EmailOTP.id.desc()).first()
    if not otp_record or not otp_record.is_valid():
        return jsonify({
            "success": False,
            "error": "Verification code has expired or is invalid. Please request a new code."
        }), 400

    otp_record.attempts += 1

    if not verify_otp_hash(otp, otp_record.otp_hash, app.secret_key):
        if otp_record.attempts >= 5:
            otp_record.is_used = True
            db.session.commit()
            return jsonify({
                "success": False,
                "error": "Maximum invalid attempts exceeded. This verification code has been invalidated."
            }), 400
        db.session.commit()
        remaining = 5 - otp_record.attempts
        return jsonify({
            "success": False,
            "error": f"Incorrect verification code. {remaining} attempt(s) remaining."
        }), 400

    # OTP is valid! Invalidate immediately (single-use policy)
    otp_record.is_used = True

    # Policy 5 & 6: Assign VIEWER role automatically. No public admin registration or role selection.
    user = User.query.filter_by(email=email).first()
    hashed_pwd = generate_password_hash(password, method="scrypt")

    if user:
        user.full_name = full_name or user.full_name
        user.password_hash = hashed_pwd
        user.is_verified = True
        user.status = "ACTIVE"
        if not user.role:
            user.role = "VIEWER"
    else:
        user = User(
            email=email,
            full_name=full_name or "Institutional Staff Member",
            password_hash=hashed_pwd,
            role="VIEWER",  # Strictly Viewer on self-registration
            is_main_admin=False,
            is_verified=True,
            status="ACTIVE",
            created_at=datetime.utcnow()
        )
        db.session.add(user)

    db.session.commit()

    # Establish session
    session["user_id"] = user.id
    session["user"] = user.to_dict()

    return jsonify({
        "success": True,
        "message": "Account successfully verified. Viewer role assigned.",
        "user": user.to_dict()
    })


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Authenticate institutional staff member or demo user."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required."}), 400

    # Rate limiting on failed logins: max 10 per 5 minutes per IP
    client_ip = request.remote_addr or "client"
    if is_rate_limited("login_failed", client_ip, max_requests=10, window_seconds=300):
        return jsonify({
            "success": False,
            "error": "Too many failed login attempts. Please wait 5 minutes before trying again."
        }), 429

    # Database check (Users table)
    search_email = email if "@" in email else f"{email}{ALLOWED_DOMAIN}"
    db_user = User.query.filter_by(email=search_email).first()

    if not db_user or not check_password_hash(db_user.password_hash, password):
        return jsonify({"success": False, "error": "Invalid email or password."}), 401

    if not db_user.is_verified:
        return jsonify({"success": False, "error": "Account pending verification. Please verify your OTP."}), 401

    if db_user.status == "SUSPENDED":
        return jsonify({"success": False, "error": "Account suspended. Please contact the Main Administrator."}), 403

    db_user.last_login = datetime.utcnow()
    db.session.commit()

    session["user_id"] = db_user.id
    session["user"] = db_user.to_dict()

    return jsonify({
        "success": True,
        "message": "Authentication successful",
        "user": db_user.to_dict()
    })


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Clear session on logout."""
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})


@app.route("/api/auth/session", methods=["GET"])
def auth_session():
    """Check current session."""
    user = get_current_user()
    if user:
        return jsonify({"authenticated": True, "user": user.to_dict()})
    demo_user = session.get("user")
    if demo_user:
        return jsonify({"authenticated": True, "user": demo_user})
    return jsonify({"authenticated": False, "user": None})


# ---------------------------------------------------------------------------
# Admin User Management Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/admin/users", methods=["GET"])
@role_required(["ADMIN", "MAIN_ADMIN"])
def admin_list_users():
    """Admin-only: List all registered institutional users."""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({
        "success": True,
        "users": [u.to_dict() for u in users],
        "total": len(users)
    })


@app.route("/api/admin/users/<int:user_id>/role", methods=["POST"])
@main_admin_required
def admin_modify_user_role(user_id):
    """Main Admin only: Promote to Admin or demote to Viewer. Other Admins cannot change roles."""
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"success": False, "error": "User not found."}), 404

    if target_user.is_main_admin:
        return jsonify({"success": False, "error": "Cannot modify role of the Main Administrator."}), 400

    data = request.get_json() or {}
    new_role = (data.get("role") or "").strip().upper()
    if new_role not in ("ADMIN", "VIEWER"):
        return jsonify({"success": False, "error": "Invalid role. Must be 'ADMIN' or 'VIEWER'."}), 400

    target_user.role = new_role
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"User {target_user.email} role updated to {new_role}.",
        "user": target_user.to_dict()
    })


@app.route("/api/admin/users/<int:user_id>/status", methods=["POST"])
@role_required(["ADMIN", "MAIN_ADMIN"])
def admin_modify_user_status(user_id):
    """Admin-only: Activate or suspend user account."""
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"success": False, "error": "User not found."}), 404

    if target_user.is_main_admin:
        return jsonify({"success": False, "error": "Cannot suspend the Main Administrator."}), 400

    data = request.get_json() or {}
    new_status = (data.get("status") or "").strip().upper()
    if new_status not in ("ACTIVE", "SUSPENDED"):
        return jsonify({"success": False, "error": "Invalid status. Must be 'ACTIVE' or 'SUSPENDED'."}), 400

    target_user.status = new_status
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"User {target_user.email} status changed to {new_status}.",
        "user": target_user.to_dict()
    })

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/overview", methods=["GET"])
def get_overview():
    """Unified telemetry overview for top metric cards and status banner."""
    payload = telemetry_instance.get_overview_payload()
    payload["hardware_bridge"] = hardware_bridge_state
    return jsonify(payload)

@app.route("/api/live-stream", methods=["GET"])
def get_live_stream():
    """Tick forward simulation and return updated readings and recent history."""
    telemetry_instance.tick_simulation()
    payload = telemetry_instance.get_overview_payload()
    payload["history"] = telemetry_instance.history
    payload["hardware_bridge"] = hardware_bridge_state
    return jsonify(payload)

@app.route("/api/history", methods=["GET"])
def get_history():
    """Returns telemetry time-series backed by SQLite database with in-memory fallback."""
    range_param = request.args.get("range", "15m")
    cyl_id = request.args.get("cylinder_id", telemetry_instance.config["cylinder_id"])

    limit_map = {"15m": 30, "1h": 60, "24h": 300}
    limit = limit_map.get(range_param, 60)

    try:
        db_cyl = Cylinder.query.filter(Cylinder.cylinder_id.ilike(cyl_id)).first()
        if db_cyl:
            records = Telemetry.query.filter_by(cylinder_db_id=db_cyl.id).order_by(Telemetry.timestamp.desc()).limit(limit).all()
            if records:
                pts = []
                for r in reversed(records):
                    p_bar = round(float(r.pressure_bar), 1)
                    f_lpm = round(float(r.flow_rate_lpm), 2)
                    ts_str = r.timestamp.strftime("%H:%M:%S") if r.timestamp else ""
                    iso_str = r.timestamp.isoformat() if r.timestamp else ""
                    rem_pct = round((p_bar / 200.0) * 100, 1)
                    ete_m = round((db_cyl.capacity_l or 660.0) * (p_bar / 200.0) / max(0.1, f_lpm), 1) if p_bar > 0 and f_lpm > 0 else 0
                    stat = "NORMAL"
                    if p_bar <= 20.0:
                        stat = "CRITICAL"
                    elif p_bar <= 50.0:
                        stat = "LOW_PRESSURE"
                    pts.append({
                        "timestamp": ts_str,
                        "iso_time": iso_str,
                        "pressure_bar": p_bar,
                        "pressure_psi": round(p_bar * 14.5038, 0),
                        "flow_lpm": f_lpm,
                        "remaining_pct": rem_pct,
                        "ete_minutes": ete_m,
                        "status": stat,
                        "data_source": r.data_source,
                        "is_simulated": r.is_simulated
                    })
                return jsonify({"range": range_param, "points": pts, "total": len(pts)})
    except Exception:
        pass

    # Return in-memory historical points as fallback
    pts = telemetry_instance.history
    if range_param == "15m":
        pts = pts[-15:]
    elif range_param == "1h":
        pts = pts[-30:]
    return jsonify({
        "range": range_param,
        "points": pts,
        "total": len(pts)
    })

@app.route("/api/cylinders", methods=["GET"])
def list_cylinders():
    """Searchable & filterable hospital cylinder fleet backed by SQLite database."""
    search = request.args.get("search", "").lower().strip()
    status_filter = request.args.get("status", "ALL").upper().strip()

    # Mirror live primary cylinder into the fleet list
    primary_live = telemetry_instance.get_overview_payload()
    
    # Query SQLite database first, fallback to mock if DB empty
    try:
        db_cylinders = Cylinder.query.all()
        source_fleet = [c.to_dict() for c in db_cylinders] if db_cylinders else MOCK_CYLINDERS
    except Exception:
        source_fleet = MOCK_CYLINDERS

    updated_fleet = []
    for c in source_fleet:
        item = dict(c)
        if item["id"] == telemetry_instance.config["cylinder_id"]:
            item["pressure_bar"] = primary_live["pressure"]["bar"]
            item["pressure_psi"] = primary_live["pressure"]["psi"]
            item["flow_lpm"] = primary_live["flow"]["value"]
            item["status"] = primary_live["status"]["level"]
            item["ete"] = primary_live["ete"]["display"]
            item["last_updated"] = primary_live["device"]["last_update"]
        updated_fleet.append(item)

    results = []
    for c in updated_fleet:
        if status_filter != "ALL" and c["status"] != status_filter:
            continue
        if search and (search not in c["id"].lower() and search not in c["ward"].lower() and search not in c["patient"].lower()):
            continue
        results.append(c)

    return jsonify({"cylinders": results, "total": len(results)})

@app.route("/api/cylinders/active", methods=["GET", "POST"])
def active_cylinder():
    """Get or switch the active monitored cylinder on the overview dashboard."""
    if request.method == "POST":
        data = request.get_json() or {}
        cyl_id = (data.get("cylinder_id") or "").strip().upper()

        # Check database first
        db_cyl = Cylinder.query.filter(Cylinder.cylinder_id.ilike(cyl_id)).first()
        if db_cyl:
            c_dict = db_cyl.to_dict()
            telemetry_instance.switch_active_cylinder(c_dict)
            return jsonify({
                "success": True,
                "active_cylinder_id": db_cyl.cylinder_id,
                "cylinder": c_dict,
                "overview": telemetry_instance.get_overview_payload()
            })

        for c in MOCK_CYLINDERS:
            if c["id"].upper() == cyl_id:
                telemetry_instance.switch_active_cylinder(c)
                return jsonify({
                    "success": True,
                    "active_cylinder_id": c["id"],
                    "cylinder": c,
                    "overview": telemetry_instance.get_overview_payload()
                })
        return jsonify({"success": False, "error": f"Cylinder {cyl_id} not found"}), 404

    return jsonify({
        "success": True,
        "active_cylinder_id": telemetry_instance.config["cylinder_id"],
        "overview": telemetry_instance.get_overview_payload()
    })

@app.route("/api/cylinders/<cyl_id>", methods=["GET"])
def get_cylinder_detail(cyl_id):
    """Detailed view for cylinder modal backed by SQLite."""
    cyl_id_clean = (cyl_id or "").strip().upper()
    db_c = Cylinder.query.filter(Cylinder.cylinder_id.ilike(cyl_id_clean)).first()
    if db_c:
        item = db_c.to_dict()
        if item["id"] == telemetry_instance.config["cylinder_id"]:
            live = telemetry_instance.get_overview_payload()
            item["pressure_bar"] = live["pressure"]["bar"]
            item["pressure_psi"] = live["pressure"]["psi"]
            item["flow_lpm"] = live["flow"]["value"]
            item["status"] = live["status"]["level"]
            item["ete"] = live["ete"]["display"]
        return jsonify({"success": True, "cylinder": item})

    for c in MOCK_CYLINDERS:
        if c["id"].upper() == cyl_id_clean:
            item = dict(c)
            if item["id"] == telemetry_instance.config["cylinder_id"]:
                live = telemetry_instance.get_overview_payload()
                item["pressure_bar"] = live["pressure"]["bar"]
                item["pressure_psi"] = live["pressure"]["psi"]
                item["flow_lpm"] = live["flow"]["value"]
                item["status"] = live["status"]["level"]
                item["ete"] = live["ete"]["display"]
            return jsonify({"success": True, "cylinder": item})
    return jsonify({"success": False, "error": "Cylinder not found"}), 404

@app.route("/api/cylinders/<cyl_id>/telemetry", methods=["GET"])
def get_cylinder_telemetry_history(cyl_id):
    """Retrieve historical telemetry readings from SQLite database for a cylinder."""
    cyl_id_clean = (cyl_id or "").strip().upper()
    db_cyl = Cylinder.query.filter(Cylinder.cylinder_id.ilike(cyl_id_clean)).first()
    if not db_cyl:
        return jsonify({"success": False, "error": f"Cylinder '{cyl_id}' not found"}), 404

    limit = request.args.get("limit", 100, type=int)
    if limit < 1 or limit > 5000:
        limit = 500

    total_in_db = Telemetry.query.filter_by(cylinder_db_id=db_cyl.id).count()
    records = Telemetry.query.filter_by(cylinder_db_id=db_cyl.id).order_by(Telemetry.timestamp.desc()).limit(limit).all()
    history = [r.to_dict() for r in reversed(records)]
    return jsonify({
        "success": True,
        "cylinder_id": db_cyl.cylinder_id,
        "total_records": total_in_db,
        "returned_records": len(history),
        "telemetry": history
    })

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    """Active and logged alerts backed by SQLite database."""
    try:
        db_alerts = Alert.query.order_by(Alert.created_at.desc()).all()
        alert_list = [a.to_dict() for a in db_alerts] if db_alerts else telemetry_instance.alerts
    except Exception:
        alert_list = telemetry_instance.alerts

    active_cnt = len([a for a in alert_list if not a.get("acknowledged", a.get("is_resolved", False))])
    return jsonify({
        "alerts": alert_list,
        "active_count": active_cnt
    })

@app.route("/api/alerts/acknowledge", methods=["POST"])
def acknowledge_alert():
    """Acknowledge an alert."""
    curr_user = get_current_user()
    if curr_user and curr_user.role == "VIEWER":
        return jsonify({
            "success": False,
            "error": "Permission denied: Viewers cannot acknowledge alerts. Admin privileges required."
        }), 403

    data = request.get_json() or {}
    alert_id = str(data.get("alert_id", "")).strip()

    # Update database alert if ID matches
    try:
        raw_num = int(alert_id.replace("ALT-", ""))
        db_alert = Alert.query.get(raw_num)
        if db_alert:
            db_alert.is_resolved = True
            db.session.commit()
    except Exception:
        db.session.rollback()

    for a in telemetry_instance.alerts:
        if a["id"] == alert_id:
            a["acknowledged"] = True
            return jsonify({"success": True, "alert_id": alert_id})
    return jsonify({"success": True, "alert_id": alert_id})

NOMINAL_REFILL_PRESSURES = {
    "CYL-ICU-101": 160.0,
    "CYL-ER-204": 180.0,
    "CYL-GW-302": 190.0,
    "CYL-REC-108": 165.0,
    "CYL-PED-044": 145.0,
    "CYL-TRANS-012": 105.0
}

@app.route("/api/simulation/scenario", methods=["POST"])
def set_scenario():
    """Set simulation scenario: NORMAL, LOW_PRESSURE, SENSOR_DISCONNECTED, RESET"""
    curr_user = get_current_user()
    if curr_user and curr_user.role == "VIEWER":
        return jsonify({
            "success": False,
            "error": "Permission denied: Viewers cannot trigger simulation scenarios. Admin privileges required."
        }), 403

    data = request.get_json(silent=True) or {}
    scenario = data.get("scenario", "RESET").upper()
    now = datetime.now()
    is_hw = bool(
        telemetry_instance.hardware_active
        and telemetry_instance.last_hardware_time
        and (now - telemetry_instance.last_hardware_time).total_seconds() <= 3.5
    )

    if scenario == "RESET":
        # Oxygen Refilling: refill active cylinder and entire hospital fleet back to full capacity
        for c in MOCK_CYLINDERS:
            refill_p = NOMINAL_REFILL_PRESSURES.get(c["id"], 160.0)
            c["pressure_bar"] = refill_p
            c["pressure_psi"] = round(refill_p * 14.5038, 0)
            c["flow_lpm"] = 2.0
            c["status"] = "NORMAL"
            c["ete"] = calculate_cylinder_ete(c.get("capacity_l", 660), refill_p, 2.0)
            c["last_updated"] = f"Refilled ({now.strftime('%H:%M:%S')})"

        # Sync refill to SQLite database
        try:
            for cyl_id_k, refill_val in NOMINAL_REFILL_PRESSURES.items():
                db_c = Cylinder.query.filter_by(cylinder_id=cyl_id_k).first()
                if db_c:
                    db_c.pressure_bar = refill_val
                    db_c.flow_rate_lpm = 2.0
                    db_c.status = "NORMAL"
                    db_c.last_updated = datetime.utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()

        cur_id = telemetry_instance.config["cylinder_id"]
        refill_p = NOMINAL_REFILL_PRESSURES.get(cur_id, 160.0)
        telemetry_instance.current_pressure_bar = refill_p
        telemetry_instance.current_flow_lpm = telemetry_instance.config.get("prescribed_flow_lpm", 2.0)
        telemetry_instance.simulation_scenario = "NORMAL"

        if not is_hw:
            # Without physical ESP32, keep simulation OFF and dashboard offline
            telemetry_instance.simulation_scenario = "NORMAL"
            telemetry_instance.config["simulation_mode"] = False
            telemetry_instance.is_sensor_connected = False
            telemetry_instance.hardware_active = False
            telemetry_instance.current_pressure_bar = 0.0
            telemetry_instance.current_flow_lpm = 0.0
            for a in telemetry_instance.alerts:
                a["acknowledged"] = True
            return jsonify({
                "success": True,
                "scenario": "NORMAL",
                "message": "Reset complete. No ESP32 connected — dashboard remains offline.",
                "state": telemetry_instance.get_overview_payload()
            })

        telemetry_instance.is_sensor_connected = True
        telemetry_instance.hardware_active = True
        telemetry_instance.simulation_scenario = "NORMAL"
        for a in telemetry_instance.alerts:
            a["acknowledged"] = True
        telemetry_instance.alerts.insert(0, {
            "id": f"ALT-REFILL-{int(time.time())}",
            "severity": "INFO",
            "title": "Oxygen Cylinder Refilled",
            "description": f"Cylinder {cur_id} refilled to {refill_p:.0f} bar ({refill_p * 14.5038:.0f} PSI). Telemetry nominal.",
            "timestamp": now.strftime("%H:%M:%S"),
            "acknowledged": True
        })

        telemetry_instance.switch_active_cylinder({
            "id": cur_id,
            "ward": telemetry_instance.config["ward"],
            "capacity_l": telemetry_instance.config["cylinder_capacity_litres"],
            "pressure_bar": refill_p,
            "flow_lpm": telemetry_instance.current_flow_lpm
        })

        return jsonify({
            "success": True,
            "scenario": "NORMAL",
            "message": f"Oxygen Refilled: Cylinder {cur_id} restored to {refill_p:.0f} bar ({refill_p * 14.5038:.0f} PSI).",
            "state": telemetry_instance.get_overview_payload()
        })

    telemetry_instance.set_scenario(scenario)
    return jsonify({
        "success": True,
        "scenario": telemetry_instance.simulation_scenario,
        "state": telemetry_instance.get_overview_payload()
    })

@app.route("/api/ai-insights", methods=["GET"])
def get_ai_insights():
    """Clinical AI operational recommendations for oxygen cylinder inventory (Groq + rule fallback)."""
    try:
        target_cyl_id = request.args.get("cylinder_id")
        if target_cyl_id:
            target_clean = target_cyl_id.strip().upper()
            if target_clean != (telemetry_instance.config.get("cylinder_id") or "").upper():
                db_target = Cylinder.query.filter(Cylinder.cylinder_id.ilike(target_clean)).first()
                if db_target:
                    telemetry_instance.switch_active_cylinder(db_target.to_dict())
                else:
                    for c in MOCK_CYLINDERS:
                        if c["id"].upper() == target_clean:
                            telemetry_instance.switch_active_cylinder(c)
                            break

        inventory_summary = {
            "total_cylinders": 0,
            "normal_count": 0,
            "warning_count": 0,
            "critical_count": 0,
            "critical_cylinders": [],
            "warning_cylinders": []
        }
        active_alerts = []

        try:
            db_cyls = Cylinder.query.all()
            if db_cyls:
                inventory_summary["total_cylinders"] = len(db_cyls)
                for c in db_cyls:
                    st = (c.status or "NORMAL").upper()
                    p_val = float(c.pressure_bar) if c.pressure_bar is not None else 0.0
                    if st == "CRITICAL" or p_val <= 20.0:
                        inventory_summary["critical_count"] += 1
                        inventory_summary["critical_cylinders"].append(f"{c.cylinder_id} ({c.ward or 'Ward'} - {p_val:.1f} bar)")
                    elif st in ("LOW_PRESSURE", "WARNING") or p_val <= 50.0:
                        inventory_summary["warning_count"] += 1
                        inventory_summary["warning_cylinders"].append(f"{c.cylinder_id} ({c.ward or 'Ward'} - {p_val:.1f} bar)")
                    else:
                        inventory_summary["normal_count"] += 1

            unresolved = Alert.query.filter_by(is_resolved=False).order_by(Alert.created_at.desc()).limit(5).all()
            active_alerts = [a.to_dict() for a in unresolved]
        except Exception:
            pass

        insights = generate_ai_insights(
            state=telemetry_instance,
            inventory_summary=inventory_summary,
            active_alerts=active_alerts
        )
        return jsonify(insights)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route("/api/settings", methods=["GET", "POST"])
def manage_settings():
    """Get or update system settings."""
    if request.method == "POST":
        curr_user = get_current_user()
        if curr_user and curr_user.role == "VIEWER":
            return jsonify({
                "success": False,
                "error": "Permission denied: Viewers cannot modify system settings. Admin privileges required."
            }), 403

        data = request.get_json() or {}
        if "warning_threshold_bar" in data:
            telemetry_instance.config["warning_threshold_bar"] = float(data["warning_threshold_bar"])
        if "critical_threshold_bar" in data:
            telemetry_instance.config["critical_threshold_bar"] = float(data["critical_threshold_bar"])
        if "prescribed_flow_lpm" in data:
            telemetry_instance.config["prescribed_flow_lpm"] = float(data["prescribed_flow_lpm"])
        if "cylinder_capacity_litres" in data:
            telemetry_instance.config["cylinder_capacity_litres"] = float(data["cylinder_capacity_litres"])
        if "pressure_unit" in data:
            telemetry_instance.config["pressure_unit"] = data["pressure_unit"].upper()
        return jsonify({"success": True, "config": telemetry_instance.config})
    return jsonify({"config": telemetry_instance.config})

@app.route("/api/export-csv", methods=["GET"])
def export_csv():
    """Export time-series telemetry to CSV for auditing backed by SQLite database."""
    cyl_id = request.args.get("cylinder_id", telemetry_instance.config["cylinder_id"])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Cylinder ID", "ISO Timestamp", "Clock Time", "Pressure (Bar)", "Pressure (PSI)", "Flow (L/min)", "Remaining %", "Status", "Note"])

    exported = False
    try:
        db_cyl = Cylinder.query.filter(Cylinder.cylinder_id.ilike(cyl_id)).first()
        if db_cyl:
            records = Telemetry.query.filter_by(cylinder_db_id=db_cyl.id).order_by(Telemetry.timestamp.asc()).all()
            if records:
                for r in records:
                    p_bar = round(float(r.pressure_bar), 1)
                    f_lpm = round(float(r.flow_rate_lpm), 2)
                    rem_pct = round((p_bar / 200.0) * 100, 1)
                    stat = "NORMAL"
                    if p_bar <= 20.0:
                        stat = "CRITICAL"
                    elif p_bar <= 50.0:
                        stat = "LOW_PRESSURE"
                    writer.writerow([
                        cyl_id,
                        r.timestamp.isoformat() if r.timestamp else "",
                        r.timestamp.strftime("%H:%M:%S") if r.timestamp else "",
                        p_bar,
                        round(p_bar * 14.5038, 0),
                        f_lpm,
                        rem_pct,
                        stat,
                        r.data_source or "SQLITE_AUDIT_LOG"
                    ])
                exported = True
    except Exception:
        pass

    if not exported:
        for pt in telemetry_instance.history:
            writer.writerow([
                cyl_id,
                pt.get("iso_time", ""),
                pt.get("timestamp", ""),
                pt.get("pressure_bar", ""),
                pt.get("pressure_psi", ""),
                pt.get("flow_lpm", ""),
                pt.get("remaining_pct", ""),
                pt.get("status", ""),
                "LIVE HARDWARE TELEMETRY" if telemetry_instance.hardware_active else "NOMINAL AUDIT LOG"
            ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=oxysense_{cyl_id.lower()}_report.csv"}
    )

def calculate_cylinder_ete(capacity_l, pressure_bar, flow_lpm):
    if pressure_bar <= 0:
        return "0h 00m (Exhausted)"
    if flow_lpm <= 0:
        return "Flow stopped"
    remaining_l = capacity_l * (pressure_bar / 200.0)
    minutes = remaining_l / flow_lpm
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}h {mins:02d}m"

def classify_cylinder_status(pressure_bar, is_connected=True):
    if not is_connected:
        return "SENSOR_DISCONNECTED"
    if pressure_bar <= 0.0:
        return "CRITICAL"
    if pressure_bar <= 20.0:
        return "CRITICAL"
    if pressure_bar <= 50.0:
        return "LOW_PRESSURE"
    return "NORMAL"

def process_telemetry_payload(data: dict) -> int:
    """Processes incoming ESP32 multi-cylinder telemetry (from HTTP or automatic USB serial thread)."""
    now_str = datetime.now().strftime("%H:%M:%S")

    cyl_list = data.get("cylinders")
    if not cyl_list:
        if "cylinder_id" in data:
            cyl_list = [data]
        elif "pressure_bar" in data:
            data["cylinder_id"] = telemetry_instance.config["cylinder_id"]
            cyl_list = [data]
        else:
            cyl_list = []

    updated_count = 0
    for cyl in cyl_list:
        cid = cyl.get("cylinder_id")
        raw_p = float(cyl.get("pressure_bar", 0.0))
        raw_f = float(cyl.get("flow_lpm", 2.0))
        batt = max(0, min(100, int(cyl.get("battery_pct", 90))))

        # Physical constraints & Auto-Recovery:
        # If legacy ESP32 code drifted negative (< 0), auto-recover cylinder to full refilled pressure
        if raw_p < 0.0:
            p_bar = NOMINAL_REFILL_PRESSURES.get(cid, 160.0)
            f_lpm = max(0.5, raw_f)
        elif raw_p == 0.0:
            # Gauge pressure reaches 0 -> STOP AT 0 (empty cylinder)
            p_bar = 0.0
            f_lpm = 0.0
        else:
            p_bar = raw_p
            f_lpm = max(0.0, raw_f)

        # Update matching cylinder in MOCK_CYLINDERS
        for c in MOCK_CYLINDERS:
            if c["id"] == cid:
                c["pressure_bar"] = round(p_bar, 1)
                c["pressure_psi"] = round(p_bar * 14.5038, 1)
                c["flow_lpm"] = round(f_lpm, 2)
                c["battery_pct"] = batt
                c["status"] = classify_cylinder_status(p_bar, True)
                c["ete"] = calculate_cylinder_ete(c.get("capacity_l", 660), p_bar, f_lpm)
                c["last_updated"] = f"ESP32 ({now_str})"
                updated_count += 1
                break

        # Persist to SQLite database (Cylinder state + separate historical Telemetry point)
        try:
            def _persist_to_sqlite():
                db_c = Cylinder.query.filter(Cylinder.cylinder_id.ilike(cid)).first()
                status_calc = classify_cylinder_status(p_bar, True)
                now_utc = datetime.utcnow()
                if not db_c:
                    db_c = Cylinder(
                        cylinder_id=cid,
                        pressure_bar=round(p_bar, 1),
                        flow_rate_lpm=round(f_lpm, 2),
                        battery_percentage=batt,
                        status=status_calc,
                        data_source="HARDWARE_ESP32",
                        is_simulated=False,
                        last_updated=now_utc
                    )
                    db.session.add(db_c)
                    db.session.flush()
                else:
                    db_c.pressure_bar = round(p_bar, 1)
                    db_c.flow_rate_lpm = round(f_lpm, 2)
                    db_c.battery_percentage = batt
                    db_c.status = status_calc
                    db_c.last_updated = now_utc

                # Historical telemetry record (persisted separately)
                t_record = Telemetry(
                    cylinder_db_id=db_c.id,
                    cylinder_id=db_c.cylinder_id,
                    pressure_bar=round(p_bar, 1),
                    flow_rate_lpm=round(f_lpm, 2),
                    battery_percentage=batt,
                    is_simulated=False,
                    data_source="HARDWARE_ESP32",
                    timestamp=now_utc
                )
                db.session.add(t_record)

                # Alert trigger if critical
                if status_calc == "CRITICAL":
                    recent_unresolved = Alert.query.filter_by(cylinder_id=cid, is_resolved=False).first()
                    if not recent_unresolved:
                        db.session.add(Alert(
                            cylinder_db_id=db_c.id,
                            cylinder_id=cid,
                            alert_type="CRITICAL",
                            message=f"Critical pressure reserve ({p_bar:.1f} bar) on {cid}. Replacement recommended.",
                            created_at=now_utc,
                            is_resolved=False
                        ))
                db.session.commit()
                # Automatically prune telemetry older than 24 hours (throttled to at most once per 5 min)
                prune_telemetry_older_than(hours=24)

            if has_app_context():
                _persist_to_sqlite()
            else:
                with app.app_context():
                    _persist_to_sqlite()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

        # If primary cylinder, mirror to telemetry_instance
        if cid == telemetry_instance.config["cylinder_id"]:
            telemetry_instance.current_pressure_bar = p_bar
            telemetry_instance.current_flow_lpm = f_lpm
            telemetry_instance.is_sensor_connected = True
            telemetry_instance.hardware_active = True
            telemetry_instance.last_hardware_time = datetime.now()
            telemetry_instance.config["simulation_mode"] = False
            telemetry_instance.last_update = datetime.now()

    return updated_count

@app.route("/api/telemetry", methods=["POST"])
@app.route("/api/telemetry/hardware-ingest", methods=["POST"])
def ingest_hardware_telemetry():
    """Hardware Ingestion Endpoint for ESP32 / HTTP."""
    if not app.config.get("TESTING") and not verify_esp32_key(request):
        return jsonify({"success": False, "error": "Unauthorized: Invalid or missing ESP32 device key."}), 401

    data = request.get_json() or {}
    updated_count = process_telemetry_payload(data)
    return jsonify({
        "success": True,
        "message": f"Processed {updated_count} cylinders from ESP32",
        "updated_cylinders": updated_count,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

@app.route("/api/telemetry/retention", methods=["GET", "POST"])
def manage_retention():
    """Manual trigger or query to enforce 24-hour telemetry retention policy."""
    if request.method == "POST":
        curr_user = get_current_user()
        if curr_user and curr_user.role == "VIEWER":
            return jsonify({"success": False, "error": "Permission denied: Admin role required."}), 403

    hours = request.args.get("hours", 24, type=int)
    force = request.args.get("force", "true").lower() in ("true", "1", "yes")
    deleted = prune_telemetry_older_than(hours=hours, force=force)
    total_remaining = Telemetry.query.count()
    return jsonify({
        "success": True,
        "retention_hours": hours,
        "deleted_records": deleted,
        "total_remaining_records": total_remaining,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

hardware_bridge_state = {
    "detected_port": None,
    "status": "disconnected",  # "connected", "busy", "disconnected"
    "message": "No ESP32 connected"
}

def auto_hardware_serial_worker():
    """
    Automatic Serial Bridge Worker:
    Continuously monitors physical USB UART (CP210x, CH340, FTDI) and configured ports.
    Auto-connects as soon as ESP32 is plugged in; auto-disconnects when unplugged.
    """
    if not serial:
        return

    last_busy_alert_time = 0.0

    while True:
        try:
            target_port = None
            is_physical_usb = False
            ports = list(serial.tools.list_ports.comports())

            # 1. Prioritize physical USB cable if connected (CP210x, CH340, FTDI, etc.)
            for p in ports:
                desc = (p.description or "").lower()
                hwid = (getattr(p, "hwid", "") or "").lower()
                if any(k in desc or k in hwid for k in ("cp210", "ch340", "ftdi", "usb serial", "usb-serial", "prolific")):
                    target_port = p.device
                    is_physical_usb = True
                    break

            # 2. Check explicit env override (e.g. ESP32_PORT=COM10 in .env) if no USB detected
            if not target_port:
                env_port = os.environ.get("ESP32_PORT", "").strip().upper()
                if env_port:
                    for p in ports:
                        if p.device.upper() == env_port:
                            target_port = p.device
                            is_physical_usb = False
                            break

            # 3. Check Bluetooth ESP32 outgoing port (COM10 default or standard BT link)
            if not target_port:
                for p in ports:
                    if p.device.upper() == 'COM10':
                        target_port = 'COM10'
                        is_physical_usb = False
                        break

            if not target_port:
                hardware_bridge_state["detected_port"] = None
                hardware_bridge_state["status"] = "disconnected"
                hardware_bridge_state["message"] = "No physical or Bluetooth ESP32 detected"
                time.sleep(2.0)
                continue

            hardware_bridge_state["detected_port"] = target_port

            # Attempt to open serial port
            try:
                ser = serial.Serial(target_port, 115200, timeout=2)
            except (serial.SerialException, PermissionError, OSError) as port_err:
                err_str = str(port_err).lower()
                if "access is denied" in err_str or "permission" in err_str or isinstance(port_err, PermissionError):
                    hardware_bridge_state["status"] = "busy"
                    hardware_bridge_state["message"] = f"{target_port} is busy. Close Arduino Serial Monitor."
                    now_ts = time.time()
                    if now_ts - last_busy_alert_time > 5.0:
                        print(f"[OxySense Auto-Bridge] {target_port} is busy (close Arduino Serial Monitor). Retrying...", flush=True)
                        last_busy_alert_time = now_ts
                else:
                    hardware_bridge_state["status"] = "disconnected"
                    hardware_bridge_state["message"] = f"{target_port} disconnected or unreachable."
                time.sleep(2.0)
                continue

            with ser:
                hardware_bridge_state["status"] = "connected"
                hardware_bridge_state["message"] = f"Connected on {target_port}"
                print(f"[OxySense Auto-Bridge] Connected to ESP32 on {target_port}!")
                consecutive_timeouts = 0
                while True:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        consecutive_timeouts += 1
                        if consecutive_timeouts >= 3:
                            print(f"[OxySense Auto-Bridge] No data received on {target_port} for 6s. Reconnecting...")
                            break
                        continue
                    consecutive_timeouts = 0
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            payload = json.loads(line)
                            process_telemetry_payload(payload)
                        except json.JSONDecodeError:
                            pass
        except (serial.SerialException, OSError):
            hardware_bridge_state["status"] = "disconnected"
            hardware_bridge_state["message"] = "ESP32 disconnected."
            time.sleep(1.5)
        except Exception:
            hardware_bridge_state["status"] = "disconnected"
            time.sleep(1.5)

# Start background auto-hardware serial worker (disabled in serverless environments like Vercel)
if not os.environ.get("VERCEL"):
    _serial_thread = threading.Thread(target=auto_hardware_serial_worker, daemon=True)
    _serial_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
