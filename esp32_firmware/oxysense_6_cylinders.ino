/*
 * ==============================================================================
 * OxySense — ESP32 Smart Oxygen Cylinder Monitoring System (6-Cylinder Firmware)
 * ==============================================================================
 * 
 * Hardware:
 *   - ESP32 Development Board (NodeMCU / WROOM-32)
 *   - USB Cable to Laptop
 *   - Optional: Pressure sensor or Potentiometer on GPIO 34 (ADC1)
 *   - Built-in status LED on GPIO 2
 *
 * How It Works:
 *   1. Reads real hardware sensor (or potentiometer) on GPIO 34 for Cylinder 1.
 *   2. Generates telemetry for the complete 6-cylinder hospital ward fleet.
 *   3. Transmits telemetry every 2 seconds via:
 *        A) USB Cable (Serial JSON at 115200 baud)
 *        B) Wi-Fi HTTP POST (if Wi-Fi credentials are enabled)
 * ==============================================================================
 */

#include <Arduino.h>
#include "BluetoothSerial.h"

BluetoothSerial SerialBT;

// ------------------------------------------------------------------------------
// Optional Wi-Fi Configuration (Set ENABLE_WIFI to true if using Wi-Fi)
// ------------------------------------------------------------------------------
#define ENABLE_WIFI false

#if ENABLE_WIFI
  #include <WiFi.h>
  #include <HTTPClient.h>
  const char* WIFI_SSID     = "YOUR_WIFI_NAME";
  const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
  const char* SERVER_URL    = "http://192.168.1.9:5000/api/telemetry"; // Your laptop IP
#endif

// ------------------------------------------------------------------------------
// Pin Definitions
// ------------------------------------------------------------------------------
const int SENSOR_PIN = 34;   // Analog Input (ADC1) for Pressure Sensor / Potentiometer
const int LED_PIN    = 2;    // Built-in Blue LED for status blinking

// ------------------------------------------------------------------------------
// Cylinder Structure
// ------------------------------------------------------------------------------
struct CylinderNode {
  const char* id;
  float pressure_bar;
  float flow_lpm;
  int battery_pct;
};

// 6 Hospital Cylinders Fleet
CylinderNode fleet[6] = {
  { "CYL-ICU-101",   155.0, 2.0, 94 }, // ICU Bed 04 (Monitored via Pin 34)
  { "CYL-ER-204",     42.0, 4.5, 85 }, // Emergency Trauma Bay (Low supply)
  { "CYL-GW-302",    190.0, 1.5, 98 }, // General Ward 2
  { "CYL-REC-108",    18.0, 3.0, 76 }, // Post-Op Recovery (Critical)
  { "CYL-PED-044",   140.0, 1.0, 91 }, // Pediatric Ward 3
  { "CYL-TRANS-012",  95.0, 2.5, 88 }  // Ambulance Transit Bay
};

unsigned long lastSendTime = 0;
const unsigned long SEND_INTERVAL_MS = 2000; // Send every 2 seconds

// ------------------------------------------------------------------------------
// Setup
// ------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  SerialBT.begin("OxySense-ESP32");
  Serial.println("Bluetooth Serial started: OxySense-ESP32");
  pinMode(LED_PIN, OUTPUT);
  pinMode(SENSOR_PIN, INPUT);

  delay(1000);
  Serial.println();
  Serial.println("=================================================");
  Serial.println("  OxySense ESP32 6-Cylinder Firmware Initialized");
  Serial.println("  Baud Rate: 115200 | Sensor Pin: GPIO 34");
  Serial.println("=================================================");

#if ENABLE_WIFI
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[Wi-Fi] Connected! IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n[Wi-Fi] Not connected. Falling back to USB Serial mode.");
  }
#endif
}

// ------------------------------------------------------------------------------
// Loop
// ------------------------------------------------------------------------------
void loop() {
  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;

    // 1. Read Analog Sensor on GPIO 34 for Cylinder 1 (CYL-ICU-101)
    int rawAnalog = analogRead(SENSOR_PIN); // 0 to 4095
    if (rawAnalog > 50) {
      // Map analog input to 0 - 200 Bar (approx 0 - 2900 PSI)
      fleet[0].pressure_bar = (float)map(rawAnalog, 0, 4095, 0, 2000) / 10.0;
    } else {
      // Gentle drift simulation if no physical sensor attached to pin
      fleet[0].pressure_bar -= 0.05;
      if (fleet[0].pressure_bar < 20.0) fleet[0].pressure_bar = 160.0;
    }

    // Gentle realistic physiological oscillation on fleet cylinders with strict clinical bounds
    float jitter1 = (float)(random(-2, 3)) / 10.0;
    fleet[1].pressure_bar = constrain(fleet[1].pressure_bar + jitter1, 35.0, 48.0); // Emergency Bay (Low Supply 35-48 Bar)

    float jitter2 = (float)(random(-2, 3)) / 10.0;
    fleet[2].pressure_bar = constrain(fleet[2].pressure_bar + jitter2, 175.0, 195.0); // General Ward (Nominal 175-195 Bar)

    fleet[3].pressure_bar -= 0.02; 
    if (fleet[3].pressure_bar < 12.0) fleet[3].pressure_bar = 22.0; // Post-Op Recovery (Critical 12-22 Bar)

    // Safety guard: ensure every cylinder in fleet is strictly non-negative
    for (int i = 0; i < 6; i++) {
      if (fleet[i].pressure_bar < 0.0) fleet[i].pressure_bar = 0.0;
    }

    // 2. Build Multi-Cylinder JSON Payload
    String json = "{\"cylinders\":[";
    for (int i = 0; i < 6; i++) {
      json += "{";
      json += "\"cylinder_id\":\"" + String(fleet[i].id) + "\",";
      json += "\"pressure_bar\":" + String(fleet[i].pressure_bar, 1) + ",";
      json += "\"flow_lpm\":" + String(fleet[i].flow_lpm, 1) + ",";
      json += "\"battery_pct\":" + String(fleet[i].battery_pct);
      json += "}";
      if (i < 5) json += ",";
    }
    json += "]}";

    // 3. Output to USB Serial & Bluetooth Serial
    Serial.println(json);
    SerialBT.println(json);

    // 4. Blink Status LED
    digitalWrite(LED_PIN, HIGH);
    delay(40);
    digitalWrite(LED_PIN, LOW);

#if ENABLE_WIFI
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(SERVER_URL);
      http.addHeader("Content-Type", "application/json");
      int httpCode = http.POST(json);
      if (httpCode > 0) {
        // Serial.printf("[HTTP] POST response: %d\n", httpCode);
      }
      http.end();
    }
#endif
  }
}
