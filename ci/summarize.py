#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总各平台的运行结果，只推一条 Server酱 消息。

为什么单独做这一步
------------------
四个平台是并行的独立 job，各自结束时推送会变成「一天 8 条」：既刷屏，
也会超出 Server酱 免费版每天 5 条的额度。因此：
- 平台脚本在 CI 里只把结果写成 JSON（见 checkin_result.py）；
- 本脚本在所有平台跑完后合并、去重、发一条摘要。

判断「谁本该有结果」
--------------------
从平台注册表 + 当前配置推出「已配置、应当运行」的平台，再和实际拿到的结果对比：
少了的平台会被标成「无结果（可能超时或任务中断）」，不会静默消失。

退出码
------
0  已发送，或本来就没有可发的内容（例如所有平台都未配置）
1  配了推送但发送失败（这样「没通知到」不会显示成绿色）
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (str(REPO_ROOT), str(REPO_ROOT / "ci")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from checkin_result import RESULT_DIR_ENV, load_results, totals  # noqa: E402
from notification import notification_manager  # noqa: E402


def expected_platforms(select: str = "") -> List[Dict[str, Any]]:
    """返回「已配置、本轮应当运行」的平台（读注册表 + 当前配置 + platforms 过滤）。

    select 必须和 checkin 作业用的一致，否则手动只跑一个平台时，
    其余平台会被误判成「没有产出结果」。
    """
    try:
        import platform_guard as guard
    except Exception as exc:  # 注册表导入失败不应让汇总整体失败
        print(f"::warning::无法读取平台注册表，跳过「缺失平台」检查: {exc}")
        return []

    rows = [row for row in guard.inspect_all(None, None) if row["configured"]]
    try:
        wanted = guard.parse_select(select)
    except ValueError as exc:
        print(f"::warning::{exc}")
        return rows
    if wanted is not None:
        rows = [row for row in rows if row["key"] in wanted]
    return rows


def build_message(results: List[Dict[str, Any]], expected: List[Dict[str, Any]]) -> Dict[str, str]:
    """组装标题与正文。"""
    # 按注册表顺序排列，避免每次运行因文件名字母序而顺序漂移
    order = {row["key"]: index for index, row in enumerate(expected)}
    results = sorted(results, key=lambda item: order.get(item.get("platform"), len(order)))
    stats = totals(results)
    seen = {item.get("platform") for item in results}
    missing = [row for row in expected if row["key"] not in seen]

    if stats["failed"]:
        title = f"签到汇总：{stats['failed']} 个账号失败"
    elif missing:
        title = f"签到汇总：{len(missing)} 个平台无结果"
    else:
        title = f"签到汇总：全部成功（{stats['success']} 个账号）"

    lines: List[str] = [
        f"📊 平台 {stats['platforms']} 个 · 账号 {stats['total']} 个 · "
        f"成功 {stats['success']} · 失败 {stats['failed']}",
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    for item in results:
        name = item.get("name") or item.get("platform")
        total = int(item.get("total") or 0)
        success = int(item.get("success") or 0)
        mark = "✅" if int(item.get("failed") or 0) == 0 else "❌"
        lines.append(f"## {mark} {name} {success}/{total}")
        for detail in item.get("lines") or []:
            text = str(detail).strip()
            if text:
                lines.append(text)
        lines.append("")

    for row in missing:
        lines.append(f"## ⚠️ {row['name']} 无结果")
        lines.append("该平台没有产出结果文件，可能是超时或任务被中断，请查看对应 job 日志。")
        lines.append("")

    return {"title": title, "content": "\n".join(lines).strip()}


def write_step_summary(message: Dict[str, str], results: List[Dict[str, Any]]) -> None:
    """把同样的内容写进 Actions 运行摘要，方便不点日志也能看。"""
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    rows = ["| 平台 | 账号 | 成功 | 失败 |", "| --- | --- | --- | --- |"]
    for item in results:
        rows.append(f"| {item.get('name')} | {item.get('total')} | {item.get('success')} | {item.get('failed')} |")
    try:
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(f"### {message['title']}\n\n" + "\n".join(rows) + "\n\n")
            fh.write("<details><summary>完整内容</summary>\n\n```\n" + message["content"] + "\n```\n\n</details>\n")
    except OSError:
        pass


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="汇总各平台结果并推送一条通知")
    parser.add_argument("--dir", default=os.environ.get(RESULT_DIR_ENV, ".checkin-results"),
                        help="结果目录，默认取 CHECKIN_RESULT_DIR 或 .checkin-results")
    parser.add_argument("--no-send", action="store_true", help="只打印，不实际推送")
    parser.add_argument("--select", default=os.environ.get("SELECT", ""),
                        help="与 checkin 一致的 platforms 过滤，避免误报「无结果」")
    args = parser.parse_args(argv)

    directory = Path(args.dir)
    results = load_results(directory)
    expected = expected_platforms(args.select)

    if not results:
        print(f"::notice::{directory} 下没有任何平台结果，本次不发送汇总（可能是全部未配置或被跳过）")
        return 0

    message = build_message(results, expected)
    print("=" * 60)
    print(message["title"])
    print("=" * 60)
    print(message["content"])
    print("=" * 60)
    write_step_summary(message, results)

    if args.no_send:
        print("（--no-send：未实际推送）")
        return 0

    if not notification_manager.is_enabled():
        print("::notice::未配置 Server酱 SendKey，跳过推送（内容已打印在上面）")
        return 0

    print(f"推送通道：{notification_manager.describe()}")
    ok = notification_manager.send(message["title"], message["content"])
    if not ok:
        print("::error::汇总推送失败，请检查 SendKey、当日额度（免费 5 条/天）与微信绑定")
        return 1
    print("::notice::汇总推送已发送")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
