"""
backend/models.py — SQLAlchemy Database Models for OxySense
IoT-Enabled Smart Oxygen Cylinder Monitoring System with AI-Driven Healthcare Recommendations.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Cylinder(db.Model):
    """
    Cylinder Table:
    Represents physical or simulated hospital oxygen cylinders.
    Stores the latest operational telemetry snapshot for fast querying.
    """
    __tablename__ = "cylinders"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cylinder_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    pressure_bar = db.Column(db.Float, nullable=False, default=0.0)
    flow_rate_lpm = db.Column(db.Float, nullable=False, default=0.0)
    battery_percentage = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="NORMAL")
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Optional clinical metadata to preserve seamless frontend dashboard integration
    ward = db.Column(db.String(100), nullable=True)
    patient = db.Column(db.String(100), nullable=True)
    cylinder_type = db.Column(db.String(50), nullable=True, default="Type E (660 L)")
    capacity_l = db.Column(db.Float, nullable=True, default=660.0)
    data_source = db.Column(db.String(50), nullable=False, default="SIMULATED_DEMO")
    is_simulated = db.Column(db.Boolean, nullable=False, default=True)

    # Relationships (One-to-Many)
    telemetry_records = db.relationship(
        "Telemetry",
        backref="cylinder",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="desc(Telemetry.timestamp)"
    )
    alerts = db.relationship(
        "Alert",
        backref="cylinder",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="desc(Alert.created_at)"
    )

    def to_dict(self):
        """Converts model to dictionary for JSON API responses."""
        p_bar = round(max(0.0, float(self.pressure_bar)), 1)
        p_psi = round(p_bar * 14.5038, 1)
        f_lpm = round(max(0.0, float(self.flow_rate_lpm)), 2)

        # Boyle-Mariotte linear estimation for display
        ete_str = "Estimate unavailable"
        if p_bar > 0 and f_lpm > 0:
            rem_l = (self.capacity_l or 660.0) * (p_bar / 200.0)
            mins = rem_l / f_lpm
            h = int(mins // 60)
            m = int(mins % 60)
            ete_str = f"{h}h {m:02d}m"
        elif p_bar <= 0:
            ete_str = "0h 00m (Exhausted)"

        return {
            "id": self.cylinder_id,
            "db_id": self.id,
            "cylinder_id": self.cylinder_id,
            "ward": self.ward or "Unassigned Ward",
            "patient": self.patient or "General Ward Reserve",
            "type": self.cylinder_type or "Type E (660 L)",
            "capacity_l": self.capacity_l or 660.0,
            "pressure_bar": p_bar,
            "pressure_psi": p_psi,
            "flow_lpm": f_lpm,
            "flow_rate_lpm": f_lpm,
            "battery_pct": self.battery_percentage,
            "battery_percentage": self.battery_percentage,
            "status": self.status,
            "ete": ete_str,
            "data_source": self.data_source,
            "is_simulated": self.is_simulated,
            "last_updated": self.last_updated.strftime("%Y-%m-%d %H:%M:%S") if self.last_updated else "Just now"
        }


class Telemetry(db.Model):
    """
    Telemetry Table:
    Stores historical time-series telemetry points for trend analysis,
    medical waveforms, and consumption auditing.
    """
    __tablename__ = "telemetry"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cylinder_db_id = db.Column(db.Integer, db.ForeignKey("cylinders.id", ondelete="CASCADE"), nullable=False, index=True)
    cylinder_id = db.Column(db.String(50), nullable=False, index=True)
    pressure_bar = db.Column(db.Float, nullable=False)
    flow_rate_lpm = db.Column(db.Float, nullable=False)
    battery_percentage = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_simulated = db.Column(db.Boolean, nullable=False, default=True)
    data_source = db.Column(db.String(50), nullable=False, default="SIMULATED_DEMO")

    def to_dict(self):
        """Converts model to dictionary for JSON API responses."""
        p_bar = round(max(0.0, float(self.pressure_bar)), 1)
        return {
            "id": self.id,
            "cylinder_id": self.cylinder_id,
            "pressure_bar": p_bar,
            "pressure_psi": round(p_bar * 14.5038, 0),
            "flow_lpm": round(max(0.0, float(self.flow_rate_lpm)), 2),
            "flow_rate_lpm": round(max(0.0, float(self.flow_rate_lpm)), 2),
            "battery_percentage": self.battery_percentage,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "",
            "iso_time": self.timestamp.isoformat() if self.timestamp else "",
            "is_simulated": self.is_simulated,
            "data_source": self.data_source
        }


class Alert(db.Model):
    """
    Alert Table:
    Stores clinical warnings, threshold breaches, and operational notifications.
    """
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cylinder_db_id = db.Column(db.Integer, db.ForeignKey("cylinders.id", ondelete="CASCADE"), nullable=True, index=True)
    cylinder_id = db.Column(db.String(50), nullable=False, index=True)
    alert_type = db.Column(db.String(50), nullable=False)  # "CRITICAL", "WARNING", "INFO"
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_resolved = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        """Converts model to dictionary for JSON API responses."""
        return {
            "id": f"ALT-{self.id}",
            "db_id": self.id,
            "cylinder_id": self.cylinder_id,
            "alert_type": self.alert_type,
            "severity": self.alert_type,
            "title": f"{self.alert_type.title()} Alert — {self.cylinder_id}",
            "message": self.message,
            "description": self.message,
            "timestamp": self.created_at.strftime("%H:%M:%S") if self.created_at else "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "is_resolved": self.is_resolved,
            "acknowledged": self.is_resolved
        }
