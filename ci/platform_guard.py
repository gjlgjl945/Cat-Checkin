#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 平台守卫。

用途
----
GitHub Actions 需要解决四个问题：一是「某个平台没配账号时不要让工作流变红」，
二是「配置写错时要尽早报错」，三是「平台注册表与工作流的静态矩阵不能漂移」，
四是「一个平台的配置坏掉不能连累其它平台」。本脚本负责这四件事，并且
**只输出平台名、账号数量与文件路径，不打印任何凭据值**。

配置来源
--------
每个平台只读自己那份文件：``config/token.<key>.json``（内容仍是旧 token.json 里的
那一个顶层节点）。旧 ``config/token.json`` 仍存在时会回退读取并给出迁移提示。

子命令
------
``--validate``          逐平台校验配置，打印账号数、文件与状态
``--matrix``            列出可运行的平台（JSON），用于本地巡检与手动触发前确认
``--platform <key>``    判断单个平台是否已配置，供 job 内跳过未配置平台
``--check-matrix``      校验工作流的静态矩阵是否与下方注册表一致（唯一事实来源）
``--sync-matrix``       按注册表重写工作流的静态矩阵（改注册表后运行一次）

退出码
------
0  正常（含「该平台未配置」，由调用方决定是否跳过）
1  没有任何平台可用，或矩阵发生漂移，或指定平台的配置存在但不可解析
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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from platform_config import (  # noqa: E402 - 依赖上面的 sys.path 设置
    SOURCE_EXPLICIT,
    SOURCE_LEGACY,
    SOURCE_MISSING,
    SOURCE_PLATFORM,
    MissingPlatformNode,
    normalize_node,
    resolve_path,
)

TEMPLATE_PATH = REPO_ROOT / "config" / "template_token.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "checkin.yml"

# 工作流里静态矩阵的边界标记。矩阵区块由 --sync-matrix 生成，--check-matrix 校验，
# 这样「平台清单」只有注册表这一个事实来源，不会再出现「加了平台却忘记加矩阵」。
MATRIX_BEGIN = "# >>> PLATFORM_MATRIX"
MATRIX_END = "# <<< PLATFORM_MATRIX"
MATRIX_INDENT = " " * 10

# 平台注册表。字段含义：
#   key       工作流矩阵标识，同时也是 dispatch 输入与配置文件名后缀
#   name      展示名（Actions 任务标题）
#   entry     入口脚本（相对仓库根目录）
#   creds     判定「该账号已填写」所需字段
#   creds_all True 表示 creds 全部必填，False 表示任一即可
#   timeout   单平台超时（秒），用于 shell 层 timeout，避免单平台拖垮整条流水线
#
# 约定：本表即「本次要跑的全部平台」。新增平台时在此加一行，然后执行
# `python ci/platform_guard.py --sync-matrix` 同步工作流（CI 会校验一致性）。
PLATFORMS: List[Dict[str, Any]] = [
    {"key": "kanxue", "name": "看雪论坛", "entry": "script/kanxue/sign_in.py",
     "creds": ("cookie",), "creds_all": True, "timeout": 300},
    {"key": "wps", "name": "WPS Office", "entry": "script/wps/main.py",
     "creds": ("cookies",), "creds_all": True, "timeout": 1500},
    {"key": "smzdm", "name": "什么值得买", "entry": "script/smzdm/sign_daily_task/main.py",
     "creds": ("cookie",), "creds_all": True, "timeout": 1500},
    {"key": "trae", "name": "Trae CN", "entry": "script/trae/main.py",
     "creds": ("sessionid", "session", "access_token"), "creds_all": False, "timeout": 900},
]

PLATFORM_BY_KEY = {spec["key"]: spec for spec in PLATFORMS}


def gh_output(pairs: Dict[str, str]) -> None:
    """写入 GitHub Actions 的 step 输出。"""
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    try:
        with open(target, "a", encoding="utf-8") as fh:
            for key, value in pairs.items():
                fh.write(f"{key}={value}\n")
    except OSError as exc:  # 输出写入失败不应影响判定结果
        print(f"::warning::写入 GITHUB_OUTPUT 失败: {exc}")


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
    except (OSError, json.JSONDecodeError):
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
    if isinstance(value, bool):
        # user_id 之类允许为 0，但布尔值不是有效凭据
        return True
    if isinstance(value, (int, float)):
        return False
    text = str(value).strip()
    if not text:
        return True
    if text in placeholders:
        return True
    if "MASKED" in text.upper():
        return True
    return False


