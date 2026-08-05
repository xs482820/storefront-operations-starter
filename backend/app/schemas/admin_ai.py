from typing import Any, Literal

from pydantic import BaseModel, Field


class AdminAiPageContext(BaseModel):
    route: str
    entity_type: Literal[
        "dashboard",
        "product",
        "order",
        "aftersale",
        "customer",
        "wholesale",
        "storefront",
    ] | None = None
    entity_id: int | str | None = None
    filters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class AdminAiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    session_id: str | None = Field(default=None, max_length=80)
    page_context: AdminAiPageContext | None = None


class AdminAiToolResult(BaseModel):
    name: str
    title: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)


class AdminAiChatResponse(BaseModel):
    answer: str
    session_id: str
    model: str | None = None
    disabled: bool = False
    tool_results: list[AdminAiToolResult] = Field(default_factory=list)
