from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import bad_request
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.product import ProductCategory
from app.models.user import User
from app.schemas.product import ProductCategoryOut
from app.services.events import write_business_event
from app.services.storefront_config import STOREFRONT_CONFIG_PATH, default_storefront_config

router = APIRouter(tags=["storefront-extra"])


class SearchSuggestionsPayload(BaseModel):
    suggestions: list[str] = Field(default_factory=list)


def _normalize_search_suggestions(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in raw:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(text[:24])
        if len(items) >= 20:
            break
    return items


def _load_config_json() -> dict:
    if not STOREFRONT_CONFIG_PATH.exists():
        return default_storefront_config()
    try:
        raw = STOREFRONT_CONFIG_PATH.read_text(encoding="utf-8")
        data = json.loads(raw) if raw else {}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return default_storefront_config()


def _save_config_json(payload: dict) -> None:
    STOREFRONT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    STOREFRONT_CONFIG_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("/admin/storefront-search-suggestions", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def get_admin_storefront_search_suggestions() -> dict:
    config = _load_config_json()
    return {"suggestions": _normalize_search_suggestions(config.get("search_suggestions"))}


@router.put("/admin/storefront-search-suggestions", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_admin_storefront_search_suggestions(
    payload: SearchSuggestionsPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    config = _load_config_json()
    if not isinstance(config, dict):
        raise bad_request("invalid storefront config")
    before = _normalize_search_suggestions(config.get("search_suggestions"))
    after = _normalize_search_suggestions(payload.suggestions)
    config["search_suggestions"] = after
    _save_config_json(config)
    await write_business_event(
        db=db,
        entity_type="storefront_config",
        entity_id=None,
        entity_no="storefront-search-suggestions",
        action_code="storefront.search_suggestions.updated",
        action_label="推荐搜索词更新",
        source="admin",
        actor=current_user,
        before_data={"search_suggestions": before},
        after_data={"search_suggestions": after},
    )
    return {"suggestions": after}


@router.get("/customer/storefront-search-suggestions")
async def get_customer_storefront_search_suggestions() -> dict:
    config = _load_config_json()
    return {"suggestions": _normalize_search_suggestions(config.get("search_suggestions"))}


@router.get("/products/categories", response_model=list[ProductCategoryOut])
async def list_product_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProductCategoryOut]:
    result = await db.execute(
        select(ProductCategory)
        .where(ProductCategory.is_active.is_(True))
        .order_by(ProductCategory.sort_order, ProductCategory.name)
    )
    rows = result.scalars().all()
    return [
        ProductCategoryOut(
            id=row.id,
            name=row.name,
            code="",
            parent_id=None,
            sort_order=row.sort_order or 0,
            is_active=bool(row.is_active),
            children=[],
        )
        for row in rows
    ]

