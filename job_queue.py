"""
Simple RQ job queue helpers for enqueuing and checking build jobs.

Requires `redis` and `rq` packages and a running Redis server.
"""
import os
from typing import Optional

try:
    import redis
    from rq import Queue
    from rq.job import Job
except Exception:
    redis = None
    Queue = None
    Job = None

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = os.environ.get("RQ_QUEUE", "default")


def get_queue() -> Optional[Queue]:
    if redis is None:
        return None
    conn = redis.from_url(REDIS_URL)
    return Queue(QUEUE_NAME, connection=conn)


def enqueue_build(cache_path: str = "backtest_summary.csv") -> Optional[str]:
    """Enqueue the `build_tasks.build_summary` job and return the job id.

    Returns None if RQ/Redis not available.
    """
    q = get_queue()
    if q is None:
        return None

    # Import the worker function lazily so module import doesn't require Flask
    from build_tasks import build_summary as _build
    job = q.enqueue(_build, cache_path)
    return job.get_id()


def get_job_status(job_id: str) -> Optional[dict]:
    """Return a small status dict for job id or None if unavailable."""
    if Job is None:
        return None
    try:
        job = Job.fetch(job_id, connection=redis.from_url(REDIS_URL))
        return {"id": job.get_id(), "status": job.get_status(), "result": str(job.result)}
    except Exception as e:
        return {"error": str(e)}
