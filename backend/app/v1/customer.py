from datetime import UTC, datetime
from decimal import Decimal
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import bad_request, not_found
from app.db.session import get_db
from app.models.aftersale import AfterSaleRequest
from app.models.customer_runtime import (
    CustomerAddress,
    CustomerCartItem,
    CustomerNotification,
    CustomerSearchHistory,
)
from app.models.enums import (
    AfterSaleStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    SKUType,
    UserRole,
    WholesaleApplicationStatus,
)
from app.models.order import Order, OrderItem
from app.models.payment import PaymentRecord
from app.models.product import Product, ProductSKU
from app.models.user import User, WholesaleApplication
from app.schemas.customer import (
    CustomerAfterSaleCreateIn,
    CustomerAfterSaleOut,
    CustomerAddressIn,
    CustomerAddressOut,
    CustomerCartItemOut,
    CustomerCartUpsertIn,
    CustomerMeOut,
    CustomerMeUpdateIn,
    CustomerNotificationOut,
    CustomerOrderCreateIn,
    CustomerOrderItemOut,
    CustomerOrderOut,
    CustomerProductOut,
    CustomerProductSKUOut,
    CustomerSearchHistoryIn,
    CustomerSearchHistoryOut,
    WechatPayCreateOut,
    WholesaleApplicationCreateIn,
    WholesaleApplicationOut,
)
from app.services.storefront_config import load_storefront_config
from app.services.orders import cancel_order as cancel_customer_order
from app.services.orders import create_customer_order
from app.services.events import write_business_event
from app.services.notifications import create_customer_notification
from app.services.wechat_pay import build_jsapi_pay_params, create_jsapi_transaction

router = APIRouter(prefix="/customer", tags=["customer"])
settings = get_settings()


def _can_use_wholesale_scope(user: User) -> bool:
    return user.role in {UserRole.WHOLESALE, UserRole.EMPLOYEE}


def _parse_image_urls(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(item) for item in data if isinstance(item, str) and item.strip()]
    except json.JSONDecodeError:
        return []
    return []


def _serialize_me(user: User) -> CustomerMeOut:
    profile = user.profile
    return CustomerMeOut(
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        display_name=profile.display_name if profile else None,
        phone=profile.phone if profile else None,
        avatar_url=profile.avatar_url if profile else None,
        company_name=profile.company_name if profile else None,
        store_name=profile.store_name if profile else None,
        contact_name=profile.contact_name if profile else None,
        address=profile.address if profile else None,
        business_license_url=profile.business_license_url if profile else None,
        is_verified_wholesale=bool(profile.is_verified_wholesale) if profile else False,
        wechat_bound=bool(profile.wechat_openid) if profile else False,
        employee_mode=(
            profile.employee_mode
            if profile and profile.employee_mode in {"shopping", "workbench"}
            else "shopping"
        ),
    )


def _serialize_order(order: Order, items: list[OrderItem]) -> CustomerOrderOut:
    return CustomerOrderOut(
        order_id=order.id,
        order_no=order.order_no,
        status=order.status.value,
        buyer_role=order.buyer_role.value,
        original_amount=Decimal(order.original_amount),
        shipping_fee=Decimal(order.shipping_fee),
        payable_amount=Decimal(order.payable_amount),
        payment_method=order.payment_method.value,
        shipping_mode=order.shipping_mode.value if order.shipping_mode else None,
        shipping_proof_url=order.shipping_proof_url,
        shipping_recipient=order.shipping_recipient,
        shipping_phone=order.shipping_phone,
        shipping_address=order.shipping_address,
        note=order.note,
        created_at=order.created_at.isoformat(),
        items=[
            CustomerOrderItemOut(
                sku_id=item.sku_id,
                product_name=item.product_name_snapshot,
                sku_code=item.sku_code_snapshot,
                sku_type=item.sku_type_snapshot,
                spec_value_1=item.spec_value_1_snapshot,
                spec_value_2=item.spec_value_2_snapshot,
                quantity=item.quantity,
                unit_price=Decimal(item.unit_price),
                line_amount=Decimal(item.line_amount),
            )
            for item in items
        ],
    )


