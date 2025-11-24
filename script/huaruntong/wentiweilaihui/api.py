"""
华润通文体未来荟API接口
"""
import requests
import uuid
import time


class WenTiWeiLaiHuiAPI:
    """文体未来荟API接口类"""

    def __init__(self, token, mobile, user_agent=None):
        """
        初始化API
        :param token: 认证token
        :param mobile: 手机号（用于显示）
        :param user_agent: 用户代理字符串
        """
        self.token = token
        self.mobile = mobile
        self.base_url = "https://wtmp.crland.com.cn"
        self.user_agent = user_agent or 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) UnifiedPCMacWechat(0xf26405f0) XWEB/13910'
        self.headers = {
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json',
            'xweb_xhr': '1',
            'x-hrt-mid-appid': 'API_AUTH_MINI',
            'token': self.token,
            'sec-fetch-site': 'cross-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://servicewechat.com/wx3c35b1f0737c23ce/11/page-frame.html',
            'accept-language': 'zh-CN,zh;q=0.9',
            'priority': 'u=1, i'
        }

    def sign_in(self):
        """
        签到接口
        :return: 接口响应数据
        """
        url = f"{self.base_url}/promotion/app/sign/signin"

        # 生成签到数据
        data = {
            "data": {
                "outOrderNo": str(uuid.uuid4()),
                "mobile": self.mobile,
                "timestamp": int(time.time() * 1000),
                "projectCode": "df2d2333f94f4c508073e0646610c021",
                "deviceChannel": "WECHAT",
                "businessChannel": "miniprogram",
                "channelCode": "wechat"
            }
        }

        try:
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "msg": f"请求失败: {str(e)}"}

    def query_points(self):
        """
        查询万象星积分
        :return: 接口响应数据
        """
        url = f"{self.base_url}/pointsAccount/app/queryAccount"

        try:
            response = requests.post(url, json={}, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "msg": f"请求失败: {str(e)}"}

