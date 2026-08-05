from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SystemLogCategory
from app.models.system_log import SystemLog


async def write_system_log(
    db: AsyncSession,
    category: SystemLogCategory,
    action: str,
    message: str,
    order_no: str | None = None,
    details: dict | None = None,
) -> SystemLog:
    row = SystemLog(
        category=category,
        action=action,
        order_no=order_no,
        message=message,
        details=details or {},
    )
    db.add(row)
    await db.flush()
    return row
