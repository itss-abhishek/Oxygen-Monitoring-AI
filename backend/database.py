"""
backend/database.py — Database Initialization and Safe Demonstration Data Seeding
IoT-Enabled Smart Oxygen Cylinder Monitoring System with AI-Driven Healthcare Recommendations.
"""

import os
import time
from datetime import datetime, timedelta
from backend.models import db, Cylinder, Telemetry, Alert

# Base project path where oxygen_monitoring.db resides
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "oxygen_monitoring.db")

# 6 Sample Cylinders with clearly designated simulated healthcare demo data
SAMPLE_CYLINDERS = [
    {
        "cylinder_id": "CYL-ICU-101",
        "ward": "ICU — Bed 04",
        "patient": "Patient Ref #4021",
        "cylinder_type": "Type E (660 L)",
        "capacity_l": 660.0,
        "pressure_bar": 155.0,
        "flow_rate_lpm": 2.0,
        "battery_percentage": 94,
        "status": "NORMAL"
    },
    {
        "cylinder_id": "CYL-ER-204",
        "ward": "Emergency Dept — Trauma Bay 1",
        "patient": "Patient Ref #4088",
        "cylinder_type": "Type M (3450 L)",
        "capacity_l": 3450.0,
        "pressure_bar": 42.0,
        "flow_rate_lpm": 4.5,
        "battery_percentage": 82,
        "status": "LOW_PRESSURE"
    },
    {
        "cylinder_id": "CYL-GW-302",
        "ward": "General Ward 2 — Bed 12",
        "patient": "Patient Ref #3991",
        "cylinder_type": "Type D (415 L)",
        "capacity_l": 415.0,
        "pressure_bar": 190.0,
        "flow_rate_lpm": 1.5,
        "battery_percentage": 98,
        "status": "NORMAL"
    },
    {
        "cylinder_id": "CYL-REC-108",
        "ward": "Post-Op Recovery — Bed 08",
        "patient": "Patient Ref #4102",
        "cylinder_type": "Type E (660 L)",
        "capacity_l": 660.0,
        "pressure_bar": 18.0,
        "flow_rate_lpm": 3.0,
        "battery_percentage": 76,
        "status": "CRITICAL"
    },
    {
        "cylinder_id": "CYL-PED-044",
        "ward": "Pediatric Ward — Room 3",
        "patient": "Pediatric Ref #1209",
        "cylinder_type": "Type E (660 L)",
        "capacity_l": 660.0,
        "pressure_bar": 140.0,
        "flow_rate_lpm": 1.0,
        "battery_percentage": 91,
        "status": "NORMAL"
    },
    {
        "cylinder_id": "CYL-TRANS-012",
        "ward": "Ambulance Transit Bay",
        "patient": "Transit Ref #5501",
        "cylinder_type": "Type D (415 L)",
        "capacity_l": 415.0,
        "pressure_bar": 95.0,
        "flow_rate_lpm": 2.5,
        "battery_percentage": 88,
        "status": "NORMAL"
    }
]


def init_db(app):
    """
    Safely initializes SQLite database and creates missing tables
    without dropping or modifying any existing user records.
    """
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if "sqlalchemy" not in app.extensions:
        db.init_app(app)

    with app.app_context():
        # db.create_all() only creates tables that do NOT already exist.
        # It never deletes existing tables or records.
        db.create_all()
        seed_initial_cylinders()
        prune_telemetry_older_than(hours=24, force=True)


_last_prune_ts = 0.0


def prune_telemetry_older_than(hours: int = 24, force: bool = False) -> int:
    """
    Automatically purges telemetry records older than specified hours (default 24h).
    Ensures the SQLite database stores only the last 24 hours of clinical data.
    Throttled to run at most once every 5 minutes unless force=True.
    """
    global _last_prune_ts
    now_ts = time.time()
    if not force and (now_ts - _last_prune_ts < 300):
        return 0

    _last_prune_ts = now_ts
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    try:
        deleted = Telemetry.query.filter(Telemetry.timestamp < cutoff).delete()
        db.session.commit()
        if deleted > 0:
            print(f"[OxySense Retention] Pruned {deleted} telemetry records older than {hours} hours.")
        return deleted
    except Exception as e:
        db.session.rollback()
        return 0


def seed_initial_cylinders():
    """
    Creates six sample demonstration cylinders ONLY when they do not already exist.
    All readings are explicitly marked as SIMULATED demonstration data.
    """
    created_count = 0
    now = datetime.utcnow()

    for item in SAMPLE_CYLINDERS:
        existing = Cylinder.query.filter_by(cylinder_id=item["cylinder_id"]).first()
        if not existing:
            cyl = Cylinder(
                cylinder_id=item["cylinder_id"],
                ward=item["ward"],
                patient=item["patient"],
                cylinder_type=item["cylinder_type"],
                capacity_l=item["capacity_l"],
                pressure_bar=item["pressure_bar"],
                flow_rate_lpm=item["flow_rate_lpm"],
                battery_percentage=item["battery_percentage"],
                status=item["status"],
                data_source="SIMULATED_DEMO",
                is_simulated=True,
                last_updated=now
            )
            db.session.add(cyl)
            db.session.flush()  # Populates cyl.id for relationship

            # Seed initial telemetry history points for this cylinder
            p_curr = item["pressure_bar"]
            f_curr = item["flow_rate_lpm"]
            for i in range(10, -1, -1):
                pt_time = now - timedelta(minutes=i * 2)
                p_sample = round(min(200.0, max(0.0, p_curr + (i * 0.2))), 1)
                db.session.add(
                    Telemetry(
                        cylinder_db_id=cyl.id,
                        cylinder_id=cyl.cylinder_id,
                        pressure_bar=p_sample,
                        flow_rate_lpm=f_curr,
                        battery_percentage=item["battery_percentage"],
                        timestamp=pt_time,
                        is_simulated=True,
                        data_source="SIMULATED_DEMO"
                    )
                )

            # If cylinder has critical/warning status, seed corresponding alert
            if item["status"] == "CRITICAL":
                db.session.add(
                    Alert(
                        cylinder_db_id=cyl.id,
                        cylinder_id=cyl.cylinder_id,
                        alert_type="CRITICAL",
                        message=f"Critical depletion on {cyl.cylinder_id}: Pressure at {cyl.pressure_bar:.1f} bar. Immediate cylinder exchange required.",
                        created_at=now,
                        is_resolved=False
                    )
                )
            elif item["status"] == "LOW_PRESSURE":
                db.session.add(
                    Alert(
                        cylinder_db_id=cyl.id,
                        cylinder_id=cyl.cylinder_id,
                        alert_type="WARNING",
                        message=f"Low cylinder supply on {cyl.cylinder_id}: Pressure at {cyl.pressure_bar:.1f} bar (below 50 bar threshold).",
                        created_at=now,
                        is_resolved=False
                    )
                )

            created_count += 1

    # Seed initial system info alert if no alerts exist
    if not Alert.query.first():
        db.session.add(
            Alert(
                cylinder_db_id=None,
                cylinder_id="SYSTEM",
                alert_type="INFO",
                message="SQLite database initialized with simulated hospital cylinder fleet demonstration data.",
                created_at=now,
                is_resolved=True
            )
        )

    if created_count > 0:
        db.session.commit()
        print(f"[OxySense DB] Seeded {created_count} demonstration cylinders into oxygen_monitoring.db")
    else:
        db.session.commit()
