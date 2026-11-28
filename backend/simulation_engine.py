"""
backend/simulation_engine.py — Core IoT and Telemetry Simulation Engine for OxySense.

Contains:
- Hardware abstraction interface (for ESP32 and digital sensors)
- ETE (Estimated Time to Empty) formula and clinical limitations documentation
- Alert threshold classification
- Rule-based AI Recommendation engine with optional Groq LLM integration
"""

import os
import math
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from groq import Groq
except ImportError:
    Groq = None

# ---------------------------------------------------------------------------
# Default Demonstration Configurations
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "cylinder_id": "CYL-ICU-101",
    "ward": "Intensive Care Unit (ICU) — Bed 04",
    "cylinder_capacity_litres": 660.0,   # Type E cylinder
    "max_pressure_bar": 200.0,           # ~2900 PSI
    "prescribed_flow_lpm": 2.0,          # Standard prescribed clinical baseline
    "warning_threshold_bar": 50.0,       # ~725 PSI
    "critical_threshold_bar": 20.0,      # ~290 PSI
    "pressure_unit": "PSI",              # "PSI" or "BAR"
    "sensor_status": "DISCONNECTED",     # Default to DISCONNECTED without physical ESP32
    "simulation_mode": False,            # Simulation OFF by default: physical ESP32 required
}

# ---------------------------------------------------------------------------
# Hardware & Telemetry State
# ---------------------------------------------------------------------------

