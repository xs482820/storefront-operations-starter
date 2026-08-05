"""
Safely clean up test data from the database.

Run inside the Docker container:
    docker compose exec backend python scripts/cleanup_test_data.py
    docker compose exec backend python scripts/cleanup_test_data.py --dry-run  # preview only

This script:
- Identifies records with test/seed patterns (e.g., "e2e", "Test", "test", "demo")
- Respects FK cascades (orders -> items -> payments -> aftersales)
- Skips admin/employee accounts and storefront config
- Requires explicit --confirm flag to actually delete
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal


# Known test patterns — records matching these will be flagged for cleanup
TEST_PATTERNS = [
    "e2e", "test", "Test", "TEST", "demo", "Demo", "DEMO",
    "mock", "Mock", "smoke", "seed", "sample",
]


async def _count(table_name: str, session: AsyncSession) -> int:
    result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
    return result.scalar() or 0


async def _delete_where(table_name: str, column: str, patterns: list[str], session: AsyncSession) -> int:
    """Delete rows where column matches any pattern via ILIKE. Returns count."""
    total = 0
    for pat in patterns:
        result = await session.execute(
            text(f"DELETE FROM {table_name} WHERE {column} ILIKE :pat RETURNING 1"),
            {"pat": f"%{pat}%"},
        )
        total += len(result.fetchall())
    await session.commit()
    return total


async def _delete_users_by_pattern(patterns: list[str], session: AsyncSession) -> int:
    """Delete users (and cascaded profiles) where username matches test patterns."""
    total = 0
    for pat in patterns:
        result = await session.execute(
            text("DELETE FROM users WHERE username ILIKE :pat AND role IN ('retail', 'wholesale') RETURNING 1"),
            {"pat": f"%{pat}%"},
        )
        total += len(result.fetchall())
    await session.commit()
    return total


async def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up test data from the database")
    parser.add_argument("--confirm", action="store_true", help="Actually delete (without this, only preview)")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be deleted")
    args = parser.parse_args()

    if not args.confirm and not args.dry_run:
        print("[INFO] Preview mode. Use --confirm to actually delete, or --dry-run for explicit preview.")
        args.dry_run = True

    async with SessionLocal() as session:
        # ---- Count before ----
        print("\n=== Current data counts ===")
        tables = [
            "products", "product_skus", "product_categories",
            "orders", "order_items", "payment_records",
            "aftersale_requests",
            "users", "customer_profiles", "wholesale_applications",
            "customer_cart_items", "customer_addresses", "customer_notifications",
            "online_stock_logs", "business_events",
        ]
        before_counts: dict[str, int] = {}
        for t in tables:
            c = await _count(t, session)
            before_counts[t] = c or 0
            print(f"  {t:30s} = {c or 0}")

        # ---- Identify test records ----
        print("\n=== Test data found ===")
        found = False

        # Check for test products
        rows = await session.execute(
            text("SELECT id, name, product_code FROM products WHERE " +
                 " OR ".join([f"name ILIKE '%{p}%'" for p in TEST_PATTERNS]) +
                 " OR " + " OR ".join([f"product_code ILIKE '%{p}%'" for p in TEST_PATTERNS]))
        )
        test_products = rows.fetchall()
        if test_products:
            found = True
            for row in test_products:
                print(f"  PRODUCT: id={row[0]}, name={row[1]}, code={row[2]}")

        # Check for test users
        for pat in TEST_PATTERNS:
            rows = await session.execute(
                text("SELECT id, username, role FROM users WHERE username ILIKE :pat AND role IN ('retail', 'wholesale')"),
                {"pat": f"%{pat}%"},
            )
            for row in rows.fetchall():
                found = True
                print(f"  USER: id={row[0]}, username={row[1]}, role={row[2]}")

        if not found:
            print("  No test data found matching known patterns.")
            return

        if args.dry_run:
            print("\n[Dry-run complete. Run with --confirm to delete.]")
            return

        # ---- Delete in FK-safe order ----
        print("\n=== Deleting test data ===")
        deleted: dict[str, int] = {}

        # Order: payments -> aftersales -> order_items -> orders -> cart -> products -> wholesale -> users
        order = [
            ("payment_records", "note"),
            ("aftersale_requests", "note"),
            ("order_items", "product_name"),
            ("customer_cart_items", ""),
            ("customer_notifications", ""),
            ("online_stock_logs", "note"),
            ("business_events", "label"),
            ("orders", "note"),
        ]
        for table, col in order:
            if not col:
                continue
            n = await _delete_where(table, col, TEST_PATTERNS, session)
            if n:
                deleted[table] = n
                print(f"  Deleted {n} from {table}")

        # Delete products (must come before users due to FK)
        for pat in TEST_PATTERNS:
            r = await session.execute(
                text("DELETE FROM products WHERE name ILIKE :pat OR product_code ILIKE :pat RETURNING 1"),
                {"pat": f"%{pat}%"},
            )
            n = len(r.fetchall())
            if n:
                deleted["products"] = deleted.get("products", 0) + n
        await session.commit()
        if "products" in deleted:
            print(f"  Deleted {deleted['products']} product(s)")

        # Delete wholesale applications for test users
        for pat in TEST_PATTERNS:
            r = await session.execute(
                text("DELETE FROM wholesale_applications WHERE remark ILIKE :pat RETURNING 1"),
                {"pat": f"%{pat}%"},
            )
            n = len(r.fetchall())
            if n:
                deleted["wholesale_applications"] = deleted.get("wholesale_applications", 0) + n
        await session.commit()

        # Delete test users (cascades to customer_profiles)
        n = await _delete_users_by_pattern(TEST_PATTERNS, session)
        if n:
            deleted["users"] = n
            print(f"  Deleted {n} test user(s) (cascaded to profiles)")

        # ---- Count after ----
        print("\n=== After cleanup ===")
        total_removed = 0
        for t in tables:
            c = await _count(t, session)
            after = c or 0
            before = before_counts.get(t, 0)
            diff = before - after
            if diff != 0:
                total_removed += diff
                print(f"  {t:30s} = {after}  (-{diff})")
            else:
                print(f"  {t:30s} = {after}  (unchanged)")

        print(f"\n  Total records removed: {total_removed}")
        print("[DONE] Test data cleanup complete.")


if __name__ == "__main__":
    asyncio.run(main())
