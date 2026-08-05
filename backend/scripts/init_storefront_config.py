"""
初始化店铺配置 JSON 文件

在首次部署或重置店铺配置时使用。
从代码中的默认值生成 data/storefront-config.json 文件，
确保小程序和管理后台能读取到完整的配置结构。

用法:
    docker compose exec backend python scripts/init_storefront_config.py
    # 或本地开发:
    cd backend && python scripts/init_storefront_config.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.storefront_config import default_storefront_config, normalize_storefront_config


def load_existing(path: Path) -> dict | None:
    """读取已有的 storefront-config.json，保留已有数据。"""
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else None
    except (json.JSONDecodeError, OSError):
        return None


def main() -> None:
    # 确定配置文件路径
    # 容器内路径: /app/data/storefront-config.json
    # 本地路径: backend/data/storefront-config.json (docker volume mount 映射)
    container_path = Path("/app/data/storefront-config.json")
    local_path = Path(__file__).resolve().parent.parent / "data" / "storefront-config.json"

    # 优先使用容器路径，否则用本地路径
    config_path = container_path if container_path.exists() else local_path
    parent = config_path.parent
    parent.mkdir(parents=True, exist_ok=True)

    # 尝试保留已有数据
    existing = load_existing(config_path)
    include_secrets = True  # 容器内部可以包含密钥

    if existing:
        print(f"[INFO] 读取已有配置: {config_path}")
        config = normalize_storefront_config(existing, include_secrets=include_secrets)
        print(f"[INFO] 已有配置已规范化（保留 {len(json.dumps(config))} 字节）")
    else:
        print(f"[INFO] 创建默认配置: {config_path}")
        config = default_storefront_config(include_secrets=include_secrets)
        print("[INFO] 使用代码中的默认值")

    # 写入配置
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # 验证
    written = config_path.read_text(encoding="utf-8")
    parsed = json.loads(written)
    sections = [k for k in parsed if isinstance(parsed[k], dict)]
    print(f"[OK] 配置已写入: {config_path}")
    print(f"    配置节: {', '.join(sections)}")
    print(f"    文件大小: {len(written)} 字节")


if __name__ == "__main__":
    main()