class TelemetryState:
    """Represents live telemetry state, requiring physical ESP32 input by default."""
    def __init__(self):
        self.config = dict(DEFAULT_CONFIG)
        self.current_pressure_bar = 0.0
        self.current_flow_lpm = 0.0
        self.is_sensor_connected = False
        self.hardware_active = False
        self.last_hardware_time = None
        self.last_update = datetime.now()
        self.simulation_scenario = "NORMAL"  # "NORMAL", "LOW_PRESSURE", "SENSOR_DISCONNECTED"
        self.history: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []
        self._init_default_alerts()
        if os.environ.get("VERCEL"):
            self.config["simulation_mode"] = True
            self.is_sensor_connected = True
            self._init_mock_history()
            if self.history:
                self.current_pressure_bar = self.history[-1]["pressure_bar"]
                self.current_flow_lpm = self.history[-1]["flow_lpm"]

    def _init_mock_history(self):
        """Populate 30 minutes of realistic synthetic baseline telemetry."""
        now = datetime.now()
        p = 180.0
        for i in range(30, -1, -1):
            ts = now - timedelta(minutes=i * 2)
            p = max(p - random.uniform(0.6, 1.4), 145.0)
            flow = max(1.8, min(2.2, 2.0 + random.gauss(0, 0.08)))
            ete_val = self._calc_ete_minutes(p, flow, self.config["cylinder_capacity_litres"], self.config["max_pressure_bar"])
            self.history.append({
                "timestamp": ts.strftime("%H:%M:%S"),
                "iso_time": ts.isoformat(),
                "pressure_bar": round(p, 1),
                "pressure_psi": round(p * 14.5038, 0),
                "flow_lpm": round(flow, 2),
                "remaining_pct": round((p / self.config["max_pressure_bar"]) * 100, 1),
                "ete_minutes": round(ete_val, 1) if ete_val else 0,
                "status": "NORMAL"
            })
        self.current_pressure_bar = self.history[-1]["pressure_bar"]
        self.current_flow_lpm = self.history[-1]["flow_lpm"]

    def _init_default_alerts(self):
        """Seed initial alert queue."""
        now = datetime.now()
        self.alerts = [
            {
                "id": "ALT-1001",
                "severity": "INFO",
                "title": "System Initialized in Simulation Mode",
                "description": "Virtual ESP32 telemetry telemetry node active. No physical hardware attached.",
                "timestamp": (now - timedelta(minutes=25)).strftime("%H:%M:%S"),
                "acknowledged": True
            }
        ]

    @staticmethod
    def _calc_ete_minutes(pressure_bar: float, flow_lpm: float, capacity_l: float, max_p_bar: float) -> Optional[float]:
        """Calculates Estimated Time to Empty in minutes using linear Boyle-Mariotte demonstration model."""
        if flow_lpm <= 0 or max_p_bar <= 0 or pressure_bar < 0:
            return None
        remaining_litres = capacity_l * (pressure_bar / max_p_bar)
        return remaining_litres / flow_lpm

    def tick_simulation(self):
        """Advances the telemetry state based strictly on ESP32 hardware presence."""
        now = datetime.now()
        self.last_update = now

        if self.simulation_scenario == "SENSOR_DISCONNECTED":
            self.is_sensor_connected = False
            return

        # Check real hardware connection (ESP32 via serial_bridge)
        if self.hardware_active and self.last_hardware_time:
            # If received packet within the last 3.5 seconds, mark hardware connected
            if (now - self.last_hardware_time).total_seconds() <= 3.5:
                self.is_sensor_connected = True
                status = self.classify_status()["level"]
                ete = self.calculate_ete()
                self._check_automatic_alerts(status)

                # Hardware mode: Use actual flow and pressure from ESP32 sensor without synthetic distortion
                hw_flow = round(self.current_flow_lpm, 2)
                hw_p_bar = round(self.current_pressure_bar, 1)

                # Append live point to history
                self.history.append({
                    "timestamp": now.strftime("%H:%M:%S"),
                    "iso_time": now.isoformat(),
                    "pressure_bar": hw_p_bar,
                    "pressure_psi": round(hw_p_bar * 14.5038, 0),
                    "flow_lpm": hw_flow,
                    "remaining_pct": round((self.current_pressure_bar / self.config["max_pressure_bar"]) * 100, 1),
                    "ete_minutes": round(ete["minutes"], 1) if ete["valid"] else 0,
                    "status": status
                })
                if len(self.history) > 60:
                    self.history.pop(0)
                return
            else:
                # Hardware packet timed out (ESP32 UNPLUGGED OR REMOVED!)
                # STOP EVERYTHING IMMEDIATELY
                self.is_sensor_connected = False
                self.hardware_active = False
                return

        # If user explicitly turned on simulation via Demonstration panel or in Vercel cloud
        if self.config.get("simulation_mode", False) or os.environ.get("VERCEL"):
            self.is_sensor_connected = True
            if self.simulation_scenario == "LOW_PRESSURE":
                self.current_pressure_bar = max(0.0, self.current_pressure_bar - random.uniform(3.5, 6.0))
            elif self.simulation_scenario == "NORMAL":
                self.current_pressure_bar = max(0.0, self.current_pressure_bar - random.uniform(0.15, 0.45))
            target_flow = self.config["prescribed_flow_lpm"]
            self.current_flow_lpm = max(0.5, round(target_flow + random.gauss(0, 0.12), 2))
            status = self.classify_status()["level"]
            ete = self.calculate_ete()
            self._check_automatic_alerts(status)
            self.history.append({
                "timestamp": now.strftime("%H:%M:%S"),
                "iso_time": now.isoformat(),
                "pressure_bar": round(self.current_pressure_bar, 1),
                "pressure_psi": round(self.current_pressure_bar * 14.5038, 0),
                "flow_lpm": round(self.current_flow_lpm, 2),
                "remaining_pct": round((self.current_pressure_bar / self.config["max_pressure_bar"]) * 100, 1),
                "ete_minutes": round(ete["minutes"], 1) if ete["valid"] else 0,
                "status": status
            })
            if len(self.history) > 60:
                self.history.pop(0)
        else:
            # HARDWARE REQUIRED: Without ESP32 hardware packet, STOP EVERYTHING AND SHOW DISCONNECTED!
            self.is_sensor_connected = False
            self.current_pressure_bar = 0.0
            self.current_flow_lpm = 0.0
            return

        # Append to live history (keep last 60 points)
        self.history.append({
            "timestamp": now.strftime("%H:%M:%S"),
            "iso_time": now.isoformat(),
            "pressure_bar": round(self.current_pressure_bar, 1),
            "pressure_psi": round(self.current_pressure_bar * 14.5038, 0),
            "flow_lpm": round(self.current_flow_lpm, 2),
            "remaining_pct": round((self.current_pressure_bar / self.config["max_pressure_bar"]) * 100, 1),
            "ete_minutes": round(ete["minutes"], 1) if ete["valid"] else 0,
            "status": status
        })
        if len(self.history) > 60:
            self.history.pop(0)

    def _check_automatic_alerts(self, current_status: str):
        now_str = datetime.now().strftime("%H:%M:%S")
        
        # Critical Alert
        if current_status == "CRITICAL":
            if not any(a["id"] == "ALT-CRIT" and not a["acknowledged"] for a in self.alerts):
                self.alerts.insert(0, {
                    "id": "ALT-CRIT",
                    "severity": "CRITICAL",
                    "title": "Critical Pressure Warning",
                    "description": f"Pressure at {self.current_pressure_bar:.1f} bar ({self.current_pressure_bar * 14.5038:.0f} PSI). Immediate cylinder replacement required.",
                    "timestamp": now_str,
                    "acknowledged": False
                })
        # Warning Alert
        elif current_status == "LOW_PRESSURE":
            if not any(a["id"] == "ALT-WARN" and not a["acknowledged"] for a in self.alerts):
                self.alerts.insert(0, {
                    "id": "ALT-WARN",
                    "severity": "WARNING",
                    "title": "Low Cylinder Supply",
                    "description": f"Pressure dropped below {self.config['warning_threshold_bar']} bar threshold. Schedule replacement cylinder.",
                    "timestamp": now_str,
                    "acknowledged": False
                })

        # Flow deviation alert
        flow_diff = abs(self.current_flow_lpm - self.config["prescribed_flow_lpm"])
        if flow_diff > 0.8:
            if not any(a["id"] == "ALT-FLOW" and not a["acknowledged"] for a in self.alerts):
                self.alerts.insert(0, {
                    "id": "ALT-FLOW",
                    "severity": "WARNING",
                    "title": "Flow Rate Deviation Detected",
                    "description": f"Observed flow ({self.current_flow_lpm:.1f} L/min) differs from prescribed ({self.config['prescribed_flow_lpm']:.1f} L/min).",
                    "timestamp": now_str,
                    "acknowledged": False
                })

    def set_scenario(self, scenario: str):
        """Sets simulation scenario: NORMAL, LOW_PRESSURE, SENSOR_DISCONNECTED, RESET"""
        now_str = datetime.now().strftime("%H:%M:%S")
        if scenario == "RESET":
            self.simulation_scenario = "NORMAL"
            self.config["simulation_mode"] = True
            self.is_sensor_connected = True
            self.current_pressure_bar = 160.0
            self.current_flow_lpm = self.config["prescribed_flow_lpm"]
            for a in self.alerts:
                a["acknowledged"] = True
            self.alerts.insert(0, {
                "id": f"ALT-{int(time.time())}",
                "severity": "INFO",
                "title": "Simulation Reset to Normal",
                "description": "Cylinder supply restored to 160 bar. Telemetry nominal.",
                "timestamp": now_str,
                "acknowledged": True
            })
        elif scenario == "LOW_PRESSURE":
            self.simulation_scenario = "LOW_PRESSURE"
            self.config["simulation_mode"] = True
            self.is_sensor_connected = True
            self.current_pressure_bar = 42.0  # triggers warning threshold
            self.alerts.insert(0, {
                "id": "ALT-WARN",
                "severity": "WARNING",
                "title": "Simulated Low Pressure Activated",
                "description": "Pressure forced to 42 bar (609 PSI) to verify threshold alert propagation.",
                "timestamp": now_str,
                "acknowledged": False
            })
        elif scenario == "SENSOR_DISCONNECTED":
            self.simulation_scenario = "SENSOR_DISCONNECTED"
            self.config["simulation_mode"] = False
            self.is_sensor_connected = False
            self.hardware_active = False
            self.current_pressure_bar = 0.0
            self.current_flow_lpm = 0.0
            self.simulation_scenario = "SENSOR_DISCONNECTED"
            self.is_sensor_connected = False
            self.alerts.insert(0, {
                "id": "ALT-DISCONN",
                "severity": "CRITICAL",
                "title": "Sensor Disconnected (Simulated)",
                "description": "ESP32 telemetry stream interrupted or sensor probe offline.",
                "timestamp": now_str,
                "acknowledged": False
            })
        elif scenario == "NORMAL":
            self.simulation_scenario = "NORMAL"
            self.is_sensor_connected = True

    def switch_active_cylinder(self, cylinder_dict: Dict[str, Any]):
        """Switch the primary monitored cylinder in the telemetry state."""
        self.config["cylinder_id"] = cylinder_dict["id"]
        self.config["ward"] = cylinder_dict.get("ward", self.config["ward"])
        self.config["cylinder_capacity_litres"] = float(cylinder_dict.get("capacity_l", 660.0))
        self.config["prescribed_flow_lpm"] = float(cylinder_dict.get("flow_lpm", 2.0))
        p_init = float(cylinder_dict.get("pressure_bar", 150.0))
        if p_init <= 0:
            p_init = 150.0
        self.current_pressure_bar = p_init
        self.current_flow_lpm = float(cylinder_dict.get("flow_lpm", 2.0))
        self.is_sensor_connected = True
        self.simulation_scenario = "NORMAL"
        self.last_update = datetime.now()

        # Seed chart history for this cylinder with realistic dynamic curve
        now = datetime.now()
        self.history = []
        p = min(200.0, self.current_pressure_bar + 2.5)
        base_flow = self.current_flow_lpm
        for i in range(25, -1, -1):
            ts = now - timedelta(seconds=i * 5)
            p = max(0.0, p - 0.1)
            flow_sample = round(base_flow, 2)
            p_sample = max(0.0, round(p, 1))
            ete_calc = self._calc_ete_minutes(p_sample, flow_sample, self.config["cylinder_capacity_litres"], self.config["max_pressure_bar"])
            self.history.append({
                "timestamp": ts.strftime("%H:%M:%S"),
                "iso_time": ts.isoformat(),
                "pressure_bar": p_sample,
                "pressure_psi": round(p_sample * 14.5038, 0),
                "flow_lpm": flow_sample,
                "remaining_pct": round((p_sample / self.config["max_pressure_bar"]) * 100, 1),
                "ete_minutes": round(ete_calc, 1) if ete_calc else 0,
                "status": self.classify_status()["level"]
            })
        self.history[-1]["pressure_bar"] = round(self.current_pressure_bar, 1)
        self.history[-1]["pressure_psi"] = round(self.current_pressure_bar * 14.5038, 0)
        self.history[-1]["flow_lpm"] = round(self.current_flow_lpm, 2)

    def calculate_ete(self) -> Dict[str, Any]:
        """Calculates Estimated Time to Empty and includes clinical disclaimer."""
        if not self.is_sensor_connected:
            return {
                "valid": False,
                "display": "Estimate unavailable",
                "hours": 0,
                "minutes": 0,
                "reason": "Sensor is disconnected or offline."
            }

        if self.current_pressure_bar <= 0.0:
            return {
                "valid": True,
                "display": "0h 00m (Exhausted)",
                "hours": 0,
                "minutes": 0.0,
                "remaining_litres": 0.0,
                "reason": "Cylinder is completely empty. Immediate cylinder replacement required.",
                "formula": "Remaining Litres = 0 L",
                "disclaimer": "⚠️ Cylinder depleted."
            }

        mins = self._calc_ete_minutes(
            self.current_pressure_bar,
            self.current_flow_lpm,
            self.config["cylinder_capacity_litres"],
            self.config["max_pressure_bar"]
        )

        if mins is None or mins == float("inf"):
            return {
                "valid": False,
                "display": "Estimate unavailable",
                "hours": 0,
                "minutes": 0,
                "reason": "Flow rate is zero or invalid pressure parameters."
            }

        h = int(mins // 60)
        m = int(mins % 60)

        return {
            "valid": True,
            "display": f"{h}h {m:02d}m",
            "hours": h,
            "minutes": round(mins, 1),
            "remaining_litres": round(self.config["cylinder_capacity_litres"] * (self.current_pressure_bar / self.config["max_pressure_bar"]), 1),
            "formula": "Remaining Litres = Capacity × (P_current / P_max); ETE = Litres / Flow Rate",
            "disclaimer": "⚠️ Demonstration linear model only. Not calibrated for medical compliance or variable respiratory cycles."
        }

    def classify_status(self) -> Dict[str, str]:
        """Classifies cylinder telemetry into clear healthcare states."""
        if not self.is_sensor_connected:
            return {
                "level": "SENSOR_DISCONNECTED",
                "label": "Sensor Disconnected",
                "badge_class": "badge-disconnected",
                "color": "#64748b"
            }
        
        p = self.current_pressure_bar
        crit = self.config["critical_threshold_bar"]
        warn = self.config["warning_threshold_bar"]

        if p <= crit:
            return {
                "level": "CRITICAL",
                "label": "Critical Pressure",
                "badge_class": "badge-critical",
                "color": "#ef4444"
            }
        elif p <= warn:
            return {
                "level": "LOW_PRESSURE",
                "label": "Low Pressure",
                "badge_class": "badge-warning",
                "color": "#f59e0b"
            }
        else:
            return {
                "level": "NORMAL",
                "label": "Normal Operation",
                "badge_class": "badge-normal",
                "color": "#10b981"
            }

    def get_overview_payload(self) -> Dict[str, Any]:
        """Assembles unified overview response for front-end dashboard."""
        status = self.classify_status()
        ete = self.calculate_ete()
        unit = self.config.get("pressure_unit", "PSI")
        safe_p_bar = max(0.0, self.current_pressure_bar)
        
        pressure_val = (
            round(safe_p_bar * 14.5038, 0)
            if unit == "PSI"
            else round(safe_p_bar, 1)
        )
        max_pressure_val = (
            round(self.config["max_pressure_bar"] * 14.5038, 0)
            if unit == "PSI"
            else self.config["max_pressure_bar"]
        )

        if not self.is_sensor_connected:
            data_source = "HARDWARE (Disconnected — No ESP32)"
            pressure_val = 0
            pressure_bar = 0.0
            pressure_psi = 0
            percentage = 0
        elif self.hardware_active:
            data_source = "HARDWARE (ESP32 Live)"
            pressure_val = (
                round(safe_p_bar * 14.5038, 0)
                if unit == "PSI"
                else round(safe_p_bar, 1)
            )
            pressure_bar = round(safe_p_bar, 1)
            pressure_psi = round(safe_p_bar * 14.5038, 0)
            percentage = round((safe_p_bar / self.config["max_pressure_bar"]) * 100, 1)
        else:
            data_source = "SIMULATION (Synthetic Stream)"
            pressure_val = (
                round(safe_p_bar * 14.5038, 0)
                if unit == "PSI"
                else round(safe_p_bar, 1)
            )
            pressure_bar = round(safe_p_bar, 1)
            pressure_psi = round(safe_p_bar * 14.5038, 0)
            percentage = round((safe_p_bar / self.config["max_pressure_bar"]) * 100, 1)

        return {
            "device": {
                "id": self.config["cylinder_id"],
                "ward": self.config["ward"],
                "esp32_connected": self.is_sensor_connected,
                "pressure_sensor_status": "OK" if self.is_sensor_connected else "FAULT",
                "flow_sensor_status": "OK" if self.is_sensor_connected else "FAULT",
                "data_source": data_source,
                "last_update": self.last_update.strftime("%H:%M:%S")
            },
            "pressure": {
                "value": pressure_val,
                "unit": unit,
                "bar": pressure_bar,
                "psi": pressure_psi,
                "max": max_pressure_val,
                "percentage": percentage,
                "trend": "decreasing" if (self.is_sensor_connected and self.simulation_scenario in ["NORMAL", "LOW_PRESSURE"]) else "stable"
            },
            "flow": {
                "value": round(self.current_flow_lpm, 2) if self.is_sensor_connected else 0.0,
                "unit": "L/min",
                "prescribed": self.config["prescribed_flow_lpm"],
                "is_simulated": not self.hardware_active
            },
            "ete": ete,
            "status": status,
            "simulation_scenario": self.simulation_scenario,
            "active_alerts_count": len([a for a in self.alerts if not a["acknowledged"]])
        }

# ---------------------------------------------------------------------------
# AI Recommendation Generator (Rule-Based + Optional Groq API)
# ---------------------------------------------------------------------------

def generate_ai_insights(
    state: TelemetryState,
    inventory_summary: Optional[Dict[str, Any]] = None,
    active_alerts: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Generates intelligent operational recommendations for oxygen cylinder inventory.
    Uses official Groq Python SDK if GROQ_API_KEY is configured in environment.
    Gracefully falls back to structured rule-based healthcare logic otherwise.
    Strictly enforces non-clinical operational assistance (no medical prescription changes).
    """
    status_info = state.classify_status()
    ete_info = state.calculate_ete()

    # Deterministic rule-driven condition and action analysis
    conditions = []
    actions = []
    triggers = []

    if not state.is_sensor_connected:
        conditions.append("Telemetry signal loss: ESP32 or sensor node unreachable.")
        actions.append("Inspect physical cable connections and battery on ESP32 telemetry collar.")
        triggers.append("Rule S-01: Heartbeat timeout / Null telemetry stream.")
    else:
        if status_info["level"] == "CRITICAL":
            conditions.append(f"Severe oxygen depletion: Cylinder pressure is {state.current_pressure_bar:.1f} bar.")
            actions.append("Prepare replacement Type E cylinder immediately. Notify ward nursing supervisor.")
            triggers.append(f"Rule P-01: Pressure below critical threshold ({state.config['critical_threshold_bar']} bar).")
        elif status_info["level"] == "LOW_PRESSURE":
            conditions.append(f"Supply warning: Cylinder has reached {state.current_pressure_bar:.1f} bar.")
            actions.append("Schedule cylinder exchange within the next 45 minutes to prevent treatment interruption.")
            triggers.append(f"Rule P-02: Pressure below warning threshold ({state.config['warning_threshold_bar']} bar).")

        flow_delta = abs(state.current_flow_lpm - state.config["prescribed_flow_lpm"])
        if flow_delta > 0.6:
            conditions.append(f"Flow variance detected: Measured {state.current_flow_lpm:.1f} L/min vs prescribed {state.config['prescribed_flow_lpm']:.1f} L/min.")
            actions.append("Request authorized respiratory care staff to verify regulator valve calibration.")
            triggers.append("Rule F-03: Flow rate discrepancy > 0.6 L/min from prescribed target.")

    # Incorporate inventory warnings if present
    if inventory_summary and inventory_summary.get("critical_count", 0) > 0:
        crit_list = ", ".join(inventory_summary.get("critical_cylinders", []))
        conditions.append(f"Hospital fleet reserve alert: {inventory_summary['critical_count']} cylinder(s) at critical depletion ({crit_list}).")
        actions.append("Dispatch central oxygen replenishment orderly to stage backup cylinders.")
        triggers.append("Rule INV-01: Fleet inventory critical reserve threshold reached.")

    if not conditions:
        conditions.append("Nominal cylinder operation: Pressure and flow within normal parameters.")
        actions.append("Continue routine scheduled monitoring. No logistical intervention needed.")
        triggers.append("Rule N-00: Telemetry steady within green envelope.")

    # Try Groq LLM via official SDK if key is provided and valid
    llm_output = None
    engine_used = "Rule-Based Expert Engine (Offline Deterministic)"

    # Dynamically refresh .env so newly added keys are picked up immediately
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
    except Exception:
        pass

    groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model_name = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
    is_key_configured = bool(groq_api_key and not groq_api_key.startswith("gsk_your_") and len(groq_api_key) > 10)
    diagnostic_status = "NOT_CONFIGURED" if not is_key_configured else "PENDING"
    latency_ms = None

    if Groq and is_key_configured:
        start_ts = time.time()
        try:
            client = Groq(api_key=groq_api_key, timeout=5.0)

            context_lines = [
                f"- Monitored Cylinder: {state.config['cylinder_id']} ({state.config.get('ward', 'ICU')})",
                f"- Pressure: {state.current_pressure_bar:.1f} bar ({state.current_pressure_bar * 14.5038:.0f} PSI)",
                f"- Flow Rate: {state.current_flow_lpm:.1f} L/min (Prescribed: {state.config['prescribed_flow_lpm']:.1f} L/min)",
                f"- Calculated Supply ETE: {ete_info['display']}",
                f"- Status Level: {status_info['level']}",
                f"- Sensor Link: {'Online' if state.is_sensor_connected else 'Disconnected'}"
            ]
            if inventory_summary:
                context_lines.append(f"- Fleet Total: {inventory_summary.get('total_cylinders', 6)} cylinders | {inventory_summary.get('normal_count', 0)} Nominal | {inventory_summary.get('warning_count', 0)} Low | {inventory_summary.get('critical_count', 0)} Critical")
                if inventory_summary.get("critical_cylinders"):
                    context_lines.append(f"- Critical Cylinders in Wards: {', '.join(inventory_summary['critical_cylinders'])}")
            if active_alerts:
                alert_text = "; ".join([a.get("message", "") for a in active_alerts[:3] if a.get("message")])
                if alert_text:
                    context_lines.append(f"- Active Fleet Alerts: {alert_text}")

            system_instruction = (
                "You are OxySense Clinical Logistics & Inventory AI, an operational assistance system for hospital oxygen supplies. "
                "Provide a concise 2-sentence operational logistics and inventory summary for hospital orderly and nursing staff. "
                "SAFETY CONSTRAINTS: DO NOT prescribe oxygen or alter medical prescriptions. "
                "DO NOT recommend changing prescribed oxygen flow rates or dosages. "
                "Focus strictly on cylinder logistics, replacement timing, inventory readiness, and equipment safety. "
                "Clearly frame your output as operational assistance only."
            )

            user_prompt = "Current Hospital Oxygen Telemetry & Inventory Context:\n" + "\n".join(context_lines)

            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=180
            )

            latency_ms = int((time.time() - start_ts) * 1000)

            if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
                llm_output = completion.choices[0].message.content.strip()
                engine_used = f"Groq Cloud LLM ({model_name})"
                diagnostic_status = "SUCCESS"
                print(f"[OxySense AI] Live Groq API request succeeded with model '{model_name}' ({latency_ms}ms).", flush=True)
        except Exception as groq_err:
            latency_ms = int((time.time() - start_ts) * 1000)
            clean_err = str(groq_err).split("api_key")[0].strip()[:80]
            diagnostic_status = f"ERROR: {type(groq_err).__name__} ({clean_err})"
            print(f"[OxySense AI] Groq API call failed: {type(groq_err).__name__}. Falling back to deterministic rules.", flush=True)
            llm_output = None

    summary = llm_output or (
        f"Cylinder {state.config['cylinder_id']} in {state.config['ward']} is operating at {state.current_pressure_bar:.0f} bar with an estimated {ete_info['display']} supply remaining."
        if state.is_sensor_connected else
        f"Telemetry from {state.config['cylinder_id']} is unavailable. Immediate device check is advised."
    )

    return {
        "engine": engine_used,
        "is_llm_active": bool(llm_output),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "detected_conditions": conditions,
        "operational_suggestions": actions,
        "trigger_rules": triggers,
        "safety_disclaimer": "⚠️ Non-Clinical Operational Assistance Only: OxySense AI provides logistical and inventory guidance. It does NOT generate patient-specific treatment instructions or authorize changing prescribed oxygen flow rates. Clinical adjustments must be performed solely by licensed medical professionals.",
        "diagnostic": {
            "groq_configured": is_key_configured,
            "model": model_name,
            "status": diagnostic_status,
            "latency_ms": latency_ms
        }
    }

# Global singleton simulation instance
telemetry_instance = TelemetryState()
