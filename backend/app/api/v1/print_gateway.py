from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import bad_request, not_found, unauthorized
from app.db.session import get_db
from app.models.print_job import PrintJob
from app.services.events import write_business_event
from app.services.print_layout import render_print_text
from app.services.storefront_config import load_storefront_config

router = APIRouter(prefix="/print-gateway", tags=["print-gateway"])


def require_gateway_token(x_print_gateway_token: Annotated[str | None, Header()] = None) -> None:
    expected = (get_settings().PRINT_GATEWAY_TOKEN or "").strip()
    if not expected or not x_print_gateway_token or not hmac.compare_digest(expected, x_print_gateway_token.strip()):
        raise unauthorized("Invalid print gateway token")


class JobFailureIn(BaseModel):
    error: str = Field(min_length=1, max_length=240)


async def _job_or_404(job_id: int, db: AsyncSession) -> PrintJob:
    job = await db.scalar(select(PrintJob).where(PrintJob.id == job_id))
    if not job:
        raise not_found("print job not found")
    return job


@router.post("/claim-next", dependencies=[Depends(require_gateway_token)])
async def claim_next_job(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    # The row lock keeps a second gateway from receiving the same job.
    job = await db.scalar(
        select(PrintJob)
        .where(PrintJob.status == "pending_device")
        .order_by(PrintJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if not job:
        return {"job": None}

    job.status = "printing"
    layout = load_storefront_config(include_secrets=True).get("print_layout", "")
    print_text = render_print_text(layout, job.payload)
    await write_business_event(
        db=db,
        entity_type="print_job",
        entity_id=job.id,
        entity_no=str(job.payload.get("order_no") or job.order_id),
        action_code="print.gateway_claimed",
        action_label="打印网关已取单",
        source="print_gateway",
        after_data={"status": job.status},
    )
    await db.commit()
    return {"job": {"id": job.id, "document_type": job.document_type, "print_text": print_text}}


@router.post("/jobs/{job_id}/complete", dependencies=[Depends(require_gateway_token)])
async def complete_job(job_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    job = await _job_or_404(job_id, db)
    if job.status != "printing":
        raise bad_request("print job is not being printed")
    job.status = "printed"
    await write_business_event(
        db=db, entity_type="print_job", entity_id=job.id,
        entity_no=str(job.payload.get("order_no") or job.order_id),
        action_code="print.gateway_completed", action_label="打印完成", source="print_gateway",
        after_data={"status": job.status},
    )
    await db.commit()
    return {"id": job.id, "status": job.status}


@router.post("/jobs/{job_id}/failed", dependencies=[Depends(require_gateway_token)])
async def fail_job(job_id: int, payload: JobFailureIn, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    job = await _job_or_404(job_id, db)
    if job.status != "printing":
        raise bad_request("print job is not being printed")
    job.status = "failed"
    job.payload = {**job.payload, "gateway_error": payload.error.strip()}
    await write_business_event(
        db=db, entity_type="print_job", entity_id=job.id,
        entity_no=str(job.payload.get("order_no") or job.order_id),
        action_code="print.gateway_failed", action_label="打印失败", source="print_gateway",
        after_data={"status": job.status, "error": payload.error.strip()},
    )
    await db.commit()
    return {"id": job.id, "status": job.status}
