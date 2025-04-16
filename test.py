import streamlit as st
import numpy as np
import tensorflow as tf
import cv2

# Konfigurasi halaman
st.set_page_config(page_title="Deteksi Sampah", layout="centered")
st.title("🗑️ Deteksi Sampah Otomatis")
st.markdown("Pilih metode input gambar: menggunakan **kamera** atau **unggah gambar** dari galeri.")
st.info("Gunakan **background hitam atau putih** agar gambar sampah lebih mudah terdeteksi oleh sistem.")

# Load model TFLite
@st.cache_resource
def load_model():
    interpreter = tf.lite.Interpreter(model_path="model.tflite")
    interpreter.allocate_tensors()
    return interpreter

# Load label dari file
@st.cache_data
def load_labels():
    with open("labels.txt", "r") as f:
        return [line.strip().split(" ", 1)[1] for line in f.readlines()]

interpreter = load_model()
labels = load_labels()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
input_shape = input_details[0]['shape']

# Pilihan metode input: pilih gambar dari file atau kamera
st.subheader("Pilih Metode Input")
input_method = st.selectbox("Pilih metode input gambar:", ["📁 Unggah Gambar", "📷 Gunakan Kamera"], index=0)

frame = None

if input_method == "📁 Unggah Gambar":
    # Pilihan upload gambar dari file
    uploaded_file = st.file_uploader("📤 Unggah gambar sampah", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

elif input_method == "📷 Gunakan Kamera":
    # Pilihan mengambil gambar langsung dari kamera
    camera_image = st.camera_input("Ambil foto menggunakan kamera")
    if camera_image is not None:
        file_bytes = np.asarray(bytearray(camera_image.read()), dtype=np.uint8)
        frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

# Jika gambar tersedia, lakukan prediksi
if frame is not None:
    # Preprocessing
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

    # Tampilkan hasil
    col1, col2 = st.columns(2)

    with col1:
        st.image(frame, caption="📸 Gambar yang digunakan", use_container_width=True)

    with col2:
        st.metric("📌 Hasil Deteksi", f"{label.upper()}")
        st.metric("🔍 Tingkat Keyakinan", f"{confidence*100:.2f} %")

        if confidence < 0.5:
            st.warning("⚠️ Keyakinan rendah. Hasil mungkin tidak akurat.")
        elif label == "tidakterdeteksi":
            st.info("⚠️ Tidak ada sampah terdeteksi.")
        else:
            st.success(f"✅ Sampah terdeteksi: {label.upper()}")

    # Tampilkan grafik prediksi
    chart_data = {labels[i]: float(prediction[i]) for i in range(len(labels))}
    sorted_chart = sorted(chart_data.items(), key=lambda x: x[1], reverse=True)
    st.subheader("📊 Probabilitas Setiap Kelas")
    st.bar_chart(dict(sorted_chart))

else:
    st.info("⬆️ Silakan unggah gambar atau ambil foto terlebih dahulu.")
