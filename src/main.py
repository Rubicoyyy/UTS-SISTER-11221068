from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import asyncio
import uvicorn
import time
import logging
from .dedup import DedupStore  # Pastikan Anda punya file ini di src/dedup.py
from contextlib import asynccontextmanager

# --- Konfigurasi Logging ---
logger = logging.getLogger("aggregator")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Model Data Pydantic ---
class EventModel(BaseModel):
    topic: str
    event_id: str
    timestamp: str
    source: str
    payload: Dict[str, Any]

# --- Fungsi Pabrik Aplikasi (Factory Function) ---
def create_app(db_path: str = "./data/dedup.db"):
    app = FastAPI(title="UTS Log Aggregator")

    # --- Middleware untuk CORS (opsional tapi baik untuk pengembangan) ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Inisialisasi State Aplikasi ---
    app.state.start_time = time.time()
    app.state.queue = asyncio.Queue()
    app.state.store = DedupStore(db_path)
    app.state.counters = {
        "received": 0,
        "unique_processed": 0,
        "duplicate_dropped": 0,
    }

    # --- Lifespan Manager untuk Startup dan Shutdown ---
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # --- Proses Startup ---
        logger.info("🚀 Aplikasi memulai proses startup...")
        app.state.store.init_db()
        app.state.consumer_task = asyncio.create_task(consumer_loop(app))
        logger.info("✅ Consumer worker telah dimulai.")
        
        yield  # Aplikasi berjalan di sini
        
        # --- Proses Shutdown ---
        logger.info("👋 Aplikasi memulai proses shutdown...")
        app.state.consumer_task.cancel()
        try:
            await app.state.consumer_task
        except asyncio.CancelledError:
            logger.info("Consumer worker berhasil dihentikan.")
        app.state.store.close()
        logger.info(" koneksi database ditutup.")

    app.router.lifespan_context = lifespan

    # --- Endpoint API ---
    
    # PERBAIKAN 1: Menambahkan status_code=202 Accepted
    @app.post("/publish", status_code=202)
    async def publish(request: Request):
        """Menerima satu atau batch event JSON dan memasukkannya ke antrian."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON format")

        events_to_process = []
        if isinstance(body, dict):
            events_to_process = [body]
        elif isinstance(body, list):
            events_to_process = body
        else:
            raise HTTPException(status_code=400, detail="JSON must be a single object or an array of objects")

        accepted_count = 0
        for raw_event in events_to_process:
            try:
                event_model = EventModel(**raw_event)
                # Gunakan model_dump() untuk Pydantic v2
                await app.state.queue.put(event_model.model_dump())
                
                # PERBAIKAN 2: Counter 'received' diinkremen di sini saat diterima
                app.state.counters["received"] += 1
                
                accepted_count += 1
            except ValidationError as e:
                # Jika validasi gagal, hentikan proses dan kembalikan error
                raise HTTPException(status_code=422, detail=f"Schema validation error: {e}")

        return {"message": f"{accepted_count} event(s) were accepted into the queue."}

    @app.get("/events")
    async def get_events(topic: Optional[str] = None):
        """Mengambil semua event yang unik, bisa difilter berdasarkan topik."""
        rows = app.state.store.list_events(topic)
        return rows

    @app.get("/stats")
    async def get_stats():
        """Menampilkan statistik operasional sistem."""
        uptime = time.time() - app.state.start_time
        stats = {
            "received": app.state.counters["received"],
            "unique_processed": app.state.counters["unique_processed"],
            "duplicate_dropped": app.state.counters["duplicate_dropped"],
            "topics": app.state.store.list_topics(),
            "uptime_seconds": round(uptime, 2),
        }
        return stats

    return app

# --- Consumer Worker ---
async def consumer_loop(app: FastAPI):
    """Loop tak terbatas yang mengambil event dari antrian dan memprosesnya."""
    while True:
        try:
            event_data = await app.state.queue.get()
            
            is_new = app.state.store.record_event(
                event_data["topic"],
                event_data["event_id"],
                event_data["timestamp"],
                event_data.get("source", ""),
                event_data.get("payload", {})
            )
            
            if not is_new:
                app.state.counters["duplicate_dropped"] += 1
                logger.info(f"💡 Duplicate dropped: {event_data['topic']}|{event_data['event_id']}")
            else:
                app.state.counters["unique_processed"] += 1
                logger.info(f"✅ Processed unique event: {event_data['topic']}|{event_data['event_id']}")
            
            app.state.queue.task_done()
        except Exception as e:
            logger.exception(f"Error processing event: {e}")

# --- Inisialisasi utama untuk Uvicorn ---
app = create_app()

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)