from types import SimpleNamespace

from app.api.v1.employee import _print_customer_identity


def test_print_customer_identity_falls_back_to_customer_profile() -> None:
    order = SimpleNamespace(shipping_recipient=None, shipping_phone=None)
    customer = SimpleNamespace(
        username="buyer_1",
        profile=SimpleNamespace(contact_name=None, display_name="张三", phone="13800138000"),
    )
    assert _print_customer_identity(order, customer) == ("张三", "13800138000")
