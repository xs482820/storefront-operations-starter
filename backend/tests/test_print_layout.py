from datetime import datetime

from app.services.print_layout import CHINA_TIME, render_print_text


def test_render_print_text_replaces_fields_and_lines() -> None:
    text = render_print_text(
        "订单 {{order_no}}\n{{lines}}\n{{total_summary}}\n总数 {{total_quantity}}\n总额 {{total_amount}}\n客服 {{wechat_id}}\n门店 {{store_phone}}\n{{customer_note}}\n{{printed_at}}",
        {"order_no": "SO-1", "lines": [{"name": "柔巾", "quantity": 2, "spec": "12包", "unit_price": "5.5", "line_amount": "11"}], "total_quantity": 2, "total_amount": "11", "wechat_id": "demo_service", "store_phone": "13800000000"},
    )
    assert "订单 SO-1" in text
    assert "柔巾" in text
    assert "12包" in text
    assert "5.50" in text
    assert "11.00" in text
    assert "总数 2" in text
    assert "合计：2 件" in text
    assert "客服 yyy客服" in text
    assert "门店 13800000000" in text
    printed_at = datetime.strptime(text.rsplit("\n", 1)[-1], "%Y-%m-%d %H:%M")
    assert abs((datetime.now(CHINA_TIME).replace(tzinfo=None) - printed_at).total_seconds()) < 61
