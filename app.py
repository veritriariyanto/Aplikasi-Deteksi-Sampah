import streamlit as st
import cv2
import numpy as np
import tensorflow as tf
import requests
import time

# Konfigurasi halaman
st.set_page_config(page_title="Deteksi Sampah (ESP32-CAM)", layout="wide")
st.title("🗑️ Deteksi Sampah Otomatis via Kamera IP (ESP32-CAM)")

ESP32_CAM_URL = "http://192.168.1.115/capture"  # Ganti dengan IP ESP32-CAM
ESP32_SERVO_URL = "http://192.168.1.119/sampah"  # Ganti dengan IP ESP32 servo kamu

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

st.sidebar.success("📷 Kamera IP aktif. Deteksi dilakukan setiap 10 detik.")
st.sidebar.write(f"Input model shape: {input_shape}")
st.sidebar.write("Model baru berhasil dimuat")
st.sidebar.info("Model mendeteksi 3 kelas: organik, anorganik, dan tidakterdeteksi")

# Placeholder
image_placeholder = st.empty()
label_placeholder = st.empty()
chart_placeholder = st.empty()

# Tracking deteksi terakhir dengan timestamp
last_sent = {
    "label": None,
    "timestamp": 0
}
COOLDOWN_PERIOD = 15  # Waktu cooldown dalam detik

# Fungsi untuk ambil gambar dari ESP32-CAM
def get_snapshot(url=ESP32_CAM_URL):
    try:
        resp = requests.get(url, timeout=3)
        img_array = np.asarray(bytearray(resp.content), dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return frame
    except Exception as e:
        st.error(f"❌ Gagal ambil gambar dari kamera: {e}")
        return None

# Fungsi prediksi dan kirim ke ESP32 servo
def predict_and_send(frame):
    # Resize gambar sesuai input model
    img = cv2.resize(frame, (input_shape[1], input_shape[2]))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Cek apakah model menggunakan grayscale atau RGB
    if input_shape[-1] == 1:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        img = np.expand_dims(img, axis=-1)
    
    # Tambahkan dimensi batch
    img = np.expand_dims(img, axis=0)
    
    # Pra-pemrosesan sesuai dengan tipe data model
    if input_details[0]['dtype'] == np.uint8:
        input_scale, input_zero_point = input_details[0]['quantization']
        img = img.astype(np.uint8)
    else:
        img = img.astype(np.float32) / 255.0

    # Set tensor input dan jalankan inferensi
    interpreter.set_tensor(input_details[0]['index'], img)
    interpreter.invoke()
    
    # Ambil hasil prediksi
    prediction = interpreter.get_tensor(output_details[0]['index'])[0]
    
    # Dequantisasi hasil jika model adalah quantized model
    if output_details[0]['dtype'] == np.uint8:
        scale, zero_point = output_details[0]['quantization']
        prediction = (prediction.astype(np.float32) - zero_point) * scale
    
    # Ambil kelas dengan probabilitas tertinggi
    class_id = int(np.argmax(prediction))
    confidence = float(prediction[class_id])
    label = labels[class_id].lower()
    
    return label, confidence, prediction

# Loop utama (otomatis tiap 10 detik)
while True:
    frame = get_snapshot()
    if frame is None:
        break

    # Prediksi dan kirim data ke ESP32 jika ada objek yang sesuai
    label, confidence, prediction = predict_and_send(frame)
    current_time = time.time()

    # Cek jika prediksi lebih dari 50% dan objeknya adalah organik atau anorganik
    can_send = (
        current_time - last_sent["timestamp"] > COOLDOWN_PERIOD or 
        label != last_sent["label"]
    )
    
    if confidence > 0.5 and label in ["organik", "anorganik"] and can_send:
        try:
            response = requests.post(ESP32_SERVO_URL, json={"jenis": label}, timeout=3)
            if response.status_code == 200:
                st.success(f"✅ Terkirim: {label} pada {time.strftime('%H:%M:%S')}")
                last_sent["label"] = label
                last_sent["timestamp"] = current_time
            else:
                st.error(f"❌ Gagal kirim: {response.status_code}")
        except Exception as e:
            st.error(f"❌ Error koneksi: {e}")

    # Status message untuk tidakterdeteksi
    if label == "tidakterdeteksi" and confidence > 0.5:
        label_placeholder.warning("⚠️ Tidak ada sampah terdeteksi")
    else:
        label_placeholder.empty()

    # Debug info - tampilkan status cooldown
    if label in ["organik", "anorganik"] and label == last_sent["label"]:
        remaining_cooldown = COOLDOWN_PERIOD - (current_time - last_sent["timestamp"])
        if remaining_cooldown > 0:
            st.sidebar.info(f"Cooldown: {remaining_cooldown:.1f} detik sebelum kirim {label} lagi")

    # Tampilkan frame gambar dari kamera
    image_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB", 
                            caption=f"Deteksi: {label} ({confidence:.2f})")

    # Tampilkan grafik probabilitas semua kelas
    chart_data = {labels[i]: float(prediction[i]) for i in range(len(labels))}
    sorted_chart = sorted(chart_data.items(), key=lambda x: x[1], reverse=True)
    chart_placeholder.bar_chart(dict(sorted_chart))

    time.sleep(7)
