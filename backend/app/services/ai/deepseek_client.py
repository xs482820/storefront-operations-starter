from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request

from app.core.config import get_settings
from app.schemas.admin_ai import AdminAiToolResult
from app.services.storefront_config import load_admin_ai_runtime_settings


def build_admin_ai_prompt(message: str, tool_results: list[AdminAiToolResult]) -> list[dict[str, str]]:
    context = json.dumps(
        [item.model_dump() for item in tool_results],
        ensure_ascii=False,
        default=str,
    )
    return [
        {
            "role": "system",
            "content": (
                "你是 YYY HUB 管理后台的只读 AI 助手。你服务老板/管理员，目标是让后台更顺手。"
                "你只能基于提供的后台数据做归纳、风险提示和下一步建议。"
                "不要声称已经执行写入操作，不要编造不存在的数据，不要要求用户提供密码或密钥。"
                "回答要短、准、可执行，优先用中文。"
            ),
        },
        {
            "role": "user",
            "content": f"管理员问题：{message}\n\n可用后台上下文 JSON：\n{context}",
        },
    ]


def build_fallback_answer(message: str, tool_results: list[AdminAiToolResult]) -> str:
    snapshot = next((item for item in tool_results if item.name == "dashboard_snapshot"), None)
    low_stock = next((item for item in tool_results if item.name == "low_stock"), None)
    aftersales = next((item for item in tool_results if item.name == "pending_aftersales"), None)
    wholesale = next((item for item in tool_results if item.name == "pending_wholesale"), None)

    lines = ["AI 模型暂未启用，我先按后台数据给你一个只读摘要。"]
    if snapshot:
        lines.append(snapshot.summary)
    if aftersales and aftersales.data.get("total"):
        lines.append(f"售后优先处理：{aftersales.data.get('total')} 单待处理。")
    if low_stock and low_stock.data.get("total"):
        first = (low_stock.data.get("items") or [{}])[0]
        name = first.get("product_name") or first.get("sku_code") or "低库存 SKU"
        stock = first.get("stock")
        lines.append(f"库存风险：{name} 当前库存 {stock}，建议先补货或确认是否下架。")
    if wholesale and wholesale.data.get("total"):
        lines.append(f"认证审核：还有 {wholesale.data.get('total')} 个申请待确认。")
    if "库存" not in message and "售后" not in message and "订单" not in message:
        lines.append("你可以继续问：今天优先处理什么、哪些商品缺货、售后是否异常。")
    return "\n".join(lines)


def _request_deepseek(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    runtime = load_admin_ai_runtime_settings()
    base_url = str(runtime.get("base_url") or settings.DEEPSEEK_BASE_URL).rstrip("/")
    url = f"{base_url}/chat/completions"
    model = str(runtime.get("model") or settings.DEEPSEEK_MODEL).strip()
    if model in {"deepseek-chat", "deepseek-reasoner", ""}:
        model = "deepseek-v4-flash"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": int(runtime.get("max_output_tokens") or settings.DEEPSEEK_MAX_OUTPUT_TOKENS),
        "thinking": {"type": "disabled"},
    }
    api_key = str(runtime.get("api_key") or settings.DEEPSEEK_API_KEY or "")
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=int(runtime.get("timeout_seconds") or settings.DEEPSEEK_TIMEOUT_SECONDS)) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str(data["choices"][0]["message"]["content"]).strip()


async def chat_with_deepseek(message: str, tool_results: list[AdminAiToolResult]) -> tuple[str, bool]:
    settings = get_settings()
    runtime = load_admin_ai_runtime_settings()
    enabled = bool(runtime.get("enabled", settings.AI_ADMIN_ENABLED))
    dry_run = bool(runtime.get("dry_run", settings.AI_ADMIN_DRY_RUN))
    api_key = str(runtime.get("api_key") or settings.DEEPSEEK_API_KEY or "")
    if not enabled or dry_run or not api_key:
        return build_fallback_answer(message, tool_results), True

    messages = build_admin_ai_prompt(message, tool_results)
    try:
        answer = await asyncio.to_thread(_request_deepseek, messages)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        return build_fallback_answer(message, tool_results), True
    return answer, False
