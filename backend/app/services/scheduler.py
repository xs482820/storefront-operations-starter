import asyncio
from contextlib import suppress
from datetime import datetime

from app.core.config import get_settings
from app.core.rate_limit import redis_client
from app.db.session import SessionLocal
from app.services.ops_jobs import auto_cancel_expired_orders, auto_complete_shipped_orders

settings = get_settings()
_task: asyncio.Task | None = None


async def _run_daily_auto_complete(now: datetime) -> None:
    if now.hour != 2:
        return
    run_key = f"scheduler:auto-complete:{now.date().isoformat()}"
    if await redis_client.get(run_key):
        return
    async with SessionLocal() as db:
        completed = await auto_complete_shipped_orders(
            db=db,
            express_days=settings.SCHEDULER_EXPRESS_AUTO_COMPLETE_DAYS,
            offline_days=settings.SCHEDULER_OFFLINE_AUTO_COMPLETE_DAYS,
            batch_size=500,
        )
        if completed:
            await db.commit()
    await redis_client.setex(run_key, 60 * 60 * 24 * 2, "1")


async def _scheduler_loop() -> None:
    while True:
        try:
            now = datetime.now()
            async with SessionLocal() as db:
                canceled = await auto_cancel_expired_orders(
                    db=db,
                    cutoff_minutes=settings.ORDER_AUTO_CANCEL_MINUTES,
                    batch_size=300,
                )
                if canceled:
                    await db.commit()
            await _run_daily_auto_complete(now)
        except Exception:
            pass
        await asyncio.sleep(max(30, settings.SCHEDULER_INTERVAL_SECONDS))


def start_scheduler() -> None:
    global _task
    if _task is not None and not _task.done():
        return
    if not settings.SCHEDULER_ENABLED:
        return
    _task = asyncio.create_task(_scheduler_loop(), name="yyy-refactor-scheduler")


async def stop_scheduler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    with suppress(asyncio.CancelledError):
        await _task
    _task = None
