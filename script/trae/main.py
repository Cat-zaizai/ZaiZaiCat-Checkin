#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new Env('TraeCN签到');
cron: 30 8 * * *
"""

"""
Trae CN 每日签到脚本

Trae CN 已切换为积分计费，本脚本每天自动为配置中的每个账号领取签到积分。
接口实现参考 cockpit-tools PR #2179 (feat/trae-cn-checkin-credits)：
- 签到状态: POST https://api.trae.cn/trae/api/v2/ug/checkin_credits/status
- 领取积分: POST https://api.trae.cn/trae/api/v2/ug/checkin_credits/claim

设备绑定说明（重要）：
- Trae CN 的签到按「账号 × 已注册设备」校验，x-device-id 必须使用该账号自己注册的
  设备（本机客户端 icube-dc 键后缀的 16 位数字 ID）。
- 一台机器上多个账号共用同一设备时，只有该设备所属账号能领取成功，其它账号会被服务端
  以 code=9095（当前设备今日已经签到 / 设备维度限额）或 code=9074（设备未登记/冲突，
  文案常为「当前参与用户太多」）拒绝。
- 伪造/随机设备不可行（实测 code=9074）。
- 因此每个账号建议单独配置其 device_id；单账号场景下脚本会自动回退使用本机主客户端设备。

主要能力：
- 多账号依次处理，账号间随机延迟 5-10 秒
- 账号级签到设备 ID：优先取账号自身配置/官方客户端配对设备
- 网页会话（session）失效时自动回退该账号 access_token 再试一次
- 令牌本地过期预检（expires_at），HTTP 连接/5xx 自动重试（会话复用）
- 领取失败自动复查状态，区分「真已签到」与「设备冲突/未登记」，如实上报
- 汇总与推送单列「需更新凭证」账号，便于及时处理

