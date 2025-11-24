"""
答题接口封装
"""
import requests


class QuizAPI:
    """答题相关 API"""

    def __init__(self, token: str, mobile: str, user_agent: str = None):
        """
        初始化 API

        :param token: 认证 token
        :param mobile: 手机号
        :param user_agent: 用户代理字符串
        """
        self.base_url = "https://api4.jiankangyouyi.com/base-data/v1/api/gadgets"
        self.token = token
        self.mobile = mobile
        self.user_agent = user_agent or 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) UnifiedPCMacWechat(0xf26405f0) XWEB/13910'

    def _get_headers(self):
        """获取请求头"""
        return {
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'customdata': f'{{"mobile":"{self.mobile}","point":5,"entrance":"huarun-sj-mryt"}}',
            'token': self.token,
            'origin': 'https://apps.jiankangyouyi.com',
            'referer': 'https://apps.jiankangyouyi.com/',
            'accept-language': 'zh-CN,zh;q=0.9'
        }

    def get_question(self):
        """
        获取题目信息

        :return: 题目数据
        """
        url = f"{self.base_url}/business-knowledge-challenges?bizType=160107"
        payload = {
            "userId": self.mobile,
            "strategy": "1",
            "customerParams": ["huarun-sanjiu-prointsRewardScore"],
            "customers": ["050205"],
            "configId": ""
        }

        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "resultCode": "-1",
                "message": f"请求失败: {str(e)}"
            }

    def submit_answer(self, question_id: str, option_codes: list):
        """
        提交答案

        :param question_id: 题目 ID
        :param option_codes: 选项代码列表
        :return: 提交结果
        """
        url = f"{self.base_url}/knowledge-challenges/user-choice?bizType=160107"
        payload = {
            "userId": self.mobile,
            "questionId": question_id,
            "userOptionCodes": option_codes,
            "customerParams": ["huarun-sanjiu-prointsRewardScore"],
            "mobile": self.mobile,
            "configId": ""
        }

        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "resultCode": "-1",
                "message": f"提交失败: {str(e)}"
            }

