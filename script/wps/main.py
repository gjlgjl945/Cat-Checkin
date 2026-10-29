#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new Env('WPS签到抽奖');
cron: 1 1 1 1 1
"""

"""
WPS 多页面任务入口脚本

当前统一执行以下活动页面：
- 任务中心
- 天天领福利

Author: Assistant
Date: 2026-03-11
"""

import argparse
import logging
import random
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type

# 获取项目根目录
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from daily_benefits import DailyBenefitsTasks
from logging_utils import (
    bind_logger,
    configure_logging,
    get_logger,
    log_account_end,
    log_account_start,
    log_banner,
    log_startup,
)
from notification import send_notification, NotificationSound
from platform_config import SOURCE_LEGACY, normalize_node, resolve_path
from task_center import WPSTaskCenterPage


class WPSMultiPageRunner:
    """WPS 多页面任务统一入口"""

    def __init__(self, config_path: str = None):
        # 每个平台只读自己那份配置：默认 config/token.wps.json，
        # 旧 config/token.json 存在时会回退读取并提示迁移
        self.config_path, self.config_source = resolve_path("wps", config_path, project_root)
        self.logger = self._setup_logger()
        self.accounts: List[Dict[str, Any]] = self._load_accounts()
        self.account_results: List[Dict[str, Any]] = []
        self.page_tasks: List[Tuple[str, Type]] = [
            ("任务中心", WPSTaskCenterPage),
            ("天天领福利", DailyBenefitsTasks),
        ]

    def _setup_logger(self) -> logging.Logger:
        configure_logging()
        return bind_logger(get_logger("main"), page="主入口")

    def _load_accounts(self) -> List[Dict[str, Any]]:
        """读取本平台自己的配置文件。"""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {self.config_path}（本平台应使用 config/token.wps.json）")

        with open(self.config_path, "r", encoding="utf-8") as file:
            config_data = json.load(file)

        if self.config_source == SOURCE_LEGACY:
            self.logger.warning(
                "当前读取的是旧 config/token.json，建议拆分后删除；"
                "执行 python ci/migrate_config.py --apply 自动拆分")

        # 取出属于 WPS 的那一个节点（兼容 {"wps":{...}} 与 {"accounts":[...]} 两种写法）
        wps_config = normalize_node(config_data, "wps")
        raw_accounts = wps_config.get("accounts", [])
        # 丢弃非对象条目，避免一条写错的配置让整轮任务崩在 .get() 上
        skipped = sum(1 for item in raw_accounts if not isinstance(item, dict))
        accounts = [item for item in raw_accounts if isinstance(item, dict)]
        if skipped:
            self.logger.warning("忽略 %s 条非对象格式的账号配置", skipped)
        if accounts:
            self.logger.info("成功加载 %s 个 WPS 账号", len(accounts))
        else:
            self.logger.warning("配置文件中没有找到 WPS 账号信息")
        return accounts

    @staticmethod
    def _is_auth_expired_result(page_result: Dict[str, Any]) -> bool:
        """判断页面结果是否为登录态失效。"""
        if page_result.get("auth_expired"):
            return True

        message = str(page_result.get("message", ""))
        keywords = ("Token已过期", "ErrNotLogin", "userNotLogin", "未登录", "请重新登录")
        return any(keyword in message for keyword in keywords)

    def run(self) -> Dict[str, int]:
        """按账号顺序执行所有页面任务，返回汇总计数供调用方决定退出码。"""
        log_startup(self.logger, len(self.accounts))
        self.logger.info("")

        if not self.accounts:
            self.logger.warning("没有需要处理的账号")
            return self.stats()

        page_runners = [
            (
                page_name,
                task_class(config_path=str(self.config_path), enable_notification=False, load_accounts=False)
            )
            for page_name, task_class in self.page_tasks
        ]

        for account_index, account_info in enumerate(self.accounts):
            account_name = account_info.get("account_name", "未命名账号")
            account_result = {
                "account_name": account_name,
                "success": True,
                "pages": []
            }

            log_account_start(self.logger, account_name)

            for page_index, (page_name, page_runner) in enumerate(page_runners):
                try:
                    page_result = page_runner.process_account(account_info)
                except Exception as exc:
                    page_result = {
                        "account_name": account_name,
                        "success": False,
                        "message": f"{page_name}执行异常: {exc}"
                    }
                    self.logger.error("%s 页面执行失败: %s", page_name, exc)
                    import traceback
                    traceback.print_exc()

                account_result["pages"].append({
                    "page_name": page_name,
                    "result": page_result
                })

                if not page_result.get("success", False):
                    account_result["success"] = False

                if self._is_auth_expired_result(page_result):
                    self.logger.warning("[%s] 登录态已失效，停止执行该账号后续页面任务", account_name)
                    break

                if page_index < len(page_runners) - 1:
                    delay = random.uniform(1, 2)
                    self.logger.info("")
                    time.sleep(delay)

            self.account_results.append(account_result)
            if account_index < len(self.accounts) - 1:
                delay = random.uniform(3, 6)
                log_account_end(self.logger, account_name, account_result["success"], delay)
                self.logger.info("")
                time.sleep(delay)
            else:
                log_account_end(self.logger, account_name, account_result["success"])

        self._print_summary()
        self._send_notification()
        return self.stats()

    def stats(self) -> Dict[str, int]:
        """汇总账号级结果；failed 为「至少一个页面失败」的账号数。"""
        total = len(self.account_results)
        success = sum(1 for item in self.account_results if item["success"])
        return {"total": total, "success": success, "failed": total - success}

    def _print_summary(self) -> None:
        """打印账号级页面汇总结果。"""
        self.logger.info("")
        log_banner(self.logger, "多页面任务执行结果统计")

        total = len(self.account_results)
        success = sum(1 for item in self.account_results if item["success"])
        failed = total - success

        self.logger.info("总账号数: %s", total)
        self.logger.info("执行成功: %s", success)
        self.logger.info("执行失败: %s", failed)

        for item in self.account_results:
            status = "✅ 成功" if item["success"] else "❌ 失败"
            self.logger.info("%s: %s", item["account_name"], status)
            for page_item in item["pages"]:
                page_result = page_item["result"]
                self.logger.info(
                    "  - %s: %s",
                    page_item["page_name"],
                    page_result.get("message", "")
                )

        self.logger.info("%s", "=" * 60)

    def _send_notification(self) -> None:
        """统一发送所有页面的汇总通知。"""
        if not self.account_results:
            return

        total = len(self.account_results)
        success = sum(1 for item in self.account_results if item["success"])
        failed = total - success

        content_lines = [
            f"📊 总账号数: {total}",
            f"✅ 执行成功: {success}",
            f"❌ 执行失败: {failed}",
            "",
            "📋 详细结果:"
        ]

        page_line_builders = {
            WPSTaskCenterPage.page_name: WPSTaskCenterPage.build_notification_lines,
            DailyBenefitsTasks.page_name: DailyBenefitsTasks.build_notification_lines,
        }

        for account_result in self.account_results:
            status = "✅" if account_result["success"] else "❌"
            content_lines.append(f"{status} {account_result['account_name']}")

            for page_item in account_result["pages"]:
                page_name = page_item["page_name"]
                page_result = page_item["result"]
                line_builder = page_line_builders.get(page_name)
                if line_builder is None:
                    content_lines.append(f"    [{page_name}] {page_result.get('message', '')}")
                    continue
                content_lines.extend(line_builder(page_result))

            if account_result != self.account_results[-1]:
                content_lines.append("")

        try:
            delivered = send_notification(
                title="WPS多页面任务结果通知",
                content="\n".join(content_lines),
                sound=NotificationSound.BIRDSONG
            )
            if delivered:
                self.logger.info("统一推送通知已发送: %s", ", ".join(delivered))
            else:
                self.logger.info("未配置可用的推送通道，跳过通知")
        except Exception as exc:
            self.logger.warning("发送统一推送通知失败: %s", exc)


def main() -> int:
    """主函数。退出码：0 全部成功，1 存在失败账号或运行异常。"""
    parser = argparse.ArgumentParser(description="WPS 多页面任务")
    parser.add_argument("--config", default=None, help="配置文件路径，默认 config/token.json")
    parser.add_argument("--allow-failures", action="store_true",
                        help="存在失败账号时仍返回 0（默认返回 1，便于 CI 报红）")
    args = parser.parse_args()

    try:
        stats = WPSMultiPageRunner(config_path=args.config).run()
    except FileNotFoundError as exc:
        print(f"❌ 错误: {exc}")
        print("请确保配置文件存在并包含 WPS 账号信息")
        return 1
    except ValueError as exc:
        # 配置结构错误（JSON 非法、accounts 不是数组）属于用户输入问题，不打印调用栈
        print(f"❌ 配置错误: {exc}")
        return 1
    except Exception as exc:
        print(f"❌ 发生未知错误: {exc}")
        import traceback
        traceback.print_exc()
        return 1

    failed = stats.get("failed", 0)
    if failed and not args.allow_failures:
        print(f"❌ {failed} 个账号执行失败，退出码 1（可用 --allow-failures 关闭该行为）")
        return 1
    if stats.get("total", 0) == 0:
        print("❌ 没有可执行的 WPS 账号")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
