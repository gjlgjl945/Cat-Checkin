#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new Env('看雪论坛签到');
cron: 1 1 1 1 1
"""
"""
看雪论坛自动签到脚本

功能：
1. 从token.json配置文件读取账号信息
2. 支持多账号管理
3. 自动执行签到并推送通知

Author: ZaiZaiCat
Date: 2025-01-20
"""

import argparse
import json
import logging
import sys
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from checkin_result import defer_notification, write_result
from notification import send_notification
from platform_config import SOURCE_LEGACY, normalize_node, resolve_path
from api import KanxueAPI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KanxueSignInManager:
    """看雪论坛签到管理器"""

    def __init__(self, config_path: str = None):
        """
        初始化签到管理器

        Args:
            config_path: 配置文件路径；默认读本平台自己的 config/token.kanxue.json
        """
        # 每个平台只读自己那份配置：默认 config/token.kanxue.json，
        # 旧 config/token.json 存在时会回退读取并提示迁移
        self.config_path, self.config_source = resolve_path("kanxue", config_path, project_root)
        self.site_name = "看雪论坛"
        self.accounts = []
        self.load_config()

    def load_config(self) -> None:
        """加载配置文件"""
        try:
            logger.info(f"正在读取配置文件: {self.config_path}")
            if not self.config_path.exists():
                raise FileNotFoundError(
                    f"配置文件不存在: {self.config_path}（本平台应使用 config/token.kanxue.json）")

            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if self.config_source == SOURCE_LEGACY:
                logger.warning(
                    "当前读取的是旧 config/token.json，建议拆分后删除；"
                    "执行 python ci/migrate_config.py --apply 自动拆分")

            # 取出属于看雪的那一个节点（兼容 {"kanxue":{...}} 与 {"accounts":[...]} 两种写法）
            kanxue_config = normalize_node(config, "kanxue")
            raw_accounts = kanxue_config.get('accounts', [])
            # 丢弃非对象条目：一条格式写错的配置不应让整轮任务在 .get() 上崩掉
            skipped = sum(1 for item in raw_accounts if not isinstance(item, dict))
            self.accounts = [item for item in raw_accounts if isinstance(item, dict)]
            if skipped:
                logger.warning(f"忽略 {skipped} 条非对象格式的账号配置")

            if not self.accounts:
                logger.warning("配置文件中没有找到看雪论坛账号信息")
            else:
                logger.info(f"成功加载 {len(self.accounts)} 个账号配置")

        except FileNotFoundError:
            logger.error(f"配置文件不存在: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON格式错误: {e}")
            raise
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise

    def sign_in_single_account(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """
        单个账号签到

        Args:
            account: 账号配置信息

        Returns:
            Dict: 签到结果
        """
        account_name = account.get('account_name', '未命名账号')
        cookie = account.get('cookie', '')
        csrf_token = account.get('csrf_token', '')
        user_agent = account.get('user_agent')

        logger.info(f"开始执行账号 [{account_name}] 的签到...")

        if not cookie or not csrf_token:
            error_msg = "cookie或csrf_token为空"
            logger.error(f"账号 [{account_name}] {error_msg}")
            return {
                'account_name': account_name,
                'success': False,
                'error': error_msg
            }

        try:
            # 创建API实例并执行签到
            api = KanxueAPI(cookie, csrf_token, user_agent)
            result = api.sign_in()

            # 添加账号名称到结果中
            result['account_name'] = account_name

            if result.get('success'):
                logger.info(f"账号 [{account_name}] 签到成功")
            else:
                logger.error(f"账号 [{account_name}] 签到失败: {result.get('error', '未知错误')}")

            return result

        except Exception as e:
            error_msg = f"签到异常: {str(e)}"
            logger.error(f"账号 [{account_name}] {error_msg}", exc_info=True)
            return {
                'account_name': account_name,
                'success': False,
                'error': error_msg
            }

    def sign_in_all_accounts(self) -> List[Dict[str, Any]]:
        """
        所有账号签到

        Returns:
            List[Dict]: 所有账号的签到结果列表
        """
        if not self.accounts:
            logger.warning("没有可签到的账号")
            return []

        results = []
        for i, account in enumerate(self.accounts, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"正在处理第 {i}/{len(self.accounts)} 个账号")
            logger.info(f"{'='*60}")

            result = self.sign_in_single_account(account)
            results.append(result)

        return results

    def send_notification(self, results: List[Dict[str, Any]], start_time: datetime, end_time: datetime) -> None:
        """
        发送签到结果通知

        Args:
            results: 签到结果列表
            start_time: 任务开始时间
            end_time: 任务结束时间
        """
        try:
            duration = (end_time - start_time).total_seconds()

            # 统计结果
            total_count = len(results)
            success_count = sum(1 for r in results if r.get('success'))
            failed_count = total_count - success_count

            # 构建通知标题
            if failed_count == 0:
                title = f"{self.site_name}签到成功 ✅"
            elif success_count == 0:
                title = f"{self.site_name}签到失败 ❌"
            else:
                title = f"{self.site_name}签到部分成功 ⚠️"

            # 构建通知内容
            content_parts = [f"📊 执行统计:"]

            if success_count > 0:
                content_parts.append(f"✅ 成功: {success_count} 个账号")
            if failed_count > 0:
                content_parts.append(f"❌ 失败: {failed_count} 个账号")

            content_parts.append(f"📈 总计: {total_count} 个账号")
            content_parts.append("")

            # 添加详细信息
            content_parts.append("📝 详情:")
            for result in results:
                account_name = result.get('account_name', '未知账号')
                if result.get('success'):
                    api_result = result.get('result', {})

                    # 处理看雪论坛的返回格式
                    if 'code' in api_result:
                        if api_result.get('code') == '0':
                            message = api_result.get('message', '')
                            content_parts.append(f"  ✅ [{account_name}] 获得积分: {message}")
                        else:
                            message = api_result.get('message', '签到完成')
                            if len(message) > 50:
                                message = message[:50] + "..."
                            content_parts.append(f"  ✅ [{account_name}] {message}")
                    elif 'message' in api_result:
                        message = api_result.get('message', '签到成功')
                        if len(message) > 50:
                            message = message[:50] + "..."
                        content_parts.append(f"  ✅ [{account_name}] {message}")
                    else:
                        content_parts.append(f"  ✅ [{account_name}] 签到成功")
                else:
                    error = result.get('error', '未知错误')
                    if len(error) > 50:
                        error = error[:50] + "..."
                    content_parts.append(f"  ❌ [{account_name}] {error}")

            # 添加执行信息
            content_parts.append("")
            content_parts.append(f"⏱️ 执行耗时: {int(duration)}秒")
            content_parts.append(f"🕐 完成时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

            content = "\n".join(content_parts)

            # CI 里不单独推送：交给汇总作业合并成一条，避免一天 8 条打爆免费额度
            if defer_notification():
                path = write_result("kanxue", self.site_name, total_count,
                                    success_count, failed_count, content_parts)
                logger.info(f"结果已写入 {path}，由汇总作业统一推送" if path else "结果落盘失败，不影响签到")
                return

            if send_notification(title=title, content=content):
                logger.info(f"✅ {self.site_name}签到推送已发送")
            else:
                logger.info("未发送推送（具体原因见上一行）")

        except Exception as e:
            logger.error(f"❌ {self.site_name}推送通知失败: {str(e)}", exc_info=True)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="看雪论坛每日签到")
    parser.add_argument("--config", default=None,
                        help="配置文件路径，默认 config/token.kanxue.json")
    parser.add_argument("--allow-failures", action="store_true",
                        help="存在失败账号时仍返回 0（默认返回 1，便于 CI 报红）")
    args = parser.parse_args()

    # 记录开始时间
    start_time = datetime.now()
    print(f"\n{'='*60}")
    print(f"## 看雪论坛签到任务开始")
    print(f"## 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    logger.info("="*60)
    logger.info(f"看雪论坛签到任务开始执行 - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)

    try:
        # 创建签到管理器
        manager = KanxueSignInManager(config_path=args.config)

        # 执行所有账号签到
        results = manager.sign_in_all_accounts()

        # 记录结束时间
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"\n{'='*60}")
        print(f"## 看雪论坛签到任务完成")
        print(f"## 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"## 执行耗时: {int(duration)} 秒")
        print(f"{'='*60}\n")

        logger.info("="*60)
        logger.info(f"看雪论坛签到任务执行完成 - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"执行耗时: {int(duration)} 秒")
        logger.info("="*60)

        # 发送推送通知
        if results:
            manager.send_notification(results, start_time, end_time)

        # 统计结果
        total_count = len(results)
        success_count = sum(1 for r in results if r.get('success'))
        failed_count = total_count - success_count

        # 打印总结
        print(f"📊 签到总结:")
        print(f"   ✅ 成功: {success_count} 个账号")
        print(f"   ❌ 失败: {failed_count} 个账号")
        print(f"   📈 总计: {total_count} 个账号\n")

        # 根据结果返回退出码：0 才代表「真的签到了」，其余一律非 0，
        # 避免「账号全失败但 job 显示绿色」这种与事实不符的结论。
        # 原实现部分失败返回 2，与包装脚本的「用法错误」语义冲突，此处统一为 1。
        if failed_count > 0:
            if not args.allow_failures:
                print(f"❌ {failed_count}/{total_count} 个账号签到失败，退出码 1"
                      f"（可用 --allow-failures 关闭该行为）")
                return 1
            return 0
        if total_count == 0:
            print("❌ 没有可执行的账号（配置中的账号均不可用）")
            return 1
        return 0

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error(f"签到任务执行异常: {str(e)}", exc_info=True)

        print(f"\n{'='*60}")
        print(f"## ❌ 签到任务执行异常")
        print(f"## 错误信息: {str(e)}")
        print(f"## 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"## 执行耗时: {int(duration)} 秒")
        print(f"{'='*60}\n")

        # 发送错误通知
        try:
            send_notification(
                title=f"看雪论坛签到任务异常 ❌",
                content=(
                    f"❌ 任务执行异常\n"
                    f"💬 错误信息: {str(e)}\n"
                    f"⏱️ 执行耗时: {int(duration)}秒\n"
                    f"🕐 完成时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            )
        except Exception:
            # 通知失败不影响退出码：真正的失败原因已经写进日志与返回值
            pass

        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
