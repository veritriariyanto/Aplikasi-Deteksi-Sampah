#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

const char* ssid = "Pak Kuncoro";
const char* password = "sakarepmu";

// Inisialisasi Web Server
WebServer server(80);

// Servo
Servo servoKiri;
Servo servoKanan;

void setup() {
  Serial.begin(115200);


  // Koneksi ke WiFi
  WiFi.begin(ssid, password);
  Serial.print("Menghubungkan ke WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nTerhubung ke WiFi!");
  Serial.print("Alamat IP: ");
  Serial.println(WiFi.localIP());

  // Servo setup
  servoKiri.attach(18);
  servoKanan.attach(19);
  servoKiri.write(90);
  servoKanan.write(90);

  // Endpoint POST /sampah
  server.on("/sampah", HTTP_POST, []() {
    if (server.hasArg("plain")) {
      DynamicJsonDocument doc(1024);
      DeserializationError error = deserializeJson(doc, server.arg("plain"));
      if (!error) {
        String jenis = doc["jenis"];
        Serial.println("Jenis diterima: " + jenis);

        // Kontrol servo
        if (jenis == "organik") {
          servoKiri.write(0);
          servoKanan.write(180);
        } else if (jenis == "anorganik") {
          servoKiri.write(180);
          servoKanan.write(0);
        }

        delay(2000);
        servoKiri.write(90);
        servoKanan.write(90);

        server.send(200, "application/json", "{\"status\": \"ok\"}");
      } else {
        server.send(400, "application/json", "{\"error\": \"Bad JSON\"}");
      }
    } else {
      server.send(400, "application/json", "{\"error\": \"No body\"}");
    }
  });

  server.begin();
}

void loop() {
  server.handleClient();
}