def count_configured(node: Dict[str, Any], spec: Dict[str, Any], placeholders: set) -> int:
    """统计节点下「看起来已填写凭据」的账号数量。"""
    total = 0
    accounts = node.get("accounts")
    if not isinstance(accounts, list):
        return 0
    for account in accounts:
        if not isinstance(account, dict):
            continue
        checks = [not is_placeholder(account.get(field), placeholders) for field in spec["creds"]]
        ready = all(checks) if spec["creds_all"] else any(checks)
        if ready:
            total += 1
    return total


def _display_path(path: Path) -> str:
    """把绝对路径压成相对仓库根目录的形式，日志更好读。"""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except (ValueError, OSError):
        return str(path)


def inspect_platform(spec: Dict[str, Any], explicit: Optional[str],
                     directory: Optional[str], placeholders: set) -> Dict[str, Any]:
    """读取单个平台的配置并给出状态。

    Returns:
        dict，含 path/source/accounts/configured/status/error；
        status 取值 "ok" / "missing" / "invalid"。只有该平台自己的文件会被读取。
    """
    path, source = resolve_path(spec["key"], explicit, REPO_ROOT, directory)
    row: Dict[str, Any] = {
        "key": spec["key"],
        "name": spec["name"],
        "entry": spec["entry"],
        "timeout": spec["timeout"],
        "path": path,
        "source": source,
        "accounts": 0,
        "configured": False,
        "status": "missing",
        "error": "",
    }

    if not path.exists():
        # 显式指定却不存在属于用法错误，单独标出来
        if source == SOURCE_EXPLICIT:
            row["status"] = "invalid"
            row["error"] = f"指定的配置文件不存在: {path}"
        return row

    try:
        node = normalize_node(load_json(path), spec["key"])
    except MissingPlatformNode as exc:
        # 旧 token.json 里没有该节点 = 这个平台本来就没配；独立文件里缺节点 = 内容放错了
        if source == SOURCE_LEGACY:
            row["error"] = str(exc)
        else:
            row["status"] = "invalid"
            row["error"] = str(exc)
        return row
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        row["status"] = "invalid"
        row["error"] = str(exc)
        return row

    count = count_configured(node, spec, placeholders)
    row.update({"accounts": count, "configured": count > 0, "status": "ok"})
    return row


def inspect_all(explicit: Optional[str], directory: Optional[str]) -> List[Dict[str, Any]]:
    placeholders = placeholder_set()
    return [inspect_platform(spec, explicit, directory, placeholders) for spec in PLATFORMS]


def _source_label(source: str) -> str:
    return {
        SOURCE_EXPLICIT: "命令行指定",
        SOURCE_PLATFORM: "",
        SOURCE_LEGACY: "旧 token.json",
        SOURCE_MISSING: "",
    }.get(source, source)


def cmd_validate(explicit: Optional[str], directory: Optional[str]) -> int:
    rows = inspect_all(explicit, directory)

    print(f"{'平台':<20}{'账号数':>6}  状态        配置文件")
    print("-" * 78)
    for row in rows:
        if row["status"] == "invalid":
            state = "结构错误"
        elif row["configured"]:
            state = "已配置"
        else:
            state = "未配置"
        note = _source_label(row["source"])
        suffix = f"  ({note})" if note else ""
        print(f"{row['name']:<20}{row['accounts']:>6}  {state:<10}  {_display_path(row['path'])}{suffix}")

    # 结构错误不允许静默通过：否则该平台会在「看起来配了」的情况下永远不跑
    broken = [row for row in rows if row["status"] == "invalid"]
    for row in broken:
        gh_announce("error", f"{row['name']} 配置不可用（{_display_path(row['path'])}）: {row['error']}")

    usable = [row for row in rows if row["configured"]]
    if not usable:
        gh_announce("error", "没有任何平台配置了有效账号，请检查 TOKEN_JSON 是否仍是模板内容")
        return 1

    if broken:
        # 故意不返回 1：坏掉的只是那一个平台，其余平台应当照常运行（隔离要求）
        gh_announce("warning",
                    f"{len(broken)} 个平台配置不可用，这些平台本次会失败，其余平台照常执行")

    # 部分拆分状态：既有独立文件又在读旧文件。若某个平台文件是被「删掉以停用」的，
    # 这里就会悄悄用回旧配置 —— 必须提示，否则现象很难解释。
    split = [row for row in rows if row["source"] == SOURCE_PLATFORM]
    legacy = [row for row in rows if row["source"] == SOURCE_LEGACY]
    if split and legacy:
        gh_announce("warning",
                    "部分平台已拆分、仍在使用旧 token.json："
                    + "、".join(row["name"] for row in legacy)
                    + "。若这些平台是你主动停用的，请删除 config/token.json 以免误用旧配置")

    gh_announce("notice", f"可用平台 {len(usable)} 个：" + "、".join(row["name"] for row in usable))
    return 0


