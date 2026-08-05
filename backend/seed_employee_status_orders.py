import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.aftersale import AfterSaleRequest
from app.models.enums import AfterSaleReason, AfterSaleStatus, OrderStatus, PaymentMethod, ShippingMode, UserRole
from app.models.order import Order, OrderItem
from app.models.product import ProductSKU
from app.models.user import User


def _now_suffix() -> str:
    return datetime.now(UTC).strftime("%y%m%d%H%M%S")


def _order_no(prefix: str) -> str:
    return f"{prefix}{_now_suffix()}"


async def main() -> None:
    async with SessionLocal() as db:
        customer = await db.scalar(
            select(User).where(User.role.in_([UserRole.RETAIL, UserRole.WHOLESALE, UserRole.EMPLOYEE])).order_by(User.id.asc())
        )
        if not customer:
            raise RuntimeError("no customer-like user found")

        sku = await db.scalar(
            select(ProductSKU)
            .options(selectinload(ProductSKU.product))
            .where(ProductSKU.is_active.is_(True))
            .order_by(ProductSKU.id.asc())
        )
        if not sku:
            raise RuntimeError("no active sku found")

        unit_price = Decimal(sku.retail_price or 0) if customer.role == UserRole.RETAIL else Decimal(sku.wholesale_price or sku.retail_price or 0)
        if unit_price <= 0:
            unit_price = Decimal("1.00")

        created: list[tuple[str, str, int]] = []

        async def create_order(status: OrderStatus, tag: str) -> Order:
            order = Order(
                order_no=_order_no(tag),
                customer_id=customer.id,
                buyer_role=customer.role,
                status=status,
                original_amount=unit_price,
                shipping_fee=Decimal("0.00"),
                payable_amount=unit_price,
                payment_method=PaymentMethod.WECHAT_PAY,
                shipping_mode=ShippingMode.EXPRESS,
                shipping_recipient="测试客户",
                shipping_phone="18800001234",
                shipping_province="浙江省",
                shipping_city="温州市",
                shipping_district="鹿城区",
                shipping_address=f"店员状态测试-{tag}",
                note="自动生成的状态测试订单",
                paid_at=datetime.now(UTC) if status in {OrderStatus.AWAITING_SHIPMENT, OrderStatus.SHIPPED, OrderStatus.COMPLETED} else None,
                shipped_at=datetime.now(UTC) if status in {OrderStatus.SHIPPED, OrderStatus.COMPLETED} else None,
                completed_at=datetime.now(UTC) if status == OrderStatus.COMPLETED else None,
                canceled_at=datetime.now(UTC) if status == OrderStatus.CANCELED else None,
            )
            db.add(order)
            await db.flush()

            item = OrderItem(
                order_id=order.id,
                sku_id=sku.id,
                product_name_snapshot=sku.product.name if sku.product else f"SKU-{sku.id}",
                sku_code_snapshot=sku.sku_code,
                sku_type_snapshot=sku.sku_type.value,
                spec_value_1_snapshot=sku.spec_value_1,
                spec_value_2_snapshot=sku.spec_value_2,
                quantity=1,
                unit_price=unit_price,
                line_amount=unit_price,
            )
            db.add(item)
            await db.flush()

            created.append((order.order_no, status.value, order.id))
            return order

        pending = await create_order(OrderStatus.PENDING_PAYMENT, "EP")
        await create_order(OrderStatus.AWAITING_SHIPMENT, "EA")
        shipped = await create_order(OrderStatus.SHIPPED, "ES")
        await create_order(OrderStatus.COMPLETED, "EC")
        await create_order(OrderStatus.CANCELED, "EX")

        aftersale = AfterSaleRequest(
            order_id=shipped.id,
            customer_id=customer.id,
            reason=AfterSaleReason.OTHER,
            custom_reason_text="店员侧流程验证售后单",
            note="自动生成，用于工作台售后入口联调",
            status=AfterSaleStatus.PENDING,
            refund_amount=unit_price,
        )
        db.add(aftersale)
        await db.flush()
        await db.commit()

        print("seed done")
        print(f"customer_id={customer.id}, role={customer.role.value}, sku_id={sku.id}")
        for no, st, oid in created:
            print(f"{no} | {st} | id={oid}")
        print(f"aftersale_id={aftersale.id}, order_id={aftersale.order_id}")


if __name__ == "__main__":
    asyncio.run(main())
