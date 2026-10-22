"""
app.py — Streamlit Dashboard for the Personalized Healthcare Recommendation System.

IoT-Enabled Smart Oxygen Cylinder Monitoring with AI-Driven Recommendations
(SOFTWARE SIMULATION — no physical hardware connected)

Launch:  python -m streamlit run app.py
"""

import time
import random
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from simulation import (
    SimulatedReading,
    calculate_ete,
    classify_alert,
    generate_recommendations,
    generate_synthetic_history,
    CYLINDER_PRESETS,
    DEFAULT_THRESHOLDS,
)

# ── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="O₂ Cylinder Monitor — Simulation",
    page_icon="🫁",
    layout="wide",
)

# ── Demo credentials (for demonstration only — NOT production auth) ─────────

DEMO_USERS = {
    "admin": {"password": "admin123", "name": "Administrator", "role": "Admin"},
    "doctor": {"password": "doctor123", "name": "Dr. Sharma", "role": "Doctor"},
    "nurse": {"password": "nurse123", "name": "Nurse Priya", "role": "Nurse"},
}

# ── Session state defaults ──────────────────────────────────────────────────

if "page" not in st.session_state:
    st.session_state.page = "home"          # home → login → dashboard
    st.session_state.authenticated = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.login_error = ""


# ═══════════════════════════════════════════════════════════════════════════
#  PAGE 1 — HOME / LANDING PAGE
# ═══════════════════════════════════════════════════════════════════════════