def _serialize_address(item: CustomerAddress) -> CustomerAddressOut:
    return CustomerAddressOut(
        id=item.id,
        contact_name=item.contact_name,
        phone=item.phone,
        region=item.region,
        detail=item.detail,
        tag=item.tag,
        is_default=item.is_default,
        created_at=item.created_at.isoformat(),
    )


@router.get("/me", response_model=CustomerMeOut)
async def get_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerMeOut:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    return _serialize_me(user)


@router.patch("/me", response_model=CustomerMeOut)
async def update_me(
    payload: CustomerMeUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerMeOut:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    if not user.profile:
        raise bad_request("user profile missing")
    update_data = payload.model_dump(exclude_unset=True)
    employee_mode = update_data.get("employee_mode")
    if employee_mode is not None and user.role != UserRole.EMPLOYEE:
        update_data.pop("employee_mode", None)
    for key, value in update_data.items():
        setattr(user.profile, key, value)
    await write_business_event(
        db=db,
        entity_type="user",
        entity_id=user.id,
        entity_no=user.username,
        action_code="customer.profile.updated",
        action_label="客户资料更新",
        source="customer",
        actor=current_user,
        after_data=update_data,
    )
    await db.commit()
    await db.refresh(user.profile)
    return _serialize_me(user)


@router.get("/storefront-config")
async def get_storefront_config(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    _ = current_user.id
    return load_storefront_config()


@router.get("/products", response_model=list[CustomerProductOut])
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    keyword: str | None = Query(default=None, min_length=1, max_length=64),
) -> list[CustomerProductOut]:
    can_wholesale = _can_use_wholesale_scope(current_user)
    sku_type = SKUType.WHOLESALE if can_wholesale else SKUType.RETAIL
    stmt = (
        select(Product)
        .options(selectinload(Product.skus))
        .where(Product.is_active.is_(True))
        .order_by(desc(Product.id))
    )
    if sku_type == SKUType.RETAIL:
        stmt = stmt.where(Product.supports_retail.is_(True))
    else:
        stmt = stmt.where(Product.supports_wholesale.is_(True))
    if keyword:
        like_kw = f"%{keyword.strip()}%"
        stmt = stmt.where(Product.name.ilike(like_kw) | Product.model_name.ilike(like_kw))

    products = (await db.scalars(stmt)).all()
    result: list[CustomerProductOut] = []
    for product in products:
        skus = [
            CustomerProductSKUOut(
                sku_id=sku.id,
                sku_code=sku.sku_code,
                sku_type=sku.sku_type.value,
                spec_value_1=sku.spec_value_1,
                spec_value_2=sku.spec_value_2,
                sku_label=sku.sku_label,
                online_stock=sku.online_stock,
                retail_price=Decimal(sku.retail_price),
                wholesale_price=Decimal(sku.wholesale_price) if can_wholesale else None,
                min_sale_qty=sku.min_sale_qty,
                min_wholesale_qty=sku.min_wholesale_qty,
                is_mixed_pack=sku.is_mixed_pack,
                mixed_pack_note=sku.mixed_pack_note,
            )
            for sku in product.skus
            if sku.is_active and sku.sku_type == sku_type
        ]
        if not skus:
            continue
        result.append(
            CustomerProductOut(
                product_id=product.id,
                product_code=product.product_code,
                name=product.name,
                model_name=product.model_name,
                brand=product.brand,
                category=product.category,
                description=product.description,
                image_urls=_parse_image_urls(product.image_urls),
                spec_dim_1_name=product.spec_dim_1_name,
                spec_dim_2_name=product.spec_dim_2_name,
                skus=skus,
            )
        )
    return result


@router.get("/products/{product_id}", response_model=CustomerProductOut)
async def get_product_detail(
    product_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerProductOut:
    can_wholesale = _can_use_wholesale_scope(current_user)
    sku_type = SKUType.WHOLESALE if can_wholesale else SKUType.RETAIL
    product = await db.scalar(
        select(Product).options(selectinload(Product.skus)).where(Product.id == product_id, Product.is_active.is_(True))
    )
    if not product:
        raise not_found("product not found")
    if sku_type == SKUType.RETAIL and not product.supports_retail:
        raise not_found("product not found")
    if sku_type == SKUType.WHOLESALE and not product.supports_wholesale:
        raise not_found("product not found")

    skus = [
        CustomerProductSKUOut(
            sku_id=sku.id,
            sku_code=sku.sku_code,
            sku_type=sku.sku_type.value,
            spec_value_1=sku.spec_value_1,
            spec_value_2=sku.spec_value_2,
            sku_label=sku.sku_label,
            online_stock=sku.online_stock,
            retail_price=Decimal(sku.retail_price),
            wholesale_price=Decimal(sku.wholesale_price) if can_wholesale else None,
            min_sale_qty=sku.min_sale_qty,
            min_wholesale_qty=sku.min_wholesale_qty,
            is_mixed_pack=sku.is_mixed_pack,
            mixed_pack_note=sku.mixed_pack_note,
        )
        for sku in product.skus
        if sku.is_active and sku.sku_type == sku_type
    ]
    if not skus:
        raise not_found("product not found")

    return CustomerProductOut(
        product_id=product.id,
        product_code=product.product_code,
        name=product.name,
        model_name=product.model_name,
        brand=product.brand,
        category=product.category,
        description=product.description,
        image_urls=_parse_image_urls(product.image_urls),
        spec_dim_1_name=product.spec_dim_1_name,
        spec_dim_2_name=product.spec_dim_2_name,
        skus=skus,
    )


@router.post("/orders", response_model=CustomerOrderOut)
async def create_order(
    payload: CustomerOrderCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerOrderOut:
    order = await create_customer_order(db=db, payload=payload, current_user=current_user)
    await db.commit()
    items = (await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
    return _serialize_order(order, list(items))


@router.get("/orders", response_model=list[CustomerOrderOut])
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerOrderOut]:
    orders = (
        await db.scalars(
            select(Order)
            .where(Order.customer_id == current_user.id)
            .order_by(desc(Order.id))
            .limit(100)
        )
    ).all()
    result: list[CustomerOrderOut] = []
    for order in orders:
        items = (await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
        result.append(_serialize_order(order, list(items)))
    return result


@router.get("/orders/{order_id}", response_model=CustomerOrderOut)
async def get_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerOrderOut:
    order = await db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == current_user.id))
    if not order:
        raise not_found("order not found")
    items = (await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
    return _serialize_order(order, list(items))


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == current_user.id))
    if not order:
        raise not_found("order not found")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("only pending_payment order can be canceled")
    order = await cancel_customer_order(db=db, order=order, operator=current_user, note="customer canceled order")
    await db.commit()
    return {"order_id": order.id, "order_no": order.order_no, "status": order.status.value}


@router.post("/orders/{order_id}/wechat-pay", response_model=WechatPayCreateOut)
async def create_wechat_payment(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WechatPayCreateOut:
    order = await db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == current_user.id))
    if not order:
        raise not_found("order not found")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("order status is not pending_payment")
    if order.payment_method != PaymentMethod.WECHAT_PAY:
        raise bad_request("order is not using wechat_pay")
    if _can_use_wholesale_scope(current_user) and current_user.profile and not current_user.profile.is_verified_wholesale:
        raise bad_request("wholesale qualification not verified")

    existing = await db.scalar(
        select(PaymentRecord)
        .where(
            PaymentRecord.order_id == order.id,
            PaymentRecord.channel == "wechat_jsapi",
            PaymentRecord.status == PaymentStatus.PENDING,
        )
        .order_by(PaymentRecord.id.desc())
    )
    if existing and existing.prepay_id:
        jsapi_params = None if settings.WECHAT_PAY_MOCK else build_jsapi_pay_params(existing.prepay_id)
        return WechatPayCreateOut(
            payment_no=existing.payment_no,
            order_no=order.order_no,
            status=existing.status.value,
            amount=f"{Decimal(existing.amount):.2f}",
            prepay_id=existing.prepay_id,
            jsapi_params=jsapi_params,
            message="reuse existing prepay",
        )

    openid = current_user.profile.wechat_openid if current_user.profile else None
    if not openid and not settings.WECHAT_PAY_MOCK:
        raise bad_request("wechat openid is required")
    openid = openid or f"mock_openid_{current_user.id}"

    payment = PaymentRecord(
        payment_no=f"PAY{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
        order_id=order.id,
        channel="wechat_jsapi",
        status=PaymentStatus.PENDING,
        amount=Decimal(order.payable_amount),
        openid=openid,
        provider_payload={"mode": "mock_jsapi" if settings.WECHAT_PAY_MOCK else "wechat_v3_jsapi"},
    )
    if settings.WECHAT_PAY_MOCK:
        payment.prepay_id = f"mock_prepay_{order.order_no}"
        jsapi_params = None
    else:
        rsp = await create_jsapi_transaction(
            order_no=order.order_no,
            amount=Decimal(order.payable_amount),
            openid=openid,
            description=f"Order {order.order_no}",
        )
        if not rsp.prepay_id:
            raise bad_request("wechat jsapi create failed")
        payment.prepay_id = rsp.prepay_id
        payment.provider_payload = rsp.raw or {}
        jsapi_params = build_jsapi_pay_params(payment.prepay_id)

    db.add(payment)
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="payment",
        entity_id=payment.id,
        entity_no=payment.payment_no,
        action_code="payment.created",
        action_label="发起微信支付",
        source="customer",
        actor=current_user,
        after_data={
            "status": payment.status.value,
            "channel": payment.channel,
            "amount": f"{payment.amount:.2f}",
            "prepay_id": payment.prepay_id,
        },
    )
    await db.commit()
    return WechatPayCreateOut(
        payment_no=payment.payment_no,
        order_no=order.order_no,
        status=payment.status.value,
        amount=f"{Decimal(payment.amount):.2f}",
        prepay_id=payment.prepay_id,
        jsapi_params=jsapi_params,
        message="mock jsapi created" if settings.WECHAT_PAY_MOCK else "wechat jsapi created",
    )


