"""
backend/mock_data.py — Mock inventory of hospital oxygen cylinders and fleet registry.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any

MOCK_CYLINDERS: List[Dict[str, Any]] = [
    {
        "id": "CYL-ICU-101",
        "ward": "ICU — Bed 04",
        "patient": "Patient Ref #4021",
        "type": "Type E (660 L)",
        "capacity_l": 660,
        "pressure_bar": 155,
        "pressure_psi": 2248,
        "flow_lpm": 2.0,
        "ete": "4h 15m",
        "status": "NORMAL",
        "battery_pct": 94,
        "sensor_id": "ESP32-NODE-A1",
        "last_updated": "Just now",
        "assigned_staff": "Nurse Priya"
    },
    {
        "id": "CYL-ER-204",
        "ward": "Emergency Dept — Trauma Bay 1",
        "patient": "Patient Ref #4088",
        "type": "Type M (3450 L)",
        "capacity_l": 3450,
        "pressure_bar": 38,
        "pressure_psi": 551,
        "flow_lpm": 5.0,
        "ete": "1h 05m",
        "status": "LOW_PRESSURE",
        "battery_pct": 82,
        "sensor_id": "ESP32-NODE-B2",
        "last_updated": "2 min ago",
        "assigned_staff": "Dr. Sharma"
    },
    {
        "id": "CYL-GW-302",
        "ward": "General Ward 2 — Bed 12",
        "patient": "Patient Ref #3991",
        "type": "Type D (415 L)",
        "capacity_l": 415,
        "pressure_bar": 190,
        "pressure_psi": 2756,
        "flow_lpm": 1.5,
        "ete": "6h 20m",
        "status": "NORMAL",
        "battery_pct": 98,
        "sensor_id": "ESP32-NODE-C3",
        "last_updated": "1 min ago",
        "assigned_staff": "Nurse Anita"
    },
    {
        "id": "CYL-REC-108",
        "ward": "Post-Op Recovery — Bed 08",
        "patient": "Patient Ref #4102",
        "type": "Type E (660 L)",
        "capacity_l": 660,
        "pressure_bar": 16,
        "pressure_psi": 232,
        "flow_lpm": 3.0,
        "ete": "0h 35m",
        "status": "CRITICAL",
        "battery_pct": 76,
        "sensor_id": "ESP32-NODE-D4",
        "last_updated": "Just now",
        "assigned_staff": "Dr. Mehta"
    },
    {
        "id": "CYL-PED-044",
        "ward": "Pediatric Ward — Room 3",
        "patient": "Patient Ref #4155",
        "type": "Type D (415 L)",
        "capacity_l": 415,
        "pressure_bar": 140,
        "pressure_psi": 2030,
        "flow_lpm": 1.0,
        "ete": "9h 40m",
        "status": "NORMAL",
        "battery_pct": 91,
        "sensor_id": "ESP32-NODE-E5",
        "last_updated": "5 min ago",
        "assigned_staff": "Nurse Rita"
    },
    {
        "id": "CYL-TRANS-012",
        "ward": "Ambulance Transit Bay",
        "patient": "En Route Transit",
        "type": "Type E (660 L)",
        "capacity_l": 660,
        "pressure_bar": 0,
        "pressure_psi": 0,
        "flow_lpm": 0.0,
        "ete": "Unavailable",
        "status": "SENSOR_DISCONNECTED",
        "battery_pct": 14,
        "sensor_id": "ESP32-NODE-F6",
        "last_updated": "18 min ago",
        "assigned_staff": "Paramedic Singh"
    }
]
