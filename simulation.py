"""
simulation.py — Core logic for the Personalized Healthcare Recommendation System.

All data in this module is SYNTHETIC / SIMULATED.
No physical sensors, ESP32 hardware, or cloud services are connected.
ETE calculations are simplified demonstrations and must NOT be used for clinical decisions.
"""

from dataclasses import dataclass
from typing import List, Tuple
import random
import math

# ---------------------------------------------------------------------------
# Configuration — demonstration thresholds (adjustable in the dashboard)
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS = {
    "warning_pressure_bar": 50,   # bar — below this → Warning
    "critical_pressure_bar": 20,  # bar — below this → Critical
    "prescribed_flow_lpm": 2.0,   # L/min — illustrative prescribed setting
}

CYLINDER_PRESETS = {
    "Type D (≈415 L)": 415,
    "Type E (≈660 L)": 660,
    "Type M (≈3450 L)": 3450,
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SimulatedReading:
    """A single simulated sensor reading."""
    pressure_bar: float
    flow_rate_lpm: float
    cylinder_capacity_litres: float
    max_pressure_bar: float  # full-cylinder reference pressure


@dataclass
class AlertStatus:
    level: str        # "Normal", "Warning", "Critical"
    color: str        # CSS-safe colour
    emoji: str


@dataclass
class ETEResult:
    minutes: float
    hours: float
    formula_description: str
    assumptions: List[str]
    clinical_disclaimer: str


@dataclass
class Recommendation:
    icon: str
    text: str
    basis: str  # why this recommendation was generated


# ---------------------------------------------------------------------------
# ETE calculation
# ---------------------------------------------------------------------------

def calculate_ete(reading: SimulatedReading) -> ETEResult:
    """
    Simplified Estimated Time to Exhaustion (ETE).

    Formula
    -------
    remaining_litres = cylinder_capacity × (current_pressure / max_pressure)
    ETE_minutes      = remaining_litres / flow_rate

    This is a LINEAR approximation.  Real gas behaviour (compressibility,
    temperature, regulator characteristics) makes this unsuitable for
    clinical use.

    Parameters
    ----------
    reading : SimulatedReading

    Returns
    -------
    ETEResult
    """
    if reading.flow_rate_lpm <= 0:
        return ETEResult(
            minutes=float("inf"),
            hours=float("inf"),
            formula_description="Flow rate is zero; ETE is undefined (infinite).",
            assumptions=[],
            clinical_disclaimer="",
        )

    if reading.max_pressure_bar <= 0:
        return ETEResult(
            minutes=0.0,
            hours=0.0,
            formula_description="Max pressure is zero; cannot calculate ETE.",
            assumptions=[],
            clinical_disclaimer="",
        )

    remaining_litres = reading.cylinder_capacity_litres * (
        reading.pressure_bar / reading.max_pressure_bar
    )
    remaining_litres = max(remaining_litres, 0.0)

    ete_minutes = remaining_litres / reading.flow_rate_lpm

    formula_desc = (
        f"remaining_litres = {reading.cylinder_capacity_litres:.0f} L "
        f"× ({reading.pressure_bar:.1f} bar / {reading.max_pressure_bar:.1f} bar) "
        f"= {remaining_litres:.1f} L\n"
        f"ETE = {remaining_litres:.1f} L ÷ {reading.flow_rate_lpm:.1f} L/min "
        f"= {ete_minutes:.1f} min"
    )

    assumptions = [
        "Ideal gas behaviour (no compressibility correction).",
        "Constant flow rate over the remaining duration.",
        "No ambient temperature or altitude correction.",
        "Cylinder capacity label is taken at face value.",
        "This is a DEMONSTRATION formula only.",
    ]

    disclaimer = (
        "⚠️ This ETE is a simplified illustration for academic demonstration. "
        "It must NOT be used for patient care. All clinical oxygen management "
        "decisions must be made by qualified healthcare professionals."
    )

    return ETEResult(
        minutes=ete_minutes,
        hours=ete_minutes / 60.0,
        formula_description=formula_desc,
        assumptions=assumptions,
        clinical_disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Alert classification
# ---------------------------------------------------------------------------

def classify_alert(
    pressure_bar: float,
    warning_threshold: float = DEFAULT_THRESHOLDS["warning_pressure_bar"],
    critical_threshold: float = DEFAULT_THRESHOLDS["critical_pressure_bar"],
) -> AlertStatus:
    """Return alert level based on configurable pressure thresholds."""
    if pressure_bar < 0:
        pressure_bar = 0.0

    if pressure_bar <= critical_threshold:
        return AlertStatus(level="Critical", color="#e74c3c", emoji="🔴")
    elif pressure_bar <= warning_threshold:
        return AlertStatus(level="Warning", color="#f39c12", emoji="🟡")
    else:
        return AlertStatus(level="Normal", color="#2ecc71", emoji="🟢")


# ---------------------------------------------------------------------------
# Rule-based recommendations
# ---------------------------------------------------------------------------

def generate_recommendations(
    reading: SimulatedReading,
    ete: ETEResult,
    alert: AlertStatus,
    prescribed_flow: float = DEFAULT_THRESHOLDS["prescribed_flow_lpm"],
    warning_threshold: float = DEFAULT_THRESHOLDS["warning_pressure_bar"],
    critical_threshold: float = DEFAULT_THRESHOLDS["critical_pressure_bar"],
) -> List[Recommendation]:
    """
    Transparent, rule-based recommendations.

    These do NOT constitute medical advice.  They are demonstration alerts
    that would, in a real system, notify qualified clinical staff.
    """
    recs: List[Recommendation] = []

    # --- pressure-based rules ---
    if alert.level == "Critical":
        recs.append(Recommendation(
            icon="🚨",
            text=(
                "Simulated pressure is critically low. "
                "In a real deployment, this alert would notify clinical staff "
                "to arrange a cylinder replacement immediately."
            ),
            basis=f"Pressure ({reading.pressure_bar:.1f} bar) ≤ critical threshold ({critical_threshold} bar).",
        ))
    elif alert.level == "Warning":
        recs.append(Recommendation(
            icon="⚠️",
            text=(
                "Simulated pressure is below the warning threshold. "
                "A real system would flag this for the care team to schedule "
                "a cylinder change."
            ),
            basis=f"Pressure ({reading.pressure_bar:.1f} bar) ≤ warning threshold ({warning_threshold} bar).",
        ))

    # --- flow deviation rule ---
    if prescribed_flow > 0 and abs(reading.flow_rate_lpm - prescribed_flow) > 0.5:
        direction = "above" if reading.flow_rate_lpm > prescribed_flow else "below"
        recs.append(Recommendation(
            icon="📋",
            text=(
                f"Simulated flow rate ({reading.flow_rate_lpm:.1f} L/min) differs from "
                f"the illustrative prescribed setting ({prescribed_flow:.1f} L/min). "
                "In a real system, qualified healthcare staff would review and "
                "adjust as clinically appropriate."
            ),
            basis=f"Flow is {direction} the prescribed setting by >{0.5} L/min.",
        ))

    # --- ETE rule ---
    if ete.minutes != float("inf") and ete.minutes < 30:
        recs.append(Recommendation(
            icon="⏱️",
            text=(
                f"Estimated time to exhaustion is {ete.minutes:.0f} minutes. "
                "A real system would alert the care team to prepare a replacement."
            ),
            basis="ETE < 30 minutes.",
        ))

    # --- all-clear ---
    if not recs:
        recs.append(Recommendation(
            icon="✅",
            text="All simulated parameters are within demonstration thresholds.",
            basis="No rule triggered.",
        ))

    return recs


# ---------------------------------------------------------------------------
# Synthetic history data
# ---------------------------------------------------------------------------

def generate_synthetic_history(
    start_pressure: float = 200.0,
    points: int = 60,
    noise_std: float = 1.5,
) -> List[Tuple[int, float]]:
    """
    Generate a synthetic pressure-over-time series.

    Returns a list of (minute, pressure_bar) tuples with a gentle downward
    trend plus Gaussian noise.  This is ENTIRELY SYNTHETIC sample data for
    chart demonstration.
    """
    random.seed(42)  # reproducible for demo
    history = []
    pressure = start_pressure
    for minute in range(points):
        pressure -= random.uniform(0.3, 0.8)       # gentle decline
        pressure += random.gauss(0, noise_std)      # noise
        pressure = max(pressure, 0.0)
        history.append((minute, round(pressure, 2)))
    return history
