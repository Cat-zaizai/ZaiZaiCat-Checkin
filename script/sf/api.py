#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
顺丰快递API模块

提供顺丰快递积分任务相关的API接口
"""

import requests
import time
import hashlib
import execjs
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SFExpressAPI:
    """顺丰速运API接口类"""

    def __init__(self, cookies: str = None, user_id: str = None, user_agent: str = None, channel: str = None, device_id: str = None):
        """
        初始化SF Express API

        Args:
            cookies: Cookie字符串
            user_id: 用户ID
            user_agent: 用户代理
            channel: 渠道
            device_id: 设备ID
        """
        self.js_file_path = os.path.join(os.path.dirname(__file__), 'code.js')
        self.base_url = "https://mcs-mimp-web.sf-express.com"
        self.session = requests.Session()
        self.cookies = cookies
        self.user_id = user_id
        self.user_agent = user_agent or (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) '
            'Version/18.5 Mobile/15E148 Safari/604.1'
        )
        self.channel = channel
        self.device_id = device_id
        self._init_js()

        self.default_headers = {
            "User-Agent": self.user_agent,
            "pragma": "no-cache",
            "cache-control": "no-cache",
            "timestamp": "",
            "signature": "",
            "channel": self.channel,
            "syscode": "MCS-MIMP-CORE",
            "sw8": "",
            "platform": "SFAPP",
            "sec-gpc": "1",
            "accept-language": "zh-CN,zh;q=0.9",
            "origin": "https://mcs-mimp-web.sf-express.com",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://mcs-mimp-web.sf-express.com/superWelfare?citycode=&cityname=&tab=0",
            "cookie": self.cookies,
            "priority": "u=1, i"
        }

    def _init_js(self):
        """初始化JavaScript环境"""
        try:
            with open(self.js_file_path, 'r', encoding='utf-8') as f:
                js_code = f.read()
            self.js_context = execjs.compile(js_code)
        except Exception as e:
            logger.error(f"初始化JavaScript环境失败: {e}")
            self.js_context = None

    def get_sw8(self, url_path):
        """调用JavaScript中的get_sw8函数"""
        if self.js_context is None:
            raise RuntimeError("JavaScript context not initialized")

        try:
            result = self.js_context.call('get_sw8', url_path)
            return result
        except Exception as e:
            logger.error(f"调用get_sw8函数时出错: {e}")
            return None

    def generate_signature(self, timestamp: str, sys_code: str = None) -> str:
        """生成签名"""
        sign_str = f"wwesldfs29aniversaryvdld29&timestamp={timestamp}&sysCode={sys_code}"
        return hashlib.md5(sign_str.encode()).hexdigest()

    def query_point_task_and_sign(self, channel_type: str = "1", device_id: str = None) -> Dict[str, Any]:
        """
        查询积分任务和签到信息

        Args:
            channel_type: 渠道类型，默认为"1"
            device_id: 设备ID，如果不提供则使用初始化时的device_id

        Returns:
            Dict: API响应结果
        """
        url_path = "/mcs-mimp/commonPost/~memberNonactivity~integralTaskStrategyService~queryPointTaskAndSignFromES"
        url = f"{self.base_url}{url_path}"

        timestamp = str(int(time.time() * 1000))

        data = {
            "channelType": channel_type,
            "deviceId": device_id or self.device_id
        }

        headers = self.default_headers.copy()
        sys_code = 'MCS-MIMP-CORE'
        headers.update({
            'timestamp': timestamp,
            'signature': self.generate_signature(timestamp, sys_code),
            'sw8': self.get_sw8(url_path).get('code')
        })

        try:
            response = self.session.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": "请求失败"
            }

    def finish_task(self, task_code: str) -> Dict[str, Any]:
        """
        完成任务接口

        Args:
            task_code: 任务代码

        Returns:
            Dict: API响应结果
        """
        url_path = "/mcs-mimp/commonPost/~memberEs~taskRecord~finishTask"
        url = f"{self.base_url}{url_path}"

        timestamp = str(int(time.time() * 1000))

        data = {
            "taskCode": task_code
        }

        headers = self.default_headers.copy()
        sys_code = 'MCS-MIMP-CORE'
        headers.update({
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'timestamp': timestamp,
            'signature': self.generate_signature(timestamp, sys_code),
            'sw8': self.get_sw8(url_path).get('code') if self.get_sw8(url_path) else '',
            'referer': 'https://mcs-mimp-web.sf-express.com/home?from=qqjrwzx515&WC_AC_ID=111&WC_REPORT=111'
        })

        try:
            response = self.session.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": "完成任务请求失败"
            }

    def fetch_tasks_reward(self, channel_type: str = "1", device_id: str = None) -> Dict[str, Any]:
        """
        获取任务奖励接口

        Args:
            channel_type: 渠道类型，默认为"1"
            device_id: 设备ID，如果不提供则使用初始化时的device_id

        Returns:
            Dict: API响应结果
        """
        url_path = "/mcs-mimp/commonNoLoginPost/~memberNonactivity~integralTaskStrategyService~fetchTasksReward"
        url = f"{self.base_url}{url_path}"

        timestamp = str(int(time.time() * 1000))

        data = {
            "channelType": channel_type,
            "deviceId": device_id or self.device_id
        }

        headers = self.default_headers.copy()
        sys_code = 'MCS-MIMP-CORE'
        headers.update({
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'timestamp': timestamp,
            'signature': self.generate_signature(timestamp, sys_code),
            'sw8': self.get_sw8(url_path).get('code') if self.get_sw8(url_path) else '',
            'referer': 'https://mcs-mimp-web.sf-express.com/superWelfare?citycode=&cityname=&tab=0',
        })

        try:
            response = self.session.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": "获取任务奖励请求失败"
            }

    def automatic_sign_fetch_package(self, come_from: str = "vioin", channel_from: str = "SFAPP") -> Dict[str, Any]:
        """
        自动签到获取礼包接口

        Args:
            come_from: 来源，默认为"vioin"
            channel_from: 渠道来源，默认为"SFAPP"

        Returns:
            Dict: API响应结果
        """
        url_path = "/mcs-mimp/commonPost/~memberNonactivity~integralTaskSignPlusService~automaticSignFetchPackage"
        url = f"{self.base_url}{url_path}"

        timestamp = str(int(time.time() * 1000))

        data = {
            "comeFrom": come_from,
            "channelFrom": channel_from
        }

        headers = self.default_headers.copy()
        sys_code = 'MCS-MIMP-CORE'
        headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'timestamp': timestamp,
            'signature': self.generate_signature(timestamp, sys_code),
            'sw8': self.get_sw8(url_path).get('code') if self.get_sw8(url_path) else '',
            'deviceid': self.device_id,
            'accept-language': 'zh-CN,zh-Hans;q=0.9',
            'priority': 'u=3, i',
            'referer': f'https://mcs-mimp-web.sf-express.com/superWelfare?mobile=176****2621&userId={self.user_id}&path=/superWelfare&supportShare=YES&from=appIndex&tab=1'
        })

        try:
            response = self.session.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": "自动签到获取礼包请求失败"
            }

