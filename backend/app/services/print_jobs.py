import json
import uuid
from datetime import UTC, datetime

import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()
redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _job_key(job_id: str) -> str:
    return f"print:job:{job_id}"


INDEX_KEY = "print:jobs:index"


async def create_print_job(payload: dict) -> dict:
    job_id = f"PJ{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8]}"
    now = _now_iso()
    job = {
        "job_id": job_id,
        "status": "queued",
        "provider": payload.get("provider") or settings.PRINT_PROVIDER,
        "message": "print job queued (reserved mode)",
        "source_type": payload.get("source_type") or "custom",
        "source_no": payload.get("source_no"),
        "copies": payload.get("copies") or 1,
        "printer_model": payload.get("printer_model"),
        "target_ip": payload.get("target_ip"),
        "target_port": payload.get("target_port"),
        "note": payload.get("note"),
        "content": payload.get("content") or {},
        "created_at": now,
        "updated_at": now,
    }
    key = _job_key(job_id)
    await redis_client.setex(key, settings.PRINT_JOB_TTL_SECONDS, json.dumps(job, ensure_ascii=False))
    await redis_client.zadd(INDEX_KEY, {job_id: datetime.now(UTC).timestamp()})
    return job


async def get_print_job(job_id: str) -> dict | None:
    raw = await redis_client.get(_job_key(job_id))
    if not raw:
        return None
    return json.loads(raw)


async def list_print_jobs(limit: int = 50) -> list[dict]:
    ids = await redis_client.zrevrange(INDEX_KEY, 0, max(0, limit - 1))
    jobs: list[dict] = []
    for job_id in ids:
        job = await get_print_job(job_id)
        if job:
            jobs.append(job)
    return jobs


async def update_print_job_status(job_id: str, status: str, message: str) -> dict | None:
    job = await get_print_job(job_id)
    if not job:
        return None
    job["status"] = status
    job["message"] = message
    job["updated_at"] = _now_iso()
    await redis_client.setex(_job_key(job_id), settings.PRINT_JOB_TTL_SECONDS, json.dumps(job, ensure_ascii=False))
    return job


async def dispatch_print_job(job_id: str) -> dict | None:
    # Reserved extension point:
    # - vendor cloud API
    # - local gateway relay
    # Current behavior: mark as accepted for future dispatch worker.
    return await update_print_job_status(
        job_id=job_id,
        status="accepted",
        message="reserved dispatch accepted; waiting provider integration",
    )
