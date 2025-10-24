# UTS Sistem Terdistribusi - Layanan Log Aggregator

Layanan ini adalah sebuah **log aggregator** berbasis FastAPI yang dirancang untuk menerima, melakukan deduplikasi, dan menyimpan *event* log secara persisten. Proyek ini dibangun untuk memenuhi tugas Ujian Tengah Semester (UTS) mata kuliah Sistem Paralel dan Terdistribusi.

## ✨ Fitur Utama

-   **API Asinkron**: Dibangun dengan FastAPI untuk performa tinggi, menerima *event* tunggal atau *batch* melalui endpoint `POST /publish`.
-   **Deduplikasi Persisten**: Menggunakan database **SQLite** untuk memastikan setiap *event* dengan `(topic, event_id)` yang sama hanya diproses sekali, bahkan setelah layanan di-*restart*.
-   **Pemrosesan Latar Belakang**: *Event* yang masuk dimasukkan ke dalam antrian `asyncio.Queue` dan diproses oleh *worker* di latar belakang untuk menjaga responsivitas API.
-   **Orkestrasi Multi-Container**: Menggunakan **Docker Compose** untuk menjalankan layanan `aggregator` dan `publisher` secara terpisah, menunjukkan pemisahan layanan yang modular.
-   **Statistik Real-time**: Menyediakan statistik operasional sistem melalui endpoint `GET /stats`.

---

## 🚀 Cara Menjalankan

### Metode 1: Menggunakan Docker Compose (Direkomendasikan + Bonus)

Metode ini akan menjalankan layanan `aggregator` dan `publisher` secara bersamaan. *Publisher* akan secara otomatis mengirim 5000+ *event* (termasuk duplikat) untuk demonstrasi.

1.  **Build dan Jalankan Container**:
    Dari direktori utama proyek, jalankan perintah berikut:
    ```bash
    docker-compose up --build
    ```

2.  **Pantau Log**: Anda akan melihat log dari kedua layanan di terminal. `publisher_service` akan menunggu 5 detik, lalu mulai mengirim *event*. `aggregator_service` akan mulai memprosesnya.

3.  **Hentikan Layanan**: Tekan `Ctrl + C` di terminal untuk menghentikan kedua layanan.

---

### Metode 2: Menjalankan Aggregator Saja (Manual)

Gunakan metode ini jika Anda hanya ingin menjalankan layanan `aggregator` dan mengirim *request* secara manual (misalnya menggunakan `curl` atau Postman).

1.  **Build Docker Image**:
    ```bash
    docker build -t uts-aggregator .
    ```

2.  **Jalankan Container**:
    Pastikan Anda sudah memiliki folder `data/` di direktori proyek.
    ```bash
    docker run -p 8080:8080 -v ./data:/app/data --name aggregator-uts uts-aggregator
    ```

---

## 📡 Endpoint API

-   **`POST /publish`**: Mengirim satu atau *batch event* JSON.
    -   **Respons Sukses**: `202 Accepted`
    -   **Contoh cURL**:
        ```bash
        # Menggunakan curl.exe di PowerShell
        curl.exe -X POST "http://localhost:8080/publish" -H "Content-Type: application/json" -d '{\"topic\":\"demo\",\"event_id\":\"id-123\",\"timestamp\":\"2025-10-24T21:00:00Z\",\"source\":\"curl_test\",\"payload\":{\"message\":\"hello\"}}'
        ```

-   **`GET /events?topic={topic_name}`**: Mengambil *event* unik yang telah diproses untuk *topic* tertentu.
    -   **Contoh cURL**: `curl "http://localhost:8080/events?topic=demo"`

-   **`GET /stats`**: Melihat statistik operasional.
    -   **Contoh cURL**: `curl http://localhost:8080/stats`

---

## 🎥 Video Demo

Berikut adalah link ke video demonstrasi sistem yang berjalan:

**[https://youtu.be/yWEU48rka2M]**