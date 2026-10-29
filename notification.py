#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通知推送模块：仅 Server酱。

为什么只保留 Server酱
--------------------
一个通道就够用，且免费额度（每天 5 条）本来就只够发摘要；多通道并存会让
「到底发出去了没有」变得难以判断。需要别的落点时，Server酱 后台可以把消息
转发到企业微信/钉钉/飞书，不必在代码里各写一遍。

SendKey 的两种形态（按前缀自动选接口，不用手工配域名）
----------------------------------------------------
- ``SCT`` 开头   → Server酱 Turbo：``POST https://sctapi.ftqq.com/{SendKey}.send``
- ``sctp`` 开头  → Server酱³：    ``POST https://{uid}.push.ft07.com/send/{SendKey}.send``
  uid 是 ``sctp`` 与 ``t`` 之间的数字，例如 ``sctp123tABC`` → uid = ``123``
  两者是独立产品、SendKey 不通用（官方口径）。

请求参数
--------
``title``（必填，**不能含换行**）、``desp``（正文，支持 Markdown）。
本模块会把 title 里的换行压成空格，正文按 Server酱³ 的要求把单换行补成双换行。

成功判定
--------
HTTP 200 且响应 ``code == 0``。其余情况（额度用完、key 失效、限流）一律返回
False，并把服务端原始 message 打到日志里 —— 不再出现「日志说成功、实际没收到」。

配置来源（优先级从高到低）
--------------------------
1. 环境变量 ``SERVERCHAN_SENDKEY`` / ``SERVERCHAN_SCKEY``
2. ``config/notification.json`` 的 ``server.sendkey`` / ``server.sckey``

注意：``config/template_notification.json`` 是公开模板，代码**不会**读它。
把 key 写进模板既不会生效，也有泄露风险。

Author: Cat-Checkin
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Tuple

import requests

logger = logging.getLogger("NotificationManager")

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "notification.json"

# 免费版额度提示（官方口径：Turbo 每天 5 条、每分钟 50 条）
QUOTA_HINT = "（免费版每天 5 条、每分钟 50 条；超限需等次日或订阅）"


class SendKeyError(ValueError):
    """SendKey 形态无法识别。"""


def mask_key(key: str) -> str:
    """日志里只露出前缀与长度，避免把凭据写进日志/工件。"""
    if not key:
        return "(空)"
    return f"{key[:3]}***(len={len(key)})"


def endpoint_for(key: str) -> str:
    """按 SendKey 前缀返回接口地址；无法识别时抛 SendKeyError。"""
    key = (key or "").strip()
    if key.startswith("sctp"):
        matched = re.match(r"^sctp(\d+)t", key)
        if not matched:
            raise SendKeyError(
                "Server酱³ 的 SendKey 形如 sctp123tXXXX，无法解析出 uid，请到 sc3.ft07.com 重新复制")
        return f"https://{matched.group(1)}.push.ft07.com/send/{key}.send"
    if key.startswith("SCT"):
        return f"https://sctapi.ftqq.com/{key}.send"
    raise SendKeyError(
        "SendKey 应以 SCT（Server酱Turbo）或 sctp（Server酱³）开头；"
        "旧版 SCKEY（sc.ftqq.com）接口已停止服务，请换用新 SendKey")


def normalize_title(title: str) -> str:
    """title 不能含换行，统一压成单行；为空时给个兜底标题。"""
    text = " ".join(str(title or "").split())
    return text or "定时任务通知"


def normalize_body(content: str) -> str:
    """正文按 Server酱³ 的要求补成「每行之间空一行」，Turbo 下同样正常分段。"""
    text = "\n".join(line.rstrip() for line in str(content or "").splitlines()).strip()
    text = text.replace("\n", "\n\n")
    return re.sub(r"\n{3,}", "\n\n", text)


class NotificationManager:
    """Server酱 推送管理器。"""

    def __init__(self) -> None:
        self.sendkey, self.source = self._resolve_key()

    def _resolve_key(self) -> Tuple[str, str]:
        for env_name in ("SERVERCHAN_SENDKEY", "SERVERCHAN_SCKEY"):
            value = os.environ.get(env_name, "").strip()
            if value:
                return value, f"环境变量 {env_name}"
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return "", "未配置"
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("读取 %s 失败: %s", CONFIG_PATH, exc)
            return "", "配置文件读取失败"
        server = data.get("server") if isinstance(data, dict) else None
        if not isinstance(server, dict):
            return "", "配置里没有 server 节点"
        key = str(server.get("sendkey") or server.get("sckey") or "").strip()
        return (key, str(CONFIG_PATH)) if key else ("", "未配置")

    def is_enabled(self) -> bool:
        return bool(self.sendkey)

    def describe(self) -> str:
        """给日志用的一句话状态（不含 key 本身）。"""
        if not self.sendkey:
            return f"Server酱未配置（来源：{self.source}）"
        kind = "Server酱³" if self.sendkey.startswith("sctp") else "Server酱Turbo"
        return f"{kind} 已配置 {mask_key(self.sendkey)}（来源：{self.source}）"

    def send(self, title: str, content: str, timeout: int = 10) -> bool:
        """发送一条消息。返回是否**真的**被服务端接受（code == 0）。"""
        if not self.sendkey:
            logger.info("未配置 Server酱 SendKey，跳过推送")
            return False

        # 测试 / 演练开关：完全不发外部请求
        if os.environ.get("NOTIFICATION_DISABLED"):
            logger.info("已设置 NOTIFICATION_DISABLED，跳过推送")
            return False

        try:
            url = endpoint_for(self.sendkey)
        except SendKeyError as exc:
            logger.error("SendKey 不可用: %s（%s）", exc, mask_key(self.sendkey))
            return False

        payload = {"title": normalize_title(title), "desp": normalize_body(content)}
        try:
            response = requests.post(url, data=payload, timeout=timeout)
        except requests.RequestException as exc:
            logger.error("推送请求失败（网络）: %s", exc)
            return False

        # 429 = IP 维度的 24 小时调用总量超限，与今日条数是两回事
        if response.status_code == 429:
            logger.error("推送被限流（HTTP 429）：该 IP 24 小时内调用次数超限，需等待恢复")
            return False

        try:
            body = response.json()
        except ValueError:
            logger.error("推送返回非 JSON（HTTP %s）: %s", response.status_code, response.text[:200])
            return False

        code = body.get("code")
        if response.status_code == 200 and code == 0:
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            pushid = data.get("pushid") or "-"
            logger.info("✅ 推送已被服务端接受（pushid=%s）", pushid)
            return True

        message = body.get("message") or body.get("msg") or response.text[:200]
        extra = QUOTA_HINT if any(word in str(message) for word in ("额度", "限制", "频率", "超限")) else ""
        logger.error("推送失败 code=%s: %s%s", code, message, extra)
        return False


def build_manager() -> NotificationManager:
    return NotificationManager()


notification_manager = NotificationManager()


def send_notification(title: str, content: str, timeout: int = 10) -> bool:
    """便捷函数：发送一条 Server酱 通知，返回是否成功。

    注意：调用方必须处理返回值。之前的实现无论成败都返回「已发送」，
    导致日志与实际送达情况不一致。
    """
    return notification_manager.send(title, content, timeout=timeout)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    manager = NotificationManager()
    print(manager.describe())
    if not manager.is_enabled():
        raise SystemExit("未配置 SendKey：设置 SERVERCHAN_SENDKEY 或写入 config/notification.json")
    ok = manager.send("推送自检", "如果你在微信里看到这条，说明通道是通的。")
    raise SystemExit(0 if ok else 1)
