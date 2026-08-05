import asyncio
from types import SimpleNamespace

from app.api.v1.customer import _resolve_role_sku as resolve_customer_sku
from app.models.enums import SKUType
from app.services.orders import _resolve_role_sku as resolve_order_sku


class EmptySession:
    async def scalar(self, _statement):
        return None


def test_legacy_single_type_sku_keeps_its_specification() -> None:
    sku = SimpleNamespace(
        sku_type=SKUType.RETAIL,
        product_id=1,
        spec_value_1="A",
        spec_value_2="B",
    )
    session = EmptySession()
    assert asyncio.run(resolve_customer_sku(session, sku, SKUType.WHOLESALE)) is sku
    assert asyncio.run(resolve_order_sku(session, sku, SKUType.WHOLESALE)) is sku


if __name__ == "__main__":
    test_legacy_single_type_sku_keeps_its_specification()
