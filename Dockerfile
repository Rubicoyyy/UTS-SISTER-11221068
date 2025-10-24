# Gunakan base image python yang ramping (slim)
FROM python:3.11-slim

# Set working directory di dalam container
WORKDIR /app

# Buat user non-root untuk keamanan
RUN adduser --disabled-password --gecos '' appuser

# Salin file dependensi terlebih dahulu untuk memanfaatkan Docker layer caching
COPY requirements.txt ./

# Install dependensi sebagai root
RUN pip install --no-cache-dir -r requirements.txt

# Salin kode aplikasi.
# Jika ada folder lain seperti 'scripts', salin juga.
COPY src/ ./src/
# Contoh: COPY scripts/ ./scripts/

# Buat direktori data dan pastikan kepemilikan untuk non-root user
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Ganti ke user non-root
USER appuser

# Buka port yang akan digunakan oleh aplikasi
EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]