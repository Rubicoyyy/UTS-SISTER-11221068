import requests
import time
import uuid
import random
import argparse
from datetime import datetime, timezone

def generate_event(topic, event_id):
    """Membuat satu event JSON."""
    return {
        "topic": topic,
        "event_id": str(event_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "publisher-script",
        "payload": {"value": random.randint(1, 100), "ts": time.time()}
    }

def main(args):
    """Fungsi utama untuk menjalankan publisher."""
    print("🚀 Publisher service started.")
    print(f"Target URL: {args.url}")
    print(f"Total Events: {args.count}, Duplicate Ratio: {args.dup_ratio}")
    
    # Beri waktu aggregator untuk siap
    print("Waiting 5 seconds for aggregator to be ready...")
    time.sleep(5)

    print("Generating events...")
    unique_count = int(args.count * (1 - args.dup_ratio))
    dup_count = args.count - unique_count

    # 1. Buat event unik
    unique_events = [generate_event(f"topic_{i % 10}", uuid.uuid4()) for i in range(unique_count)]
    
    # 2. Buat event duplikat dengan memilih secara acak dari event unik
    duplicate_events = [random.choice(unique_events) for _ in range(dup_count)]

    # 3. Gabungkan dan acak
    all_events = unique_events + duplicate_events
    random.shuffle(all_events)
    
    print(f"Total events generated: {len(all_events)}. Sending in batches of {args.batch_size}...")

    total_sent = 0
    for i in range(0, len(all_events), args.batch_size):
        batch = all_events[i:i + args.batch_size]
        try:
            response = requests.post(args.url, json=batch, timeout=10)
            if response.status_code == 202:
                total_sent += len(batch)
                print(f"✅ Batch {i // args.batch_size + 1} sent successfully. Total sent: {total_sent}")
            else:
                print(f"⚠️ Failed to send batch. Status: {response.status_code}, Body: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending request: {e}")
        
        time.sleep(0.5) # Jeda antar batch
        
    print("🎉 Finished sending all events.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send events to the aggregator.")
    parser.add_argument("--url", required=True, help="URL of the aggregator's /publish endpoint.")
    parser.add_argument("--count", type=int, default=5000, help="Total number of events to send.")
    parser.add_argument("--dup_ratio", type=float, default=0.2, help="Ratio of duplicate events (0.0 to 1.0).")
    parser.add_argument("--batch_size", type=int, default=100, help="Number of events per batch.")
    
    args = parser.parse_args()
    main(args)