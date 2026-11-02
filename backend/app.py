"""
backend/app.py — Flask REST API Server for OxySense Web Dashboard.
"""

import os
import io
import csv
import json
import time
import threading
from datetime import datetime
from flask import Flask, jsonify, request, render_template, Response, send_file, session, has_app_context
from backend.simulation_engine import telemetry_instance, generate_ai_insights
from backend.mock_data import MOCK_CYLINDERS
from backend.models import db, Cylinder, Telemetry, Alert
from backend.database import init_db, prune_telemetry_older_than

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

# Initialize SQLite database (oxygen_monitoring.db) and demonstration fleet models
init_db(app)

# Demo user credentials for presentation
DEMO_USERS = {
    "doctor@oxysense.med": {
        "password": "doctor123",
        "name": "Dr. Sharma",
        "role": "ICU Ward Incharge",
        "department": "Critical Care Unit"
    },
    "admin@oxysense.med": {
        "password": "admin123",
        "name": "Administrator",
        "role": "Hospital Biomedical Admin",
        "department": "Biomedical Engineering"
    },
    "nurse@oxysense.med": {
        "password": "nurse123",
        "name": "Nurse Priya",
        "role": "Senior Respiratory Nurse",
        "department": "General Ward 2"
    }
}

# ---------------------------------------------------------------------------
# Page Route
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

# ---------------------------------------------------------------------------
# Authentication Endpoints (Demo Mode)
# ---------------------------------------------------------------------------

@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Authenticate against demo accounts."""
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    # Also allow logging in with username before @
    matched_user = None
    for user_email, user_info in DEMO_USERS.items():
        if email == user_email or email == user_email.split("@")[0]:
            if user_info["password"] == password:
                matched_user = user_info
                matched_user["email"] = user_email
                break

    if matched_user:
        session["user"] = matched_user
        return jsonify({
            "success": True,
            "message": "Authentication successful",
            "user": matched_user
        })

    return jsonify({
        "success": False,
        "error": "Invalid email or password. Use demo credentials."
    }), 401

@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Clear session on logout."""
    session.pop("user", None)
    return jsonify({"success": True, "message": "Logged out successfully"})

@app.route("/api/auth/session", methods=["GET"])
def auth_session():
    """Check current session."""
    user = session.get("user")
    if user:
        return jsonify({"authenticated": True, "user": user})
    return jsonify({"authenticated": False, "user": None})

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
    data = request.get_json() or {}
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

        if is_hw:
            telemetry_instance.is_sensor_connected = True
            telemetry_instance.hardware_active = True
        else:
            telemetry_instance.is_sensor_connected = True
            telemetry_instance.config["simulation_mode"] = True

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
    """Clinical AI operational insights (Groq + rule fallback)."""
    insights = generate_ai_insights(telemetry_instance)
    return jsonify(insights)

@app.route("/api/settings", methods=["GET", "POST"])
def manage_settings():
    """Get or update system settings."""
    if request.method == "POST":
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
def ingest_hardware_telemetry():
    """Hardware Ingestion Endpoint for ESP32 / HTTP."""
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
    Continuously monitors USB (CP210x, CH340, FTDI) and Bluetooth (COM10, COM9) ports.
    Auto-connects as soon as ESP32 is plugged in; auto-disconnects when unplugged.
    """
    if not serial:
        return

    last_busy_alert_time = 0.0

    while True:
        try:
            target_port = None
            ports = list(serial.tools.list_ports.comports())
            # 1. Prioritize physical USB cable if connected
            for p in ports:
                desc = (p.description or "").lower()
                if "cp210" in desc or "ch340" in desc or "uart" in desc:
                    target_port = p.device
                    break
            # 2. If USB not present, connect via Bluetooth Outgoing port (COM10)
            if not target_port:
                for p in ports:
                    if p.device == 'COM10':
                        target_port = 'COM10'
                        break

            if not target_port:
                hardware_bridge_state["detected_port"] = None
                hardware_bridge_state["status"] = "disconnected"
                hardware_bridge_state["message"] = "No ESP32 detected on USB/Bluetooth"
                time.sleep(1.5)
                continue

            hardware_bridge_state["detected_port"] = target_port

            # Attempt to open serial port
            try:
                ser = serial.Serial(target_port, 115200, timeout=2)
            except (serial.SerialException, PermissionError, OSError) as port_err:
                hardware_bridge_state["status"] = "busy"
                hardware_bridge_state["message"] = f"{target_port} is busy. Close Arduino Serial Monitor."
                now_ts = time.time()
                if now_ts - last_busy_alert_time > 5.0:
                    print(f"[OxySense Auto-Bridge] {target_port} is busy (close Arduino Serial Monitor). Retrying...")
                    last_busy_alert_time = now_ts
                time.sleep(1.5)
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

# Start background auto-hardware serial worker
_serial_thread = threading.Thread(target=auto_hardware_serial_worker, daemon=True)
_serial_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
