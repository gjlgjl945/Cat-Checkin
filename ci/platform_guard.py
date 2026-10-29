#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 平台守卫。

用途
----
GitHub Actions 需要解决两个问题：一是「某个平台没配账号时不要让工作流变红」，
二是「配置写错时要尽早报错」。本脚本负责这两件事，并且**只输出平台名与账号数量，
不打印任何凭据值**。

子命令
------
``--validate``          校验 config/token.json 结构，并打印各平台账号数量
``--matrix``            列出可运行的平台（JSON），用于本地巡检与手动触发前确认
``--platform <key>``    判断单个平台是否已配置，供 job 内跳过未配置平台

退出码
------
0  正常（含「平台未配置」，由调用方决定是否跳过）
1  配置不可用（文件缺失、JSON 非法、没有任何平台配置了账号）
2  参数错误（未知平台 key）

Author: Cat-Checkin CI
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "token.json"
TEMPLATE_PATH = REPO_ROOT / "config" / "template_token.json"

# 平台注册表。字段含义：
#   key       工作流矩阵标识，同时也是 dispatch 输入里使用的名字
#   name      展示名（Actions 任务标题）
#   entry     入口脚本（相对仓库根目录）
#   path      config/token.json 中的节点路径
#   creds     判定「该账号已填写」所需字段
#   creds_all True 表示 creds 全部必填，False 表示任一即可
#   timeout   单平台超时（秒），用于 shell 层 timeout，避免单平台拖垮整条流水线
#   ci        False 表示不纳入定时任务（功能不可用或需要人工交互）
PLATFORMS: List[Dict[str, Any]] = [
    {"key": "kanxue", "name": "看雪论坛", "entry": "script/kanxue/sign_in.py",
     "path": ("kanxue", "accounts"), "creds": ("cookie",), "creds_all": True,
     "timeout": 300, "ci": True},
    {"key": "wps", "name": "WPS Office", "entry": "script/wps/main.py",
     "path": ("wps", "accounts"), "creds": ("cookies",), "creds_all": True,
     "timeout": 1500, "ci": True},
    {"key": "smzdm", "name": "什么值得买", "entry": "script/smzdm/sign_daily_task/main.py",
     "path": ("smzdm", "accounts"), "creds": ("cookie", "setting"), "creds_all": False,
     "timeout": 1500, "ci": True},
    {"key": "trae", "name": "Trae CN", "entry": "script/trae/main.py",
     "path": ("trae", "accounts"), "creds": ("sessionid", "session", "access_token"), "creds_all": False,
     "timeout": 900, "ci": True},
]

PLATFORM_BY_KEY = {p["key"]: p for p in PLATFORMS}


def gh_output(pairs: Dict[str, str]) -> None:
    """写入 GitHub Actions 的 step 输出。"""
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as fh:
        for key, value in pairs.items():
            fh.write(f"{key}={value}\n")


def gh_announce(level: str, message: str) -> None:
    """输出 GitHub Actions 注解（notice / warning / error）。"""
    print(f"::{level}::{message}")


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def placeholder_set() -> set:
    """收集模板文件里的占位文本，用于识别「还是模板默认值」的字段。"""
    values = set()
    try:
        template = load_json(TEMPLATE_PATH)
    except Exception:
        return values

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            text = node.strip()
            if text:
                values.add(text)

    walk(template)
    return values


def is_placeholder(value: Any, placeholders: set) -> bool:
    """判断字段值是否仍为占位内容。"""
    if value is None:
        return True
    if isinstance(value, (int, float, bool)):
        return False
    text = str(value).strip()
    if not text:
        return True
    if text in placeholders:
        return True
    if "MASKED" in text.upper():
        return True
    return False


def dig(config: Any, path: Sequence[str]) -> Any:
    """按路径取节点；任一层缺失都返回 None。"""
    node = config
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def count_configured(node: Any, spec: Dict[str, Any], placeholders: set) -> int:
    """统计指定节点下「看起来已填写凭据」的账号数量。"""
    if not isinstance(node, list):
        return 0
    total = 0
    for account in node:
        if not isinstance(account, dict):
            continue
        checks = [not is_placeholder(account.get(field), placeholders) for field in spec["creds"]]
        ready = all(checks) if spec["creds_all"] else any(checks)
        if ready:
            total += 1
    return total


def summarize(config: Any, placeholders: set) -> List[Dict[str, Any]]:
    """返回每个平台的配置状态。"""
    rows = []
    for spec in PLATFORMS:
        node = dig(config, spec["path"])
        count = count_configured(node, spec, placeholders)
        rows.append({**spec, "accounts": count, "configured": count > 0})
    return rows


