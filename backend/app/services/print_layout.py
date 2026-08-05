from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any
from unicodedata import east_asian_width

CHINA_TIME = timezone(timedelta(hours=8), name="CST")
RECEIPT_COLUMNS = 46


def _display_width(value: str) -> int:
    return sum(2 if east_asian_width(char) in {"W", "F"} else 1 for char in value)


def _truncate_display(value: str, width: int) -> str:
    result = ""
    for char in value:
        if _display_width(result + char) > width:
            while result and _display_width(result) > width - 3:
                result = result[:-1]
            return result + "..."
        result += char
    return result


def _format_money(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _render_line(line: dict[str, Any]) -> str:
    name = _truncate_display(str(line.get("name") or "商品").strip(), RECEIPT_COLUMNS)
    spec = str(line.get("spec") or "默认规格").strip()
    quantity = str(line.get("quantity") or 0).strip()
    unit_price = _format_money(line.get("unit_price"))
    line_amount = _format_money(line.get("line_amount"))
    spec_column = _truncate_display(spec, 20)
    spec_padding = max(0, 20 - _display_width(spec_column))
    return f"{name}\n  {spec_column}{' ' * spec_padding}{unit_price:>8}{quantity:>6}{line_amount:>10}"


def _render_total_summary(quantity: Any, amount: Any) -> str:
    left = f"合计：{quantity or 0} 件"
    right = f"￥{_format_money(amount)}"
    return left + " " * max(1, RECEIPT_COLUMNS - _display_width(left) - _display_width(right)) + right


def render_print_text(layout: str, payload: dict[str, Any]) -> str:
    """Render the operator-managed pick-list template into plain receipt text."""
    lines = payload.get("lines") if isinstance(payload.get("lines"), list) else []
    rendered_lines = [_render_line(line) for line in lines if isinstance(line, dict)]

    values = {
        "order_no": payload.get("order_no") or "",
        "recipient": payload.get("recipient") or "",
        "phone": payload.get("phone") or "",
        "address": payload.get("address") or "",
        "shipping_channel": payload.get("shipping_channel") or "",
        "customer_note": payload.get("customer_note") or "",
        "internal_note": payload.get("internal_note") or "",
        "total_quantity": payload.get("total_quantity") or 0,
        "total_amount": _format_money(payload.get("total_amount")),
        "total_summary": _render_total_summary(payload.get("total_quantity"), payload.get("total_amount")),
        "wechat_id": payload.get("wechat_id") or "请咨询店内客服",
        "store_phone": payload.get("store_phone") or "请咨询店内客服",
        "lines": "\n".join(rendered_lines) or "暂无商品明细",
        "printed_at": datetime.now(CHINA_TIME).strftime("%Y-%m-%d %H:%M"),
    }
    text = str(layout or "")
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", str(value))

    # ponytail: omit empty labelled fields so a missing phone or note does not waste receipt rows.
    rendered = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        label_value = re.split(r"[：:]", line, maxsplit=1)
        if len(label_value) == 2 and not label_value[1].strip():
            continue
        rendered.append(line)
    return "\n".join(rendered).strip()