@router.post("/wholesale-applications")
async def create_wholesale_application(
    payload: WholesaleApplicationCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if current_user.role == UserRole.WHOLESALE:
        raise bad_request("user is already wholesale")
    active = await db.scalar(
        select(WholesaleApplication.id).where(
            WholesaleApplication.user_id == current_user.id,
            WholesaleApplication.status == WholesaleApplicationStatus.PENDING,
        )
    )
    if active:
        raise bad_request("pending wholesale application already exists")
    row = WholesaleApplication(
        user_id=current_user.id,
        company_name=payload.company_name,
        store_name=payload.store_name,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        business_license_url=payload.business_license_url,
        remark=payload.remark,
    )
    db.add(row)
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="wholesale_application",
        entity_id=row.id,
        entity_no=str(row.id),
        action_code="wholesale_application.created",
        action_label="提交批发申请",
        source="customer",
        actor=current_user,
        after_data={
            "status": row.status.value,
            "company_name": row.company_name,
            "store_name": row.store_name,
            "contact_name": row.contact_name,
            "contact_phone": row.contact_phone,
        },
        evidence={"business_license_url": row.business_license_url} if row.business_license_url else {},
        note=row.remark,
    )
    await create_customer_notification(
        db,
        user_id=current_user.id,
        title="批发申请已提交",
        summary=f"批发申请 #{row.id} 已提交，等待审核。",
        kind="wholesale",
        route="/pages/wholesale/apply",
        push_event_key="wholesale_submitted",
        push_payload={
            "title": f"批发申请 #{row.id}",
            "time": row.created_at.isoformat() if row.created_at else datetime.now(UTC).isoformat(),
            "status": "待审核",
            "note": row.remark or "请耐心等待审核结果。",
        },
    )
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "status": row.status.value}


