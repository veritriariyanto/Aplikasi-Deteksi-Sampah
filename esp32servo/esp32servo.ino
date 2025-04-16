#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>

// === WiFi ===
const char* ssid = "Novi";
const char* password = "Novi12345678";

// === Ubidots MQTT ===
#define UBIDOTS_TOKEN "BBUS-2c8M1ZnjPEQwnhTTAJ1bTupp5JVZWo"
#define DEVICE_LABEL "esp32-servo"
#define VARIABLE_ORGANIK "organik"
#define VARIABLE_ANORGANIK "anorganik"
#define VARIABLE_KONTROL "kontrol"  // variabel untuk kontrol servo (switch)
const char* mqtt_server = "industrial.api.ubidots.com";
const int mqtt_port = 1883;

// === Servo ===
Servo servoKiri;
Servo servoKanan;

// === MQTT Client ===
WiFiClient wifiClient;
PubSubClient client(wifiClient);

// === Fungsi Kirim ke Ubidots ===
void publishToUbidots(String jenis) {
  String topic = String("/v1.6/devices/") + DEVICE_LABEL;
  String payload;

  if (jenis == "organik") { 
    payload = "{\"" + String(VARIABLE_ORGANIK) + "\": {\"value\": 1}}";
  } else if (jenis == "anorganik") {
    payload = "{\"" + String(VARIABLE_ANORGANIK) + "\": {\"value\": 1}}";
  }

  client.publish(topic.c_str(), payload.c_str());
  Serial.println("📤 Dikirim ke Ubidots: " + payload);
}

// === Fungsi Kontrol Servo ===
void handleJenisSampah(String jenis) {
  Serial.println("🟢 Jenis diterima: " + jenis);

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
}

// === Callback dari Ubidots MQTT ===
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("📥 Perintah dari topic: ");
  Serial.println(topic);

  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println("🔸 Pesan: " + message);

  // Cek payload untuk nilai switch
  if (message == "0.0") {
    handleJenisSampah("organik");
    publishToUbidots("organik");
  } else if (message == "1.0") {
    handleJenisSampah("anorganik");
    publishToUbidots("anorganik");
  }
}

// === Reconnect MQTT ===
void reconnect() {
  while (!client.connected()) {
    Serial.print("🔌 Menghubungkan ke Ubidots...");
    String clientId = "ESP32Client-" + String(random(0xffff), HEX);
    if (client.connect(clientId.c_str(), UBIDOTS_TOKEN, "")) {
      Serial.println("✅ Terhubung");

      // Subscribe ke variabel kontrol (switch)
      String subTopic = String("/v1.6/devices/") + DEVICE_LABEL + "/" + VARIABLE_KONTROL + "/lv";
      client.subscribe(subTopic.c_str());
      Serial.println("📡 Subscribe ke: " + subTopic);
    } else {
      Serial.print("❌ Gagal, code=");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

// === Setup ===
void setup() {
  Serial.begin(115200);

  // Setup servo
  servoKiri.attach(18);
  servoKanan.attach(19);
  servoKiri.write(90);
  servoKanan.write(90);
  delay(1000);  // Stabilkan posisi awal servo

  // Koneksi WiFi
  WiFi.begin(ssid, password);
  Serial.print("🔌 Menghubungkan ke WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ Terhubung ke WiFi");
  Serial.println("📡 IP ESP32: " + WiFi.localIP().toString());

  // MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

// === Loop utama ===
void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}
