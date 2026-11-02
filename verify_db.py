import sqlite3

def verify():
    con = sqlite3.connect("oxygen_monitoring.db")
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("Tables in oxygen_monitoring.db:", tables)
    
    cylinders = cur.execute("SELECT id, cylinder_id, pressure_bar, flow_rate_lpm, status, is_simulated, data_source FROM cylinders").fetchall()
    print(f"\nCylinders ({len(cylinders)} total):")
    for c in cylinders:
        print(f"  [ID {c[0]}] {c[1]}: {c[2]} bar | {c[3]} L/min | Status: {c[4]} | Simulated: {c[5]} | Source: {c[6]}")

    telemetry_count = cur.execute("SELECT count(*) FROM telemetry").fetchone()[0]
    print(f"\nTelemetry records count: {telemetry_count}")

    alerts = cur.execute("SELECT id, cylinder_id, alert_type, message, is_resolved FROM alerts").fetchall()
    print(f"\nAlerts ({len(alerts)} total):")
    for a in alerts:
        print(f"  [ALT-{a[0]}] {a[1]} | {a[2]} | Resolved: {bool(a[4])} | {a[3][:60]}")

    con.close()

if __name__ == "__main__":
    verify()
