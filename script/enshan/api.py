#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
恩山论坛API模块

提供恩山论坛签到相关的API接口
"""

import requests
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class EnshanAPI:
    """恩山论坛API类"""

    def __init__(self, cookies: str, formhash: str, user_agent: Optional[str] = None):
        """
        初始化API类

        Args:
            cookies: 用户的Cookie字符串
            formhash: 表单hash值，用于验证请求
            user_agent: 用户代理字符串，可选
        """
        self.cookies = cookies
        self.formhash = formhash
        self.user_agent = user_agent or (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/141.0.0.0 Safari/537.36'
        )
        self.sign_url = 'https://www.right.com.cn/forum/plugin.php?id=erling_qd:action&action=sign'
        self.base_url = 'https://www.right.com.cn/forum'

    def get_headers(self) -> Dict[str, str]:
        """
        获取请求头

        Returns:
            Dict[str, str]: 请求头字典
        """
        return {
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'sec-ch-ua-platform': '"macOS"',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'Sec-GPC': '1',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Origin': 'https://www.right.com.cn',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://www.right.com.cn/forum/erling_qd-sign_in.html',
            'Cookie': self.cookies
        }

    def sign_in(self) -> Dict:
        """
        执行签到

        Returns:
            Dict: 签到结果
                {
                    'success': bool,  # 是否成功
                    'result': dict,   # 成功时的结果数据
                    'error': str      # 失败时的错误信息
                }
        """
        logger.info("开始执行恩山论坛签到...")
        headers = self.get_headers()
        data = {
            'formhash': self.formhash
        }

        try:
            response = requests.post(
                self.sign_url,
                headers=headers,
                data=data,
                timeout=30
            )

            # 检查响应状态
            response.raise_for_status()

            # 尝试解析JSON响应
            try:
                result = response.json()
            except json.JSONDecodeError:
                result = {
                    'status': 'success',
                    'message': response.text
                }

            logger.info(f"恩山论坛签到成功: {result}")
            return {
                'success': True,
                'result': result
            }

        except requests.RequestException as e:
            error_msg = f"签到失败: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }

    def get_user_info(self) -> Dict:
        """
        获取用户信息（可选功能）

        Returns:
            Dict: 用户信息
        """
        # 这里可以添加获取用户信息的逻辑
        # 目前返回空字典
        return {}

