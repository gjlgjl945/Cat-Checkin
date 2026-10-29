#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把旧的单文件配置 config/token.json 拆成按平台独立的配置文件。

拆分规则：旧文件的每个顶层节点 → 一份 ``config/token.<key>.json``，
文件内容仍保留同名的顶层节点（``{"wps": {"accounts": [...]}}``），
因此各脚本的字段解析逻辑无需变化，回滚也只要把文件合回去。

用法
----
    python ci/migrate_config.py                 # 预览（默认不写盘）
    python ci/migrate_config.py --apply         # 实际写入
    python ci/migrate_config.py --apply --remove-legacy   # 写入后删除旧文件
    python ci/migrate_config.py --apply --force  # 覆盖已存在的平台文件

只输出平台名、账号数与写入路径，不打印任何凭据内容。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from platform_config import (  # noqa: E402 - 依赖上面的 sys.path 设置
    PLATFORM_KEYS,
    legacy_config_path,
    platform_config_path,
)

# 与 ci/platform_guard.py 的账号字段判定保持一致：只统计「看起来填过」的账号
_SKIP_VALUES = {"", "MASKED"}


def _count_accounts(node: Any) -> int:
    """统计节点下非空的账号条目数（不校验字段是否有效，仅作体检参考）。"""
    if not isinstance(node, dict):
        return 0
    accounts = node.get("accounts")
    if not isinstance(accounts, list):
        return 0
    return sum(1 for item in accounts if isinstance(item, dict) and item)


def _write_platform_file(path: Path, key: str, node: Any) -> None:
    """写入单个平台配置；行尾固定 LF，权限收紧到 600。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({key: node}, ensure_ascii=False, indent=2) + "\n"
    # 必须显式 newline="\n"：Windows 上文本模式会把 \n 翻成 \r\n
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows 上语义不同，忽略即可


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 token.json 拆分为按平台独立的配置文件")
    parser.add_argument("--legacy", default=str(legacy_config_path(REPO_ROOT)),
                        help="旧配置文件路径，默认 config/token.json")
    parser.add_argument("--apply", action="store_true", help="实际写盘（默认仅预览）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的平台配置文件")
    parser.add_argument("--remove-legacy", action="store_true",
                        help="写入成功后删除旧配置文件（危险操作，建议确认新文件可用后再用）")
    args = parser.parse_args(argv)

    legacy = Path(args.legacy)
    if not legacy.exists():
        print(f"❌ 旧配置不存在: {legacy}")
        print("如果已经拆分过，直接运行 python ci/platform_guard.py --validate 检查各平台状态")
        return 1

    try:
        with open(legacy, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"❌ 读取旧配置失败: {exc}")
        return 1
    if not isinstance(data, dict):
        print("❌ 旧配置顶层必须是 JSON 对象")
        return 1

    unknown = sorted(set(data) - set(PLATFORM_KEYS))
    if unknown:
        print(f"::warning::旧配置里有非平台节点，将原样忽略: {', '.join(unknown)}")

    # 输出目录必须跟随 --legacy 所在的目录，而不是写死仓库的 config/：
    # 否则「拿一份备份试跑」会把结果写进真实配置，覆盖正在用的凭据。
    out_dir = legacy.parent
    print(f"输出目录: {out_dir}")

    planned = []
    for key in PLATFORM_KEYS:
        node = data.get(key)
        target = platform_config_path(key, directory=str(out_dir))
        if node is None:
            print(f"  跳过 {key:<8} 旧配置里没有该节点")
            continue
        if not isinstance(node, dict):
            print(f"  ❌ {key:<8} 节点不是对象（{type(node).__name__}），已跳过")
            continue
        exists = target.exists()
        if exists and not args.force:
            print(f"  跳过 {key:<8} {target.name} 已存在（需要覆盖请加 --force）")
            continue
        planned.append((key, node, target, exists))

    if not planned:
        print("\n没有需要写入的文件。")
        return 0

    print("\n将要写入：")
    for key, node, target, exists in planned:
        action = "覆盖" if exists else "新建"
        print(f"  {action} {target.name:<22} 账号 {_count_accounts(node)} 个")

    if not args.apply:
        print("\n（预览模式，未写盘；确认无误后加 --apply）")
        return 0

    for key, node, target, _ in planned:
        _write_platform_file(target, key, node)
        print(f"  ✅ 已写入 {target}")

    print(f"\n完成：{len(planned)} 个平台配置已拆分。")

    if args.remove_legacy:
        try:
            legacy.unlink()
            print(f"已删除旧配置: {legacy}")
        except OSError as exc:
            print(f"::warning::删除旧配置失败（不影响使用）: {exc}")
    else:
        print(f"旧配置 {legacy.name} 仍保留；平台文件存在时它不会被读取，确认无误后可手动删除。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
