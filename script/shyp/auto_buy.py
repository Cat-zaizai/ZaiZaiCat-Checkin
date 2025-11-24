"""
定时抢购脚本
用于在指定时间自动抢购商品
"""

import time
import requests
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutoBuy:
    """自动抢购类"""

    def __init__(self):
        """初始化抢购配置"""
        # API 配置
        self.api_url = "https://mall-api.shmedia.tech/trade-service/trade/carts/buy"

        # 请求参数
        self.params = {
            "sku_id": "1539881186344108034",
            "num": "1",
            "activity_id": "1706607500810358785",
            "promotion_type": "EXCHANGE"
        }

        # 请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; MI 8 SE Build/QKQ1.190828.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/87.0.4280.101 Mobile Safari/537.36Rmt/YangPu; Version/3.0.2",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
            "Content-Length": "0",
            "Authorization": "eyJhbGciOiJIUzUxMiJ9.eyJ1aWQiOjE5ODYzMTQ5MjY1MTEwOTk5MDUsInN1YiI6InVzZXIiLCJzaXRlIjoiMzEwMTEwIiwiYXJlYVByZWZpeCI6InlwIiwicm9sZXMiOlsiQlVZRVIiXSwibW9iaWxlIjoiMTc2MzM4ODI2MjEiLCJzaG9wSWQiOiIzMTAxMTAwMSIsImxpdmVNZXNzYWdlIjpudWxsLCJleHAiOjE3NjUwNzE2NjIsInV1aWQiOiJmYzI5MDAwOC00M2Q5LTRkYWYtYTMwMC1iMzM4Mjk0ZWRiYTQiLCJ1c2VybmFtZSI6Im1lZGlhX2JhNTgzOGZkIiwidGFyZ2V0IjoibWVkaWEifQ.t_xeRDJeCCj3uqaJjdyzZrbYS4FjP85-YMAFbjp_O6KPaYqCYrkzoWxkZ78YsJ4acYZXvAyl8eiOMQNIHxLs4A",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": "https://mall-mobile.shmedia.tech",
            "X-Requested-With": "com.wdit.shrmtyp",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://mall-mobile.shmedia.tech/real.html?shop_id=31011001&site_id=310110&target=media&access_id=182&version=2025091601",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cookie": "acw_tc=ac11000117624798203052297e48cbaf45af00a4165176e6e59bf1b5159fcc"
        }

    def update_config(self, sku_id=None, num=None, activity_id=None,
                     promotion_type=None, authorization=None):
        """
        更新抢购配置

        Args:
            sku_id: 商品SKU ID
            num: 购买数量
            activity_id: 活动ID
            promotion_type: 促销类型
            authorization: 授权token
        """
        if sku_id:
            self.params["sku_id"] = sku_id
        if num:
            self.params["num"] = str(num)
        if activity_id:
            self.params["activity_id"] = activity_id
        if promotion_type:
            self.params["promotion_type"] = promotion_type
        if authorization:
            self.headers["Authorization"] = authorization

        logger.info("配置已更新")

    def buy(self):
        """
        执行抢购请求

        Returns:
            tuple: (是否成功, 响应数据)
        """
        try:
            logger.info(f"开始抢购: {self.api_url}")
            logger.info(f"参数: {self.params}")

            response = requests.post(
                self.api_url,
                params=self.params,
                headers=self.headers,
                timeout=10
            )

            logger.info(f"响应状态码: {response.status_code}")
            logger.info(f"响应内容长度: {len(response.text)} 字节")
            logger.info(f"响应内容: {response.text if response.text else '[空响应]'}")
            logger.info(f"响应头 Content-Type: {response.headers.get('Content-Type', 'unknown')}")

            # 处理响应
            if response.status_code == 200:
                # 检查响应内容是否为空
                if not response.text or response.text.strip() == '':
                    logger.warning("响应内容为空，可能表示抢购成功")
                    return True, {"code": "200", "message": "响应为空，可能成功", "raw_response": ""}

                # 尝试解析JSON
                try:
                    result = response.json()
                    logger.info(f"解析后的JSON: {result}")
                    return True, result
                except ValueError as json_error:
                    logger.error(f"JSON解析失败: {str(json_error)}")
                    logger.error(f"原始响应内容(repr): {repr(response.text)}")
                    return False, {
                        "error": "JSON解析失败",
                        "json_error": str(json_error),
                        "raw_response": response.text
                    }
            else:
                # 非200状态码，尝试解析错误信息
                error_msg = f"请求失败，状态码: {response.status_code}"
                try:
                    error_data = response.json()
                    logger.error(f"错误详情: {error_data}")
                    return False, {"error": error_msg, "details": error_data}
                except:
                    return False, {"error": error_msg, "raw_response": response.text}

        except requests.exceptions.Timeout:
            logger.error("请求超时")
            return False, {"error": "请求超时"}
        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {str(e)}")
            return False, {"error": str(e)}
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return False, {"error": str(e)}

    def wait_until(self, target_time_str):
        """
        等待到指定时间

        Args:
            target_time_str: 目标时间字符串，格式: "YYYY-MM-DD HH:MM:SS" 或 "HH:MM:SS"
        """
        try:
            # 尝试解析完整日期时间
            if len(target_time_str.split()) == 2:
                target_time = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
            else:
                # 只有时间，使用今天的日期
                today = datetime.now().strftime("%Y-%m-%d")
                target_time = datetime.strptime(f"{today} {target_time_str}", "%Y-%m-%d %H:%M:%S")

                # 如果目标时间已经过去，则设置为明天
                if target_time < datetime.now():
                    logger.warning("目标时间已过，将在明天的相同时间执行")
                    from datetime import timedelta
                    target_time = target_time + timedelta(days=1)

            logger.info(f"目标抢购时间: {target_time}")

            while True:
                now = datetime.now()
                diff = (target_time - now).total_seconds()

                if diff <= 0:
                    logger.info("到达抢购时间！")
                    break

                if diff > 60:
                    logger.info(f"距离抢购还有 {int(diff)} 秒 ({int(diff/60)} 分钟)")
                    time.sleep(30)  # 超过1分钟时，每30秒检查一次
                elif diff > 10:
                    logger.info(f"距离抢购还有 {int(diff)} 秒")
                    time.sleep(1)  # 10秒到1分钟之间，每秒检查一次
                elif diff > 1:
                    logger.info(f"距离抢购还有 {diff:.3f} 秒")
                    time.sleep(0.1)  # 最后10秒，每0.1秒检查一次
                else:
                    # 最后1秒，精确等待
                    time.sleep(diff)
                    break

        except ValueError as e:
            logger.error(f"时间格式错误: {str(e)}")
            logger.error("请使用格式: 'YYYY-MM-DD HH:MM:SS' 或 'HH:MM:SS'")
            raise

    def timed_buy(self, target_time_str, retry_times=3, retry_interval=0.1):
        """
        定时抢购

        Args:
            target_time_str: 目标时间字符串
            retry_times: 失败后重试次数
            retry_interval: 重试间隔（秒）
        """
        logger.info("=" * 50)
        logger.info("定时抢购脚本启动")
        logger.info("=" * 50)

        # 等待到指定时间
        self.wait_until(target_time_str)

        # 开始抢购
        for i in range(retry_times):
            logger.info(f"第 {i + 1} 次尝试抢购")
            success, result = self.buy()

            if success:
                logger.info("=" * 50)
                logger.info("抢购成功！")
                logger.info(f"结果: {result}")
                logger.info("=" * 50)
                return True, result
            else:
                logger.warning(f"第 {i + 1} 次抢购失败: {result}")
                if i < retry_times - 1:
                    logger.info(f"等待 {retry_interval} 秒后重试...")
                    time.sleep(retry_interval)

        logger.error("=" * 50)
        logger.error("抢购失败，已达到最大重试次数")
        logger.error("=" * 50)
        return False, None


