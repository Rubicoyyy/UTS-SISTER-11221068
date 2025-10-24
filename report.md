# Laporan Desain: Sistem Log Aggregator UTS Sistem Terdistribusi

Nama : Syahrubi Alam Bahari
NIM : 11221068
Kelas : Sistem Paralel dan terdistribusi B

Laporan ini saya buat untuk menguraikan desain dan implementasi layanan *log aggregator* sebagai bagian dari Ujian Tengah Semester (UTS) mata kuliah Sistem Paralel dan Terdistribusi. Sistem ini dibangun menggunakan Python dengan kerangka kerja FastAPI dan dikemas menggunakan Docker.

## 1. Arsitektur Sistem

Sistem ini dirancang dengan arsitektur *multi-tier* logis yang berjalan di dalam satu layanan, meniru pola *Publish-Subscribe* secara internal untuk mencapai *loose coupling* dan responsivitas.

```
       Klien (Publisher Script / curl)
                    |
                    | HTTP POST
                    v
+-------------------------------------------+
|           Layanan Aggregator              |
|                                           |
|  +------------------+   Enqueue   +-----------+
|  | Endpoint /publish| ----------> | asyncio   |
|  |   (FastAPI)      |             |  Queue    |
|  +------------------+             +-----------+
|                                         | Dequeue
|                                         v
|                                 +-----------+
|                                 | Consumer  |
|                                 |  Worker   |
|                                 +-----------+
|                                      | |
|       +------------------------------+ +---------------------------+
|       |                                                            |
|       v                                                            v
| +-----------------+  INSERT/SELECT                           +-------------------+
| | Deduplication   |                                          | Event Store       |
| | Store (SQLite)  | <-- (Persisten di Docker Volume)         | (Python Dict)     |
| +-----------------+                                          +-------------------+
|       ^                                                            ^
|       | SELECT                                                     | GET
|       |                                                            |
|  +------------------+                                        +-------------------+
|  | Endpoint /stats  | <---------------------------------------| Endpoint /events  |
|  +------------------+                                        +-------------------+
|                                                                    |
+-------------------------------------------+                        | HTTP GET
                                                                     v
                                                                   Klien
```

* **API Layer (Pintu Masuk)**: *Endpoint* `POST /publish` bertindak sebagai pintu masuk. Tugas utamanya adalah memvalidasi skema *event* dan memasukkannya ke dalam antrian internal secepat mungkin, lalu merespons klien dengan status `2022 Accepted`.
* **Processing Layer (Pekerja Latar Belakang)**: Sebuah *background task* (`consumer_loop`) berjalan secara asinkron, bertindak sebagai *consumer*. Ia mengambil *event* dari antrian, melakukan logika bisnis inti (deduplikasi), dan memperbarui *state* sistem.
* **Data Layer (Penyimpanan)**: Terdiri dari dua komponen:
    * **Deduplication Store**: Database **SQLite** yang persisten, disimpan di dalam *Docker volume*. Fungsinya adalah mencatat kombinasi unik `(topic, event_id)` yang sudah diproses untuk mencegah pemrosesan ulang.
    * **Event Store**: Database SQLite yang sama juga digunakan untuk menyimpan detail *event* unik yang akan disajikan melalui `GET /events`.

## 2. Keterkaitan dengan Teori Sistem Terdistribusi

### T1 (Bab 1): Karakteristik dan Trade-off

Sistem aggregator ini menunjukkan beberapa karakteristik sistem terdistribusi. [cite_start]**Pembagian sumber daya** (*resource sharing*) terlihat dari bagaimana API dapat diakses secara bersamaan oleh banyak klien (Bab 1, hlm. 10)[cite: 95]. [cite_start]**Keterbukaan** (*openness*) diimplementasikan melalui penggunaan standar industri seperti HTTP dan JSON untuk komunikasi, memungkinkan klien dari platform mana pun untuk berinteraksi dengannya (Bab 1, hlm. 15)[cite: 141].

*Trade-off* utama dalam desain ini adalah antara **kinerja API** dan **konsistensi data**. [cite_start]Dengan memisahkan penerimaan *request* dari pemrosesannya menggunakan `asyncio.Queue`, API dapat merespons dengan sangat cepat (*low latency*), meningkatkan **skalabilitas** (Bab 1, hlm. 24) [cite: 204] dari sisi penerimaan. Namun, konsekuensinya adalah data tidak langsung konsisten; ada jeda waktu sebelum *event* diproses oleh *consumer*. Ini adalah bentuk sederhana dari *eventual consistency*.

---

### T2 (Bab 2): Pilihan Arsitektur

[cite_start]Secara konseptual, arsitektur internal sistem ini meniru pola **Publish-Subscribe** (Bab 2, hlm. 68)[cite: 470].
* **Publisher**: *Endpoint* `POST /publish`.
* **Broker**: Antrian `asyncio.Queue`.
* **Subscriber**: *Background task* `consumer_loop`.

