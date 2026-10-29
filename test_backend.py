"""
test_backend.py — Unit tests for OxySense Backend and Simulation Engine.
"""

import pytest
from backend.simulation_engine import TelemetryState, generate_ai_insights
from backend.app import app

@pytest.fixture
def test_state():
    return TelemetryState()

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_ete_calculation(test_state):
    test_state.is_sensor_connected = True
    test_state.current_pressure_bar = 100.0
    test_state.current_flow_lpm = 2.0
    ete = test_state.calculate_ete()
    assert ete["valid"] is True
    assert ete["hours"] >= 0
    assert "⚠️" in ete["disclaimer"]

def test_ete_disconnected_sensor(test_state):
    test_state.is_sensor_connected = False
    ete = test_state.calculate_ete()
    assert ete["valid"] is False
    assert ete["display"] == "Estimate unavailable"

def test_status_classification(test_state):
    test_state.is_sensor_connected = True
    test_state.current_pressure_bar = 160.0
    assert test_state.classify_status()["level"] == "NORMAL"

    test_state.current_pressure_bar = 40.0
    assert test_state.classify_status()["level"] == "LOW_PRESSURE"

    test_state.current_pressure_bar = 15.0
    assert test_state.classify_status()["level"] == "CRITICAL"

    test_state.is_sensor_connected = False
    assert test_state.classify_status()["level"] == "SENSOR_DISCONNECTED"

def test_simulation_scenarios(test_state):
    test_state.set_scenario("LOW_PRESSURE")
    assert test_state.current_pressure_bar <= 50.0
    assert test_state.simulation_scenario == "LOW_PRESSURE"

    test_state.set_scenario("SENSOR_DISCONNECTED")
    assert test_state.is_sensor_connected is False

    test_state.set_scenario("RESET")
    assert test_state.current_pressure_bar >= 150.0
    assert test_state.is_sensor_connected is True

def test_ai_insights_rule_based(test_state):
    test_state.is_sensor_connected = True
    test_state.current_pressure_bar = 150.0
    test_state.current_flow_lpm = 2.0
    insights = generate_ai_insights(test_state)
    assert "summary" in insights
    assert len(insights["operational_suggestions"]) > 0
    assert "⚠️" in insights["safety_disclaimer"]

def test_api_overview(client):
    res = client.get("/api/overview")
    assert res.status_code == 200
    data = res.get_json()
    assert "pressure" in data
    assert "flow" in data
    assert "ete" in data
    assert "status" in data

def test_api_cylinders(client):
    res = client.get("/api/cylinders")
    assert res.status_code == 200
    data = res.get_json()
    assert "cylinders" in data
    assert len(data["cylinders"]) >= 5

def test_api_alerts(client):
    res = client.get("/api/alerts")
    assert res.status_code == 200
    data = res.get_json()
    assert "alerts" in data

def test_api_simulation_trigger(client):
    res = client.post("/api/simulation/scenario", json={"scenario": "LOW_PRESSURE"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["scenario"] == "LOW_PRESSURE"

def test_api_export_csv(client):
    res = client.get("/api/export-csv")
    assert res.status_code == 200
    assert "text/csv" in res.content_type
    assert b"ISO Timestamp" in res.data

def test_api_telemetry_hardware_ingest(client):
    # Test batch ingestion of 6 cylinders from ESP32
    payload = {
        "cylinders": [
            {"cylinder_id": "CYL-ICU-101", "pressure_bar": 152.0, "flow_lpm": 2.0},
            {"cylinder_id": "CYL-ER-204", "pressure_bar": 38.0, "flow_lpm": 4.5},
            {"cylinder_id": "CYL-GW-302", "pressure_bar": 188.0, "flow_lpm": 1.5},
            {"cylinder_id": "CYL-REC-108", "pressure_bar": 17.0, "flow_lpm": 3.0},
            {"cylinder_id": "CYL-PED-044", "pressure_bar": 142.0, "flow_lpm": 1.0},
            {"cylinder_id": "CYL-TRANS-012", "pressure_bar": 96.0, "flow_lpm": 2.5}
        ]
    }
    res = client.post("/api/telemetry", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["updated_cylinders"] == 6

    # Verify cylinders endpoint reflects updated ESP32 data
    res_cyl = client.get("/api/cylinders")
    assert res_cyl.status_code == 200
    cyls = {c["id"]: c for c in res_cyl.get_json()["cylinders"]}
    assert cyls["CYL-ICU-101"]["pressure_bar"] == 152.0
    assert cyls["CYL-REC-108"]["status"] == "CRITICAL"

def test_auth_login_success(client):
    res = client.post("/api/auth/login", json={"email": "doctor@oxysense.med", "password": "doctor123"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["user"]["name"] == "Dr. Sharma"

def test_auth_login_failure(client):
    res = client.post("/api/auth/login", json={"email": "wrong@oxysense.med", "password": "wrong"})
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert "Invalid email or password" in data["error"]

def test_auth_session(client):
    # Unauthenticated session check
    res = client.get("/api/auth/session")
    assert res.status_code == 200
    assert res.get_json()["authenticated"] is False

    # Authenticate and check session
    client.post("/api/auth/login", json={"email": "nurse@oxysense.med", "password": "nurse123"})
    res2 = client.get("/api/auth/session")
    assert res2.status_code == 200
    assert res2.get_json()["authenticated"] is True
    assert res2.get_json()["user"]["role"] == "Senior Respiratory Nurse"

def test_auth_logout(client):
    client.post("/api/auth/login", json={"email": "admin@oxysense.med", "password": "admin123"})
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # Check session is cleared
    res2 = client.get("/api/auth/session")
    assert res2.get_json()["authenticated"] is False

def test_active_cylinder_switch(client):
    # Get active cylinder (default)
    res_get = client.get("/api/cylinders/active")
    assert res_get.status_code == 200
    assert "active_cylinder_id" in res_get.get_json()

    # Switch active cylinder to CYL-ER-204
    res_post = client.post("/api/cylinders/active", json={"cylinder_id": "CYL-ER-204"})
    assert res_post.status_code == 200
    data = res_post.get_json()
    assert data["success"] is True
    assert data["active_cylinder_id"] == "CYL-ER-204"

    # Overview payload should now reflect CYL-ER-204
    res_overview = client.get("/api/overview")
    assert res_overview.status_code == 200
    ov = res_overview.get_json()
    assert ov["device"]["id"] == "CYL-ER-204"

    # Switch back to CYL-ICU-101
    client.post("/api/cylinders/active", json={"cylinder_id": "CYL-ICU-101"})


