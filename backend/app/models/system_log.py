from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base_mixins import TimestampMixin
from app.models.enums import SystemLogCategory


class SystemLog(Base, TimestampMixin):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[SystemLogCategory] = mapped_column(
        Enum(SystemLogCategory, name="system_log_category", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    order_no: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
