#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trae CN 签到 API 模块

签到积分接口仅存在于 Trae CN（api.trae.cn），适配官方接口约定：
- 签到状态: POST /trae/api/v2/ug/checkin_credits/status (body "{}")
- 领取积分: POST /trae/api/v2/ug/checkin_credits/claim    (body "{}")

认证与请求头对齐 cockpit-tools PR #2179 (feat/trae-cn-checkin-credits)：
- Authorization: Cloud-IDE-JWT <access_token>（不是 Bearer）
- User-Agent: Trae/1.0.0 antigravity-cockpit-tools
- x-device-id: 该账号自己注册的设备 ID（本机客户端 icube-dc 后缀的 16 位数字）。
  注意：签到按「账号 × 设备」校验，多账号共用同一设备或使用伪造/随机设备会被拒
  （code=9074/9095）；状态查询接口不校验设备。

响应约定：扁平 JSON，仅 code == 0 视为成功。
- 状态: {"code":0,"checked_in":true,"credits":150,"enable":true,"message":"..."}，credits 为单日奖励口径参考
- 领取: {"code":0,"credits":150,"message":"..."}，credits 为本次获得的积分
"""

import logging
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# 签到接口仅存在于 Trae CN 域（api.trae.cn），国际版 Trae 无此接口
BASE_URL = 'https://api.trae.cn/trae/api/v2/ug'

CHECKIN_STATUS_PATH = '/checkin_credits/status'
CHECKIN_CLAIM_PATH = '/checkin_credits/claim'

# 与 cockpit-tools 官方客户端行为保持一致
DEFAULT_USER_AGENT = 'Trae/1.0.0 antigravity-cockpit-tools'

# 认证类业务错误码：命中即视为凭证失效（令牌过期/被拒），交由上层提示更新
# 1001 实测文案 "We're sorry, but we are not able to authenticate you."
AUTH_ERROR_CODES = {401, 1001, 1002, 1003, 10085}
# 认证失败文案关键词（对 message 小写后比对，中文不受 lower 影响）
AUTH_ERROR_HINTS = ('登录', '过期', '认证', '未授权', 'authenticate', 'unauthorized')


def _parse_code_message(body: Dict[str, Any]) -> str:
    """宽松提取接口返回的业务提示文案"""
    message = body.get('message') or body.get('msg') or 'unknown error'
    if not isinstance(message, str):
        message = str(message)
    return message


def _is_auth_error(code: Any, message: str) -> bool:
    """判断业务错误是否属于凭证失效（错误码或文案任一命中）"""
    if code in AUTH_ERROR_CODES:
        return True
    lowered = message.lower()
    return any(hint in lowered for hint in AUTH_ERROR_HINTS)


_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """
    惰性创建共享请求会话（连接复用 + 自动重试）

    仅对连接错误与 429/5xx 重试，不改动业务响应判定；签到接口按天幂等，重试安全。
    """
    global _session
    if _session is None:
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({'POST'}),
            respect_retry_after_header=False,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        _session = requests.Session()
        _session.mount('https://', adapter)
    return _session


class TraeAPI:
    """Trae CN 签到 API 类"""

    def __init__(self, access_token: str, device_id: str = '', timeout: int = 30):
        """
        初始化 API 类

        Args:
            access_token (str): Trae CN 访问令牌，对应请求头 Cloud-IDE-JWT
            device_id (str): 该账号自己注册的设备 ID（16 位数字），对应请求头 x-device-id；
                领取接口校验设备，状态接口不校验
            timeout (int): 请求超时时间（秒）
        """
        self.access_token = access_token
        self.device_id = device_id
        self.timeout = timeout

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            'Authorization': f'Cloud-IDE-JWT {self.access_token}',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'User-Agent': DEFAULT_USER_AGENT,
        }
        if self.device_id:
            headers['x-device-id'] = self.device_id
        return headers

    def _post(self, path: str) -> Dict[str, Any]:
        """
        发送 POST 请求并解析统一响应结构

        Returns:
            Dict[str, Any]: 包含 success/data/error/error_type/code 的结果字典
        """
        url = f'{BASE_URL}{path}'
        headers = self._build_headers()

        try:
            response = _get_session().post(url, headers=headers, json={}, timeout=self.timeout)
        except requests.RequestException as e:
            return {'success': False, 'error': f'请求 {path} 失败: {e}', 'error_type': 'network'}

        if response.status_code == 401:
            return {
                'success': False,
                'error': '令牌已失效 (http=401)，请重新导入账号',
                'error_type': 'token_expired',
            }

        try:
            body = response.json()
        except ValueError:
            return {
                'success': False,
                'error': f'解析 {path} 响应失败: {response.text[:200]}',
                'error_type': 'parse',
            }

        if not isinstance(body, dict):
            return {
                'success': False,
                'error': f'{path} 响应不是 JSON 对象: {str(body)[:200]}',
                'error_type': 'parse',
            }

        if not response.ok:
            return {
                'success': False,
                'error': f'请求 {path} 失败 (http={response.status_code}): {_parse_code_message(body)}',
                'error_type': 'http',
            }

        code = body.get('code', -1)
        if code != 0:
            # 业务错误（如今日已签到、风控、令牌过期），保留服务端原始提示交由上层判断
            message = _parse_code_message(body)
            error_type = 'token_expired' if _is_auth_error(code, message) else 'business'
            return {
                'success': False,
                'error': f'{message} (code={code})',
                'error_type': error_type,
                'code': code,
                'body': body,
            }

        return {'success': True, 'data': body}

    @staticmethod
    def _parse_status(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析签到状态响应

        Args:
            data (Dict[str, Any]): 接口返回的扁平 JSON

        Returns:
            Dict[str, Any]: 标准化后的签到状态
        """
        checked_in = bool(data.get('checked_in', False))
        # did_checked_in：是否为「本次所用设备」当日签到（checked_in 为账号维度真值；
        # 若 checked_in=true 而 did_checked_in=false，说明账号已在其它渠道签过，领取为幂等）
        # credits 为服务端返回的积分参考值（实测对同一时段所有账号一致，为单日奖励口径，
        # 非累计余额），此处仅原样透传，避免误当余额展示
        return {
            'success': True,
            'checked_in': checked_in,
            'did_checked_in': bool(data.get('did_checked_in', False)),
            'credits': data.get('credits') or 0,
            'extra_credits': data.get('extra_credits'),
            'enable': bool(data.get('enable', True)),
            'message': '今日已签到' if checked_in else '今日未签到',
            'raw': data,
        }

    def get_checkin_status(self) -> Dict[str, Any]:
        """
        查询今日签到状态

        Returns:
            Dict[str, Any]: 包含 checked_in/credits 的结果字典
        """
        result = self._post(CHECKIN_STATUS_PATH)
        if not result['success']:
            return {
                'success': False,
                'error': result.get('error', '查询签到状态失败'),
                'error_type': result.get('error_type', 'api'),
                'code': result.get('code'),
            }
        return self._parse_status(result['data'])

    def claim_checkin(self) -> Dict[str, Any]:
        """
        领取今日签到积分

        Returns:
            Dict[str, Any]: 包含 message/credits（本次奖励）的结果字典
        """
        result = self._post(CHECKIN_CLAIM_PATH)
        if not result['success']:
            return {
                'success': False,
                'error': result.get('error', '签到领取失败'),
                'error_type': result.get('error_type', 'api'),
                'code': result.get('code'),
            }

        body = result['data']
        # 领取成功时服务端返回的 credits 为本次获得的积分（部分响应以 data.points 返回）
        credits = None
        data = body.get('data') if isinstance(body.get('data'), dict) else None
        if data:
            credits = data.get('points') or data.get('credits')
        if credits is None:
            credits = body.get('credits')

        raw_message = body.get('message') or ''
        if not isinstance(raw_message, str) or raw_message.lower() in ('success', 'ok'):
            message = '签到成功'
        else:
            message = raw_message

        return {
            'success': True,
            'message': message,
            'credits': int(credits) if isinstance(credits, (int, float)) and not isinstance(credits, bool) else None,
        }


