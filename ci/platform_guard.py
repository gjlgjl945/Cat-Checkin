#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 平台守卫。

用途
----
GitHub Actions 需要解决三个问题：一是「某个平台没配账号时不要让工作流变红」，
二是「配置写错时要尽早报错」，三是「平台注册表与工作流的静态矩阵不能漂移」。
本脚本负责这三件事，并且**只输出平台名与账号数量，不打印任何凭据值**。

子命令
------
``--validate``          校验 config/token.json 结构，并打印各平台账号数量
``--matrix``            列出可运行的平台（JSON），用于本地巡检与手动触发前确认
``--platform <key>``    判断单个平台是否已配置，供 job 内跳过未配置平台
``--check-matrix``      校验工作流的静态矩阵是否与下方注册表一致（只有唯一事实来源）
``--sync-matrix``       按注册表重写工作流的静态矩阵（改注册表后运行一次）

退出码
------
0  正常（含「平台未配置」，由调用方决定是否跳过）
1  配置不可用（文件缺失、JSON 非法、没有任何平台配置了账号），或矩阵发生漂移
2  参数错误（未知平台 key）

Author: Cat-Checkin CI
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "token.json"
TEMPLATE_PATH = REPO_ROOT / "config" / "template_token.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "checkin.yml"

# 工作流里静态矩阵的边界标记。矩阵区块由 --sync-matrix 生成，--check-matrix 校验，
# 这样「平台清单」只有注册表这一个事实来源，不会再出现「加了平台却忘记加矩阵」。
MATRIX_BEGIN = "# >>> PLATFORM_MATRIX"
MATRIX_END = "# <<< PLATFORM_MATRIX"
MATRIX_INDENT = " " * 10

