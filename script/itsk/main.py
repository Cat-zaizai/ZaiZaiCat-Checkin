#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new Env('iTSK签到');
cron: 10 8 * * *
"""

"""
iTSK(IT天空 www.itsk.com)自动签到脚本

该脚本用于自动执行iTSK的每日签到任务，包括：
- 读取账号配置信息（config/token.json 的 itsk 节点）
- 查询签到面板状态（活动签到/普通签到双模式）
- 执行签到操作
- 令牌过期时用账密自动登录换新并回写配置
- 推送执行结果

Author: Assistant
Date: 2026-11-21
"""

import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# 获取项目根目录
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import ItsKAPI
from notification import send_notification, NotificationSound

# 启动随机延迟上限（秒）：在窗口内随机错开请求，避免与他人撞车；设为 0 关闭
JITTER_MAX_SECONDS = int(os.environ.get('ITSK_JITTER_MAX', '600'))

# 签到日界按北京时间计算
BEIJING_TZ = timezone(timedelta(hours=8))

# 活动签到日历 sign_status 语义
SIGN_STATUS_SIGNED = (1, 3)     # 1=已签(历史) 3=今日已签
SIGN_STATUS_MISSED = 2          # 错过，可补签（消耗钻石，不自动补）


def _today_str() -> str:
    """按北京时间返回今天日期，如 2026-11-21"""
    return datetime.now(BEIJING_TZ).strftime('%Y-%m-%d')


def _describe_rewards(entry: Optional[Dict[str, Any]], is_vip: Any) -> str:
    """
    从活动日历的当日条目提取奖励描述

    Args:
        entry (Optional[Dict[str, Any]]): 签到日历中今天的条目
        is_vip (Any): 签到响应中的 is_vip，真值时优先读 VIP 奖励列

    Returns:
        str: 形如 "活跃+80(VIP奖励)"，无数据返回空串
    """
    if not entry:
        return ''
    try:
        if is_vip and entry.get('vip'):
            items = entry['vip']
            suffix = '(VIP奖励)'
        else:
            items = entry.get('member') or entry.get('vip') or []
            suffix = ''
        desc = '、'.join(f"{p.get('prize_name', '')}+{p.get('value', '')}" for p in items)
        return f"{desc}{suffix}" if desc else ''
    except Exception:
        return ''


class ItsKTasks:
    """iTSK签到任务自动化执行类"""

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
                # 从统一配置文件的 itsk 节点读取
                itsk_config = config_data.get('itsk', {})
                self.accounts = itsk_config.get('accounts', [])

            if not self.accounts:
                self.logger.warning("配置文件中没有找到 itsk 账号信息")
            else:
                self.logger.info(f"成功加载 {len(self.accounts)} 个账号配置")

        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件JSON解析失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"读取配置文件失败: {e}")
            raise

    def _save_refreshed_token(self, account_index: int, api: ItsKAPI):
        """
        账密登录换新令牌后回写配置文件，避免下次执行仍使用过期令牌

        Args:
            account_index (int): 账号在配置数组中的下标
            api (ItsKAPI): 持有最新令牌的API实例
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            accounts = config_data.get('itsk', {}).get('accounts', [])
            if account_index >= len(accounts):
                self.logger.warning("⚠️ 账号下标越界，跳过令牌回写")
                return

            accounts[account_index]['access_token'] = api.access_token
            if api.uid:
                accounts[account_index]['uid'] = api.uid

            # 原子写入：先写临时文件再替换，避免进程中断导致配置文件截断损坏
            tmp_path = self.config_path.with_suffix('.json.tmp')
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.config_path)

            self.logger.info("💾 新令牌已写回配置文件")
        except Exception as e:
            self.logger.warning(f"⚠️ 回写令牌失败: {e}")

    def _ensure_valid_token(self, api: ItsKAPI) -> Dict[str, Any]:
        """
        确保拿到可用令牌：已有令牌先验证，过期则账密登录换新

        Args:
            api (ItsKAPI): API实例

        Returns:
            Dict[str, Any]: {'success', 'error', 'panel'(可用时为签到面板查询结果)}
        """
        panel = None
        if api.access_token:
            panel = api.get_sign_panel()
            if panel.get('success'):
                return {'success': True, 'panel': panel}
            if panel.get('error_type') != 'token_expired':
                return {'success': False, 'error': panel.get('error', '查询签到面板失败')}
            if not (api.username and api.password):
                return {'success': False,
                        'error': '令牌已过期且未配置账密，请重新抓取 access_token 或在配置中补充账密'}
            self.logger.info(f"🔁 令牌已过期，尝试账密登录换新")

        login = api.login()
        if not login.get('success'):
            return {'success': False, 'error': login.get('error', '账密登录失败')}

        panel = api.get_sign_panel()
        if not panel.get('success'):
            return {'success': False,
                    'error': f"登录成功但查询签到面板失败: {panel.get('error', '未知错误')}"}
        return {'success': True, 'panel': panel}

    def _do_sign(self, api: ItsKAPI, panel: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析签到面板并执行签到

        Args:
            api (ItsKAPI): API实例
            panel (Dict[str, Any]): get_sign_panel 的成功结果

        Returns:
            Dict[str, Any]: {'success', 'already_checked', 'message', 'extra', 'rewards'}
        """
        data = panel.get('data') or {}
        extra: List[str] = []
        rewards = ''

        days = data.get('prize_daily') or []
        entry = None
        if data.get('sign_type') == 2 and days:
            # 活动签到模式：按日历判定今天的状态
            today = _today_str()
            entry = next((e for e in days if e.get('date') == today), None)
            status = entry.get('sign_status') if entry else None

            missed = [e.get('date') for e in days if e.get('sign_status') == SIGN_STATUS_MISSED]
            if missed:
                extra.append(f"⚠️ 有 {len(missed)} 天可补签（消耗钻石，请到官网日历手动补签）")
            if data.get('full_sign') == 1:
                extra.append("🎉 本活动已全勤")

            if status in SIGN_STATUS_SIGNED:
                return {'success': True, 'already_checked': True,
                        'message': '今日已签到', 'extra': extra, 'rewards': ''}

            if not entry:
                extra.append("ℹ️ 今日不在活动日历中")
        elif isinstance(data.get('status'), int):
            # 普通签到模式：status 0=未签 1=已签
            status = data.get('status')
            if status == 1:
                return {'success': True, 'already_checked': True,
                        'message': '今日已签到', 'extra': extra, 'rewards': ''}
        else:
            # 未知面板结构：直接尝试签到，以服务端消息为准
            status = None
            extra.append("ℹ️ 签到面板结构未知，直接尝试签到")

        sign = api.sign_activity()
        if sign.get('success'):
            sign_data = sign.get('data') or {}
            rewards = _describe_rewards(entry if data.get('sign_type') == 2 else None,
                                        sign_data.get('is_vip'))
            message = '签到成功' + (f" {rewards}" if rewards else '')
            if sign_data.get('full_sign') == 1:
                extra.append("🎉 全勤达成")
            return {'success': True, 'already_checked': False,
                    'message': message, 'extra': extra, 'rewards': rewards}
        if '已签' in (sign.get('error') or ''):
            # 并发/重复签到时服务端会提示已签到，按成功处理
            return {'success': True, 'already_checked': True,
                    'message': '今日已签到', 'extra': extra, 'rewards': ''}
        return {'success': False, 'already_checked': False,
                'message': sign.get('error', '签到失败'), 'extra': extra, 'rewards': ''}

    def process_account(self, account_index: int, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个账号的签到任务

        Args:
            account_index (int): 账号在配置数组中的下标
            account_info (Dict[str, Any]): 账号信息字典

        Returns:
            Dict[str, Any]: 处理结果
        """
        account_name = account_info.get('account_name') or account_info.get('username') or '未命名账号'
        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"开始处理账号: {account_name}")
        self.logger.info(f"{'=' * 60}")

        result = {
            'account_name': account_name,
            'success': False,
            'message': '',
            'already_checked': False,
            'rewards': '',
            'extra': []
        }

        try:
            api = ItsKAPI(
                access_token=account_info.get('access_token'),
                username=account_info.get('username'),
                password=account_info.get('password'),
                uid=account_info.get('uid'),
                user_agent=account_info.get('user_agent'),
            )

            if not api.access_token and not (api.username and api.password):
                error_msg = "账号配置中既无 access_token 也未配置账密"
                self.logger.error(f"❌ {account_name}: {error_msg}")
                result['message'] = error_msg
                return result

            # 查询签到面板（令牌过期时账密自动换新）
            self.logger.info(f"{account_name} - 查询签到面板")
            ensured = self._ensure_valid_token(api)
            if not ensured.get('success'):
                result['message'] = ensured.get('error', '获取可用令牌失败')
                self.logger.error(f"❌ {account_name} {result['message']}")
                return result

            # 执行签到
            self.logger.info(f"{account_name} - 处理签到")
            sign = self._do_sign(api, ensured['panel'])
            result['success'] = sign['success']
            result['already_checked'] = sign['already_checked']
            result['message'] = sign['message']
            result['rewards'] = sign.get('rewards', '')
            result['extra'] = sign.get('extra', [])

            if sign['success']:
                self.logger.info(f"✅ {account_name} {sign['message']}")
            else:
                self.logger.error(f"❌ {account_name} 签到失败: {sign['message']}")
            for line in sign.get('extra', []):
                self.logger.info(f"    {line}")

            # 账密登录换新过令牌则回写配置
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
            self.logger.info(f"⏱️  随机延迟 {delay:.0f} 秒后开始（可通过环境变量 ITSK_JITTER_MAX 调整）")
            time.sleep(delay)

        self.logger.info("=" * 60)
        self.logger.info("iTSK自动签到任务开始")
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
            for line in result.get('extra', []):
                self.logger.info(f"    {line}")

        self.logger.info("=" * 60)

    def _send_notification(self):
        """发送推送通知"""
        if not self.account_results:
            return

        total = len(self.account_results)
        success = sum(1 for r in self.account_results if r['success'])
        already = sum(1 for r in self.account_results if r.get('already_checked'))
        failed = total - success

        title = "iTSK签到结果通知"

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
            if result.get('rewards'):
                content_lines.append(f"    🎁 {result['rewards']}")
            for line in result.get('extra', []):
                content_lines.append(f"    {line}")

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
        tasks = ItsKTasks()
        tasks.run()

    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        print("请确保配置文件存在并包含 itsk 账号信息")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
