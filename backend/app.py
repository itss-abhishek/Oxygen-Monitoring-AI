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
from flask import Flask, jsonify, request, render_template, Response, send_file, session
from backend.simulation_engine import telemetry_instance, generate_ai_insights
from backend.mock_data import MOCK_CYLINDERS

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
    """Returns telemetry time-series for Chart.js."""
    range_param = request.args.get("range", "15m")
    # Return historical points
    pts = telemetry_instance.history
    if range_param == "15m":
        pts = pts[-15:]
    elif range_param == "1h":
        pts = pts[-30:]
    return jsonify({
        "range": range_param,
        "points": pts
    })

@app.route("/api/cylinders", methods=["GET"])
def list_cylinders():
    """Searchable & filterable hospital cylinder fleet."""
    search = request.args.get("search", "").lower().strip()
    status_filter = request.args.get("status", "ALL").upper().strip()

    # Mirror live primary cylinder into the fleet list
    primary_live = telemetry_instance.get_overview_payload()
    updated_fleet = []
    
    for c in MOCK_CYLINDERS:
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
    """Detailed view for cylinder modal."""
    for c in MOCK_CYLINDERS:
        if c["id"].upper() == cyl_id.upper():
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

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    """Active and logged alerts."""
    return jsonify({
        "alerts": telemetry_instance.alerts,
        "active_count": len([a for a in telemetry_instance.alerts if not a["acknowledged"]])
    })

@app.route("/api/alerts/acknowledge", methods=["POST"])
def acknowledge_alert():
    """Acknowledge an alert."""
    data = request.get_json() or {}
    alert_id = data.get("alert_id")
    for a in telemetry_instance.alerts:
        if a["id"] == alert_id:
            a["acknowledged"] = True
            return jsonify({"success": True, "alert_id": alert_id})
    return jsonify({"success": False, "error": "Alert ID not found"}), 404

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
        if not is_hw:
            # Without physical ESP32, keep simulation OFF and dashboard stopped
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
        else:
            telemetry_instance.config["simulation_mode"] = False
            telemetry_instance.simulation_scenario = "NORMAL"
            for a in telemetry_instance.alerts:
                a["acknowledged"] = True
            return jsonify({
                "success": True,
                "scenario": "NORMAL",
                "message": "Reset complete on active ESP32 telemetry.",
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
    """Export time-series telemetry to CSV for auditing."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ISO Timestamp", "Clock Time", "Pressure (Bar)", "Pressure (PSI)", "Flow (L/min)", "Remaining %", "ETE (Min)", "Status", "Note"])
    for pt in telemetry_instance.history:
        writer.writerow([
            pt.get("iso_time", ""),
            pt.get("timestamp", ""),
            pt.get("pressure_bar", ""),
            pt.get("pressure_psi", ""),
            pt.get("flow_lpm", ""),
            pt.get("remaining_pct", ""),
            pt.get("ete_minutes", ""),
            pt.get("status", ""),
            "SYNTHETIC DEMO DATA"
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=oxysense_telemetry_report.csv"}
    )

def calculate_cylinder_ete(capacity_l, pressure_bar, flow_lpm):
    if flow_lpm <= 0 or pressure_bar <= 0:
        return "Unavailable"
    remaining_l = capacity_l * (pressure_bar / 200.0)
    minutes = remaining_l / flow_lpm
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}h {mins:02d}m"

def classify_cylinder_status(pressure_bar, is_connected=True):
    if not is_connected or pressure_bar <= 0:
        return "SENSOR_DISCONNECTED"
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
        p_bar = float(cyl.get("pressure_bar", 0.0))
        f_lpm = float(cyl.get("flow_lpm", 2.0))
        batt = int(cyl.get("battery_pct", 90))

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
            for p in serial.tools.list_ports.comports():
                dev = p.device
                desc = (p.description or "").lower()
                if dev in ['COM10', 'COM9']:
                    target_port = dev
                    break
                if "cp210" in desc or "ch340" in desc or "uart" in desc:
                    target_port = dev
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
                while True:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
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
