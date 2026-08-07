"""Create safe, repeatable data for the standalone open-source demo stack."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.enums import SKUType, UserRole
from app.models.product import Product, ProductCategory, ProductSKU
from app.models.storefront import StorefrontMarqueeNotice
from app.models.user import User
from app.services.storefront_config import STOREFRONT_CONFIG_PATH, default_storefront_config, normalize_storefront_config


DEMO_PRODUCTS = [
    ("Daily essentials", "Sample storage box", "DEMO-BOX", "A neutral sample product for local testing.", "Small", "One size", "19.90", "14.90", 48),
    ("Daily essentials", "Sample cotton towel", "DEMO-TOWEL", "A neutral sample product for local testing.", "Natural", "Two pack", "29.90", "22.90", 36),
    ("Travel", "Sample insulated bottle", "DEMO-BOTTLE", "A neutral sample product for local testing.", "Graphite", "500 ml", "59.90", "45.90", 20),
]


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if len(value) < 12 or value.startswith("replace-with-"):
        raise RuntimeError(f"{name} must be set to a local value with at least 12 characters")
    return value


def write_demo_config() -> None:
    config = default_storefront_config(include_secrets=False)
    config.update(
        {
            "store_info": {
                "name": "Open Source Demo Store",
                "phone": "",
                "address": "Local demo environment only",
                "pickup_note": "Replace this text from the admin console before real use.",
            },
            "customer_service": {"wechat_id": "demo_service", "wechat_qr_url": ""},
            "search_suggestions": ["storage", "towel", "bottle"],
            "watermark": {"enabled": False, "customer_enabled": False, "employee_enabled": False, "opacity": 0.05, "density": 5, "angle": 45},
        }
    )
    STOREFRONT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if STOREFRONT_CONFIG_PATH.exists():
        return
    STOREFRONT_CONFIG_PATH.write_text(
        json.dumps(normalize_storefront_config(config), ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def seed_database() -> None:
    username = os.getenv("DEMO_ADMIN_USERNAME", "demo-admin").strip() or "demo-admin"
    password = _required_env("DEMO_ADMIN_PASSWORD")
    employee_username = os.getenv("DEMO_EMPLOYEE_USERNAME", "demo-staff").strip() or "demo-staff"
    employee_password = _required_env("DEMO_EMPLOYEE_PASSWORD")
    async with SessionLocal() as db:
        admin = await db.scalar(select(User).where(User.username == username))
        if admin is None:
            db.add(User(username=username, password_hash=get_password_hash(password), role=UserRole.ADMIN, is_active=True))
        employee = await db.scalar(select(User).where(User.username == employee_username))
        if employee is None:
            db.add(User(username=employee_username, password_hash=get_password_hash(employee_password), role=UserRole.EMPLOYEE, is_active=True))

        for index, category_name in enumerate(("Daily essentials", "Travel"), start=1):
            category = await db.scalar(select(ProductCategory).where(ProductCategory.name == category_name))
            if category is None:
                db.add(ProductCategory(name=category_name, sort_order=index * 10, is_active=True))

        for category, name, code, description, spec_one, spec_two, retail_price, wholesale_price, stock in DEMO_PRODUCTS:
            product = await db.scalar(select(Product).where(Product.product_code == code))
            if product is None:
                product = Product(name=name, product_code=code)
                db.add(product)
                await db.flush()
            product.model_name = spec_two
            product.brand = "Demo"
            product.category = category
            product.description = description
            product.image_urls = "[]"
            product.spec_dim_1_name = "Style"
            product.spec_dim_2_name = "Specification"
            product.supports_retail = True
            product.supports_wholesale = True
            product.has_dual_price = True
            product.is_active = True

            for sku_type in (SKUType.RETAIL, SKUType.WHOLESALE):
                sku_code = f"{code}-{sku_type.value.upper()}"
                sku = await db.scalar(select(ProductSKU).where(ProductSKU.sku_code == sku_code))
                if sku is None:
                    sku = ProductSKU(product_id=product.id, sku_code=sku_code, sku_type=sku_type)
                    db.add(sku)
                sku.spec_value_1 = spec_one
                sku.spec_value_2 = spec_two
                sku.sku_label = f"{spec_one} / {spec_two}"
                sku.online_stock = stock
                sku.retail_price = Decimal(retail_price)
                sku.wholesale_price = Decimal(wholesale_price)
                sku.min_sale_qty = 1
                sku.min_wholesale_qty = 6
                sku.is_active = True

        notice = await db.scalar(select(StorefrontMarqueeNotice).where(StorefrontMarqueeNotice.title == "Open-source demo"))
        if notice is None:
            db.add(StorefrontMarqueeNotice(
                title="Open-source demo",
                body="All products and content in this environment are test data.",
                action_label="View",
                action_type="none",
                is_active=True,
                sort_order=10,
            ))
        await db.commit()


async def main() -> None:
    write_demo_config()
    await seed_database()
    print("[OK] Open-source demo data is ready. No customer, order, or production data was created.")


if __name__ == "__main__":
    asyncio.run(main())
