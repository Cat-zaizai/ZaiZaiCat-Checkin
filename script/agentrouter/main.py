#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new Env('AgentRouter签到');
cron: 20 9 * * *
"""

"""
Agent Router（ps.air-outer.com）每日签到脚本

签到原理：该站点没有独立签到入口，额度在**登录时**发放（官方 FAQ：「签到领 $25 额度」
需要退出后重新登录才会到账）。脚本因此每天完整重走一次 GitHub OAuth 登录：

    站点 /api/oauth/state -> GitHub 授权换 code -> 站点 /api/oauth/github 登录 -> 额度到账

GitHub 登录态由配置提供（github_cookies 或 github_session），不读取任何浏览器数据。
GitHub 回调域名为 agentrouter.org（境内不通），脚本只从其跳转地址中提取 code，
随后统一用配置中的 base_url（默认 https://ps.air-outer.com）完成登录。

配置示例（config/token.json 的 agentrouter 节点）：
{
  "agentrouter": {
    "accounts": [
      {
        "account_name": "erma0",
        "github_cookies": "user_session=xxx; __Host-user_session_same_site=xxx; logged_in=yes",
        "base_url": "https://ps.air-outer.com"
      }
    ]
  }
}

Author: Assistant
Date: 2026-09-10
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import DEFAULT_BASE_URL, AgentRouterAPI
from notification import NotificationSound, send_notification

# 多账号之间的间隔（秒），避免短时间内连续请求
ACCOUNT_INTERVAL_SECONDS = 5


class AgentRouterTasks:
    """Agent Router 签到任务执行类"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            self.config_path = project_root / 'config' / 'token.json'
        else:
            self.config_path = Path(config_path)

        self.accounts: List[Dict[str, Any]] = []
        self.account_results: List[Dict[str, Any]] = []
        self.logger = self._setup_logger()
        self._init_accounts()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            logger.addHandler(console_handler)

        return logger

    def _init_accounts(self):
        """从配置文件的 agentrouter 节点读取账号信息"""
        if not self.config_path.exists():
            raise FileNotFoundError(f'配置文件不存在: {self.config_path}')

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f'配置文件 JSON 解析失败: {exc}')

        self.accounts = (config_data.get('agentrouter') or {}).get('accounts', [])
        if not self.accounts:
            self.logger.warning('配置文件中没有找到 agentrouter 账号信息')
        else:
            self.logger.info(f'成功加载 {len(self.accounts)} 个账号配置')

    def _build_api(self, account_info: Dict[str, Any]) -> AgentRouterAPI:
        return AgentRouterAPI(
            base_url=account_info.get('base_url') or DEFAULT_BASE_URL,
            github_cookies=account_info.get('github_cookies'),
            github_session=account_info.get('github_session') or '',
            user_id=account_info.get('user_id') or '',
            proxy=account_info.get('proxy') or '',
            verify=account_info.get('verify'),
        )

    def _describe_user(self, api: AgentRouterAPI, session) -> Dict[str, Any]:
        """查询登录后的账号信息，返回额度摘要"""
        info = api.get_user_self(session)
        if not info.get('success'):
            return {'success': False, 'error': info.get('error')}

        user = info.get('user') or {}
        quota = user.get('quota')
        summary = {
            'success': True,
            'display_name': user.get('display_name') or user.get('username') or '',
            'quota': quota,
            'used_quota': user.get('used_quota'),
            'quota_usd': api.quota_to_usd(quota),
        }
        return summary

    def process_account(self, account_index: int, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个账号的签到（即重新登录）

        Args:
            account_index (int): 账号下标
            account_info (Dict[str, Any]): 账号配置

        Returns:
            Dict[str, Any]: 处理结果
        """
        account_name = account_info.get('account_name') or f'账号{account_index + 1}'
        self.logger.info(f"\n{'=' * 60}\n开始处理账号: {account_name}\n{'=' * 60}")

        result: Dict[str, Any] = {
            'account_name': account_name,
            'success': False,
            'message': '',
            'token_error': False,
            'quota_usd': None,
            'checked_in': None,
        }

        api = self._build_api(account_info)
        self.logger.info(f'{account_name} - 站点: {api.base_url}')

        # 登录即签到：重走一次 GitHub OAuth 登录，服务端在登录流程中发放额度
        self.logger.info(f'{account_name} - 通过 GitHub OAuth 重新登录以触发签到')
        login = api.login_by_github()

        if not login.get('success'):
            result['message'] = login.get('error', '登录失败')
            result['token_error'] = login.get('error_type') in ('missing_credential', 'auth_failed')
            self.logger.error(f"❌ {account_name}: {result['message']}")
            return result

        summary = self._describe_user(api, login['session'])
        result['success'] = True
        result['mode'] = login.get('mode', '')
        result['checked_in'] = login.get('checked_in')
        result['message'] = ('签到成功，新增额度已到账' if login.get('checked_in')
                             else '登录成功（今日签到状态：未标记到账）')
        if summary.get('success'):
            result['quota_usd'] = summary.get('quota_usd')
            result['display_name'] = summary.get('display_name')
            result['message'] += f"（当前余额 ${summary.get('quota_usd')}）"
        else:
            self.logger.warning(f"⚠️ {account_name}: 签到已完成，但查询余额失败"
                                f"（{summary.get('error')}）")
        self.logger.info(f"✅ {account_name}: {result['message']}")
        return result

    def run(self, dry_run: bool = False):
        """执行所有账号的签到"""
        if not self.accounts:
            self.logger.error('没有可处理的账号，请检查配置')
            return

        if dry_run:
            self.logger.info('[dry-run] 仅校验配置，不执行登录')
            for index, account in enumerate(self.accounts):
                name = account.get('account_name') or f'账号{index + 1}'
                has_github = bool(account.get('github_cookies') or account.get('github_session'))
                self.logger.info(f'{name}: GitHub登录态={has_github}')
            return

        for index, account in enumerate(self.accounts):
            self.account_results.append(self.process_account(index, account))
            if index < len(self.accounts) - 1:
                time.sleep(ACCOUNT_INTERVAL_SECONDS)

        self._send_notification()

    def _send_notification(self):
        """汇总并发送推送通知"""
        if not self.account_results:
            return

        total = len(self.account_results)
        success = sum(1 for r in self.account_results if r['success'])
        failed = total - success

        lines = [
            f'📊 总账号数: {total}',
            f'✅ 签到成功: {success}',
            f'❌ 签到失败: {failed}',
            '',
            '📋 详细结果:',
        ]
        for result in self.account_results:
            status = '✅' if result['success'] else '❌'
            lines.append(f"{status} {result['account_name']}: {result['message']}")
            if result.get('display_name'):
                lines.append(f"    👤 账号: {result['display_name']}")
            if result.get('quota_usd') is not None:
                lines.append(f"    💰 当前余额: ${result['quota_usd']}")

        try:
            send_notification(
                title='AgentRouter签到结果通知',
                content='\n'.join(lines),
                sound=NotificationSound.BIRDSONG,
            )
            self.logger.info('✅ 推送通知已发送')
        except Exception as exc:
            self.logger.warning(f'⚠️ 发送推送通知失败: {exc}')


def main():
    dry_run = '--dry-run' in sys.argv
    try:
        AgentRouterTasks().run(dry_run=dry_run)
    except (FileNotFoundError, ValueError) as exc:
        print(f'❌ 错误: {exc}')
        sys.exit(1)
    except Exception as exc:
        print(f'❌ 发生未知错误: {exc}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
