"""
backend/app.py — Flask REST API Server for OxySense Web Dashboard.
"""

import os
import io
import csv
from flask import Flask, jsonify, request, render_template, Response, send_file, session
from backend.simulation_engine import telemetry_instance, generate_ai_insights
from backend.mock_data import MOCK_CYLINDERS

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "..", "static")
)
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
    return jsonify(telemetry_instance.get_overview_payload())

@app.route("/api/live-stream", methods=["GET"])
def get_live_stream():
    """Tick forward simulation and return updated readings and recent history."""
    telemetry_instance.tick_simulation()
    payload = telemetry_instance.get_overview_payload()
    payload["history"] = telemetry_instance.history
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

@app.route("/api/telemetry", methods=["POST"])
def ingest_hardware_telemetry():
    """
    Hardware Ingestion Endpoint for ESP32 / MQTT Bridge.
    Allows real ESP32 microcontrollers to post JSON telemetry:
    {
      "cylinder_id": "CYL-ICU-101",
      "pressure_bar": 142.5,
      "flow_lpm": 2.1,
      "battery_pct": 89
    }
    """
    data = request.get_json() or {}
    if "pressure_bar" in data:
        telemetry_instance.current_pressure_bar = float(data["pressure_bar"])
    if "flow_lpm" in data:
        telemetry_instance.current_flow_lpm = float(data["flow_lpm"])
    telemetry_instance.is_sensor_connected = True
    telemetry_instance.config["simulation_mode"] = False
    telemetry_instance.last_update = datetime.now()
    return jsonify({"success": True, "message": "Telemetry accepted from hardware node"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
