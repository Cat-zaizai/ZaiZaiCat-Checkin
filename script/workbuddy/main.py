#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new Env('WorkBuddy签到');
cron: 30 8 * * *
"""

"""
WorkBuddy(CodeBuddy)自动签到脚本

该脚本用于自动执行WorkBuddy的每日签到任务，包括：
- 读取账号配置信息
- 查询今日签到状态
- 执行签到操作
- 令牌过期时自动刷新并回写配置
- 推送执行结果

Author: Assistant
Date: 2026-08-03
"""

import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# 获取项目根目录
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import WorkBuddyAPI
from notification import send_notification, NotificationSound

# 启动随机延迟上限（秒）：在窗口内随机错开请求，避免与他人撞车；设为 0 关闭
JITTER_MAX_SECONDS = int(os.environ.get('WORKBUDDY_JITTER_MAX', '600'))


class WorkBuddyTasks:
    """WorkBuddy签到任务自动化执行类"""

    def __init__(self, config_path: str = None):
        """
        初始化任务执行器

        Args:
            config_path (str): 配置文件的完整路径，如果为None则使用项目根目录下的config/token.json
        """
        if config_path is None:
            self.config_path = project_root / "config" / "token.json"
        else:
            self.config_path = Path(config_path)

        self.accounts: List[Dict[str, Any]] = []
        self.logger = self._setup_logger()
        self._init_accounts()
        self.account_results: List[Dict[str, Any]] = []

    def _setup_logger(self) -> logging.Logger:
        """
        设置日志记录器

        Returns:
            logging.Logger: 配置好的日志记录器
        """
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)

        if not logger.handlers:
            logger.addHandler(console_handler)

        return logger

    def _init_accounts(self):
        """从配置文件中读取账号信息"""
        if not self.config_path.exists():
            self.logger.error(f"配置文件不存在: {self.config_path}")
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                # 从统一配置文件的 workbuddy 节点读取
                workbuddy_config = config_data.get('workbuddy', {})
                self.accounts = workbuddy_config.get('accounts', [])

            if not self.accounts:
                self.logger.warning("配置文件中没有找到 workbuddy 账号信息")
            else:
                self.logger.info(f"成功加载 {len(self.accounts)} 个账号配置")

        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件JSON解析失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"读取配置文件失败: {e}")
            raise

    def _save_refreshed_token(self, account_index: int, api: WorkBuddyAPI):
        """
        令牌刷新后回写配置文件，避免下次执行仍使用过期令牌

        Args:
            account_index (int): 账号在配置数组中的下标
            api (WorkBuddyAPI): 持有最新令牌的API实例
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            accounts = config_data.get('workbuddy', {}).get('accounts', [])
            if account_index >= len(accounts):
                self.logger.warning("⚠️ 账号下标越界，跳过令牌回写")
                return

            accounts[account_index]['access_token'] = api.access_token
            if api.refresh_token:
                accounts[account_index]['refresh_token'] = api.refresh_token
            if api.domain:
                accounts[account_index]['domain'] = api.domain

            # 原子写入：先写临时文件再替换，避免进程中断导致配置文件截断损坏
            tmp_path = self.config_path.with_suffix('.json.tmp')
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.config_path)

            self.logger.info("💾 新令牌已写回配置文件")
        except Exception as e:
            self.logger.warning(f"⚠️ 回写令牌失败: {e}")

    def process_account(self, account_index: int, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个账号的签到任务

        Args:
            account_index (int): 账号在配置数组中的下标
            account_info (Dict[str, Any]): 账号信息字典

        Returns:
            Dict[str, Any]: 处理结果
        """
        account_name = account_info.get('account_name') or account_info.get('email') or '未命名账号'
        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"开始处理账号: {account_name}")
        self.logger.info(f"{'=' * 60}")

        result = {
            'account_name': account_name,
            'success': False,
            'message': '',
            'already_checked': False,
            'credit': None,
            'streak_days': None,
            'status_info': {}
        }

        try:
            access_token = account_info.get('access_token')
            if not access_token:
                error_msg = "账号配置中缺少 access_token"
                self.logger.error(f"❌ {account_name}: {error_msg}")
                result['message'] = error_msg
                return result

            api = WorkBuddyAPI(
                access_token=access_token,
                refresh_token=account_info.get('refresh_token'),
                uid=account_info.get('uid'),
                enterprise_id=account_info.get('enterprise_id'),
                domain=account_info.get('domain'),
                user_agent=account_info.get('user_agent'),
            )

            # 查询签到状态
            self.logger.info(f"{account_name} - 查询签到状态")
            status = api.get_checkin_status()

            if not status['success']:
                error_msg = status.get('error', '查询签到状态失败')
                if status.get('error_type') == 'token_expired':
                    result['message'] = f'{error_msg}，请重新导入账号'
                    self.logger.error(f"❌ {account_name} {result['message']}")
                else:
                    result['message'] = error_msg
                    self.logger.error(f"❌ {account_name} {error_msg}")
                return result

            result['status_info'] = status
            self.logger.info(
                f"📊 连签天数: {status.get('streak_days', 0)} 天 | "
                f"每日积分: {status.get('daily_credit', 0)}"
            )

            # 活动未开启
            if not status.get('active', True):
                result['success'] = True
                result['message'] = '签到活动未开启或不适用'
                self.logger.info(f"ℹ️ {account_name} 签到活动未开启")
                return result

            # 今日已签到
            if status.get('today_checked_in'):
                result['success'] = True
                result['already_checked'] = True
                result['message'] = '今日已签到'
                result['credit'] = status.get('today_credit')
                result['streak_days'] = status.get('streak_days')
                self.logger.info(f"✅ {account_name} 今日已签到")
                return result

            # 执行签到
            self.logger.info(f"{account_name} - 执行签到")
            checkin = api.daily_checkin()

            if checkin['success']:
                result['success'] = True
                result['message'] = checkin.get('message') or '签到成功'
                result['credit'] = checkin.get('credit')
                result['streak_days'] = checkin.get('streak_days')

                self.logger.info(f"✅ {account_name} 签到成功")
                if checkin.get('credit') is not None:
                    self.logger.info(f"🎁 获得积分: {checkin['credit']}")
                if checkin.get('streak_days') is not None:
                    self.logger.info(f"🔥 连签天数: {checkin['streak_days']} 天")
                if checkin.get('is_streak_day'):
                    self.logger.info("🎉 触发连签奖励")
            else:
                # 签到失败后复查状态，可能是并发导致的"已签到"
                latest = api.get_checkin_status()
                if latest['success'] and latest.get('today_checked_in'):
                    result['success'] = True
                    result['already_checked'] = True
                    result['message'] = '今日已签到'
                    result['streak_days'] = latest.get('streak_days')
                    self.logger.info(f"✅ {account_name} 今日已签到")
                else:
                    result['message'] = checkin.get('error', '签到失败')
                    self.logger.error(f"❌ {account_name} 签到失败: {result['message']}")

            # 令牌被刷新过则回写配置
            if api.token_refreshed:
                self._save_refreshed_token(account_index, api)

        except Exception as e:
            error_msg = f"处理账号时发生异常: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            result['message'] = error_msg
            import traceback
            traceback.print_exc()

        return result

    def run(self):
        """执行所有账号的签到任务"""
        # 启动随机抖动，错开请求高峰
        if JITTER_MAX_SECONDS > 0:
            delay = random.uniform(0, JITTER_MAX_SECONDS)
            self.logger.info(f"⏱️  随机延迟 {delay:.0f} 秒后开始（可通过环境变量 WORKBUDDY_JITTER_MAX 调整）")
            time.sleep(delay)

        self.logger.info("=" * 60)
        self.logger.info("WorkBuddy自动签到任务开始")
        self.logger.info("=" * 60)

        if not self.accounts:
            self.logger.warning("没有需要处理的账号")
            return

        for idx, account_info in enumerate(self.accounts):
            result = self.process_account(idx, account_info)
            self.account_results.append(result)

            # 处理完一个账号后，如果还有下一个账号，则等待5-10秒
            if idx < len(self.accounts) - 1:
                delay = random.uniform(5, 10)
                self.logger.info(f"\n⏱️  等待 {delay:.1f} 秒后处理下一个账号...")
                time.sleep(delay)

        self._print_summary()
        self._send_notification()

    def _print_summary(self):
        """打印执行结果统计"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("执行结果统计")
        self.logger.info("=" * 60)

        total = len(self.account_results)
        success = sum(1 for r in self.account_results if r['success'])
        already = sum(1 for r in self.account_results if r.get('already_checked'))
        failed = total - success

        self.logger.info(f"总账号数: {total}")
        self.logger.info(f"签到成功: {success - already}")
        self.logger.info(f"今日已签: {already}")
        self.logger.info(f"签到失败: {failed}")

        self.logger.info("\n详细结果:")
        for result in self.account_results:
            status = "✅ 成功" if result['success'] else "❌ 失败"
            self.logger.info(f"  {result['account_name']}: {status} - {result['message']}")

        self.logger.info("=" * 60)

    def _send_notification(self):
        """发送推送通知"""
        if not self.account_results:
            return

        total = len(self.account_results)
        success = sum(1 for r in self.account_results if r['success'])
        already = sum(1 for r in self.account_results if r.get('already_checked'))
        failed = total - success

        title = "WorkBuddy签到结果通知"

        content_lines = [
            f"📊 总账号数: {total}",
            f"✅ 签到成功: {success - already}",
            f"📅 今日已签: {already}",
            f"❌ 签到失败: {failed}",
            "",
            "📋 详细结果:"
        ]

        for result in self.account_results:
            status = "✅" if result['success'] else "❌"
            content_lines.append(f"{status} {result['account_name']}: {result['message']}")

            detail_parts = []
            if result.get('credit') is not None:
                detail_parts.append(f"积分 +{result['credit']}")
            if result.get('streak_days') is not None:
                detail_parts.append(f"连签 {result['streak_days']} 天")
            if detail_parts:
                content_lines.append(f"    🎁 {' | '.join(detail_parts)}")

        content = "\n".join(content_lines)

        try:
            send_notification(
                title=title,
                content=content,
                sound=NotificationSound.BIRDSONG
            )
            self.logger.info("✅ 推送通知已发送")
        except Exception as e:
            self.logger.warning(f"⚠️ 发送推送通知失败: {str(e)}")


def main():
    """主函数"""
    try:
        tasks = WorkBuddyTasks()
        tasks.run()

    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        print("请确保配置文件存在并包含 workbuddy 账号信息")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
