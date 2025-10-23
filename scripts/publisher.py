"""Simple publisher/load generator.
Usage: python publisher.py --url http://aggregator:8080/publish --count 5000 --dup_ratio 0.2
"""
import argparse
import random
import time
import uuid
import sys
import requests
from requests.exceptions import RequestException


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8080/publish")
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--dup_ratio", type=float, default=0.2)
    p.add_argument("--batch_size", type=int, default=100)
    p.add_argument("--retries", type=int, default=5, help="number of retries per batch on connection errors")
    p.add_argument("--backoff", type=float, default=0.5, help="base backoff seconds (exponential)")
    p.add_argument("--timeout", type=float, default=5.0, help="request timeout seconds")
    args = p.parse_args()

    count = args.count
    dup_ratio = args.dup_ratio
    batch = args.batch_size

    # prepare event ids: some duplicates
    unique = int(count * (1 - dup_ratio))
    ids = [str(uuid.uuid4()) for _ in range(unique)]
    # allow duplicates by sampling
    events = []
    for i in range(count):
        eid = random.choice(ids)
        ev = {
            "topic": "load",
            "event_id": eid,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "publisher",
            "payload": {"n": i},
        }
        events.append(ev)

    def send_with_retries(url, payload, retries=5, backoff=0.5, timeout=5.0):
        """Send payload to url, retrying on connection-related errors.

        Returns True on success, False on permanent failure after retries.
        """
        attempt = 0
        while True:
            try:
                r = requests.post(url, json=payload, timeout=timeout)
                # consider any 2xx a success
                if 200 <= r.status_code < 300:
                    return True
                else:
                    print(f"Warning: non-2xx status {r.status_code} for batch")
                    return False
            except RequestException as exc:
                attempt += 1
                if attempt > retries:
                    print(f"ERROR: batch failed after {retries} retries: {exc}")
                    return False
                sleep = backoff * (2 ** (attempt - 1))
                print(f"Retry {attempt}/{retries} after error: {exc} -> sleeping {sleep:.2f}s")
                time.sleep(sleep)

    # send in batches
    for i in range(0, len(events), batch):
        chunk = events[i : i + batch]
        ok = send_with_retries(args.url, chunk, retries=args.retries, backoff=args.backoff, timeout=args.timeout)
        print(f"Sent batch {i}//{len(events)} success={ok}")
        time.sleep(0.01)


if __name__ == "__main__":
    main()
