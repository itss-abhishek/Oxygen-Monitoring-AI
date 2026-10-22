"""
server.py — Main Entrypoint for OxySense Web Dashboard.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 66)
    print("  OxySense -- Smart Oxygen Cylinder Monitoring Dashboard")
    print(f"  Live at: http://localhost:{port}")
    print("=" * 66)
    app.run(host="0.0.0.0", port=port, debug=False)
