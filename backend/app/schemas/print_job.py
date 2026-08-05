from typing import Any

from pydantic import BaseModel, Field


class PrintJobCreateIn(BaseModel):
    source_type: str = Field(default="custom", max_length=32)
    source_no: str | None = Field(default=None, max_length=64)
    copies: int = Field(default=1, ge=1, le=20)
    printer_model: str | None = Field(default="DS-1900Y", max_length=64)
    target_ip: str | None = Field(default=None, max_length=64)
    target_port: int | None = Field(default=9100, ge=1, le=65535)
    provider: str | None = Field(default=None, max_length=32)
    content: dict[str, Any] = Field(default_factory=dict)
    note: str | None = Field(default=None, max_length=255)


class PrintJobOut(BaseModel):
    job_id: str
    status: str
    provider: str
    message: str | None = None
    source_type: str
    source_no: str | None = None
    copies: int
    printer_model: str | None = None
    target_ip: str | None = None
    target_port: int | None = None
    note: str | None = None
    created_at: str
    updated_at: str


class PrintJobDispatchOut(BaseModel):
    job_id: str
    status: str
    message: str