def show_home_page():
    st.markdown("""
    <style>
        /* Medical accessories background pattern */
        .stApp {
            background-color: #f7fafc;
            background-image: 
                radial-gradient(#e2e8f0 1.2px, transparent 1.2px),
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140' viewBox='0 0 140 140'%3E%3Cg fill='%230284c7' fill-opacity='0.045'%3E%3C!-- Stethoscope --%3E%3Cpath d='M100 20c-2.5 0-4.5 2-4.5 4.5v12c0 3.3-2.7 6-6 6s-6-2.7-6-6v-12c0-2.5-2-4.5-4.5-4.5s-4.5 2-4.5 4.5v12c0 8.3 6.7 15 15 15s15-6.7 15-15v-12c0-2.5-2-4.5-4.5-4.5z'/%3E%3Ccircle cx='89.5' cy='58' r='4'/%3E%3C!-- Medical Cross --%3E%3Cpath d='M28 16h8v8h8v8h-8v8h-8v-8h-8v-8h8z'/%3E%3C!-- Medicine Capsule --%3E%3Crect x='18' y='80' width='24' height='10' rx='5' transform='rotate(-35 30 85)'/%3E%3C!-- ECG Wave --%3E%3Cpath d='M70 105h12l4-12 6 22 5-15 4 7h15' stroke='%230284c7' stroke-width='2.2' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C!-- Oxygen Tank / Syringe --%3E%3Crect x='108' y='75' width='10' height='26' rx='4'/%3E%3C/g%3E%3C/svg%3E");
            background-size: 140px 140px;
        }
        .hero-wrap {
            text-align: center;
            padding: 30px 10px 10px 10px;
            position: relative;
        }
        .hero-icon { font-size: 5rem; }
        .hero-title {
            font-size: 2.4rem;
            font-weight: 800;
            color: #1a1a2e;
            margin: 10px 0 4px 0;
        }
        .hero-subtitle {
            font-size: 1.05rem;
            color: #444;
            margin-bottom: 14px;
        }
        .med-accessories-strip {
            display: inline-flex;
            gap: 12px;
            flex-wrap: wrap;
            justify-content: center;
            background: rgba(255, 255, 255, 0.85);
            border: 1px solid #e2e8f0;
            border-radius: 30px;
            padding: 8px 22px;
            margin-bottom: 18px;
            box-shadow: 0 4px 15px rgba(2, 132, 199, 0.08);
            font-size: 0.88rem;
            color: #0369a1;
            font-weight: 600;
        }
        .hero-badge {
            display: inline-block;
            background: #1a1a2e;
            color: #e94560;
            padding: 6px 18px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 1px;
            margin-bottom: 24px;
        }
        .feature-card {
            background: rgba(255, 255, 255, 0.92);
            border-radius: 14px;
            padding: 22px 18px;
            text-align: center;
            border-top: 4px solid;
            box-shadow: 0 4px 12px rgba(0,0,0,0.04);
            height: 100%;
        }
        .accessory-card {
            background: rgba(255, 255, 255, 0.95);
            border: 1px solid #e0f2fe;
            border-radius: 12px;
            padding: 16px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(3, 105, 161, 0.05);
        }
        .accessory-card h5 { margin: 8px 0 4px 0; color: #0f172a; }
        .accessory-card p  { font-size: 0.82rem; color: #475569; margin: 0; }
        .feature-card h4 { margin: 10px 0 6px 0; }
        .feature-card p  { font-size: 0.88rem; color: #555; }
    </style>
    """, unsafe_allow_html=True)

    # ── Hero ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero-wrap">
        <div class="hero-icon">🫁</div>
        <div class="hero-title">Personalized Healthcare<br>Recommendation System</div>
        <div class="hero-subtitle">
            IoT-Enabled Smart Oxygen Cylinder Monitoring<br>
            with AI-Driven Recommendations
        </div>
        <div class="med-accessories-strip">
            <span>🩺 Stethoscope</span>
            <span>•</span>
            <span>🫁 Oxygen Mask & Cannula</span>
            <span>•</span>
            <span>🩹 Pulse Oximeter</span>
            <span>•</span>
            <span>⚙️ Pressure Regulator</span>
            <span>•</span>
            <span>💉 Infusion Kit</span>
        </div>
        <br>
        <div class="hero-badge">🔬 SOFTWARE SIMULATION — COLLEGE MAJOR PROJECT</div>
    </div>
    """, unsafe_allow_html=True)

    # ── "Get Started" button ────────────────────────────────────────────────
    _, btn_col, _ = st.columns([2, 1, 2])
    with btn_col:
        if st.button("🚀  Get Started", use_container_width=True, type="primary"):
            st.session_state.page = "login"
            st.rerun()

    st.markdown("---")

    # ── Feature highlights ──────────────────────────────────────────────────
    st.subheader("✨ Key Features")
    f1, f2, f3, f4 = st.columns(4)

    with f1:
        st.markdown("""
        <div class="feature-card" style="border-color:#3498db">
            <h3>📊</h3>
            <h4>Live Monitoring</h4>
            <p>Real-time pressure gauge &amp; flow rate tracking with auto-simulation</p>
        </div>
        """, unsafe_allow_html=True)

    with f2:
        st.markdown("""
        <div class="feature-card" style="border-color:#e74c3c">
            <h3>🚨</h3>
            <h4>Smart Alerts</h4>
            <p>Normal, Warning &amp; Critical status with configurable thresholds</p>
        </div>
        """, unsafe_allow_html=True)

    with f3:
        st.markdown("""
        <div class="feature-card" style="border-color:#2ecc71">
            <h3>🤖</h3>
            <h4>AI Recommendations</h4>
            <p>Rule-based intelligent alerts for cylinder management</p>
        </div>
        """, unsafe_allow_html=True)

    with f4:
        st.markdown("""
        <div class="feature-card" style="border-color:#f39c12">
            <h3>⏱️</h3>
            <h4>ETE Prediction</h4>
            <p>Estimated Time to Exhaustion with transparent formula</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Medical Accessories & Ecosystem ──────────────────────────────────────
    st.subheader("🩺 Medical Accessories & Clinical Context")
    st.caption("Illustrative clinical equipment modeled within this monitoring ecosystem:")
    a1, a2, a3, a4 = st.columns(4)

    with a1:
        st.markdown("""
        <div class="accessory-card">
            <h3>🫁</h3>
            <h5>O₂ Delivery Interfaces</h5>
            <p>Nasal Cannula &amp; Venturi / Non-Rebreather Masks</p>
        </div>
        """, unsafe_allow_html=True)

    with a2:
        st.markdown("""
        <div class="accessory-card">
            <h3>⚙️</h3>
            <h5>Regulator &amp; Flowmeter</h5>
            <p>Two-stage pressure reduction &amp; 0–15 L/min flow valve</p>
        </div>
        """, unsafe_allow_html=True)

    with a3:
        st.markdown("""
        <div class="accessory-card">
            <h3>🩹</h3>
            <h5>Pulse Oximeter (SpO₂)</h5>
            <p>Non-invasive arterial oxygen saturation feedback</p>
        </div>
        """, unsafe_allow_html=True)

    with a4:
        st.markdown("""
        <div class="accessory-card">
            <h3>📡</h3>
            <h5>IoT Sensor Collar</h5>
            <p>Pressure transducer &amp; digital telemetry module</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Architecture overview ───────────────────────────────────────────────
    st.subheader("🏗️ System Architecture")
    st.markdown("""
    ```
    ┌──────────────┐    ┌──────────┐    ┌───────────────┐    ┌────────────────┐    ┌────────────┐
    │ O₂ Sensors   │───▶│  ESP32   │───▶│ Python Backend│───▶│ ETE & Alert    │───▶│ Dashboard  │
    │ (🔲 Planned) │    │(🔲 Plan) │    │ (✅ Simulated)│    │ Engine (✅ Sim)│    │ (✅ Live)  │
    └──────────────┘    └──────────┘    └───────────────┘    └────────────────┘    └────────────┘
                                                                                          │
                                                                                   ┌──────▼───────┐
                                                                                   │Recommendation│
                                                                                   │Module (⚙️)   │
                                                                                   └──────────────┘
    ```
    """)

    st.markdown("---")

    # ── Project info ────────────────────────────────────────────────────────
    st.subheader("📚 About This Project")
    i1, i2 = st.columns(2)
    with i1:
        st.markdown("""
        **Project Type:** College Major Project  
        **Technology:** Python, Streamlit, Plotly  
        **Mode:** Software Simulation (no hardware)  
        **AI Module:** Rule-based recommendations  
        """)
    with i2:
        st.markdown("""
        **Planned Hardware:** ESP32 + Pressure/Flow sensors  
        **Planned Cloud:** MQTT / AWS IoT  
        **Status:** Prototype / MVP  
        **Medical Use:** ❌ Not validated for clinical use  
        """)

    st.markdown("---")

    # ── Disclaimer ──────────────────────────────────────────────────────────
    st.warning(
        "⚠️ **Disclaimer:** This is a software simulation for academic demonstration only. "
        "No real hardware, sensors, or patient data are used. Not a medical device."
    )

    # ── Footer ──────────────────────────────────────────────────────────────
    st.caption(
        "Personalized Healthcare Recommendation System · "
        "College Major Project · Built with Python & Streamlit"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  PAGE 2 — LOGIN PAGE
# ═══════════════════════════════════════════════════════════════════════════

def show_login_page():
    st.markdown("""
    <style>
        .login-header { text-align: center; margin-bottom: 10px; }
        .login-header h1 { font-size: 2.8rem; margin-bottom: 0; }
        .login-title {
            text-align: center; font-size: 1.4rem; font-weight: 700;
            color: #1a1a2e; margin-bottom: 4px;
        }
        .login-subtitle {
            text-align: center; font-size: 0.85rem; color: #555;
            margin-bottom: 20px;
        }
        .login-sim-badge {
            text-align: center; background: #1a1a2e; color: #e94560;
            padding: 6px 14px; border-radius: 6px; font-size: 0.75rem;
            font-weight: 700; letter-spacing: 1px; margin-bottom: 20px;
        }
        .cred-box {
            background: #eaf4fe; border-left: 4px solid #3498db;
            padding: 12px 16px; border-radius: 8px; font-size: 0.82rem;
            margin-top: 16px;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_l, col_mid, col_r = st.columns([1, 2, 1])

    with col_mid:
        # ── Back to Home ───────────────────────────────────────────────────
        if st.button("← Back to Home"):
            st.session_state.page = "home"
            st.rerun()

        st.markdown('<div class="login-header"><h1>🫁</h1></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-title">Personalized Healthcare<br>Recommendation System</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="login-subtitle">'
            'IoT-Enabled Smart Oxygen Cylinder Monitoring<br>'
            'with AI-Driven Recommendations</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="login-sim-badge">🔬 SOFTWARE SIMULATION — NO HARDWARE CONNECTED</div>',
            unsafe_allow_html=True,
        )

        # ── Login form ─────────────────────────────────────────────────────
        with st.form("login_form"):
            username = st.text_input("👤 Username", placeholder="Enter username")
            password = st.text_input("🔒 Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("🔑  Login", use_container_width=True)

            if submitted:
                user = DEMO_USERS.get(username.strip().lower())
                if user and user["password"] == password:
                    st.session_state.authenticated = True
                    st.session_state.page = "dashboard"
                    st.session_state.user_name = user["name"]
                    st.session_state.user_role = user["role"]
                    st.session_state.login_error = ""
                    st.rerun()
                else:
                    st.session_state.login_error = "Invalid username or password."

        if st.session_state.login_error:
            st.error(st.session_state.login_error)

        # ── Demo credentials hint ──────────────────────────────────────────
        st.markdown(
            '<div class="cred-box">'
            '💡 <b>Demo credentials</b><br>'
            '<code>admin / admin123</code> · '
            '<code>doctor / doctor123</code> · '
            '<code>nurse / nurse123</code>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<p style="text-align:center;font-size:0.75rem;color:#888;margin-top:30px">'
            'College Major Project · Software Simulation Prototype<br>'
            'Built with Python &amp; Streamlit</p>',
            unsafe_allow_html=True,
        )


# ── Page router ─────────────────────────────────────────────────────────────

if st.session_state.page == "home":
    show_home_page()
    st.stop()

if st.session_state.page == "login" or not st.session_state.authenticated:
    show_login_page()
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# EVERYTHING BELOW RUNS ONLY AFTER SUCCESSFUL LOGIN
# ═══════════════════════════════════════════════════════════════════════════

# ── Session-state defaults ──────────────────────────────────────────────────

_DEFAULTS = {
    "sim_running": False,
    "sim_pressure": 195.0,        # start near full
    "sim_flow": 2.0,
    "sim_tick": 0,
    "sim_history": [],            # list of (tick, pressure) tuples
    "sim_last_update": None,
    "sim_started_once": False,
}

for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Custom CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .sim-banner {
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        color: #e94560;
        text-align: center;
        padding: 8px 16px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.95rem;
        letter-spacing: 1px;
        margin-bottom: 6px;
    }
    .live-banner {
        background: linear-gradient(90deg, #0b3d0b 0%, #145214 50%, #1a6b1a 100%);
        color: #4cff4c;
        text-align: center;
        padding: 8px 16px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.95rem;
        letter-spacing: 1px;
        margin-bottom: 6px;
        animation: pulse 1.5s ease-in-out infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }
    .status-badge {
        display: inline-block;
        padding: 6px 18px;
        border-radius: 20px;
        color: white;
        font-weight: 700;
        font-size: 1.1rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Banners ─────────────────────────────────────────────────────────────────

st.markdown(
    '<div class="sim-banner">🔬 SIMULATION MODE — All data is synthetic. '
    'No physical sensors or hardware are connected.</div>',
    unsafe_allow_html=True,
)

if st.session_state.sim_running:
    ts = st.session_state.sim_last_update
    ts_str = ts.strftime("%H:%M:%S") if ts else "—"
    st.markdown(
        f'<div class="live-banner">▶️ LIVE SIMULATION RUNNING — '
        f'Auto-updating every 2 s · Tick #{st.session_state.sim_tick} · '
        f'Last update: {ts_str}</div>',
        unsafe_allow_html=True,
    )

st.title("🫁 Personalized Healthcare Recommendation System")
st.caption(
    "IoT-Enabled Smart Oxygen Cylinder Monitoring with AI-Driven Recommendations "
    "· **College Major Project — Software Simulation**"
)

# ── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    # ── User info + logout ──────────────────────────────────────────────────
    uc1, uc2 = st.columns([3, 1])
    with uc1:
        st.markdown(
            f"👤 **{st.session_state.user_name}** · {st.session_state.user_role}"
        )
    with uc2:
        if st.button("Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.session_state.page = "home"
            st.rerun()
    st.markdown("---")

    st.header("⚙️ Simulation Controls")
    st.info("No real sensors, ESP32, or oxygen cylinder are connected.")

    # ── Live simulation controls ────────────────────────────────────────────
    st.subheader("🔄 Live Simulation")

    btn_cols = st.columns(3)
    with btn_cols[0]:
        if st.button("▶️ Start", use_container_width=True):
            if not st.session_state.sim_started_once:
                # fresh start — initialise from sidebar defaults
                st.session_state.sim_pressure = 195.0
                st.session_state.sim_flow = 2.0
                st.session_state.sim_tick = 0
                st.session_state.sim_history = [(0, 195.0)]
            st.session_state.sim_running = True
            st.session_state.sim_started_once = True
            st.rerun()

    with btn_cols[1]:
        if st.button("⏹️ Stop", use_container_width=True):
            st.session_state.sim_running = False
            st.rerun()

    with btn_cols[2]:
        if st.button("🔁 Reset", use_container_width=True):
            st.session_state.sim_running = False
            st.session_state.sim_pressure = 195.0
            st.session_state.sim_flow = 2.0
            st.session_state.sim_tick = 0
            st.session_state.sim_history = [(0, 195.0)]
            st.session_state.sim_last_update = None
            st.session_state.sim_started_once = False
            st.rerun()

    if st.session_state.sim_running:
        st.success("● Simulation is **running** — values auto-update every 2 s.")
    else:
        st.warning("● Simulation is **stopped** — use sliders for manual control.")

    st.markdown("---")

    # ── Cylinder settings ───────────────────────────────────────────────────
    st.subheader("Cylinder Settings")
    cylinder_type = st.selectbox(
        "Cylinder type (illustrative)", list(CYLINDER_PRESETS.keys())
    )
    capacity = CYLINDER_PRESETS[cylinder_type]
    max_pressure = st.number_input(
        "Max pressure when full (bar)", 50, 300, 200, step=10
    )

    # ── Manual sensor readings (disabled during live sim) ───────────────────
    st.subheader("Manual Sensor Readings")
    if st.session_state.sim_running:
        st.caption("🔒 Sliders locked while live simulation runs.")
        manual_pressure = st.slider(
            "Cylinder pressure (bar)", 0, int(max_pressure),
            int(st.session_state.sim_pressure), disabled=True,
        )
        manual_flow = st.slider(
            "Flow rate (L/min)", 0.0, 15.0,
            st.session_state.sim_flow, 0.5, disabled=True,
        )
    else:
        manual_pressure = st.slider(
            "Cylinder pressure (bar)", 0, int(max_pressure), 130,
        )
        manual_flow = st.slider(
            "Flow rate (L/min)", 0.0, 15.0, 2.0, 0.5,
        )

    # ── Thresholds ──────────────────────────────────────────────────────────
    st.subheader("Demonstration Thresholds")
    warn_thresh = st.number_input(
        "Warning threshold (bar)",
        0, int(max_pressure),
        DEFAULT_THRESHOLDS["warning_pressure_bar"],
        step=5,
    )
    crit_thresh = st.number_input(
        "Critical threshold (bar)",
        0, int(max_pressure),
        DEFAULT_THRESHOLDS["critical_pressure_bar"],
        step=5,
    )
    prescribed_flow = st.number_input(
        "Illustrative prescribed flow (L/min)", 0.0, 15.0,
        DEFAULT_THRESHOLDS["prescribed_flow_lpm"], 0.5,
    )

# ── Resolve active pressure & flow ──────────────────────────────────────────

if st.session_state.sim_running:
    pressure = st.session_state.sim_pressure
    flow_rate = st.session_state.sim_flow
else:
    pressure = float(manual_pressure)
    flow_rate = float(manual_flow)

# ── Core calculations ──────────────────────────────────────────────────────

reading = SimulatedReading(
    pressure_bar=pressure,
    flow_rate_lpm=flow_rate,
    cylinder_capacity_litres=capacity,
    max_pressure_bar=max_pressure,
)

ete = calculate_ete(reading)
alert = classify_alert(pressure, warn_thresh, crit_thresh)
recs = generate_recommendations(
    reading, ete, alert, prescribed_flow, warn_thresh, crit_thresh
)

# ── Pressure gauge + status row ─────────────────────────────────────────────

st.markdown("---")
col_gauge, col_status, col_ete = st.columns([2, 1, 1])

with col_gauge:
    gauge_fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pressure,
        number={"suffix": " bar", "font": {"size": 28}},
        delta={"reference": max_pressure, "relative": False, "suffix": " bar"},
        title={"text": "Cylinder Pressure", "font": {"size": 14}},
        gauge={
            "axis": {
                "range": [0, max_pressure],
                "tickwidth": 2,
                "tickcolor": "#333",
                "dtick": max_pressure / 10,
            },
            "bar": {"color": alert.color, "thickness": 0.3},
            "bgcolor": "#f0f0f0",
            "borderwidth": 2,
            "bordercolor": "#ccc",
            "steps": [
                {"range": [0, crit_thresh], "color": "#fdedec"},
                {"range": [crit_thresh, warn_thresh], "color": "#fef9e7"},
                {"range": [warn_thresh, max_pressure], "color": "#eafaf1"},
            ],
            "threshold": {
                "line": {"color": "#e74c3c", "width": 3},
                "thickness": 0.8,
                "value": crit_thresh,
            },
        },
    ))
    gauge_fig.update_layout(
        height=170,
        margin=dict(l=5, r=5, t=30, b=0),
    )
    st.plotly_chart(gauge_fig, use_container_width=True)

with col_status:
    st.subheader("Status")
    st.markdown(
        f'<span class="status-badge" style="background:{alert.color}">'
        f'{alert.emoji} {alert.level}</span>',
        unsafe_allow_html=True,
    )
    remaining_pct = (pressure / max_pressure * 100) if max_pressure > 0 else 0
    st.metric("Remaining", f"{remaining_pct:.0f}%")

with col_ete:
    st.subheader("Time Left")
    if ete.minutes == float("inf"):
        st.metric("ETE", "∞ (flow is 0)")
    elif ete.minutes >= 60:
        st.metric("ETE", f"{ete.hours:.1f} h ({ete.minutes:.0f} min)")
    else:
        st.metric("ETE", f"{ete.minutes:.1f} min")

# ── Live metrics ────────────────────────────────────────────────────────────

st.markdown("---")
m1, m2, m3 = st.columns(3)
m1.metric("Pressure", f"{pressure:.1f} bar")
m2.metric("Flow Rate", f"{flow_rate:.1f} L/min")
m3.metric("Cylinder", f"{capacity} L ({cylinder_type.split('(')[0].strip()})")

# ── Recommendations ────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📋 Recommendations (Rule-Based)")
st.caption(
    "These are **transparent, rule-based** alerts generated from the simulated data. "
    "They are **not** AI/LLM-generated and do **not** constitute medical advice."
)

for rec in recs:
    with st.expander(f"{rec.icon} {rec.text}", expanded=(alert.level != "Normal")):
        st.markdown(f"**Trigger rule:** {rec.basis}")

# ── ETE formula ─────────────────────────────────────────────────────────────

st.markdown("---")
with st.expander("📐 ETE Calculation Details"):
    st.code(ete.formula_description, language="text")
    st.markdown("**Assumptions (all simplifications for demonstration):**")
    for a in ete.assumptions:
        st.markdown(f"- {a}")
    st.warning(ete.clinical_disclaimer)

# ── Pressure history chart ──────────────────────────────────────────────────

st.markdown("---")
st.subheader("📈 Pressure History")

if st.session_state.sim_started_once and st.session_state.sim_history:
    st.caption("🔴 Live simulation history — synthetic auto-generated data.")
    df = pd.DataFrame(
        st.session_state.sim_history, columns=["Tick (×2 s)", "Pressure (bar)"]
    )
    df = df.set_index("Tick (×2 s)")
else:
    st.caption("Synthetic sample data (seed=42) for chart demonstration only.")
    history = generate_synthetic_history(start_pressure=pressure, points=60)
    df = pd.DataFrame(history, columns=["Minute", "Pressure (bar)"])
    df = df.set_index("Minute")

st.line_chart(df, use_container_width=True)

# ── Architecture ────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("🏗️ Project Architecture")
st.caption("Components marked 🔲 are **planned but not implemented** in this prototype.")

arch_md = """
| # | Component | Status | Description |
|---|-----------|--------|-------------|
| 1 | **Oxygen Sensor (pressure, flow)** | 🔲 Planned | Physical sensors on the cylinder. Not connected. |
| 2 | **ESP32 Microcontroller** | 🔲 Planned | Would read sensors and transmit via Wi-Fi/BLE. |
| 3 | **Cloud / MQTT Broker** | 🔲 Planned | Data transport layer (e.g., AWS IoT, MQTT). |
| 4 | **Python Backend** | ✅ Simulated | `simulation.py` — ETE calc, alerts, recommendations. |
| 5 | **Streamlit Dashboard** | ✅ Running | `app.py` — this page. |
| 6 | **AI Recommendation Module** | ⚙️ Rule-Based | Transparent threshold rules. LLM integration planned. |
"""
st.markdown(arch_md)

st.markdown("""
```
┌──────────────┐    ┌──────────┐    ┌───────────────┐    ┌────────────────┐    ┌────────────┐
│ O₂ Sensors   │───▶│  ESP32   │───▶│ Python Backend│───▶│ ETE & Alert    │───▶│ Dashboard  │
│ (🔲 Planned) │    │(🔲 Plan) │    │ (✅ Simulated)│    │ Engine (✅ Sim)│    │ (✅ Live)  │
└──────────────┘    └──────────┘    └───────────────┘    └────────────────┘    └────────────┘
                                                                                      │
                                                                               ┌──────▼───────┐
                                                                               │Recommendation│
                                                                               │Module (⚙️)   │
                                                                               └──────────────┘
```
""")

# ── Limitations & Safety ────────────────────────────────────────────────────

st.markdown("---")
st.subheader("⚠️ Limitations & Safety Disclaimer")

st.error("""
**This is a software simulation prototype for academic demonstration only.**

1. **No real hardware** — No sensors, ESP32, or IoT devices are connected.
2. **No clinical validation** — ETE and alert thresholds are illustrative, not tested against real cylinder behaviour.
3. **Not a medical device** — This software does not meet any medical device regulatory standard (FDA, CE, etc.).
4. **No patient data** — All values are synthetic inputs from the sidebar sliders.
5. **Clinical decisions** — Oxygen therapy adjustments must **only** be made by qualified healthcare professionals. This tool does not recommend changing a patient's oxygen flow rate or treatment plan.

Do not use this software for actual patient care under any circumstances.
""")

# ── Footer ──────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption(
    "Personalized Healthcare Recommendation System · "
    "College Major Project · Software Simulation Prototype · "
    "Built with Python & Streamlit"
)

# ── Auto-refresh loop (MUST be last) ───────────────────────────────────────
# When the simulation is running, sleep 2 s then advance the tick and rerun.
# This block lives at the very end so all widgets are rendered first.

if st.session_state.sim_running:
    time.sleep(2)

    # ── advance pressure: drop ~2-4 bar per tick with small noise ───────────
    p = st.session_state.sim_pressure
    drop = random.uniform(2.0, 4.0)        # realistic gradual decline
    noise = random.gauss(0, 0.3)
    p = max(p - drop + noise, 0.0)
    st.session_state.sim_pressure = round(p, 1)

    # ── flow-rate small variation around prescribed ─────────────────────────
    f = prescribed_flow + random.gauss(0, 0.3)
    f = max(0.5, min(f, 10.0))
    st.session_state.sim_flow = round(f, 1)

    # ── bookkeeping ─────────────────────────────────────────────────────────
    st.session_state.sim_tick += 1
    st.session_state.sim_history.append(
        (st.session_state.sim_tick, st.session_state.sim_pressure)
    )
    st.session_state.sim_last_update = datetime.now()

    st.rerun()
