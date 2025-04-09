import streamlit as st
import cv2
import numpy as np
import tensorflow as tf
from PIL import Image

# Set page title
st.set_page_config(page_title="Deteksi Sampah", layout="wide")
st.title("Aplikasi Deteksi Sampah")

# Load model using TFLite Interpreter
@st.cache_resource
def load_model():
    # Catatan: Aplikasi ini hanya menggunakan 2 model deteksi sampah
    interpreter = tf.lite.Interpreter(model_path="model.tflite")
    interpreter.allocate_tensors()
    return interpreter

# Load labels
@st.cache_data
def load_labels():
    with open("labels.txt", "r") as f:
        return [line.strip().split(" ", 1)[1] for line in f.readlines()]

interpreter = load_model()
labels = load_labels()

# Get input and output details
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# Debug input shape information
input_shape = input_details[0]['shape']
# Menampilkan informasi dimensi input yang diharapkan oleh model (batch_size, height, width, channels)
# Ini membantu pengguna memahami ukuran dan format gambar yang diperlukan model
# serta memudahkan debugging jika terjadi ketidakcocokan dimensi input
# (1, 224, 224, 3) artinya:
#   - 1: Batch size (jumlah gambar yang diproses sekaligus)
#   - 224: Tinggi gambar dalam piksel
#   - 224: Lebar gambar dalam piksel
#   - 3: Jumlah channel warna (RGB)
st.sidebar.write("Model expects input shape:", input_shape)

# Image uploader
uploaded_file = st.file_uploader("Unggah gambar sampah", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # Process the uploaded image
    image = Image.open(uploaded_file)
    st.image(image, caption='Gambar yang diunggah', use_container_width=True)
    
    try:
        # Preprocess image for model - fixing the shape issue
        img = np.array(image.resize((224, 224)))
        
        # Check if model expects grayscale or RGB
        if input_shape[-1] == 1 and len(img.shape) == 3:
            # Convert to grayscale if needed
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            img = np.expand_dims(img, axis=-1)  # Add channel dimension
        elif input_shape[-1] == 3 and len(img.shape) == 2:
            # Convert grayscale to RGB if needed
            img = np.stack((img,)*3, axis=-1)
        
        # Get input data type from model details
        input_dtype = input_details[0]['dtype']
        
        # Add batch dimension and format based on expected input type
        img = np.expand_dims(img, axis=0)
        
        if input_dtype == np.uint8:
            # For UINT8 input, keep pixel values in 0-255 range
            img = img.astype(np.uint8)
        else:
            # For FLOAT32 input, normalize to 0-1 range
            img = img.astype(np.float32) / 255.0
        
        # Debug to show processed shape and data type
        st.sidebar.write("Processed image shape:", img.shape)
        # "Processed image dtype: uint8" menunjukkan tipe data gambar yang diproses.
        # uint8 berarti "unsigned integer 8-bit", yang merepresentasikan nilai piksel
        # dalam rentang 0-255. Ini adalah format standar untuk gambar digital di mana
        # setiap piksel disimpan sebagai bilangan bulat 8-bit tanpa tanda.
        # Tipe data ini penting karena harus sesuai dengan tipe data yang diharapkan
        # oleh model untuk input.
        st.sidebar.write("Processed image dtype:", img.dtype)
        
        # Set input tensor
        interpreter.set_tensor(input_details[0]['index'], img)
        
        # Run inference
        interpreter.invoke()
        
        # Get output tensor
        prediction = interpreter.get_tensor(output_details[0]['index'])
        
        # Check if output needs to be normalized (for UINT8 quantized models)
        output_dtype = output_details[0]['dtype']
        if output_dtype == np.uint8:
            # If model output is quantized, dequantize it
            scale, zero_point = output_details[0]['quantization']
            prediction = (prediction.astype(np.float32) - zero_point) * scale
        
        class_id = np.argmax(prediction[0])
        confidence = prediction[0][class_id]
        
        # Ensure confidence is properly scaled between 0 and 1
        if confidence > 1.0:
            confidence = confidence / 255.0
        
        # Display prediction
        st.subheader("Hasil Deteksi:")
        st.write(f"**Jenis Sampah:** {labels[class_id]}")
        st.write(f"**Tingkat Kepercayaan:** {confidence:.2f}")
        
        # Display bar chart for all predictions if confidence is high enough
        if confidence > 0.5:
            # "Probabilitas Semua Kelas" menampilkan grafik batang yang menunjukkan
            # probabilitas/keyakinan model untuk 2.
            # Fungsinya untuk memberikan visualisasi perbandingan antara berbagai kelas
            # sehingga pengguna dapat melihat tidak hanya kelas dengan probabilitas tertinggi
            # tetapi juga kelas-kelas lain yang mungkin dipertimbangkan oleh model.
            st.subheader("Probabilitas Semua Kelas:")
            chart_data = {labels[i]: float(prediction[0][i]) for i in range(len(labels))}
            chart_items = sorted(chart_data.items(), key=lambda x: x[1], reverse=True)[:2]  # Top 5 predictions
            chart_labels = [item[0] for item in chart_items]
            chart_values = [item[1] for item in chart_items]
            
            st.bar_chart({
                'Jenis': chart_labels,
                'Probabilitas': chart_values
            })
    except Exception as e:
        st.error(f"Error during inference: {str(e)}")
        st.info("Model input shape may not match processed image shape")
else:
    st.info("Silakan unggah gambar untuk dideteksi")