# 网页会话模式使用的主机根（GetUserToken 不在 /trae/... 子路径下）
ROOT_URL = 'https://api.trae.cn'
GET_TOKEN_PATH = '/cloudide/api/v3/common/GetUserToken'


class TraeWebAPI:
    """
    Trae CN 网页会话签到 API 类（方案 C，参考 star620 云端思路）

    账号在浏览器登录后获得 HttpOnly Cookie `X-Cloudide-Session`（约 14 天有效），
    每次运行用它 POST /cloudide/api/v3/common/GetUserToken 换取全新 JWT
    （网页 JWT 约 8 小时），再走常规签到接口。

    实测：网页链路换来的 JWT + 随机 16 位设备可以正常签到（code=0），
    不像桌面令牌那样校验客户端注册设备（否则随机设备会 code=9074）。
    因此多账号各自提供 session 后即可分别每日签到，不受一机一设备限制。
    """

    def __init__(self, session: str, device_id: str = '', timeout: int = 30):
        self.session = session
        self.device_id = device_id
        self.timeout = timeout
        self._jwt: Optional[str] = None

    def _fetch_jwt(self) -> Dict[str, Any]:
        """用 X-Cloudide-Session 换取全新 JWT"""
        headers = {
            'Cookie': f'X-Cloudide-Session={self.session}',
            'Referer': 'https://www.trae.cn/',
            'Origin': 'https://www.trae.cn',
            'User-Agent': 'TraeCheckin/1.0',
            'Accept': 'application/json, text/plain, */*',
        }
        try:
            response = _get_session().post(ROOT_URL + GET_TOKEN_PATH, headers=headers,
                                           data='{}', timeout=self.timeout)
        except requests.RequestException as e:
            return {'success': False, 'error': f'换取 JWT 失败: {e}', 'error_type': 'network'}
        if response.status_code != 200:
            return {
                'success': False,
                'error': f'换取 JWT 失败 (http={response.status_code})，session 可能已失效',
                'error_type': 'session_invalid',
            }
        try:
            body = response.json()
        except ValueError:
            return {'success': False, 'error': '解析 JWT 响应失败', 'error_type': 'parse'}
        token = (body.get('Result') or {}).get('Token')
        if not token:
            msg = body.get('ResponseMetadata', {}).get('Error', {}).get('Message') or body
            return {
                'success': False,
                'error': f'换取 JWT 失败: {str(msg)[:120]}',
                'error_type': 'session_invalid',
            }
        self._jwt = token
        return {'success': True, 'jwt': token}

    def _delegate(self, method: str) -> Dict[str, Any]:
        """构造临时 TraeAPI 并调用指定方法；JWT 失效时换新重试一次"""
        for attempt in (1, 2):
            if not self._jwt:
                fetched = self._fetch_jwt()
                if not fetched['success']:
                    return {'success': False, 'error': fetched['error'],
                            'error_type': fetched['error_type']}
            api = TraeAPI(access_token=self._jwt, device_id=self.device_id, timeout=self.timeout)
            result = getattr(api, method)()
            if result['success'] or result.get('error_type') != 'token_expired' or attempt == 2:
                return result
            self._jwt = None  # 强制下次换新后重试
        return {'success': False, 'error': '网页令牌异常', 'error_type': 'token_expired'}

    def get_checkin_status(self) -> Dict[str, Any]:
        """查询今日签到状态"""
        return self._delegate('get_checkin_status')

    def claim_checkin(self) -> Dict[str, Any]:
        """领取今日签到积分"""
        return self._delegate('claim_checkin')
