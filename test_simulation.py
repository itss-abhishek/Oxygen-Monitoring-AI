"""
test_simulation.py — Unit tests for ETE calculation and alert thresholds.

Run with:  python -m pytest test_simulation.py -v
"""

import math
import pytest
from simulation import (
    SimulatedReading,
    calculate_ete,
    classify_alert,
    generate_recommendations,
    generate_synthetic_history,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _reading(pressure=150, flow=2.0, capacity=660, max_p=200):
    return SimulatedReading(
        pressure_bar=pressure,
        flow_rate_lpm=flow,
        cylinder_capacity_litres=capacity,
        max_pressure_bar=max_p,
    )


# ── ETE tests ───────────────────────────────────────────────────────────────

class TestETE:
    def test_basic_calculation(self):
        """remaining = 660 * (150/200) = 495 L → 495/2 = 247.5 min"""
        ete = calculate_ete(_reading())
        assert math.isclose(ete.minutes, 247.5, rel_tol=1e-6)

    def test_zero_flow_returns_inf(self):
        ete = calculate_ete(_reading(flow=0))
        assert ete.minutes == float("inf")

    def test_negative_flow_returns_inf(self):
        ete = calculate_ete(_reading(flow=-1))
        assert ete.minutes == float("inf")

    def test_zero_pressure(self):
        ete = calculate_ete(_reading(pressure=0))
        assert ete.minutes == 0.0

    def test_negative_pressure_clamped(self):
        ete = calculate_ete(_reading(pressure=-10))
        assert ete.minutes == 0.0

    def test_zero_max_pressure(self):
        ete = calculate_ete(_reading(max_p=0))
        assert ete.minutes == 0.0

    def test_full_cylinder(self):
        """At full pressure, remaining = capacity → ETE = capacity / flow."""
        ete = calculate_ete(_reading(pressure=200, max_p=200))
        assert math.isclose(ete.minutes, 660 / 2.0)

    def test_hours_consistent(self):
        ete = calculate_ete(_reading())
        assert math.isclose(ete.hours, ete.minutes / 60.0)

    def test_formula_description_present(self):
        ete = calculate_ete(_reading())
        assert "remaining_litres" in ete.formula_description

    def test_disclaimer_present(self):
        ete = calculate_ete(_reading())
        assert "NOT" in ete.clinical_disclaimer


# ── Alert tests ─────────────────────────────────────────────────────────────

class TestAlerts:
    def test_normal(self):
        assert classify_alert(100).level == "Normal"

    def test_warning_boundary(self):
        assert classify_alert(50).level == "Warning"

    def test_warning_just_below(self):
        assert classify_alert(49).level == "Warning"

    def test_critical_boundary(self):
        assert classify_alert(20).level == "Critical"

    def test_critical_below(self):
        assert classify_alert(5).level == "Critical"

    def test_zero_pressure(self):
        assert classify_alert(0).level == "Critical"

    def test_negative_pressure(self):
        assert classify_alert(-10).level == "Critical"

    def test_custom_thresholds(self):
        assert classify_alert(80, warning_threshold=90, critical_threshold=30).level == "Warning"
        assert classify_alert(25, warning_threshold=90, critical_threshold=30).level == "Critical"
        assert classify_alert(95, warning_threshold=90, critical_threshold=30).level == "Normal"


# ── Recommendation tests ───────────────────────────────────────────────────

class TestRecommendations:
    def test_normal_gives_all_clear(self):
        r = _reading(pressure=150, flow=2.0)
        ete = calculate_ete(r)
        alert = classify_alert(r.pressure_bar)
        recs = generate_recommendations(r, ete, alert, prescribed_flow=2.0)
        assert any("within" in rec.text.lower() for rec in recs)

    def test_critical_pressure_triggers_alert(self):
        r = _reading(pressure=10)
        ete = calculate_ete(r)
        alert = classify_alert(r.pressure_bar)
        recs = generate_recommendations(r, ete, alert)
        assert any("critically" in rec.text.lower() for rec in recs)

    def test_flow_deviation_triggers_alert(self):
        r = _reading(flow=5.0)
        ete = calculate_ete(r)
        alert = classify_alert(r.pressure_bar)
        recs = generate_recommendations(r, ete, alert, prescribed_flow=2.0)
        assert any("differs" in rec.text.lower() for rec in recs)


# ── Synthetic history tests ─────────────────────────────────────────────────

class TestSyntheticHistory:
    def test_length(self):
        h = generate_synthetic_history(points=30)
        assert len(h) == 30

    def test_no_negative_pressures(self):
        h = generate_synthetic_history(start_pressure=5, points=100)
        assert all(p >= 0 for _, p in h)

    def test_reproducible(self):
        h1 = generate_synthetic_history()
        h2 = generate_synthetic_history()
        assert h1 == h2  # same seed → same output
