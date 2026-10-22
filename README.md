# OxySense — Smart Oxygen Cylinder Monitoring System

> **IoT-Enabled Smart Oxygen Cylinder Monitoring System with AI-Driven Personalized Healthcare Recommendations**  
> B.Tech Major Project Software Simulation & Web Dashboard

---

## 🔬 System Overview & Context

OxySense is a responsive IoT healthcare monitoring dashboard engineered for hospital wards. It continuously monitors oxygen cylinder pressure and gas flow, predicts Estimated Time to Empty (ETE), classifies alerts, and provides operational recommendations for cylinder replacement logistics.

**Key Clarifications for Project Evaluation:**
- **Current Mode:** High-fidelity software simulation.
- **Hardware Integration:** Architecture ready for ESP32 and digital pressure/flow transducers via `POST /api/telemetry`.
- **AI Recommendation Engine:** Operates via deterministic clinical logistics rules offline, with optional cloud LLM acceleration (Groq Llama-3.3-70B).
- **Safety Boundary:** Strictly operational; never prescribes medical oxygen dosage or patient treatment.

---

## 🛠️ Technology Stack

- **Frontend:** Semantic HTML5, Modular CSS3 (dark navy sidebar + clean light theme), Vanilla JavaScript (ES6+), Chart.js 4.4, Lucide Icons.
- **Backend:** Python 3 + Flask REST API.
- **Data Transport:** JSON REST endpoints with ready-to-wire MQTT/HTTP ESP32 ingestion.
- **Testing:** Pytest automated test suite.

---

## 🚀 Quick Start Guide (Windows)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
python -m pytest test_backend.py -v
```

### 3. Launch Dashboard Server
```bash
python server.py
```
Open **[http://localhost:5000](http://localhost:5000)** in your web browser.

*(Alternative port: `set PORT=5050 && python server.py`)*

---

## 🧭 Dashboard Navigation (7 Modular Views)

| # | View | Description |
|---|------|-------------|
| 1 | **Overview** | Top metric cards (Pressure PSI/bar, Flow L/min, ETE, Status badge), real-time Chart.js trends, AI insight summary, and fleet preview. |
| 2 | **Live Monitoring** | High-frequency telemetry waveform, sensor calibration stats, and stream pause/resume controls. |
| 3 | **Cylinder Fleet** | Filterable & searchable hospital inventory (ICU, ER, General Ward) with interactive "View Details" modal. |
| 4 | **Alerts & Notifications** | Active alarms with Acknowledge buttons, logged alert history, and threshold documentation. |
| 5 | **AI Insights** | Operational suggestions, detected monitoring conditions, rule triggers, and Groq LLM integration. |
| 6 | **Historical Reports** | Audit logs table with timestamps and **Export CSV Report** button. |
| 7 | **System Settings** | Configurable test thresholds (Warning/Critical bar), cylinder capacity presets, and display unit toggles (PSI/Bar). |

---

## 🎮 Simulation Controls (Demonstration Panel)

Located directly below the header on all views:
- **Simulate Low Supply:** Drops pressure to 42 bar (609 PSI) to trigger the Low Supply warning alert and ETE countdown.
- **Simulate Sensor Fault:** Simulates ESP32 signal loss, displays "Estimate unavailable", and flags disconnected state.
- **Reset to Normal:** Restores nominal cylinder pressure (160 bar / 2320 PSI) and clears active alarms.

---

## 🤖 Optional Groq LLM Cloud Setup

To enable Groq cloud AI models:
1. Copy `.env.example` to `.env`
2. Add your Groq API key:
   ```env
   GROQ_API_KEY=gsk_your_groq_api_key_here
   ```
3. Restart `python server.py`. If omitted, OxySense automatically runs deterministic rule-based analysis.

---

## 📡 ESP32 Hardware Integration Guide

To connect physical ESP32 hardware in the future, program the microcontroller to send an HTTP POST:

```http
POST /api/telemetry HTTP/1.1
Host: <your-server-ip>:5000
Content-Type: application/json

{
  "cylinder_id": "CYL-ICU-101",
  "pressure_bar": 142.5,
  "flow_lpm": 2.1
}
```
The dashboard will automatically accept the payload and reflect live hardware measurements.

---

## ⚠️ Limitations & Safety Disclaimer

1. **Academic Prototype:** This software prototype is intended for academic evaluation.
2. **Clinical Authority:** Oxygen flow rates, titration, and therapy adjustments must **only** be conducted by licensed healthcare professionals.
3. **No Direct Hardware:** All default demonstration values are synthetic unless the ESP32 endpoint is explicitly fed.