def parse_select(select: str) -> Optional[set]:
    """解析 platforms 输入；空串返回 None 表示「全部」。未知 key 抛 ValueError。"""
    if not select.strip():
        return None
    wanted = {item.strip() for item in select.split(",") if item.strip()}
    unknown = sorted(wanted - set(PLATFORM_BY_KEY))
    if unknown:
        raise ValueError("未知平台 key: " + ", ".join(unknown))
    return wanted


def cmd_matrix(explicit: Optional[str], directory: Optional[str], select: str) -> int:
    try:
        wanted = parse_select(select)
    except ValueError as exc:
        gh_announce("error", str(exc))
        return 2

    rows = inspect_all(explicit, directory)
    matrix = [
        {"key": row["key"], "name": row["name"], "entry": row["entry"], "timeout": row["timeout"]}
        for row in rows
        if row["configured"] and (wanted is None or row["key"] in wanted)
    ]
    print(json.dumps(matrix, ensure_ascii=False, indent=2))

    skipped = [row["name"] for row in rows if not row["configured"] and row["status"] != "invalid"]
    if skipped:
        gh_announce("notice", "未配置账号、本次跳过：" + "、".join(skipped))
    for row in rows:
        if row["status"] == "invalid":
            gh_announce("error", f"{row['name']} 配置不可用: {row['error']}")
    if wanted is not None:
        missing = sorted(key for key in wanted if key not in {item["key"] for item in matrix})
        if missing:
            gh_announce("warning", "请求运行但未配置或不可用：" + ", ".join(missing))
    return 0


def cmd_platform(explicit: Optional[str], directory: Optional[str], key: str,
                 select: str = "") -> int:
    spec = PLATFORM_BY_KEY.get(key)
    if spec is None:
        gh_announce("error", f"未知平台 key: {key}")
        return 2

    # 手动触发时允许用 platforms 输入收窄范围：未选中的平台直接判为「本次不跑」，
    # 由 job 内的 if 跳过，不需要把矩阵从上游 job 传下来。
    try:
        selected = parse_select(select)
    except ValueError as exc:
        gh_announce("error", str(exc))
        return 2
    if selected is not None and key not in selected:
        gh_output({"configured": "false", "account_count": "0"})
        print(json.dumps({"key": key, "name": spec["name"], "configured": False,
                          "accounts": 0, "selected": False}, ensure_ascii=False))
        gh_announce("notice", f"{spec['name']} 不在本次 platforms 选择中，跳过")
        return 0

    row = inspect_platform(spec, explicit, directory, placeholder_set())
    configured = bool(row["configured"])

    gh_output({"configured": "true" if configured else "false",
               "account_count": str(row["accounts"])})
    print(json.dumps({"key": key, "name": spec["name"], "configured": configured,
                      "accounts": row["accounts"], "selected": True,
                      "status": row["status"], "config": _display_path(row["path"])},
                     ensure_ascii=False))

    if row["status"] == "invalid":
        # 配了但读不出来：这个平台自己失败，其它平台不受影响
        gh_announce("error", f"{spec['name']} 配置不可用（{_display_path(row['path'])}）: {row['error']}")
        return 1
    if not configured:
        gh_announce("notice",
                    f"{spec['name']} 未配置有效账号，跳过本次运行"
                    f"（如需启用，参考 config/template_token.json 的 {spec['key']} 节点"
                    f"创建 config/token.{spec['key']}.json）")
        return 0
    if row["source"] == SOURCE_LEGACY:
        gh_announce("warning", f"{spec['name']} 正在读取旧 token.json，建议运行 ci/migrate_config.py 拆分")
    return 0


