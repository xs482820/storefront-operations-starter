import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.aftersale import AfterSaleRequest
from app.models.business_event import BusinessEvent
from app.models.customer_runtime import CustomerNotification
from app.models.enums import AfterSaleReason, AfterSaleStatus, OrderStatus, PaymentMethod, ShippingMode, SKUType, UserRole
from app.models.order import Order, OrderItem
from app.models.payment import PaymentRecord
from app.models.product import ProductSKU
from app.models.user import CustomerProfile, User


def _now_code() -> str:
    return datetime.now(UTC).strftime("%y%m%d%H%M%S%f")


def _money(value) -> Decimal:
    amount = Decimal(value or 0)
    return amount if amount > 0 else Decimal("1.00")


async def main() -> None:
    async with SessionLocal() as db:
        # Keep catalog and users intact; reset only order workflow data.
        await db.execute(delete(CustomerNotification).where(CustomerNotification.kind.in_(["order", "aftersale"])))
        await db.execute(delete(BusinessEvent).where(BusinessEvent.entity_type.in_(["order", "payment", "aftersale"])))
        await db.execute(delete(AfterSaleRequest))
        await db.execute(delete(PaymentRecord))
        await db.execute(delete(OrderItem))
        await db.execute(delete(Order))
        await db.flush()

        customer = await db.scalar(
            select(User)
            .where(User.role.in_([UserRole.RETAIL, UserRole.WHOLESALE]))
            .order_by(User.id.asc())
        )
        if not customer:
            # ponytail: local workflow tests need a buyer even when only the bootstrap admin exists.
            customer = User(username="dev_order_customer", password_hash="development-only", role=UserRole.RETAIL, is_active=True)
            db.add(customer)
            await db.flush()
            db.add(CustomerProfile(user_id=customer.id, display_name="测试客户", phone="18800001200"))
            await db.flush()

        skus = (
            await db.scalars(
                select(ProductSKU)
                .options(selectinload(ProductSKU.product))
                .where(ProductSKU.is_active.is_(True))
                .order_by(ProductSKU.id.asc())
            )
        ).all()
        skus = [sku for sku in skus if sku.product and sku.product.is_active]
        if not skus:
            raise RuntimeError("no active sku found")

        def pick_sku(index: int) -> ProductSKU:
            return skus[index % len(skus)]

        created: list[tuple[str, str, int]] = []

        async def create_order(status: OrderStatus, tag: str, index: int) -> Order:
            sku = pick_sku(index)
            buyer_role = UserRole.WHOLESALE if customer.role == UserRole.WHOLESALE else UserRole.RETAIL
            unit_price = (
                _money(sku.wholesale_price)
                if buyer_role == UserRole.WHOLESALE and sku.sku_type == SKUType.WHOLESALE
                else _money(sku.retail_price or sku.wholesale_price)
            )
            quantity = 1 if index % 2 == 0 else 2
            shipping_fee = Decimal("8.00") if status in {OrderStatus.PENDING_PAYMENT, OrderStatus.AWAITING_SHIPMENT} else Decimal("0.00")
            original_amount = unit_price * quantity
            payable_amount = original_amount + shipping_fee
            now = datetime.now(UTC)

            order = Order(
                order_no=f"{tag}{_now_code()}{index}",
                customer_id=customer.id,
                buyer_role=buyer_role,
                status=status,
                original_amount=original_amount,
                shipping_fee=shipping_fee,
                payable_amount=payable_amount,
                payment_method=PaymentMethod.WECHAT_PAY,
                shipping_mode=ShippingMode.EXPRESS if index % 3 != 0 else ShippingMode.OFFLINE,
                shipping_recipient=f"测试客户{index + 1}",
                shipping_phone=f"1880000{1200 + index}",
                shipping_province="浙江省",
                shipping_city="温州市",
                shipping_district="鹿城区",
                shipping_address=f"店员侧测试地址 {index + 1} 号",
                note=f"店员侧全状态测试订单 {tag}-{index + 1}",
                paid_at=now if status in {OrderStatus.AWAITING_SHIPMENT, OrderStatus.SHIPPED, OrderStatus.COMPLETED} else None,
                shipped_at=now if status in {OrderStatus.SHIPPED, OrderStatus.COMPLETED} else None,
                delivery_signed_at=now if status == OrderStatus.COMPLETED else None,
                completed_at=now if status == OrderStatus.COMPLETED else None,
                canceled_at=now if status == OrderStatus.CANCELED else None,
            )
            db.add(order)
            await db.flush()

            db.add(
                OrderItem(
                    order_id=order.id,
                    sku_id=sku.id,
                    product_name_snapshot=sku.product.name,
                    sku_code_snapshot=sku.sku_code,
                    sku_type_snapshot=sku.sku_type.value,
                    spec_value_1_snapshot=sku.spec_value_1,
                    spec_value_2_snapshot=sku.spec_value_2,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_amount=original_amount,
                )
            )
            await db.flush()
            created.append((order.order_no, status.value, order.id))
            return order

        status_plan = [
            (OrderStatus.PENDING_PAYMENT, "EP"),
            (OrderStatus.AWAITING_SHIPMENT, "EA"),
            (OrderStatus.SHIPPED, "ES"),
            (OrderStatus.COMPLETED, "EC"),
            (OrderStatus.CANCELED, "EX"),
        ]
        seeded_orders: list[Order] = []
        index = 0
        for status, tag in status_plan:
            for _ in range(2):
                seeded_orders.append(await create_order(status, tag, index))
                index += 1

        aftersale_orders = [order for order in seeded_orders if order.status in {OrderStatus.SHIPPED, OrderStatus.COMPLETED}]
        for idx, order in enumerate(aftersale_orders[:2], start=1):
            db.add(
                AfterSaleRequest(
                    order_id=order.id,
                    customer_id=customer.id,
                    reason=AfterSaleReason.OTHER,
                    custom_reason_text=f"店员侧售后测试单 {idx}",
                    note="用于店员售后入口和处理流程验证",
                    status=AfterSaleStatus.PENDING,
                    refund_amount=Decimal(order.payable_amount),
                )
            )

        await db.commit()

        print("reset + seed done")
        print(f"customer_id={customer.id}, role={customer.role.value}")
        for no, status, order_id in created:
            print(f"{no} | {status} | id={order_id}")
        print("aftersales=2")


if __name__ == "__main__":
    asyncio.run(main())
