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
    # 660 L capacity, 200 bar max. At 100 bar, remaining = 330 L. At 2 L/min -> 165 minutes.
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