Author: Assistant
Date: 2026-09-07
"""

import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 获取项目根目录
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import TraeAPI, TraeWebAPI
from import_accounts import (
    get_or_create_device_id,
    scan_client_device_pairs,
)
from notification import send_notification, NotificationSound

# 启动随机延迟上限（秒）：在窗口内随机错开请求，避免与他人撞车；设为 0 关闭
JITTER_MAX_SECONDS = int(os.environ.get('TRAE_JITTER_MAX', '600'))

# 领取接口设备类错误码：9074 设备未登记/冲突；9095 设备当日已用于其它账号签到
DEVICE_CONFLICT_CODES = {9074, 9095}
# 9074：设备未登记或伪造（文案「当前参与用户太多」）；9095：共享设备今日已被其它账号占用
DEVICE_MISSING_HINT = (
    "签到被设备校验拒绝（code={code}: {message}）。Trae CN 领取积分必须使用该账号"
    "自己注册的设备（x-device-id），伪造/随机设备不可用。请先在本机官方 Trae 客户端"
    "用该账号登录一次完成设备注册后重新导入，或在账号配置中手动填写其 device_id。"
)
DEVICE_SHARED_HINT = "共享设备今日已被其它账号签到（code={code}: {message}），该设备每日仅一次签到名额。如需独立签到请改用网页会话模式（配置 session 即可，无需本机设备）。"


def web_device_for(user_id: str) -> str:
    """
    网页会话模式的稳定随机设备 ID（16 位数字）

    实测网页链路（GetUserToken 换的 JWT）不校验客户端注册设备，随机设备即可签到；
    按 user_id 固定生成，保证同一账号每天用同一设备、重复运行幂等。
    """
    seed = f'trae-web:{user_id}'
    rng = random.Random(seed)
    return str(rng.randint(10 ** 15, 10 ** 16 - 1))


class TraeTasks:
    """Trae CN 签到任务自动化执行类"""

    def __init__(self, config_path: str = None):
        """
        初始化任务执行器

        Args:
            config_path (str): 配置文件的完整路径，如果为 None 则使用项目根目录下的 config/token.json
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
        """从配置文件的 trae 节点读取账号信息"""
        if not self.config_path.exists():
            self.logger.error(f"配置文件不存在: {self.config_path}")
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            trae_config = config_data.get('trae', {})
            self.accounts = trae_config.get('accounts', [])
            # 只保留 CN 账号（签到积分接口仅存在于 Trae CN）
            self.accounts = [a for a in self.accounts if a.get('region', 'CN') == 'CN']

            if not self.accounts:
                self.logger.warning("配置文件中没有找到 Trae CN 账号信息")
            else:
                self.logger.info(f"成功加载 {len(self.accounts)} 个 CN 账号配置")

        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件JSON解析失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"读取配置文件失败: {e}")
            raise

    def resolve_device_for(self, account: Dict[str, Any], pair_map: Dict[str, str],
                           shared_device: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        解析账号的签到设备 ID（签到领取必须携带账号自己注册的设备）

        优先级：账号配置 device_id → 官方客户端配对（userId 匹配）→
        显式授权使用本机主客户端设备（use_shared_device=true 或单账号场景）→ 无。

        Returns:
            Tuple[Optional[str], Optional[str]]: (device_id, 缺失原因)，可取到设备时第二项为 None
        """
        device = str(account.get('device_id') or '').strip()
        if device:
            return device, None

        user_id = str(account.get('user_id') or '')
        if user_id and user_id in pair_map:
            return pair_map[user_id], None

        # 本机主客户端设备是「单设备每日仅一次」的共享资源：仅当账号显式授权
        # （use_shared_device=true 或全配置仅此一个 CN 账号）时才回退使用
        if shared_device and (bool(account.get('use_shared_device')) or len(self.accounts) == 1):
            return shared_device, None

        return None, (
            "账号未配置签到设备 device_id，本机官方客户端无该账号的注册设备配对，"
            "也未授权使用本机共享设备。Trae CN 桌面令牌链路领取必须用该账号自己注册"
            "的设备（伪造/随机设备会 code=9074，多账号共用会 code=9095）。"
            "多账号场景建议改为网页会话模式：为该账号配置 session"
            "（浏览器 https://www.trae.cn 登录后复制 X-Cloudide-Session）即不受本机"
            "设备限制。单账号可将 use_shared_device 置为 true 使用本机主客户端设备"
            "（该设备每日只能成功领取一次）。"
        )

    def _build_api(self, account_info: Dict[str, Any], prefer_desktop: bool = False
                   ) -> Tuple[Optional[Any], str, Optional[str], Optional[str]]:
        """
        按账号凭证构造 API 实例

        Args:
            account_info (Dict[str, Any]): 账号信息字典
            prefer_desktop (bool): 为 True 时跳过 session，强制走桌面令牌（用于会话失效回退）

        Returns:
            Tuple[Optional[Any], str, Optional[str], Optional[str]]:
                (api, mode, device_id, missing_reason)；api 为 None 表示凭证不可用
        """
        session = str(account_info.get('session') or '').strip()
        if session and not prefer_desktop:
            user_key = str(account_info.get('user_id') or account_info.get('account_name') or '')
            device_id = str(account_info.get('device_id') or '').strip() or web_device_for(user_key)
            return TraeWebAPI(session=session, device_id=device_id), '网页会话', device_id, None

        access_token = account_info.get('access_token')
        if not access_token:
            return None, '', None, '账号配置缺少 access_token（或未配置 session）'

        expires_at = account_info.get('expires_at')
        if expires_at:
            try:
                if time.time() > float(expires_at):
                    expired = time.strftime('%Y-%m-%d %H:%M', time.localtime(float(expires_at)))
                    return None, '', None, f'access_token 已于 {expired} 过期，请重新导入账号'
            except (TypeError, ValueError):
                pass

        device_id, missing_reason = self.resolve_device_for(
            account_info, self.device_pair_map, self.shared_device)
        mode = '桌面令牌（会话失效回退）' if (prefer_desktop and session) else '桌面令牌'
        return TraeAPI(access_token=access_token, device_id=device_id or ''), mode, device_id, missing_reason

    def process_account(self, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个账号的签到任务

        Args:
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
            'gained': None,
            'token_error': False,
            'device_missing': False,
        }

        try:
            api, mode, device_id, missing_reason = self._build_api(account_info)
            if api is None:
                result['message'] = missing_reason
                result['token_error'] = True
                self.logger.error(f"❌ {account_name}: {missing_reason}")
                return result

            # 查询签到状态（状态接口与设备无关，无设备也可查询）
            self.logger.info(f"{account_name} - 查询签到状态（{mode}）")
            status = api.get_checkin_status()

            # 网页会话失效且账号仍有 access_token：回退桌面令牌再试一次
            if (not status['success'] and status.get('error_type') == 'session_invalid'
                    and account_info.get('access_token')):
                self.logger.warning(f"⚠️ {account_name} 网页会话已失效，回退桌面令牌重试")
                api, mode, device_id, missing_reason = self._build_api(
                    account_info, prefer_desktop=True)
                if api is None:
                    result['message'] = f"{missing_reason}（网页会话已失效）"
                    result['token_error'] = True
                    self.logger.error(f"❌ {account_name} {result['message']}")
                    return result
                status = api.get_checkin_status()

            if not status['success']:
                if status.get('error_type') in ('token_expired', 'session_invalid'):
                    result['message'] = f"{status.get('error', '凭证已失效')}，请重新导入账号/更新 session"
                    result['token_error'] = True
                    self.logger.error(f"❌ {account_name} {result['message']}")
                else:
                    result['message'] = status.get('error', '查询签到状态失败')
                    self.logger.error(f"❌ {account_name} {result['message']}")
                return result

            # 功能不可用（服务端 enable=false，如活动未开放）
            if not status.get('enable', True):
                result['success'] = True
                result['message'] = '签到活动未开启或不适用'
                self.logger.info(f"ℹ️ {account_name} 签到活动未开启")
                return result

            # 今日已签到（状态接口为账号维度，与本次所用设备无关）
            if status.get('checked_in'):
                result['success'] = True
                result['already_checked'] = True
                result['message'] = '今日已签到'
                self.logger.info(f"✅ {account_name} 今日已签到")
                return result

            # dry-run 模式不执行领取
            if self.dry_run:
                result['success'] = True
                result['message'] = '状态正常，dry-run 未执行签到'
                self.logger.info(f"👀 {account_name} 状态正常（dry-run 跳过领取）")
                return result

            # 桌面令牌模式且未配置设备：无法领取，如实提示（不能伪造/复用主设备）
            if mode.startswith('桌面令牌') and not device_id:
                result['message'] = missing_reason or '账号缺少签到设备 device_id'
                result['device_missing'] = True
                self.logger.warning(f"⚠️ {account_name} 缺少签到设备: {result['message']}")
                return result

            # 执行签到
            self.logger.info(f"{account_name} - 执行签到 (device={device_id})")
            checkin = api.claim_checkin()

            if checkin['success']:
                result['success'] = True
                result['message'] = checkin.get('message') or '签到成功'
                result['gained'] = checkin.get('credits')
                extra = f"，奖励 {result['gained']} 积分" if result['gained'] is not None else ''
                self.logger.info(f"✅ {account_name} 签到成功{extra}")
            else:
                # 凭证失效单独处理
                if checkin.get('error_type') in ('token_expired', 'session_invalid'):
                    result['message'] = f"{checkin.get('error', '凭证已失效')}，请重新导入账号/更新 session"
                    result['token_error'] = True
                    self.logger.error(f"❌ {account_name} {result['message']}")
                    return result

                # 领取失败后复查状态：status 为账号维度，若已变真签到则按已签处理
                latest = api.get_checkin_status()
                if latest['success'] and latest.get('checked_in'):
                    result['success'] = True
                    result['already_checked'] = True
                    result['message'] = '领取报错但复查已签到'
                    self.logger.info(f"✅ {account_name} 领取报错但复查已签到")
                    return result

                # 设备类错误给出可操作指引；其它错误保留服务端原文
                code = checkin.get('code')
                raw_error = checkin.get('error', '签到失败')
                if code in DEVICE_CONFLICT_CODES or '设备' in raw_error or '参与用户' in raw_error:
                    if code == 9095:
                        result['message'] = DEVICE_SHARED_HINT.format(code=code or '?', message=raw_error)
                    else:
                        result['message'] = DEVICE_MISSING_HINT.format(code=code or '?', message=raw_error)
                    result['device_missing'] = True
                else:
                    result['message'] = raw_error
                self.logger.error(f"❌ {account_name} 签到失败: {result['message']}")

        except Exception as e:
            error_msg = f"处理账号时发生异常: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            result['message'] = error_msg

        return result

    def run(self, dry_run: bool = False):
        """执行所有账号的签到任务"""
        self.dry_run = dry_run

        # 设备解析：官方客户端 userId→设备配对表；本机主客户端设备仅在单账号或
        # 账号显式 use_shared_device=true 时回退使用
        self.device_pair_map = scan_client_device_pairs()
        if self.device_pair_map:
            self.logger.info(f"📱 官方客户端设备配对: {len(self.device_pair_map)} 个")
        use_shared = len(self.accounts) == 1 or any(
            a.get('use_shared_device') for a in self.accounts)
        self.shared_device = get_or_create_device_id(self.config_path.parent) if use_shared else None
        if self.shared_device:
            scope = '单账号' if len(self.accounts) == 1 else '显式授权'
            self.logger.info(f"📱 {scope}场景回退本机主客户端设备: {self.shared_device}")

        # 启动随机抖动，错开请求高峰
        if JITTER_MAX_SECONDS > 0:
            delay = random.uniform(0, JITTER_MAX_SECONDS)
            self.logger.info(f"⏱️  随机延迟 {delay:.0f} 秒后开始（可通过环境变量 TRAE_JITTER_MAX 调整）")
            time.sleep(delay)

        self.logger.info("=" * 60)
        self.logger.info("Trae CN 自动签到任务开始" + ("（dry-run 状态检查）" if dry_run else ""))
        self.logger.info("=" * 60)

        if not self.accounts:
            self.logger.warning("没有需要处理的账号")
            return

        for idx, account_info in enumerate(self.accounts):
            result = self.process_account(account_info)
            self.account_results.append(result)

            # 处理完一个账号后，如果还有下一个账号，则等待 5-10 秒
            if idx < len(self.accounts) - 1:
                delay = random.uniform(5, 10)
                self.logger.info(f"\n⏱️  等待 {delay:.1f} 秒后处理下一个账号...")
                time.sleep(delay)

        self._print_summary()
        if not dry_run:
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
        token_failed = sum(1 for r in self.account_results if r.get('token_error'))
        device_missing = sum(1 for r in self.account_results if r.get('device_missing'))

        self.logger.info(f"总账号数: {total}")
        self.logger.info(f"签到成功: {success - already}")
        self.logger.info(f"今日已签: {already}")
        self.logger.info(f"签到失败: {failed}")
        if token_failed:
            self.logger.info(f"其中需更新凭证: {token_failed}")
            for r in self.account_results:
                if r.get('token_error'):
                    self.logger.info(f"  ⚠️ {r['account_name']} 凭证失效，需重新导入账号/更新 session")
        if device_missing:
            self.logger.info(f"其中设备缺失/冲突: {device_missing}")

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
        token_failed = sum(1 for r in self.account_results if r.get('token_error'))

        title = "Trae CN签到结果通知"

        content_lines = [
            f"📊 总账号数: {total}",
            f"✅ 签到成功: {success - already}",
            f"📅 今日已签: {already}",
            f"❌ 签到失败: {failed}",
        ]
        if token_failed:
            content_lines.append(f"⚠️ 需更新凭证: {token_failed}")
        content_lines += ["", "📋 详细结果:"]

        for result in self.account_results:
            status = "✅" if result['success'] else "❌"
            content_lines.append(f"{status} {result['account_name']}: {result['message']}")
            if result.get('gained') is not None:
                content_lines.append(f"    🎁 奖励积分: {result['gained']}")

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
    dry_run = '--dry-run' in sys.argv
    try:
        tasks = TraeTasks()
        tasks.run(dry_run=dry_run)

    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        print("请确保配置文件存在并包含 trae 账号信息")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
