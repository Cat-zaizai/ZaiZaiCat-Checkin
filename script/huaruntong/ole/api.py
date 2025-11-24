"""
Ole 签到接口
"""
import requests


class OleAPI:
    """Ole 签到相关 API"""

    def __init__(self, session_id: str, device_name: str, unique: str,
                 ole_wx_open_id: str, shop_code: str = "205368",
                 city_id: str = "c_region_11122", user_agent: str = None):
        """
        初始化 API

        :param session_id: 会话 ID
        :param device_name: 设备名称（手机号）
        :param unique: 唯一标识
        :param ole_wx_open_id: 微信 openid
        :param shop_code: 门店编码
        :param city_id: 城市 ID
        :param user_agent: 用户代理字符串
        """
        self.base_url = "https://ole-app.crvole.com.cn/vgdt_app_api/v1"
        self.session_id = session_id
        self.device_name = device_name
        self.unique = unique
        self.ole_wx_open_id = ole_wx_open_id
        self.shop_code = shop_code
        self.city_id = city_id
        self.user_agent = user_agent or 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) UnifiedPCMacWechat(0xf26405f0) XWEB/13910'

    def _get_headers(self):
        """获取请求头"""
        return {
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json',
            'Tenant-Channel': 'OLE',
            'cityId': self.city_id,
            'oleWxOpenId': self.ole_wx_open_id,
            'Tenant': 'VGDT',
            'sessionId': self.session_id,
            'Device-Name': self.device_name,
            'unique': self.unique,
            'channel': 'wxmini',
            'shopCode': self.shop_code,
            'os': 'ios',
            'appVersion': '1.10.17',
            'Referer': 'https://servicewechat.com/wx6c61aaeba1551439/93/page-frame.html',
            'Accept-Language': 'zh-CN,zh;q=0.9'
        }

    def sign_in(self, enter_shop_code: str = None):
        """
        签到接口

        :param enter_shop_code: 进入的门店编码，默认使用初始化时的 shop_code
        :return: 响应数据
        """
        if enter_shop_code is None:
            enter_shop_code = self.shop_code

        url = f"{self.base_url}/vgdt-fea-app-member/front_api/member_sign"
        payload = {
            "enter_shop_code": enter_shop_code
        }

        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e)
            }

    def query_points(self):
        """
        查询积分（如果有相关接口可以添加）
        注：当前 curl 中未提供查询接口，这里预留接口

        :return: 响应数据
        """
        # 这里可以根据实际需求添加查询接口
        pass

