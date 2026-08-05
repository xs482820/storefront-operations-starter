"""
导出/导入关键业务配置数据

功能:
  1. 将数据库中的关键配置导出为 JSON（店铺设置、运费规则等）
  2. 将 JSON 配置导入到目标数据库
  3. 用于在不同环境间同步配置（开发 → 生产）

用法:
    # 从当前数据库导出配置到文件
    docker compose exec backend python scripts/export_config_data.py export /data/config-export.json

    # 从文件导入配置到当前数据库
    docker compose exec backend python scripts/export_config_data.py import /data/config-export.json

    # 导出时排除敏感信息
    docker compose exec backend python scripts/export_config_data.py export /data/config-export.json --public-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.storefront_config import (
    load_storefront_config,
    public_storefront_config,
    STOREFRONT_CONFIG_PATH,
)


def export_config(output_path: str, public_only: bool = False) -> dict[str, Any]:
    """导出配置到 JSON 文件。"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if public_only:
        config = public_storefront_config(load_storefront_config(include_secrets=False))
    else:
        config = load_storefront_config(include_secrets=True)

    # 添加导出元数据
    from datetime import UTC, datetime
    export_data = {
        "_meta": {
            "exported_at": datetime.now(UTC).isoformat(),
            "version": "1.0",
            "public_only": public_only,
        },
        "storefront_config": config,
    }

    output_file.write_text(
        json.dumps(export_data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"[OK] 配置已导出: {output_file}")
    print(f"    数据大小: {len(json.dumps(export_data))} 字节")
    print(f"    公开模式: {public_only}")
    return export_data


def import_config(input_path: str) -> dict[str, Any]:
    """从 JSON 文件导入配置。"""
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"[ERR] 文件不存在: {input_path}")
        sys.exit(1)

    raw = input_file.read_text(encoding="utf-8")
    data = json.loads(raw)

    config = data.get("storefront_config")
    if not config:
        print(f"[ERR] 无效的导出文件：缺少 storefront_config 字段")
        sys.exit(1)

    # 写入 storefront-config.json
    STOREFRONT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    STOREFRONT_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    meta = data.get("_meta", {})
    print(f"[OK] 配置已导入: {STOREFRONT_CONFIG_PATH}")
    print(f"    导出时间: {meta.get('exported_at', '未知')}")
    print(f"    数据大小: {len(json.dumps(config))} 字节")
    return config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="YyY Hub 配置数据导出/导入工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # export
    export_parser = subparsers.add_parser("export", help="导出配置")
    export_parser.add_argument("output", help="输出文件路径")
    export_parser.add_argument("--public-only", action="store_true", help="仅导出公开信息（不含密钥）")

    # import
    import_parser = subparsers.add_parser("import", help="导入配置")
    import_parser.add_argument("input", help="输入文件路径")

    args = parser.parse_args()

    if args.command == "export":
        export_config(args.output, public_only=args.public_only)
    elif args.command == "import":
        import_config(args.input)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
