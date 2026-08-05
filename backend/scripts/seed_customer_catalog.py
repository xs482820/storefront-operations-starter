"""Seed a repeatable catalog for customer mini-program visual testing.

Usage:
    docker compose exec backend python scripts/seed_customer_catalog.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.enums import SKUType
from app.models.product import Product, ProductCategory, ProductSKU


CATEGORIES = ["奶粉辅食", "纸尿裤", "洗护用品", "喂养用品", "童装内衣", "寝居用品", "出行装备", "玩具礼品"]

CATALOG = [
    ("童装内衣", "A类纯棉婴儿连体衣", "YY-TEST-CLOTH", "柔软亲肤，适合日常换洗。", [("米白", "66码", "39.90", "29.90", 48), ("浅杏", "73码", "42.90", "32.90", 26)]),
    ("纸尿裤", "云柔拉拉裤加大包", "YY-TEST-DIAPER", "轻薄透气，日常备货款。", [("L码", "48片", "69.90", "55.00", 120), ("XL码", "44片", "69.90", "55.00", 86)]),
    ("洗护用品", "婴儿洗护两件套", "YY-TEST-WASH", "洗发沐浴与润肤组合装。", [("温和型", "500ml*2", "88.00", "68.00", 33)]),
    ("喂养用品", "宽口径玻璃奶瓶", "YY-TEST-FEED", "耐热玻璃瓶身，适合日常喂养。", [("奶油白", "240ml", "49.90", "38.00", 62), ("奶油白", "300ml", "56.90", "43.00", 41)]),
    ("寝居用品", "四季纱布睡袋", "YY-TEST-SLEEP", "轻薄透气，午睡和夜睡都适用。", [("小熊", "M码", "128.00", "98.00", 18), ("小熊", "L码", "128.00", "98.00", 0)]),
    ("出行装备", "轻便婴儿推车", "YY-TEST-TRAVEL", "可折叠设计，适合家庭出行。", [("灰杏色", "标准款", "469.00", "399.00", 8)]),
    ("奶粉辅食", "高铁营养米粉", "YY-TEST-FOOD", "细腻易冲调，适合辅食初期。", [("原味", "250g", "36.90", "28.00", 72)]),
]


async def main() -> None:
    async with SessionLocal() as db:
        for index, category_name in enumerate(CATEGORIES, start=1):
            category = await db.scalar(select(ProductCategory).where(ProductCategory.name == category_name))
            if category is None:
                db.add(ProductCategory(name=category_name, sort_order=index * 10, is_active=True))
            else:
                category.sort_order = index * 10
                category.is_active = True

        for category, name, code, description, variants in CATALOG:
            product = await db.scalar(select(Product).where(Product.product_code == code))
            if product is None:
                product = Product(name=name, product_code=code)
                db.add(product)
                await db.flush()
            product.name = name
            product.model_name = variants[0][1]
            product.brand = "示例门店"
            product.category = category
            product.description = description
            product.image_urls = json.dumps([])
            product.spec_dim_1_name = "款式"
            product.spec_dim_2_name = "规格"
            product.supports_retail = True
            product.supports_wholesale = True
            product.has_dual_price = True
            product.is_active = True

            for sku_type in (SKUType.RETAIL, SKUType.WHOLESALE):
                for variant_index, (spec_1, spec_2, retail_price, wholesale_price, stock) in enumerate(variants, start=1):
                    sku_code = f"{code}-{sku_type.value.upper()}-{variant_index}"
                    sku = await db.scalar(select(ProductSKU).where(ProductSKU.sku_code == sku_code))
                    if sku is None:
                        sku = ProductSKU(product_id=product.id, sku_code=sku_code, sku_type=sku_type)
                        db.add(sku)
                    sku.spec_value_1 = spec_1
                    sku.spec_value_2 = spec_2
                    sku.sku_label = f"{spec_1} / {spec_2}"
                    sku.online_stock = stock
                    sku.retail_price = Decimal(retail_price)
                    sku.wholesale_price = Decimal(wholesale_price)
                    sku.min_sale_qty = 1
                    sku.min_wholesale_qty = 6
                    sku.is_active = True

        await db.commit()
    print(f"[OK] seeded {len(CATALOG)} products across {len(CATEGORIES)} categories")


if __name__ == "__main__":
    asyncio.run(main())
