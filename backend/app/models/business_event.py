from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base_mixins import TimestampMixin


class BusinessEvent(Base, TimestampMixin):
    __tablename__ = "business_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    entity_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_label: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="system", server_default="system", index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    actor_name_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    visibility: Mapped[str] = mapped_column(String(24), nullable=False, default="internal", server_default="internal", index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    before_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    after_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
