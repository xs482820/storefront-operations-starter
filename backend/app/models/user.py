from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base_mixins import TimestampMixin
from app.models.enums import UserRole, WholesaleApplicationStatus


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    profile: Mapped["CustomerProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CustomerProfile(Base, TimestampMixin):
    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    wechat_openid: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    wechat_unionid: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    store_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_license_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_verified_wholesale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    employee_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="shopping", server_default="shopping")
    miniapp_notification_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    miniapp_notification_event_keys: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    miniapp_notification_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class WholesaleApplication(Base, TimestampMixin):
    __tablename__ = "wholesale_applications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[WholesaleApplicationStatus] = mapped_column(
        Enum(
            WholesaleApplicationStatus,
            name="wholesale_application_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=WholesaleApplicationStatus.PENDING,
        server_default=WholesaleApplicationStatus.PENDING.value,
        index=True,
    )
    company_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    store_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    business_license_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
