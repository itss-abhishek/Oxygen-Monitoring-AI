"""
serial_bridge.py — USB Cable Serial Bridge between ESP32 and OxySense Web Dashboard.

Reads live multi-cylinder telemetry from the ESP32 via USB cable (COM port)
and forwards it directly to the local Flask backend (http://localhost:5000/api/telemetry).

Usage:
    python serial_bridge.py
    python serial_bridge.py --port COM4
"""

import sys
import time
import json
import argparse
import requests
import serial
import serial.tools.list_ports

DASHBOARD_URL = "http://127.0.0.1:5000/api/telemetry"
BAUD_RATE = 115200

def list_available_ports():
    ports = list(serial.tools.list_ports.comports())
    return ports

def detect_esp32_port():
    ports = list_available_ports()
    if not ports:
        return None
    # Prioritize common USB-to-UART chips (CP210x, CH340, FTDI)
    for p in ports:
        desc = (p.description or "").lower()
        if "cp210" in desc or "ch340" in desc or "usb" in desc or "uart" in desc:
            return p.device
    # Otherwise return first available non-Bluetooth port
    for p in ports:
        if "bluetooth" not in (p.description or "").lower():
            return p.device
    return ports[0].device

def main():
    parser = argparse.ArgumentParser(description="OxySense ESP32 USB Serial Bridge")
    parser.add_argument("--port", help="Serial COM port (e.g., COM3, COM4)", default=None)
    parser.add_argument("--baud", help="Baud rate (default: 115200)", type=int, default=BAUD_RATE)
    args = parser.parse_args()

    port_name = args.port or detect_esp32_port()

    print("=" * 66)
    print("  OxySense -- ESP32 USB Cable Telemetry Bridge")
    print(f"  Target Dashboard: {DASHBOARD_URL}")
    print("=" * 66)

    ports = list_available_ports()
    print("Available Serial COM Ports:")
    for p in ports:
        print(f"  - {p.device}: {p.description}")

    if not port_name:
        print("\n[ERROR] No active COM port detected. Please connect your ESP32 via USB cable.")
        sys.exit(1)

    print(f"\n[Connecting] Opening {port_name} at {args.baud} baud...")

    try:
        ser = serial.Serial(port_name, args.baud, timeout=2)
        time.sleep(1.5)  # Allow ESP32 reboot / buffer stabilization
        print(f"[Connected] Successfully connected to {port_name}!")
        print("Listening for 6-cylinder telemetry stream. Press Ctrl+C to exit.\n")
    except Exception as e:
        print(f"\n[ERROR] Could not open {port_name}: {e}")
        print("Tip: Close Arduino Serial Monitor if it is currently open.")
        sys.exit(1)

    packet_count = 0

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            # Check if line is JSON
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                    # Forward to local dashboard
                    res = requests.post(DASHBOARD_URL, json=payload, timeout=2)
                    if res.status_code == 200:
                        packet_count += 1
                        cyls = payload.get("cylinders", [])
                        primary_p = cyls[0].get("pressure_bar") if cyls else payload.get("pressure_bar", "N/A")
                        print(f"[{time.strftime('%H:%M:%S')}] Packet #{packet_count} -> {len(cyls)} Cylinders updated (Cylinder 1: {primary_p} Bar) [HTTP 200]")
                    else:
                        print(f"[{time.strftime('%H:%M:%S')}] Dashboard rejected payload: HTTP {res.status_code}")
                except json.JSONDecodeError:
                    pass
                except requests.exceptions.RequestException as re:
                    print(f"[{time.strftime('%H:%M:%S')}] Dashboard unreachable: {re}. Ensure 'python server.py' is running.")
            else:
                # Debug message from ESP32
                if "OxySense" in line or "Baud" in line or "Wi-Fi" in line:
                    print(f"[ESP32 Boot] {line}")

        except KeyboardInterrupt:
            print("\n[Bridge Stopped] User exited.")
            ser.close()
            break
        except Exception as e:
            print(f"[Bridge Warning] {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
