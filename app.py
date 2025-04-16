import streamlit as st
import cv2
import numpy as np
import tensorflow as tf
import requests
import time
import json
import paho.mqtt.client as mqtt

# Konfigurasi halaman       
st.set_page_config(page_title="Deteksi Sampah (ESP32-CAM)", layout="wide")
st.title("🗑️ Deteksi Sampah Otomatis via Kamera IP (ESP32-CAM)")

# === Konfigurasi ESP32-CAM ===
ESP32_CAM_URL = "http://192.168.100.137/capture"  # Ganti dengan IP ESP32-CAM

# === Konfigurasi MQTT Ubidots ===
UBIDOTS_TOKEN = "BBUS-2c8M1ZnjPEQwnhTTAJ1bTupp5JVZWo"
DEVICE_LABEL = "esp32-servo"
VARIABLE_KONTROL = "kontrol"

MQTT_BROKER = "industrial.api.ubidots.com"
MQTT_PORT = 1883
MQTT_TOPIC = f"/v1.6/devices/{DEVICE_LABEL}"

# Setup MQTT client untuk Ubidots
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(UBIDOTS_TOKEN, password="")

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    st.sidebar.success(f"📡 Terhubung ke Ubidots MQTT")
except Exception as e:
    st.sidebar.error(f"❌ Gagal koneksi ke MQTT broker: {e}")

# Load model TFLite
@st.cache_resource
def load_model():
    interpreter = tf.lite.Interpreter(model_path="model.tflite")
    interpreter.allocate_tensors()
    return interpreter

# Load label
@st.cache_data
def load_labels():
    with open("labels.txt", "r") as f:
        return [line.strip().split(" ", 1)[1] for line in f.readlines()]

interpreter = load_model()
labels = load_labels()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
input_shape = input_details[0]['shape']

st.sidebar.write(f"Input model shape: {input_shape}")
st.sidebar.info("Model mendeteksi 3 kelas: organik, anorganik, dan tidakterdeteksi")

# Placeholder tampilan
image_placeholder = st.empty()
label_placeholder = st.empty()
chart_placeholder = st.empty()

# Tracking deteksi terakhir
last_sent = {"label": None, "timestamp": 0}
COOLDOWN_PERIOD = 15  # detik

# Fungsi ambil gambar dari ESP32-CAM
def get_snapshot(url=ESP32_CAM_URL):
    try:
        resp = requests.get(url, timeout=3)
        img_array = np.asarray(bytearray(resp.content), dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return frame
    except Exception as e:
        st.error(f"❌ Gagal ambil gambar dari kamera: {e}")
        return None

# Fungsi kirim data ke Ubidots MQTT
def kirim_mqtt(label):
    if label not in ["organik", "anorganik"]:
        return
    
    value = 0 if label == "organik" else 1
    payload = json.dumps({VARIABLE_KONTROL: value})
    
    result = mqtt_client.publish(MQTT_TOPIC, payload)
    if result.rc == 0:
        print(f"📤 Terkirim ke Ubidots MQTT: {payload}")
    else:
        print(f"❌ Gagal kirim MQTT ke Ubidots")

# Fungsi prediksi
def predict_and_send(frame):
    img = cv2.resize(frame, (input_shape[1], input_shape[2]))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    if input_shape[-1] == 1:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        img = np.expand_dims(img, axis=-1)
    
    img = np.expand_dims(img, axis=0)

    if input_details[0]['dtype'] == np.uint8:
        img = img.astype(np.uint8)
    else:
        img = img.astype(np.float32) / 255.0

    interpreter.set_tensor(input_details[0]['index'], img)
    interpreter.invoke()
    
    prediction = interpreter.get_tensor(output_details[0]['index'])[0]

    if output_details[0]['dtype'] == np.uint8:
        scale, zero_point = output_details[0]['quantization']
        prediction = (prediction.astype(np.float32) - zero_point) * scale

    class_id = int(np.argmax(prediction))
    confidence = float(prediction[class_id])
    label = labels[class_id].lower()
    
    return label, confidence, prediction

# Loop utama
while True:
    frame = get_snapshot()
    if frame is None:
        break

    label, confidence, prediction = predict_and_send(frame)
    current_time = time.time()

    can_send = (
        current_time - last_sent["timestamp"] > COOLDOWN_PERIOD or 
        label != last_sent["label"]
    )
    
    if confidence > 0.5 and label in ["organik", "anorganik"] and can_send:
        try:
            kirim_mqtt(label)
            st.success(f"✅ Terkirim ke ESP32 via Ubidots MQTT: {label} pada {time.strftime('%H:%M:%S')}")
            last_sent["label"] = label
            last_sent["timestamp"] = current_time
        except Exception as e:
            st.error(f"❌ Gagal kirim MQTT: {e}")

    if label == "tidakterdeteksi" and confidence > 0.5:
        label_placeholder.warning("⚠️ Tidak ada sampah terdeteksi")
    else:
        label_placeholder.empty()

    if label in ["organik", "anorganik"] and label == last_sent["label"]:
        remaining_cooldown = COOLDOWN_PERIOD - (current_time - last_sent["timestamp"])
        # if remaining_cooldown > 0:
        #     st.sidebar.info(f"Cooldown: {remaining_cooldown:.1f} detik sebelum kirim {label} lagi")

    image_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB", 
                            caption=f"Deteksi: {label} ({confidence:.2f})")

    chart_data = {labels[i]: float(prediction[i]) for i in range(len(labels))}
    sorted_chart = sorted(chart_data.items(), key=lambda x: x[1], reverse=True)
    chart_placeholder.bar_chart(dict(sorted_chart))

    time.sleep(7)
