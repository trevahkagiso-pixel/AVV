"""Worker entrypoint for running an RQ worker for the project.

Usage (from repo root):
  python worker.py

This will start an RQ worker listening to the queue configured by
`REDIS_URL` and `RQ_QUEUE` environment variables.
"""
import os
import sys

try:
    from rq import Worker, Queue
    import redis
except Exception as e:
    import traceback
    traceback.print_exc()
    print("rq or redis not installed or import failed. Install with: pip install rq redis")
    sys.exit(1)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = os.environ.get("RQ_QUEUE", "default")


def main():
    # Create a Redis client and pass it to the Queue and Worker
    conn = redis.from_url(REDIS_URL)
    q = Queue(QUEUE_NAME, connection=conn)
    w = Worker([q], connection=conn)
    print(f"Starting RQ worker on {REDIS_URL} queue={QUEUE_NAME}")
    w.work()


if __name__ == "__main__":
    main()
