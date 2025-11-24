#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
青龙面板通知推送模块

支持的推送方式：
- Bark 推送

配置参数说明（需要在青龙面板的 config.sh 中设置）：
- BARK_PUSH: Bark推送的设备key或完整URL（必需）
- BARK_ICON: 推送图标URL（可选）
- BARK_SOUND: 推送声音（可选，默认为 'birdsong'）
- BARK_GROUP: 推送分组（可选）
- BARK_LEVEL: 推送级别（可选，active/timeSensitive/passive）
- BARK_URL: 自定义跳转URL（可选）

使用示例：
    from notification import send_notification, NotificationLevel, NotificationSound

    # 基础推送
    send_notification("测试标题", "测试内容")

    # 自定义级别和声音
    send_notification(
        "重要通知",
        "这是一条重要消息",
        level=NotificationLevel.TIME_SENSITIVE,
        sound=NotificationSound.ALARM
    )

Author: Assistant
Date: 2025-11-17
"""

import os
import json
import requests
import logging
from typing import Optional, Dict
from urllib.parse import quote


# 推送级别常量
class NotificationLevel:
    """推送级别常量"""
    ACTIVE = "active"           # 默认级别，立即亮屏显示通知
    TIME_SENSITIVE = "timeSensitive"  # 时效性通知，即使在专注模式下也会显示
    PASSIVE = "passive"         # 被动通知，不会立即显示，需要用户主动查看


# 推送声音常量
class NotificationSound:
    """推送声音常量"""
    ALARM = "alarm"
    ANTICIPATE = "anticipate"
    BELL = "bell"
    BIRDSONG = "birdsong"      # 默认
    BLOOM = "bloom"
    CALYPSO = "calypso"
    CHIME = "chime"
    CHOO = "choo"
    DESCENT = "descent"
    ELECTRONIC = "electronic"
    FANFARE = "fanfare"
    GLASS = "glass"
    GOTOSLEEP = "gotosleep"
    HEALTHNOTIFICATION = "healthnotification"
    HORN = "horn"
    LADDER = "ladder"
    MAILSENT = "mailsent"
    MINUET = "minuet"
    MULTIWAYINVITATION = "multiwayinvitation"
    NEWMAIL = "newmail"
    NEWSFLASH = "newsflash"
    NOIR = "noir"
    PAYMENTSUCCESS = "paymentsuccess"
    SHAKE = "shake"
    SHERWOODFOREST = "sherwoodforest"
    SILENCE = "silence"
    SPELL = "spell"
    SUSPENSE = "suspense"
    TELEGRAPH = "telegraph"
    TIPTOES = "tiptoes"
    TYPEWRITERS = "typewriters"
    UPDATE = "update"


class NotificationManager:
    """青龙面板通知推送管理器"""

    def __init__(self):
        """初始化推送管理器"""
        self.logger = logging.getLogger("NotificationManager")
        self.bark_config = self._load_bark_config()

    def _load_bark_config(self) -> Dict[str, str]:
        """
        从环境变量加载Bark配置

        Returns:
            Dict[str, str]: Bark配置信息
        """
        config = {}

        # 必须参数
        config['push'] = os.environ.get('BARK_PUSH', '').strip()

        # 可选参数
        config['icon'] = os.environ.get('BARK_ICON', '').strip()
        config['sound'] = os.environ.get('BARK_SOUND', 'birdsong').strip()
        config['group'] = os.environ.get('BARK_GROUP', '').strip()
        config['level'] = os.environ.get('BARK_LEVEL', '').strip()
        config['url'] = os.environ.get('BARK_URL', '').strip()

        return config

    def is_bark_enabled(self) -> bool:
        """
        检查Bark推送是否已启用

        Returns:
            bool: 如果配置了BARK_PUSH则返回True
        """
        return bool(self.bark_config.get('push'))

    def _build_bark_url(self, title: str, content: str, level: Optional[str] = None,
                       sound: Optional[str] = None, group: Optional[str] = None,
                       url: Optional[str] = None) -> Optional[str]:
        """
        构建Bark推送URL

        Args:
            title (str): 推送标题
            content (str): 推送内容
            level (Optional[str]): 推送级别，覆盖默认配置
            sound (Optional[str]): 推送声音，覆盖默认配置
            group (Optional[str]): 推送分组，覆盖默认配置
            url (Optional[str]): 跳转链接，覆盖默认配置

        Returns:
            Optional[str]: 构建的URL，失败时返回None
        """
        bark_push = self.bark_config.get('push')
        if not bark_push:
            return None

        # 处理URL编码
        title_encoded = quote(title, safe='')
        content_encoded = quote(content, safe='')

        # 判断BARK_PUSH是完整URL还是只是key
        if bark_push.startswith('http'):
            # 完整URL格式
            base_url = bark_push.rstrip('/')
            url = f"{base_url}/{title_encoded}/{content_encoded}"
        else:
            # 只有key，使用官方服务器
            url = f"https://api.day.app/{bark_push}/{title_encoded}/{content_encoded}"

        # 添加可选参数（传入参数优先于默认配置）
        params = []

        if self.bark_config.get('icon'):
            params.append(f"icon={quote(self.bark_config['icon'], safe='')}")

        # 使用传入参数或默认配置
        final_sound = sound or self.bark_config.get('sound')
        if final_sound:
            params.append(f"sound={final_sound}")

        final_group = group or self.bark_config.get('group')
        if final_group:
            params.append(f"group={quote(final_group, safe='')}")

        final_level = level or self.bark_config.get('level')
        if final_level:
            params.append(f"level={final_level}")

        final_url = url or self.bark_config.get('url')
        if final_url:
            params.append(f"url={quote(final_url, safe='')}")

        if params:
            url += "?" + "&".join(params)

        return url

    def send_bark_notification(self, title: str, content: str, timeout: int = 10,
                             level: Optional[str] = None, sound: Optional[str] = None,
                             group: Optional[str] = None, url: Optional[str] = None) -> bool:
        """
        发送Bark推送通知（使用POST方法，避免URL过长）

        Args:
            title (str): 推送标题
            content (str): 推送内容
            timeout (int): 请求超时时间（秒）
            level (Optional[str]): 推送级别，覆盖默认配置 (active/timeSensitive/passive)
            sound (Optional[str]): 推送声音，覆盖默认配置
            group (Optional[str]): 推送分组，覆盖默认配置
            url (Optional[str]): 跳转链接，覆盖默认配置

        Returns:
            bool: 推送成功返回True，失败返回False
        """
        if not self.is_bark_enabled():
            self.logger.warning("Bark推送未启用，请检查BARK_PUSH环境变量")
            return False

        try:
            bark_push = self.bark_config.get('push')
            if not bark_push:
                self.logger.error("Bark推送配置为空")
                return False

            # 判断BARK_PUSH是完整URL还是只是key
            if bark_push.startswith('http'):
                # 完整URL格式，需要提取key
                base_url = bark_push.rstrip('/')
                # 从URL中提取key (最后一个路径段)
                parts = base_url.split('/')
                device_key = parts[-1] if parts else ''
                # 重新构建基础URL（去掉key部分）
                api_url = '/'.join(parts[:-1]) if len(parts) > 1 else base_url
            else:
                # 只有key，使用官方服务器
                device_key = bark_push
                api_url = "https://api.day.app"

            # 构建POST请求的数据
            post_data = {
                "title": title,
                "body": content,
                "device_key": device_key
            }

            # 添加可选参数（传入参数优先于默认配置）
            if self.bark_config.get('icon'):
                post_data['icon'] = self.bark_config['icon']

            final_sound = sound or self.bark_config.get('sound')
            if final_sound:
                post_data['sound'] = final_sound

            final_group = group or self.bark_config.get('group')
            if final_group:
                post_data['group'] = final_group

            final_level = level or self.bark_config.get('level')
            if final_level:
                post_data['level'] = final_level

            final_url = url or self.bark_config.get('url')
            if final_url:
                post_data['url'] = final_url

            self.logger.info(f"正在发送Bark推送: {title}")
            self.logger.debug(f"Bark推送API: {api_url}/push")

            # 发送POST请求
            response = requests.post(
                f"{api_url}/push",
                json=post_data,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                timeout=timeout
            )
            response.raise_for_status()

            # 解析响应
            try:
                result = response.json()
                if result.get('code') == 200:
                    self.logger.info("✅ Bark推送发送成功")
                    return True
                else:
                    error_msg = result.get('message', '未知错误')
                    self.logger.error(f"❌ Bark推送失败: {error_msg}")
                    return False
            except json.JSONDecodeError:
                # 某些Bark服务器可能不返回JSON
                if response.status_code == 200:
                    self.logger.info("✅ Bark推送发送成功")
                    return True
                else:
                    self.logger.error(f"❌ Bark推送失败: HTTP {response.status_code}")
                    return False

        except requests.exceptions.Timeout:
            self.logger.error(f"❌ Bark推送超时（{timeout}秒）")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Bark推送网络错误: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Bark推送未知错误: {str(e)}")
            return False

    def send_notification(self, title: str, content: str, method: str = 'bark',
                         level: Optional[str] = None, sound: Optional[str] = None,
                         group: Optional[str] = None, url: Optional[str] = None) -> bool:
        """
        发送通知（通用接口）

        Args:
            title (str): 推送标题
            content (str): 推送内容
            method (str): 推送方式，目前支持 'bark'
            level (Optional[str]): 推送级别 (active/timeSensitive/passive)
            sound (Optional[str]): 推送声音
            group (Optional[str]): 推送分组
            url (Optional[str]): 跳转链接

        Returns:
            bool: 推送成功返回True，失败返回False
        """
        if method.lower() == 'bark':
            return self.send_bark_notification(title, content, level=level,
                                             sound=sound, group=group, url=url)
        else:
            self.logger.warning(f"不支持的推送方式: {method}")
            return False


# 创建全局通知管理器实例
notification_manager = NotificationManager()


def send_notification(title: str, content: str, level: Optional[str] = None,
                     sound: Optional[str] = None, group: Optional[str] = None,
                     url: Optional[str] = None) -> bool:
    """
    便捷函数：发送通知

    Args:
        title (str): 推送标题
        content (str): 推送内容
        level (Optional[str]): 推送级别 (active/timeSensitive/passive)
        sound (Optional[str]): 推送声音
        group (Optional[str]): 推送分组
        url (Optional[str]): 跳转链接

    Returns:
        bool: 推送成功返回True，失败返回False
    """
    return notification_manager.send_notification(title, content, level=level,
                                                sound=sound, group=group, url=url)


if __name__ == "__main__":
    """测试推送功能"""
    import sys

    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 检查配置
    if not notification_manager.is_bark_enabled():
        print("❌ Bark推送未配置，请设置环境变量 BARK_PUSH")
        print("示例: export BARK_PUSH='your_device_key'")
        sys.exit(1)

    print("🧪 开始测试Bark推送...\n")

    # 测试1: 基础推送（使用默认配置）
    print("测试1: 基础推送")
    result1 = send_notification("📱 青龙面板测试", "这是一条测试推送消息")
    print(f"结果: {'✅ 成功' if result1 else '❌ 失败'}\n")

    # 测试2: 自定义级别和声音
    print("测试2: 自定义推送（时效性通知 + 警报声）")
    result2 = send_notification(
        "🔔 重要通知",
        "这是一条时效性通知，即使在专注模式下也会显示",
        level=NotificationLevel.TIME_SENSITIVE,
        sound=NotificationSound.ALARM
    )
    print(f"结果: {'✅ 成功' if result2 else '❌ 失败'}\n")

    # 测试3: 自定义任务摘要（自行构建内容）
    print("测试3: 自定义任务摘要")
    task_title = "✅ 上海云媒体任务 - 部分成功"
    task_content = """📊 执行统计:
✅ 成功: 3 个账号
❌ 失败: 1 个账号
📈 总计: 4 个账号

📝 详情: 部分账号token已过期"""
    result3 = send_notification(
        task_title,
        task_content,
        level=NotificationLevel.ACTIVE,
        sound=NotificationSound.BELL
    )
    print(f"结果: {'✅ 成功' if result3 else '❌ 失败'}\n")

    # 测试4: 自定义错误通知
    print("测试4: 自定义错误通知")
    error_title = "❌ 什么值得买任务 - 执行错误"
    error_content = """💥 发生错误:
👤 账号: 测试账号1
❌ 错误: 网络连接超时"""
    result4 = send_notification(
        error_title,
        error_content,
        level=NotificationLevel.TIME_SENSITIVE,
        sound=NotificationSound.ALARM
    )
    print(f"结果: {'✅ 成功' if result4 else '❌ 失败'}\n")

    print("🎉 测试完成")







