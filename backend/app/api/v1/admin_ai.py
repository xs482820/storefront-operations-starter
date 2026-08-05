from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.admin_ai import AdminAiChatRequest, AdminAiChatResponse
from app.services.ai.admin_tools import collect_admin_ai_tools
from app.services.ai.deepseek_client import chat_with_deepseek
from app.services.storefront_config import load_admin_ai_runtime_settings

router = APIRouter(prefix="/admin/ai", tags=["admin-ai"])


@router.post("/chat", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def chat(
    payload: AdminAiChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminAiChatResponse:
    session_id = payload.session_id or uuid4().hex
    tool_results = await collect_admin_ai_tools(db, payload.page_context)
    answer, disabled = await chat_with_deepseek(payload.message.strip(), tool_results)
    runtime = load_admin_ai_runtime_settings()
    return AdminAiChatResponse(
        answer=answer,
        session_id=session_id,
        model=str(runtime.get("model") or get_settings().DEEPSEEK_MODEL),
        disabled=disabled,
        tool_results=tool_results,
    )
