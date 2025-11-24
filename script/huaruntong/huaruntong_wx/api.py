"""
华润通签到API接口
"""
import json
import time
import hmac
import hashlib
import base64
import os
import requests
from urllib.parse import quote
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP


class HuaRunTongAPI:
    """华润通签到API接口类"""

    # 配置常量
    SECRET = "c274fc67-19f9-47ba-bb84-585a2e3a1f6a"
    PUB_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDuAiqDmvn9Rf15o21qkDxN0rUf
ZsX6rVBrtfgY6tamN2Yn+1D3eHZJuKNlucyqeBr6nmfN2srYAX+oyCXr5vWwFclj
PuWh8aSASqyk7MfbAv5Q4VqYS7lsYUQRdw4plZG0NASDeBvHWi3lsHjGfNb7iUvg
rk312EDfBHtRgDvB0QIDAQAB
-----END PUBLIC KEY-----"""
    APP_ID = "API_AUTH_WEB"
    HOST = "https://mid.huaruntong.cn"

    def __init__(self, token: str, answer_result: int = 1, channel_id: str = "APP",
                 merchant_code: str = "1641000001532", store_code: str = "qiandaosonjifen",
                 sys_id: str = "T0000001", transaction_uuid: str = "",
                 invite_code: str = "", user_agent: str = None):
        """
        初始化华润通API

        :param token: 认证token
        :param answer_result: 答题结果
        :param channel_id: 渠道ID
        :param merchant_code: 商户编码
        :param store_code: 门店编码
        :param sys_id: 系统ID
        :param transaction_uuid: 交易UUID
        :param invite_code: 邀请码
        :param user_agent: 用户代理字符串
        """
        self.token = token
        self.answer_result = answer_result
        self.channel_id = channel_id
        self.merchant_code = merchant_code
        self.store_code = store_code
        self.sys_id = sys_id
        self.transaction_uuid = transaction_uuid
        self.invite_code = invite_code
        self.user_agent = user_agent or "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"

    def _generate_aes_key(self):
        """生成16字节随机AES密钥"""
        return os.urandom(16)

    def _pad_pkcs7(self, data: bytes, block_size: int = 16) -> bytes:
        """PKCS7填充"""
        padding_len = block_size - (len(data) % block_size)
        return data + bytes([padding_len] * padding_len)

    def _crypto_data(self, params: dict, api_path: str) -> dict:
        """加密请求数据"""
        # 添加必要字段
        params["apiPath"] = quote(api_path, safe='')
        params["appId"] = self.APP_ID
        params["timestamp"] = int(time.time() * 1000)

        # 生成签名 (HMAC-MD5)
        parts = []
        for key, value in params.items():
            if value is not None:
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, separators=(',', ':'))
                parts.append(f"{key}={value}")

        sign_str = "&".join(sorted(parts))
        signature = hmac.new(
            self.SECRET.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.md5
        ).hexdigest()
        params["signature"] = signature

        # AES-CBC 加密 (IV为空)
        aes_key = self._generate_aes_key()
        iv = b'\x00' * 16
        cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv)

        plaintext = json.dumps(params, separators=(',', ':')).encode('utf-8')
        padded = self._pad_pkcs7(plaintext)
        encrypted_data = cipher_aes.encrypt(padded)
        data_b64 = base64.b64encode(encrypted_data).decode('utf-8')

        # RSA-OAEP 加密 AES 密钥
        rsa_key = RSA.import_key(self.PUB_KEY)
        cipher_rsa = PKCS1_OAEP.new(rsa_key)
        encrypted_key = cipher_rsa.encrypt(aes_key)
        key_b64 = base64.b64encode(encrypted_key).decode('utf-8')

        return {"key": key_b64, "data": data_b64}

    def _get_headers(self):
        """获取请求头"""
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "X-HRT-MID-NEWRISK": "newRisk",
            "X-Hrt-Mid-Appid": self.APP_ID,
            "Origin": "https://cloud.huaruntong.cn",
            "Referer": "https://cloud.huaruntong.cn/",
        }

    def _send_request(self, api_path: str, payload: dict) -> dict:
        """发送加密请求"""
        url = f"{self.HOST}{api_path}"
        encrypted = self._crypto_data(payload.copy(), api_path)

        try:
            resp = requests.post(url, json=encrypted, headers=self._get_headers())
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e)
            }

    def sign_in(self) -> dict:
        """
        签到接口

        :return: 响应数据
        """
        payload = {
            "answerResult": self.answer_result,
            "channelId": self.channel_id,
            "merchantCode": self.merchant_code,
            "storeCode": self.store_code,
            "sysId": self.sys_id,
            "transactionUuid": self.transaction_uuid,
            "inviteCode": self.invite_code,
            "token": self.token
        }

        api_path = "/api/points/saveQuestionSignin"
        return self._send_request(api_path, payload)

