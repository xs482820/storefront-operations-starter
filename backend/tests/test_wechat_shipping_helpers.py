from types import SimpleNamespace

from app.models.enums import ShippingMode
from app.services.wechat_shipping import _express_company_code, _is_pickup


def test_shipping_type_helpers() -> None:
    assert _express_company_code("顺丰") == "SF"
    assert _express_company_code("ZTO") == "ZTO"
    assert _is_pickup(
        SimpleNamespace(shipping_address="到店自提：门店", shipping_recipient="到店自提"),
        ShippingMode.OFFLINE,
        "门店",
    )
    assert not _is_pickup(
        SimpleNamespace(shipping_address="温州市鹿城区", shipping_recipient="客户"),
        ShippingMode.OFFLINE,
        "门店",
    )
    assert not _is_pickup(
        SimpleNamespace(shipping_address="到店自提：门店", shipping_recipient="到店自提"),
        ShippingMode.EXPRESS,
        "门店",
    )


if __name__ == "__main__":
    test_shipping_type_helpers()
