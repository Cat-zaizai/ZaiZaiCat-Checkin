#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iTSK(IT天空) API模块

提供 iTSK(www.itsk.com) 签到相关的API接口封装:
- 账密登录: POST /username/login,返回 data.access_token(含 Bearer 前缀,15天有效)
- 签到面板: GET  /sign,只读状态不产生签到
- 执行签到: GET  /sign_activity,对应前端点击"签到"按钮
- 补签:     POST /sign_backdate,消耗钻石,本模块不自动调用,仅在结果里提醒

接口行为(2026-11 逆向 www.itsk.com 前端 _nuxt 产物并实测):
- 签到面板存在两种模式:
  - 活动签到(sign_type=2):data.prize_daily[] 按日期给出每日 sign_status,
    1=已签(历史) 2=错过可补签 3=今日已签 4=今日可签 0=未开放(未来)
  - 普通签到:data.status 0=未签 1=已签
- 登录与签到接口均不会在响应头下发新令牌,令牌续期只能通过账密登录

网关签名(所有请求必须携带):
- X-Request-Timestamp: 秒级时间戳
- X-Request-Nonce: 32位 [0-9A-Za-z] 随机串
- X-Request-Signature: SHA1(nonce[0:4] + str(ts) + nonce[28:32] + nonce) 小写hex
"""

import hashlib
import random
import time
from typing import Any, Dict, Optional

import requests

NONCE_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'


def _make_nonce(n: int = 32) -> str:
    """生成32位随机串"""
    return ''.join(random.choice(NONCE_CHARS) for _ in range(n))


def _request_signature(nonce: str, ts: int) -> str:
    """计算网关签名: SHA1(nonce[0:4] + ts + nonce[28:32] + nonce)"""
    raw = nonce[:4] + str(ts) + nonce[28:32] + nonce
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


class ItsKAPI:
    """iTSK API类"""

    BASE_URL = 'https://api.itsk.com/webapi'
    DEFAULT_USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36'
    )

    LOGIN_PATH = '/username/login'
    SIGN_PANEL_PATH = '/sign'
    SIGN_ACTION_PATH = '/sign_activity'

    def __init__(
        self,
        access_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        uid: Optional[str] = None,
        user_agent: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        初始化API类

        Args:
            access_token (Optional[str]): 访问令牌,即登录响应 data.access_token 的原值
                                          (含 Bearer 前缀;不带前缀网关也能识别)
            username (Optional[str]): 登录用户名或手机号,令牌过期时用于自动换新
            password (Optional[str]): 登录密码,令牌过期时用于自动换新
            uid (Optional[str]): 用户ID,登录成功后会自动更新
            user_agent (Optional[str]): 用户代理字符串,可选
            timeout (int): 请求超时时间(秒)
        """
        self.access_token = access_token or ''
        self.username = username or ''
        self.password = password or ''
        self.uid = str(uid) if uid else ''
        self.timeout = timeout
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        # 账密登录换到新令牌后置为True,供上层决定是否回写配置文件
        self.token_refreshed = False

    def _build_headers(self, method: str) -> Dict[str, str]:
        """
        构造请求头,携带网关签名

        Args:
            method (str): 请求方法,POST 时补充 Content-Type

        Returns:
            Dict[str, str]: 请求头字典
        """
        nonce, ts = _make_nonce(), int(time.time())
        headers = {
            'Authorization': self.access_token,
            'Accept': '*/*',
            'Origin': 'https://www.itsk.com',
            'Referer': 'https://www.itsk.com/',
            'User-Agent': self.user_agent,
            'X-Request-Timestamp': str(ts),
            'X-Request-Nonce': nonce,
            'X-Request-Signature': _request_signature(nonce, ts),
        }
        if method == 'POST':
            headers['Content-Type'] = 'application/json'
        return headers

    @staticmethod
    def _classify(code: Any, http_status: int) -> Optional[str]:
        """
        按业务码/HTTP状态码归类错误

        Returns:
            Optional[str]: token_expired / rate_limit / wrong_password,无匹配返回None
        """
        if http_status == 401 or code in (-2000, -2999):
            return 'token_expired'
        if http_status == 429 or code == 429:
            return 'rate_limit'
        if code == -3000:
            return 'wrong_password'
        return None

    def _request(self, path: str, method: str = 'GET', body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        统一请求入口

        Args:
            path (str): 接口路径,以 / 开头
            method (str): 请求方法
            body (Optional[Dict[str, Any]]): POST 请求体

        Returns:
            Dict[str, Any]: {'success', 'message', 'data', 'error', 'error_type', 'code', 'http_status'}
        """
        url = f'{self.BASE_URL}{path}'
        try:
            resp = requests.request(
                method,
                url,
                headers=self._build_headers(method),
                json=body,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            return {'success': False, 'error': f'网络请求异常: {e}'}

        try:
            payload = resp.json()
        except ValueError:
            return {
                'success': False,
                'error': f'响应非JSON(HTTP {resp.status_code})',
                'http_status': resp.status_code,
            }

        code = payload.get('code', payload.get('errorcode'))
        message = payload.get('message', '')
        if code != 200:
            error_type = self._classify(code, resp.status_code)
            if error_type == 'rate_limit':
                message = message or '请求过于频繁(限流),请稍后再试'
            return {
                'success': False,
                'error': message or f'接口返回异常(code={code})',
                'error_type': error_type,
                'code': code,
                'http_status': resp.status_code,
            }
        return {'success': True, 'message': message, 'data': payload.get('data') or {}}

    def login(self) -> Dict[str, Any]:
        """
        账密登录获取新令牌,成功后更新 self.access_token / self.uid

        注意:登录接口限流 3 次/分钟,调用方不要循环重试

        Returns:
            Dict[str, Any]: {'success', 'error'(失败时)}
        """
        if not self.username or not self.password:
            return {'success': False, 'error': '账号未配置 username/password,无法登录换新令牌'}

        old_token = self.access_token
        result = self._request(
            self.LOGIN_PATH,
            method='POST',
            body={
                'login_identifier': self.username,
                'password': self.password,
                'source': 'pc',
            },
        )
        if not result.get('success'):
            if result.get('error_type') == 'rate_limit':
                result['error'] = '登录被限流(3次/分钟),请稍后再试'
            elif result.get('error_type') == 'wrong_password':
                result['error'] = '用户名、手机号或密码错误(若刚修改过密码,请同步更新配置)'
            return result

        token = (result.get('data') or {}).get('access_token') or ''
        if not token:
            return {'success': False, 'error': '登录接口未返回 access_token'}
        self.access_token = token
        self.uid = str((result.get('data') or {}).get('uid') or self.uid or '')
        # 与旧令牌不同(或原先为空)才视为换新,供上层回写配置
        self.token_refreshed = token != old_token
        return {'success': True}

    def get_sign_panel(self) -> Dict[str, Any]:
        """
        查询签到面板(只读,不产生签到)

        Returns:
            Dict[str, Any]: {'success', 'data'};data 为活动签到日历或普通签到状态
        """
        return self._request(self.SIGN_PANEL_PATH)

    def sign_activity(self) -> Dict[str, Any]:
        """
        执行签到,对应前端点击"签到"按钮

        Returns:
            Dict[str, Any]: {'success', 'message', 'data'};
            data 含 is_vip / full_sign / has_vip_days / is_forever_vip
        """
        return self._request(self.SIGN_ACTION_PATH)