@router.get("/wholesale-applications", response_model=list[WholesaleApplicationOut])
async def list_my_wholesale_applications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[WholesaleApplicationOut]:
    rows = (
        await db.scalars(
            select(WholesaleApplication)
            .where(WholesaleApplication.user_id == current_user.id)
            .order_by(desc(WholesaleApplication.id))
            .limit(20)
        )
    ).all()
    return [
        WholesaleApplicationOut(
            id=row.id,
            status=row.status.value,
            company_name=row.company_name,
            store_name=row.store_name,
            contact_name=row.contact_name,
            contact_phone=row.contact_phone,
            business_license_url=row.business_license_url,
            remark=row.remark,
            review_note=row.review_note,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.post("/aftersales", response_model=CustomerAfterSaleOut)
async def create_aftersale(
    payload: CustomerAfterSaleCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerAfterSaleOut:
    order = await db.scalar(select(Order).where(Order.id == payload.order_id, Order.customer_id == current_user.id))
    if not order:
        raise not_found("order not found")
    row = AfterSaleRequest(
        order_id=order.id,
        customer_id=current_user.id,
        reason=payload.reason,
        custom_reason_text=payload.custom_reason_text,
        note=payload.note,
        status=AfterSaleStatus.PENDING,
    )
    db.add(row)
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="aftersale",
        entity_id=row.id,
        entity_no=f"AS{row.id}",
        action_code="aftersale.created",
        action_label="提交售后",
        source="customer",
        actor=current_user,
        after_data={
            "status": row.status.value,
            "reason": row.reason.value,
            "custom_reason_text": row.custom_reason_text,
            "requested_amount": payload.requested_amount if hasattr(payload, "requested_amount") else None,
        },
        note=row.note,
    )
    await create_customer_notification(
        db,
        user_id=current_user.id,
        title="售后申请已提交",
        summary=f"售后单 AS{row.id} 已提交，店里会尽快处理。",
        kind="aftersale",
        route="/pages/aftersale/list",
        push_event_key="aftersale_created",
        push_payload={
            "title": f"售后单 AS{row.id}",
            "time": row.created_at.isoformat() if row.created_at else datetime.now(UTC).isoformat(),
            "status": "待处理",
            "note": row.note or "店里会尽快处理。",
        },
    )
    await db.commit()
    await db.refresh(row)
    return CustomerAfterSaleOut(
        id=row.id,
        order_id=row.order_id,
        reason=row.reason.value,
        custom_reason_text=row.custom_reason_text,
        process_type=row.process_type.value if row.process_type else None,
        refund_amount=Decimal(row.refund_amount) if row.refund_amount is not None else None,
        chat_proof_url=row.chat_proof_url,
        status=row.status.value,
        note=row.note,
        created_at=row.created_at.isoformat(),
    )


@router.get("/aftersales", response_model=list[CustomerAfterSaleOut])
async def list_aftersales(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerAfterSaleOut]:
    rows = (
        await db.scalars(
            select(AfterSaleRequest)
            .where(AfterSaleRequest.customer_id == current_user.id)
            .order_by(desc(AfterSaleRequest.id))
            .limit(100)
        )
    ).all()
    return [
        CustomerAfterSaleOut(
            id=row.id,
            order_id=row.order_id,
            reason=row.reason.value,
            custom_reason_text=row.custom_reason_text,
            process_type=row.process_type.value if row.process_type else None,
            refund_amount=Decimal(row.refund_amount) if row.refund_amount is not None else None,
            chat_proof_url=row.chat_proof_url,
            status=row.status.value,
            note=row.note,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.get("/cart", response_model=list[CustomerCartItemOut])
async def list_cart(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerCartItemOut]:
    rows = (
        await db.scalars(
            select(CustomerCartItem)
            .where(CustomerCartItem.user_id == current_user.id)
            .order_by(desc(CustomerCartItem.updated_at))
            .limit(200)
        )
    ).all()
    if not rows:
        return []

    sku_ids = [row.sku_id for row in rows]
    skus = (
        await db.scalars(
            select(ProductSKU)
            .options(selectinload(ProductSKU.product))
            .where(ProductSKU.id.in_(sku_ids))
        )
    ).all()
    sku_map = {sku.id: sku for sku in skus}

    can_view_wholesale = _can_use_wholesale_scope(current_user)

    result: list[CustomerCartItemOut] = []
    for row in rows:
        sku = sku_map.get(row.sku_id)
        delisted = not sku or not sku.is_active or not sku.product or not sku.product.is_active
        if delisted:
            result.append(
                CustomerCartItemOut(
                    product_id=0,
                    sku_id=row.sku_id,
                    product_name="",
                    sku_code="",
                    quantity=row.quantity,
                    retail_price=Decimal("0"),
                    min_sale_qty=1,
                    min_wholesale_qty=1,
                    selected=row.selected,
                    delisted=True,
                )
            )
            continue
        result.append(
            CustomerCartItemOut(
                product_id=sku.product_id,
                sku_id=sku.id,
                product_name=sku.product.name if sku.product else sku.sku_code,
                sku_code=sku.sku_code,
                spec_value_1=sku.spec_value_1,
                spec_value_2=sku.spec_value_2,
                quantity=row.quantity,
                online_stock=sku.online_stock,
                retail_price=Decimal(sku.retail_price),
                wholesale_price=Decimal(sku.wholesale_price)
                if can_view_wholesale
                else None,
                min_sale_qty=sku.min_sale_qty or 1,
                min_wholesale_qty=sku.min_wholesale_qty or 1,
                selected=row.selected,
                product_image_url=(
                    sku.product.image_urls[0] if sku.product and sku.product.image_urls else None
                ),
            )
        )
    return result


@router.put("/cart/items/{sku_id}", response_model=CustomerCartItemOut)
async def upsert_cart_item(
    sku_id: int,
    payload: CustomerCartUpsertIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerCartItemOut:
    sku = await db.scalar(select(ProductSKU).options(selectinload(ProductSKU.product)).where(ProductSKU.id == sku_id))
    if not sku or not sku.is_active:
        raise not_found("sku not found")

    row = await db.scalar(
        select(CustomerCartItem).where(
            CustomerCartItem.user_id == current_user.id,
            CustomerCartItem.sku_id == sku_id,
        )
    )
    if row:
        row.quantity = payload.quantity
        row.selected = payload.selected
    else:
        row = CustomerCartItem(
            user_id=current_user.id,
            sku_id=sku_id,
            quantity=payload.quantity,
            selected=payload.selected,
        )
        db.add(row)
    await db.commit()
    return CustomerCartItemOut(
        product_id=sku.product_id,
        sku_id=sku.id,
        product_name=sku.product.name if sku.product else sku.sku_code,
        sku_code=sku.sku_code,
        spec_value_1=sku.spec_value_1,
        spec_value_2=sku.spec_value_2,
        quantity=payload.quantity,
        online_stock=sku.online_stock,
        retail_price=Decimal(sku.retail_price),
        wholesale_price=Decimal(sku.wholesale_price) if _can_use_wholesale_scope(current_user) else None,
        selected=payload.selected,
    )


@router.delete("/cart/items/{sku_id}")
async def remove_cart_item(
    sku_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.scalar(
        select(CustomerCartItem).where(
            CustomerCartItem.user_id == current_user.id,
            CustomerCartItem.sku_id == sku_id,
        )
    )
    if not row:
        return {"removed": 0}
    await db.delete(row)
    await db.commit()
    return {"removed": 1}


@router.delete("/cart/clear")
async def clear_cart(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    rows = (
        await db.scalars(select(CustomerCartItem).where(CustomerCartItem.user_id == current_user.id))
    ).all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    return {"cleared": len(rows)}


@router.get("/addresses", response_model=list[CustomerAddressOut])
async def list_addresses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerAddressOut]:
    rows = (
        await db.scalars(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == current_user.id)
            .order_by(desc(CustomerAddress.is_default), desc(CustomerAddress.id))
        )
    ).all()
    return [_serialize_address(row) for row in rows]


@router.post("/addresses", response_model=CustomerAddressOut)
async def create_address(
    payload: CustomerAddressIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerAddressOut:
    existing = (
        await db.scalars(select(CustomerAddress).where(CustomerAddress.user_id == current_user.id))
    ).all()
    is_default = payload.is_default or len(existing) == 0
    if is_default:
        for item in existing:
            item.is_default = False
    row = CustomerAddress(
        user_id=current_user.id,
        contact_name=payload.contact_name.strip(),
        phone=payload.phone.strip(),
        region=payload.region.strip(),
        detail=payload.detail.strip(),
        tag=payload.tag.strip() or "常用",
        is_default=is_default,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _serialize_address(row)


@router.patch("/addresses/{address_id}", response_model=CustomerAddressOut)
async def update_address(
    address_id: int,
    payload: CustomerAddressIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerAddressOut:
    row = await db.scalar(
        select(CustomerAddress).where(CustomerAddress.id == address_id, CustomerAddress.user_id == current_user.id)
    )
    if not row:
        raise not_found("address not found")
    if payload.is_default:
        rows = (
            await db.scalars(select(CustomerAddress).where(CustomerAddress.user_id == current_user.id))
        ).all()
        for item in rows:
            item.is_default = item.id == row.id
    row.contact_name = payload.contact_name.strip()
    row.phone = payload.phone.strip()
    row.region = payload.region.strip()
    row.detail = payload.detail.strip()
    row.tag = payload.tag.strip() or "常用"
    row.is_default = payload.is_default
    await db.commit()
    await db.refresh(row)
    return _serialize_address(row)


@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.scalar(
        select(CustomerAddress).where(CustomerAddress.id == address_id, CustomerAddress.user_id == current_user.id)
    )
    if not row:
        return {"removed": 0}
    removed_default = row.is_default
    await db.delete(row)
    await db.commit()

    if removed_default:
        first = await db.scalar(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == current_user.id)
            .order_by(desc(CustomerAddress.id))
        )
        if first:
            first.is_default = True
            await db.commit()
    return {"removed": 1}


@router.get("/search-histories", response_model=list[CustomerSearchHistoryOut])
async def list_search_histories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerSearchHistoryOut]:
    rows = (
        await db.scalars(
            select(CustomerSearchHistory)
            .where(CustomerSearchHistory.user_id == current_user.id)
            .order_by(desc(CustomerSearchHistory.id))
            .limit(20)
        )
    ).all()
    return [
        CustomerSearchHistoryOut(id=row.id, keyword=row.keyword, created_at=row.created_at.isoformat())
        for row in rows
    ]


@router.post("/search-histories", response_model=CustomerSearchHistoryOut)
async def add_search_history(
    payload: CustomerSearchHistoryIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerSearchHistoryOut:
    keyword = payload.keyword.strip()
    existing = (
        await db.scalars(
            select(CustomerSearchHistory).where(
                CustomerSearchHistory.user_id == current_user.id,
                CustomerSearchHistory.keyword == keyword,
            )
        )
    ).all()
    for row in existing:
        await db.delete(row)

    row = CustomerSearchHistory(user_id=current_user.id, keyword=keyword)
    db.add(row)
    await db.commit()
    await db.refresh(row)

    rows = (
        await db.scalars(
            select(CustomerSearchHistory)
            .where(CustomerSearchHistory.user_id == current_user.id)
            .order_by(desc(CustomerSearchHistory.id))
        )
    ).all()
    for stale in rows[20:]:
        await db.delete(stale)
    await db.commit()

    return CustomerSearchHistoryOut(id=row.id, keyword=row.keyword, created_at=row.created_at.isoformat())


@router.delete("/search-histories")
async def clear_search_histories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    rows = (
        await db.scalars(
            select(CustomerSearchHistory).where(CustomerSearchHistory.user_id == current_user.id)
        )
    ).all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    return {"cleared": len(rows)}


@router.get("/notifications", response_model=list[CustomerNotificationOut])
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerNotificationOut]:
    rows = (
        await db.scalars(
            select(CustomerNotification)
            .where(CustomerNotification.user_id == current_user.id)
            .order_by(desc(CustomerNotification.id))
            .limit(50)
        )
    ).all()

    if not rows:
        seed_rows = [
            CustomerNotification(
                user_id=current_user.id,
                title="系统提示",
                summary="消息中心已启用，订单、售后和批发审核结果会在这里汇总。",
                kind="system",
                route="/pages/order/list",
                unread=True,
            ),
        ]
        for item in seed_rows:
            db.add(item)
        await db.commit()
        rows = (
            await db.scalars(
                select(CustomerNotification)
                .where(CustomerNotification.user_id == current_user.id)
                .order_by(desc(CustomerNotification.id))
                .limit(50)
            )
        ).all()

    return [
        CustomerNotificationOut(
            id=row.id,
            title=row.title,
            summary=row.summary,
            kind=row.kind,
            route=row.route,
            unread=row.unread,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.scalar(
        select(CustomerNotification).where(
            CustomerNotification.id == notification_id,
            CustomerNotification.user_id == current_user.id,
        )
    )
    if not row:
        return {"updated": 0}
    row.unread = False
    await db.commit()
    return {"updated": 1}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    rows = (
        await db.scalars(
            select(CustomerNotification).where(CustomerNotification.user_id == current_user.id)
        )
    ).all()
    updated = 0
    for row in rows:
        if row.unread:
            row.unread = False
            updated += 1
    await db.commit()
    return {"updated": updated}
