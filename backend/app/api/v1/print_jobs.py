from fastapi import APIRouter, Depends, Query

from app.api.deps import require_roles
from app.core.exceptions import not_found
from app.models.enums import UserRole
from app.schemas.print_job import PrintJobCreateIn, PrintJobDispatchOut, PrintJobOut
from app.services.print_jobs import create_print_job, dispatch_print_job, list_print_jobs, update_print_job_status

router = APIRouter(prefix="/print", tags=["print"])


@router.post("/jobs", response_model=PrintJobOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def create_job(payload: PrintJobCreateIn) -> PrintJobOut:
    job = await create_print_job(payload.model_dump())
    return PrintJobOut(**job)


@router.get("/jobs", response_model=list[PrintJobOut], dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PrintJobOut]:
    jobs = await list_print_jobs(limit=limit)
    return [PrintJobOut(**job) for job in jobs]


@router.post("/jobs/{job_id}/dispatch", response_model=PrintJobDispatchOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def dispatch_job(job_id: str) -> PrintJobDispatchOut:
    job = await dispatch_print_job(job_id)
    if not job:
        raise not_found("print job not found")
    return PrintJobDispatchOut(job_id=job_id, status=job["status"], message=job["message"] or "")


@router.post("/jobs/{job_id}/cancel", response_model=PrintJobDispatchOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def cancel_job(job_id: str) -> PrintJobDispatchOut:
    job = await update_print_job_status(job_id=job_id, status="canceled", message="canceled by admin")
    if not job:
        raise not_found("print job not found")
    return PrintJobDispatchOut(job_id=job_id, status=job["status"], message=job["message"] or "")