def render_matrix_lines() -> List[str]:
    """按注册表生成工作流静态矩阵的文本行。"""
    lines = []
    for spec in PLATFORMS:
        lines.append(
            f"{MATRIX_INDENT}- {{ key: {spec['key']}, name: {spec['name']}, "
            f"entry: {spec['entry']}, timeout: {spec['timeout']} }}"
        )
    return lines


def _split_workflow(text: str) -> Optional[Tuple[List[str], List[str], List[str]]]:
    """把工作流拆成 (标记前的行, 现有矩阵块, 标记后的行)；缺少标记时返回 None。"""
    lines = text.splitlines()
    begin = next((i for i, ln in enumerate(lines) if MATRIX_BEGIN in ln), None)
    end = next((i for i, ln in enumerate(lines) if MATRIX_END in ln), None)
    if begin is None or end is None or end <= begin:
        return None
    return lines[:begin + 1], lines[begin + 1:end], lines[end:]


def _describe_mismatch(current: List[str], expected: List[str]) -> str:
    """把矩阵差异整理成一行人类可读的说明。"""
    cur = [ln.strip() for ln in current if ln.strip().startswith("- {")]
    exp = [ln.strip() for ln in expected]
    missing = [ln for ln in exp if ln not in cur]
    extra = [ln for ln in cur if ln not in exp]
    parts = []
    if missing:
        parts.append("缺少 " + str(len(missing)) + " 行: " + " | ".join(missing))
    if extra:
        parts.append("多余 " + str(len(extra)) + " 行: " + " | ".join(extra))
    return "；".join(parts) or "顺序或格式不一致"


def cmd_matrix_sync(check_only: bool) -> int:
    """校验或重写工作流中的静态矩阵。"""
    if not WORKFLOW_PATH.exists():
        gh_announce("error", f"工作流文件不存在: {WORKFLOW_PATH}")
        return 1
    try:
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        gh_announce("error", f"读取工作流失败: {exc}")
        return 1

    parts = _split_workflow(text)
    if parts is None:
        gh_announce("error", f"工作流缺少矩阵标记 {MATRIX_BEGIN} / {MATRIX_END}")
        return 1

    head, current, tail = parts
    expected = render_matrix_lines()

    if check_only:
        if [ln.rstrip() for ln in current] == expected:
            print(f"矩阵一致性校验通过：{len(expected)} 个平台")
            return 0
        gh_announce("error", "工作流矩阵与平台注册表不一致。" + _describe_mismatch(current, expected))
        print("修复方式：python ci/platform_guard.py --sync-matrix")
        return 1

    # 必须显式 newline="\n"：Windows 上 Path.write_text 会把 \n 翻成 \r\n，
    # 一旦提交进去，Linux 上 bash 读到的工作流会出现整文件差异（行尾被改写）。
    with open(WORKFLOW_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(head + expected + tail) + "\n")
    print(f"已同步 {len(expected)} 个平台到 {WORKFLOW_PATH}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cat-Checkin CI 平台守卫")
    parser.add_argument("--config", default=None,
                        help="单文件模式：所有平台都读这一份（仅用于本地演练/兼容旧配置）")
    parser.add_argument("--config-dir", default=None,
                        help="配置目录，默认仓库下的 config/（内部按 token.<key>.json 查找）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate", action="store_true", help="逐平台校验配置")
    mode.add_argument("--matrix", action="store_true", help="列出可运行的平台（巡检用）")
    mode.add_argument("--platform", metavar="KEY", help="判断单个平台是否已配置")
    mode.add_argument("--check-matrix", action="store_true", help="校验工作流矩阵与注册表一致")
    mode.add_argument("--sync-matrix", action="store_true", help="按注册表重写工作流矩阵")
    parser.add_argument("--select", default="", help="仅选择指定平台（逗号分隔，配合 --matrix / --platform）")
    args = parser.parse_args(argv)

    if args.check_matrix:
        return cmd_matrix_sync(check_only=True)
    if args.sync_matrix:
        return cmd_matrix_sync(check_only=False)

    if args.validate:
        return cmd_validate(args.config, args.config_dir)
    if args.matrix:
        return cmd_matrix(args.config, args.config_dir, args.select)
    return cmd_platform(args.config, args.config_dir, args.platform, args.select)


if __name__ == "__main__":
    raise SystemExit(main())