*Publisher* tidak mengetahui detail implementasi *subscriber*; mereka hanya perlu tahu cara "menerbitkan" *event* ke *broker*. Pemisahan ini (*decoupling*) membuat sistem lebih fleksibel. [cite_start]Jika dibandingkan dengan arsitektur *client-server* sinkron yang ketat (Bab 2, hlm. 79) [cite: 23, 718] di mana klien harus menunggu pemrosesan selesai, pendekatan Pub-Sub internal ini jauh lebih unggul untuk *throughput* tinggi.

---

### T3 & T8: Reliability, Idempotency, dan Metrik

Sistem ini dirancang untuk menangani simulasi **at-least-once delivery**, di mana *publisher* dapat mengirim *event* yang sama berkali-kali. [cite_start]Untuk mengatasi ini, *consumer* dirancang agar **idempotent** (Bab 8, hlm. 513)[cite: 1242]. Logika di dalam `DedupStore` (menggunakan `PRIMARY KEY` pada `(topic, event_id)` di SQLite) memastikan bahwa memproses *event* yang sama berulang kali tidak akan mengubah *state* akhir.

Ini secara langsung berdampak pada metrik evaluasi **duplicate rate**, yang dijaga mendekati nol oleh mekanisme ini. Metrik lain seperti **throughput** (jumlah *event* yang dapat diterima per detik) dan **latency** (waktu respons API `/publish`) dijaga tetap baik karena pemrosesan berat (penulisan ke DB) dilakukan secara asinkron.

---

### T4 (Bab 6): Penamaan untuk Deduplikasi

Skema penamaan `(topic, event_id)` digunakan sebagai *identifier* unik untuk setiap *event*. Ini adalah kombinasi dari:
* [cite_start]**Structured Naming** untuk `topic` (Bab 6, hlm. 344)[cite: 25, 1116], yang memungkinkan pengelompokan dan pemfilteran *event*.
* [cite_start]**Flat Naming** untuk `event_id` (Bab 6, hlm. 329)[cite: 25, 1096], yang diasumsikan unik dalam konteks topiknya.

Kombinasi ini menjadi kunci utama untuk mekanisme deduplikasi. *Consumer* menggunakan kunci komposit ini di database SQLite untuk secara efisien mendeteksi dan membuang duplikat.

---

### T5 (Bab 5): Ordering

[cite_start]**Total ordering** (Bab 5, hlm. 264) [cite: 1013] tidak diperlukan dalam konteks aggregator ini. *Event* dari *topic* yang berbeda umumnya independen dan tidak memiliki hubungan kausal. Memaksakan urutan global akan menjadi *bottleneck* yang tidak perlu. Sistem ini memproses *event* berdasarkan urutan kedatangannya di `asyncio.Queue`, yang secara efektif mendekati **FIFO ordering**. Untuk kebutuhan sebagian besar sistem log, urutan ini sudah lebih dari cukup. *Timestamp* dalam *event* dapat digunakan di sisi klien untuk pengurutan *best-effort* jika diperlukan.

---

### T6 (Bab 8): Failure Modes dan Toleransi Crash

[cite_start]Mode kegagalan utama yang ditangani oleh desain ini adalah **crash failure** (Bab 8, hlm. 467) [cite: 28, 1234] pada layanan aggregator. **Toleransi crash** diimplementasikan melalui strategi mitigasi berikut:
* **Durable Dedup Store**: *State* deduplikasi (ID *event* yang sudah diproses) disimpan dalam file SQLite.
* **Docker Volume**: File SQLite ini ditempatkan di dalam *Docker volume*, yang memastikan data tersebut **persisten** dan tidak hilang saat *container* berhenti atau *restart*.

Ketika layanan dimulai kembali, ia akan memuat ulang *database* dari *volume*, sehingga ia "mengingat" semua *event* yang telah diproses sebelumnya dan dapat melanjutkan proses deduplikasi tanpa kesalahan. Ini mencegah pemrosesan ulang (*reprocessing*) yang bisa menyebabkan duplikasi data.

---

### T7 (Bab 7): Konsistensi

[cite_start]Sistem ini secara eksplisit mengadopsi model **eventual consistency** (Bab 7, hlm. 407)[cite: 25, 1174]. Ketika API `/publish` merespons klien, tidak ada jaminan bahwa *event* tersebut sudah langsung terlihat di `GET /events`. Ada jeda waktu (*replication lag*) yang dibutuhkan oleh *consumer* untuk mengambil *event* dari antrian dan menyimpannya ke database. Namun, sistem menjamin bahwa jika tidak ada *event* baru yang masuk, pada akhirnya semua *event* unik yang telah diterima akan diproses dan disimpan. Mekanisme **idempotency** dan **deduplikasi** adalah fondasi yang memungkinkan sistem mencapai keadaan akhir yang konsisten meskipun ada pengiriman *event* yang berulang.

---
### Sitasi

van Steen, M., & Tanenbaum, A. S. (2023). *Distributed Systems*. Maarten van Steen.