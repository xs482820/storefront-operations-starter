from pydantic import BaseModel


class BusinessEventOut(BaseModel):
    id: int
    event_no: str
    entity_type: str
    entity_id: int | None = None
    entity_no: str | None = None
    action_code: str
    action_label: str
    source: str
    actor_user_id: int | None = None
    actor_role: str | None = None
    actor_name_snapshot: str | None = None
    visibility: str
    correlation_id: str | None = None
    request_id: str | None = None
    before_data: dict
    after_data: dict
    evidence: dict
    note: str | None = None
    created_at: str