def cmd_validate(config_path: Path) -> int:
    if not config_path.exists():
        gh_announce("error", f"配置文件不存在: {config_path}")
        return 1
    try:
        config = load_json(config_path)
    except json.JSONDecodeError as exc:
        gh_announce("error", f"配置不是合法 JSON: {exc}")
        return 1
    if not isinstance(config, dict):
        gh_announce("error", "配置顶层必须是 JSON 对象")
        return 1

    placeholders = placeholder_set()
    rows = summarize(config, placeholders)

    known_top = {"huaruntong"} | {spec["path"][0] for spec in PLATFORMS}
    unknown = sorted(set(config) - known_top)
    if unknown:
        gh_announce("warning", f"存在未知的顶层配置节点: {', '.join(unknown)}（脚本会忽略）")

    print(f"{'平台':<22}{'key':<20}{'账号数':>6}  状态")
    print("-" * 62)
    for row in rows:
        state = "已配置" if row["configured"] else ("未配置" if row["ci"] else "未配置(不纳入定时任务)")
        print(f"{row['name']:<22}{row['key']:<20}{row['accounts']:>6}  {state}")

    ci_ready = [row for row in rows if row["ci"] and row["configured"]]
    if not ci_ready:
        gh_announce("error", "没有任何平台配置了有效账号，请检查 TOKEN_JSON 是否仍是模板内容")
        return 1

    gh_announce("notice", f"可用于定时任务的平台 {len(ci_ready)} 个：" + "、".join(row["name"] for row in ci_ready))
    return 0


def cmd_matrix(config_path: Path, select: str) -> int:
    try:
        config = load_json(config_path)
    except Exception as exc:
        gh_announce("error", f"读取配置失败: {exc}")
        return 1

    placeholders = placeholder_set()
    rows = summarize(config, placeholders)

    wanted: Optional[set] = None
    if select.strip():
        wanted = {item.strip() for item in select.split(",") if item.strip()}
        unknown = sorted(wanted - set(PLATFORM_BY_KEY))
        if unknown:
            gh_announce("error", f"未知平台 key: {', '.join(unknown)}")
            return 2

    matrix = []
    for row in rows:
        if not row["ci"] or not row["configured"]:
            continue
        if wanted is not None and row["key"] not in wanted:
            continue
        matrix.append({
            "key": row["key"],
            "name": row["name"],
            "entry": row["entry"],
            "timeout": row["timeout"],
        })

    gh_output({
        "matrix": json.dumps(matrix, ensure_ascii=False, separators=(",", ":")),
        "count": str(len(matrix)),
    })
    print(json.dumps(matrix, ensure_ascii=False, indent=2))

    skipped = [row["name"] for row in rows if row["ci"] and not row["configured"]]
    if skipped:
        gh_announce("notice", "未配置账号、本次跳过：" + "、".join(skipped))
    excluded = [row["name"] for row in rows if not row["ci"]]
    if excluded:
        gh_announce("notice", "按设计不纳入定时任务：" + "、".join(excluded))

    if wanted is not None:
        missing = sorted(key for key in wanted if key not in {item["key"] for item in matrix})
        if missing:
            gh_announce("warning", "请求运行但未配置或不可用：" + ", ".join(missing))
    return 0


def cmd_platform(config_path: Path, key: str, select: str = "") -> int:
    spec = PLATFORM_BY_KEY.get(key)
    if spec is None:
        gh_announce("error", f"未知平台 key: {key}")
        return 2

    # 手动触发时允许用 platforms 输入收窄范围：未选中的平台直接判为「本次不跑」，
    # 由 job 内的 if 跳过，不再需要把矩阵从上游 job 传下来。
    selected: Optional[set] = None
    if select.strip():
        selected = {item.strip() for item in select.split(",") if item.strip()}
    if selected is not None and key not in selected:
        gh_output({"configured": "false", "account_count": "0"})
        print(json.dumps({"key": key, "name": spec["name"], "configured": False,
                          "accounts": 0, "selected": False}, ensure_ascii=False))
        gh_announce("notice", f"{spec['name']} 不在本次 platforms 选择中，跳过")
        return 0

    try:
        config = load_json(config_path)
    except Exception as exc:
        gh_announce("error", f"读取配置失败: {exc}")
        return 1

    placeholders = placeholder_set()
    count = count_configured(dig(config, spec["path"]), spec, placeholders)
    configured = count > 0

    gh_output({"configured": "true" if configured else "false", "account_count": str(count)})
    print(json.dumps({"key": key, "name": spec["name"], "configured": configured,
                      "accounts": count, "selected": True}, ensure_ascii=False))
    if not configured:
        gh_announce("notice", f"{spec['name']} 未配置有效账号，跳过本次运行")
    if not spec["ci"]:
        gh_announce("warning", f"{spec['name']} 不纳入定时任务，仅支持手动运行")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cat-Checkin CI 平台守卫")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="配置文件路径")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate", action="store_true", help="校验配置结构")
    mode.add_argument("--matrix", action="store_true", help="列出可运行的平台（巡检用）")
    mode.add_argument("--platform", metavar="KEY", help="判断单个平台是否已配置")
    parser.add_argument("--select", default="", help="仅选择指定平台（逗号分隔，配合 --matrix / --platform）")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if args.validate:
        return cmd_validate(config_path)
    if args.matrix:
        return cmd_matrix(config_path, args.select)
    return cmd_platform(config_path, args.platform, args.select)


if __name__ == "__main__":
    raise SystemExit(main())
