#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按平台拆分的配置文件：定位、规范化解包、旧配置回退。

设计要点
--------
1. **一个平台一份文件**：``config/token.<key>.json``。文件名固定由平台 key 推导，
   任何脚本都只读自己那份，改坏/删掉其它平台的文件不会影响本平台。
2. **结构保持不变**：文件内容仍是旧 ``token.json`` 里的那一个顶层节点，例如
   ``{"wps": {"accounts": [...]}}``。这样各脚本的字段解析逻辑一行都不用改，
   旧配置也能按顶层 key 原样切开。
3. **兼容扁平写法**：只写 ``{"accounts": [...]}`` 也接受——文件名已经说明了平台，
   再强制套一层 ``{"wps": ...}`` 属于重复。两种写法在这里统一成同一种结构。
4. **旧文件回退**：平台文件不存在、但旧 ``config/token.json`` 还在时，读取旧文件并
   由调用方给出迁移提示；平台文件一旦存在就以它为准（不再看旧文件）。

本模块只依赖标准库，CI 的复合动作与守卫脚本都可以直接 import，避免三处各写一套规则。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# 平台 key 与 workflow 矩阵、ci/platform_guard.py 的注册表保持一致
PLATFORM_KEYS: Tuple[str, ...] = ("kanxue", "wps", "smzdm", "trae")

CONFIG_DIR_NAME = "config"
LEGACY_FILE_NAME = "token.json"

# 回退来源标记，供调用方决定提示文案
SOURCE_EXPLICIT = "explicit"   # --config 显式指定
SOURCE_PLATFORM = "platform"   # config/token.<key>.json
SOURCE_LEGACY = "legacy"       # 回退到旧 config/token.json
SOURCE_MISSING = "missing"     # 哪都不存在


class MissingPlatformNode(ValueError):
    """文件存在、但里面没有该平台的节点。

    单独一个异常类型是为了区分两种场景：独立文件里缺节点多半是「复制了别家的文件」，
    属于配置错误；而旧 token.json 里缺节点只是「这个平台本来就没配」，属于未配置。
    """


def config_dir(root: Optional[Path] = None, directory: Optional[str] = None) -> Path:
    """配置目录：默认仓库根目录下的 config/；directory 可覆盖（CI 守卫的 --config-dir）。"""
    if directory:
        return Path(directory)
    root = Path(root) if root else Path(__file__).resolve().parent
    return root / CONFIG_DIR_NAME


def platform_config_path(key: str, root: Optional[Path] = None,
                         directory: Optional[str] = None) -> Path:
    """平台配置文件路径：config/token.<key>.json"""
    return config_dir(root, directory) / f"token.{key}.json"


def legacy_config_path(root: Optional[Path] = None, directory: Optional[str] = None) -> Path:
    """拆分前的单文件配置：config/token.json（迁移完成后可删除）"""
    return config_dir(root, directory) / LEGACY_FILE_NAME


def resolve_path(key: str, explicit: Optional[str] = None,
                 root: Optional[Path] = None,
                 directory: Optional[str] = None) -> Tuple[Path, str]:
    """确定某个平台该读哪个文件。

    Args:
        key: 平台 key
        explicit: ``--config`` 传入的路径；给了就无条件使用（不判断存在性，
            由调用方负责报「文件不存在」，避免路径打错时静默改成读别的文件）
        root: 仓库根目录，默认本文件所在目录
        directory: 配置目录覆盖（与 root 二选一）

    Returns:
        (路径, 来源标记)。来源为 SOURCE_LEGACY 时调用方应提示迁移。
    """
    if explicit:
        return Path(explicit), SOURCE_EXPLICIT

    own = platform_config_path(key, root, directory)
    if own.exists():
        return own, SOURCE_PLATFORM

    legacy = legacy_config_path(root, directory)
    if legacy.exists():
        return legacy, SOURCE_LEGACY

    return own, SOURCE_MISSING


def normalize_node(data: Any, key: str) -> Dict[str, Any]:
    """从整个 JSON 对象里取出属于 key 的节点。

    兼容两种写法：
    - ``{"kanxue": {"accounts": [...]}}``（与旧 token.json 一致）
    - ``{"accounts": [...]}``（扁平写法，文件名已表明平台）

    Raises:
        ValueError: 顶层不是对象、缺少该平台的节点、或节点不是对象。
    """
    if not isinstance(data, dict):
        raise ValueError(f"配置文件顶层必须是 JSON 对象（实际是 {type(data).__name__}）")

    if key in data:
        node = data[key]
        # 兼容历史上出现过的双层嵌套 {"kanxue": {"kanxue": {...}}}
        if isinstance(node, dict) and key in node:
            node = node[key]
    elif "accounts" in data:
        node = data
    else:
        others = ", ".join(sorted(k for k in data if isinstance(data[k], dict))) or "无"
        raise MissingPlatformNode(
            f"配置里没有 {key} 节点（现有节点：{others}）。"
            f"每个平台应只放自己那份，例如 {{\"{key}\": {{\"accounts\": [...]}}}}"
        )

    if not isinstance(node, dict):
        raise ValueError(f"{key} 节点必须是 JSON 对象（实际是 {type(node).__name__}）")

    accounts = node.get("accounts", [])
    if not isinstance(accounts, list):
        raise ValueError(f"{key}.accounts 必须是数组（实际是 {type(accounts).__name__}）")
    return node


def load_node(path: Path, key: str) -> Optional[Dict[str, Any]]:
    """读取文件并取出 key 节点；文件不存在返回 None，格式错误抛 ValueError。"""
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} 不是合法 JSON: {exc}") from exc
    return normalize_node(data, key)


def accounts_of(path: Path, key: str) -> list:
    """读取并返回 accounts 数组（文件缺失或格式错误时为空列表，容错优先）。"""
    try:
        node = load_node(path, key)
    except (OSError, ValueError):
        return []
    return node.get("accounts", []) if node else []


def describe_source(source: str) -> str:
    """把来源标记转成给用户看的说明。"""
    return {
        SOURCE_EXPLICIT: "命令行指定",
        SOURCE_PLATFORM: "平台独立配置",
        SOURCE_LEGACY: "旧 token.json（建议迁移）",
        SOURCE_MISSING: "缺失",
    }.get(source, source)
