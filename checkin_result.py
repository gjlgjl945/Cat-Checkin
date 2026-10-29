#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行结果落盘：让「所有平台跑完后统一推送一次」成为可能。

为什么需要它
------------
每个平台是一个独立的 GitHub Actions job（并行、互不依赖）。如果各自结束时
推一条，一天两次运行就是 8 条消息 —— 既刷屏，也会把 Server酱 免费额度（每天 5 条）打爆。

约定
----
- 设置了环境变量 ``CHECKIN_RESULT_DIR`` → 脚本**不推送**，把结果写成
  ``<dir>/<platform>.json``，由汇总作业（ci/summarize.py）合并后发一条。
- 没设置 → 保持原来的行为，脚本自己推送（本地单独跑的时候就是这种）。
- 写文件失败绝不影响签到结果与退出码：结果上报是附属能力，不能反过来破坏主流程。

文件格式（schema 1）
--------------------
::

    {"schema": 1, "platform": "wps", "name": "WPS Office",
     "total": 1, "success": 1, "failed": 0, "note": "",
     "lines": ["📊 执行统计:", "✅ 成功: 1 个账号"]}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

RESULT_DIR_ENV = "CHECKIN_RESULT_DIR"
SCHEMA_VERSION = 1


def defer_notification() -> bool:
    """是否把推送推迟到汇总作业（CI 里为 True）。"""
    return bool(os.environ.get(RESULT_DIR_ENV, "").strip())


def result_dir() -> Optional[Path]:
    raw = os.environ.get(RESULT_DIR_ENV, "").strip()
    return Path(raw) if raw else None


def write_result(platform: str, name: str, total: int, success: int, failed: int,
                 lines: Optional[List[str]] = None, note: str = "") -> Optional[Path]:
    """把本次运行结果写入 JSON；返回写入路径，失败或未启用时返回 None。"""
    directory = result_dir()
    if directory is None:
        return None

    payload = {
        "schema": SCHEMA_VERSION,
        "platform": platform,
        "name": name,
        "total": int(total),
        "success": int(success),
        "failed": int(failed),
        "note": note,
        "lines": [str(line) for line in (lines or [])],
    }
    path = directory / f"{platform}.json"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        # 显式 newline="\n"：Windows 上文本模式会写成 CRLF，跨平台比对会整文件不同
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        return path
    except OSError:
        # 结果上报是附属能力：写不进去也不该让签到失败
        return None


def load_results(directory: Path) -> List[Dict[str, Any]]:
    """读取目录下所有平台结果；跳过坏文件并记录原因。"""
    results: List[Dict[str, Any]] = []
    if not directory.exists():
        return results
    for path in sorted(directory.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("platform"):
            results.append(data)
    return results


def totals(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """汇总各平台计数。"""
    return {
        "platforms": len(results),
        "total": sum(int(item.get("total") or 0) for item in results),
        "success": sum(int(item.get("success") or 0) for item in results),
        "failed": sum(int(item.get("failed") or 0) for item in results),
    }
