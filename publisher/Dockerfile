FROM python:3.11-slim

WORKDIR /app

# Install dependensi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin skrip publisher dari direktori context saat ini
COPY publisher.py .

# Perintah default
CMD ["python", "-u", "publisher.py"]