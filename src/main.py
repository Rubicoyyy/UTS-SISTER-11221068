from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Dict, Any
import asyncio
import uvicorn
import time
import logging
from .dedup import DedupStore

logger = logging.getLogger("aggregator")
logging.basicConfig(level=logging.INFO)


class EventModel(BaseModel):
    topic: str
    event_id: str
    timestamp: str
    source: str
    payload: Dict[str, Any]


def create_app(db_path: str = "./data/dedup.db"):
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.start_time = time.time()
    app.state.queue = asyncio.Queue()
    app.state.store = DedupStore(db_path)
    app.state.counters = {
        "received": 0,
        "unique_processed": 0,
        "duplicate_dropped": 0,
    }

    # Use lifespan for startup/shutdown to avoid deprecation warnings
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # startup
        app.state.store.init_db()
        app.state._consumer_shutdown = asyncio.Event()
        app.state.consumer_task = asyncio.create_task(consumer_loop(app))
        try:
            yield
        finally:
            # shutdown
            app.state.consumer_task.cancel()
            try:
                await app.state.consumer_task
            except asyncio.CancelledError:
                pass
            app.state.store.close()

    app.router.lifespan_context = lifespan

    @app.post("/publish")
    async def publish(request: Request):
        """Accept either a single event JSON or a list of events."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        events = []
        if isinstance(body, dict):
            events = [body]
        elif isinstance(body, list):
            events = body
        else:
            raise HTTPException(status_code=400, detail="JSON must be object or array")

        accepted = 0
        for raw in events:
            try:
                ev = EventModel(**raw)
            except Exception as e:
                raise HTTPException(status_code=422, detail=str(e))
            # enqueue for async processing
            # use Pydantic v2 model_dump to avoid deprecation warnings
            await app.state.queue.put(ev.model_dump())
            accepted += 1

        return {"accepted": accepted}

    @app.get("/events")
    async def get_events(topic: Optional[str] = None):
        rows = app.state.store.list_events(topic)
        return rows

    @app.get("/stats")
    async def get_stats():
        uptime = time.time() - app.state.start_time
        stats = {
            "received": app.state.counters["received"],
            "unique_processed": app.state.counters["unique_processed"],
            "duplicate_dropped": app.state.counters["duplicate_dropped"],
            "topics": app.state.store.list_topics(),
            "uptime_seconds": int(uptime),
        }
        return stats

    return app


# module-level app for uvicorn import
app = create_app()


async def consumer_loop(app: FastAPI):
    # consumer pulls from queue and processes events, does dedup
    while True:
        ev = await app.state.queue.get()
        app.state.counters["received"] += 1
        try:
            is_new = app.state.store.record_event(ev["topic"], ev["event_id"], ev["timestamp"], ev.get("source",""), ev.get("payload",{}))
            if not is_new:
                app.state.counters["duplicate_dropped"] += 1
                logger.info(f"Duplicate detected: {ev['topic']}|{ev['event_id']}")
            else:
                app.state.counters["unique_processed"] += 1
                # simulate processing
                logger.info(f"Processed: {ev['topic']}|{ev['event_id']}")
        except Exception as e:
            logger.exception("Error processing event: %s", e)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