def main():
    """主函数 - 示例用法"""
    # 创建抢购实例
    buyer = AutoBuy()

    # ====== 配置示例 ======
    # 如需修改配置，可以调用 update_config 方法
    # buyer.update_config(
    #     sku_id="1539881186344108034",
    #     num=1,
    #     activity_id="1706607500810358785",
    #     promotion_type="EXCHANGE",
    #     authorization="your_new_token_here"
    # )

    # ====== 使用方式 1: 设置具体日期时间 ======
    # target_time = "2025-11-08 10:00:00"  # 指定完整的日期和时间

    # ====== 使用方式 2: 只设置时间（使用今天日期） ======
    target_time = "10:00:00"  # 只指定时间，将使用今天的日期

    # ====== 使用方式 3: 立即执行（测试用） ======
    # now = datetime.now()
    # target_time = (now + timedelta(seconds=5)).strftime("%H:%M:%S")  # 5秒后执行

    # 执行定时抢购
    # 参数说明：
    # - target_time: 抢购时间
    # - retry_times: 失败后重试次数（默认3次）
    # - retry_interval: 重试间隔秒数（默认0.1秒）
    buyer.timed_buy(
        target_time_str=target_time,
        retry_times=10,  # 重试5次
        retry_interval=0.3  # 每次间隔0.05秒
    )


if __name__ == "__main__":
    main()