# 平台注册表。字段含义：
#   key       工作流矩阵标识，同时也是 dispatch 输入里使用的名字
#   name      展示名（Actions 任务标题）
#   entry     入口脚本（相对仓库根目录）
#   path      config/token.json 中的节点路径
#   creds     判定「该账号已填写」所需字段
#   creds_all True 表示 creds 全部必填，False 表示任一即可
#   timeout   单平台超时（秒），用于 shell 层 timeout，避免单平台拖垮整条流水线
#
# 约定：本表即「本次要跑的全部平台」，四个平台都纳入定时任务。新增平台时在此加一行，
# 然后执行 `python ci/platform_guard.py --sync-matrix` 同步工作流（CI 会校验一致性）。
PLATFORMS: List[Dict[str, Any]] = [
    {"key": "kanxue", "name": "看雪论坛", "entry": "script/kanxue/sign_in.py",
     "path": ("kanxue", "accounts"), "creds": ("cookie",), "creds_all": True,
     "timeout": 300},
    {"key": "wps", "name": "WPS Office", "entry": "script/wps/main.py",
     "path": ("wps", "accounts"), "creds": ("cookies",), "creds_all": True,
     "timeout": 1500},
    {"key": "smzdm", "name": "什么值得买", "entry": "script/smzdm/sign_daily_task/main.py",
     "path": ("smzdm", "accounts"), "creds": ("cookie",), "creds_all": True,
     "timeout": 1500},
    {"key": "trae", "name": "Trae CN", "entry": "script/trae/main.py",
     "path": ("trae", "accounts"), "creds": ("sessionid", "session", "access_token"), "creds_all": False,
     "timeout": 900},
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


def dig(config: Any, path: Sequence[str]) -> Any:
    """按路径取节点；任一层缺失都返回 None。"""
    node = config
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def iter_accounts(node: Any) -> List[Dict[str, Any]]:
    """把配置节点规整成「账号字典列表」，非字典条目直接忽略。"""
    if not isinstance(node, list):
        return []
    return [item for item in node if isinstance(item, dict)]


def count_configured(node: Any, spec: Dict[str, Any], placeholders: set) -> int:
    """统计指定节点下「看起来已填写凭据」的账号数量。"""
    total = 0
    for account in iter_accounts(node):
        checks = [not is_placeholder(account.get(field), placeholders) for field in spec["creds"]]
        ready = all(checks) if spec["creds_all"] else any(checks)
        if ready:
            total += 1
    return total


def summarize(config: Any, placeholders: set) -> List[Dict[str, Any]]:
    """返回每个平台的配置状态。"""
    rows = []
    for spec in PLATFORMS:
        count = count_configured(dig(config, spec["path"]), spec, placeholders)
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
    except OSError as exc:
        gh_announce("error", f"读取配置失败: {exc}")
        return 1
    if not isinstance(config, dict):
        gh_announce("error", "配置顶层必须是 JSON 对象")
        return 1

    placeholders = placeholder_set()
    rows = summarize(config, placeholders)

    unknown = sorted(set(config) - {spec["path"][0] for spec in PLATFORMS})
    if unknown:
        gh_announce("warning", f"存在未知的顶层配置节点: {', '.join(unknown)}（脚本会忽略）")

    print(f"{'平台':<22}{'key':<16}{'账号数':>6}  状态")
    print("-" * 58)
    for row in rows:
        state = "已配置" if row["configured"] else "未配置"
        print(f"{row['name']:<22}{row['key']:<16}{row['accounts']:>6}  {state}")

    ready = [row for row in rows if row["configured"]]
    if not ready:
        gh_announce("error", "没有任何平台配置了有效账号，请检查 TOKEN_JSON 是否仍是模板内容")
        return 1

    gh_announce("notice", f"已配置平台 {len(ready)} 个：" + "、".join(row["name"] for row in ready))
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


def cmd_matrix(config_path: Path, select: str) -> int:
    try:
        config = load_json(config_path)
    except (OSError, json.JSONDecodeError) as exc:
        gh_announce("error", f"读取配置失败: {exc}")
        return 1

    try:
        wanted = parse_select(select)
    except ValueError as exc:
        gh_announce("error", str(exc))
        return 2

    rows = summarize(config, placeholder_set())
    matrix = [
        {"key": row["key"], "name": row["name"], "entry": row["entry"], "timeout": row["timeout"]}
        for row in rows
        if row["configured"] and (wanted is None or row["key"] in wanted)
    ]
    print(json.dumps(matrix, ensure_ascii=False, indent=2))

    skipped = [row["name"] for row in rows if not row["configured"]]
    if skipped:
        gh_announce("notice", "未配置账号、本次跳过：" + "、".join(skipped))
    if wanted is not None:
        missing = sorted(key for key in wanted if key not in {item["key"] for item in matrix})
        if missing:
            gh_announce("warning", "请求运行但未配置：" + ", ".join(missing))
    return 0


def cmd_platform(config_path: Path, key: str, select: str = "") -> int:
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

    try:
        config = load_json(config_path)
    except (OSError, json.JSONDecodeError) as exc:
        gh_announce("error", f"读取配置失败: {exc}")
        return 1

    count = count_configured(dig(config, spec["path"]), spec, placeholder_set())
    configured = count > 0

    gh_output({"configured": "true" if configured else "false", "account_count": str(count)})
    print(json.dumps({"key": key, "name": spec["name"], "configured": configured,
                      "accounts": count, "selected": True}, ensure_ascii=False))
    if not configured:
        gh_announce("notice", f"{spec['name']} 未配置有效账号，跳过本次运行")
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


def _split_workflow(text: str) -> Optional[tuple]:
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
    # 一旦提交进去，Linux 上 bash 读到的 shebang/引号行为都会变（CI 里表现为莫名语法错误）。
    with open(WORKFLOW_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(head + expected + tail) + "\n")
    print(f"已同步 {len(expected)} 个平台到 {WORKFLOW_PATH}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cat-Checkin CI 平台守卫")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="配置文件路径")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate", action="store_true", help="校验配置结构")
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

    config_path = Path(args.config)
    if args.validate:
        return cmd_validate(config_path)
    if args.matrix:
        return cmd_matrix(config_path, args.select)
    return cmd_platform(config_path, args.platform, args.select)


if __name__ == "__main__":
    raise SystemExit(main())
