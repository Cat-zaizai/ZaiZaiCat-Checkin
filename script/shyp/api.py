#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上海云媒体 API Interface
上海云媒体积分任务查询接口

Author: Assistant
Date: 2025-11-06
"""

import requests
import json
import logging
from typing import Dict, Any, Optional


class ShypAPI:
    """上海云媒体API接口类"""

    def __init__(self, token: str, device_id: str, site_id: str = "310110", user_agent: str = None):
        """
        初始化上海云媒体 API

        Args:
            token: 用户token
            device_id: 设备ID
            site_id: 站点ID，默认为"310110"
            user_agent: 用户代理字符串
        """
        self.base_url = "https://app.ypmedia.cn"
        self.session = requests.Session()
        self.token = token
        self.device_id = device_id
        self.site_id = site_id
        self.logger = logging.getLogger(__name__)
        self.user_agent = user_agent or "okhttp/4.10.0"

        # 默认请求头
        self.default_headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json",
            "log-header": "I am the log request header.",
            "deviceid": self.device_id,
            "siteid": self.site_id,
            "token": self.token,
            "content-type": "application/json; charset=UTF-8"
        }

    def _make_request(self, method: str, endpoint: str, data: Dict = None,
                     headers: Dict = None) -> Optional[Dict[str, Any]]:
        """
        发送HTTP请求的通用方法

        Args:
            method: 请求方法 (GET, POST等)
            endpoint: API端点
            data: 请求数据
            headers: 额外的请求头

        Returns:
            Dict: API响应结果，失败返回None
        """
        url = f"{self.base_url}{endpoint}"
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)

        try:
            self.logger.debug(f"发送{method}请求: {url}")
            self.logger.debug(f"请求数据: {json.dumps(data, ensure_ascii=False)}")

            response = self.session.request(
                method=method,
                url=url,
                json=data,
                headers=request_headers,
                timeout=30
            )

            self.logger.debug(f"响应状态码: {response.status_code}")

            response.raise_for_status()
            result = response.json()

            self.logger.debug(f"响应结果: {json.dumps(result, ensure_ascii=False)[:200]}...")

            return result

        except requests.exceptions.Timeout:
            self.logger.error(f"请求超时: {url}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求失败: {url}, 错误: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"未知错误: {str(e)}")
            return None

    def get_score_info(self, order_by: str = "release_desc",
                       request_type: str = "2") -> Optional[Dict[str, Any]]:
        """
        获取积分信息和任务列表

        Args:
            order_by: 排序方式，默认为"release_desc"
            request_type: 请求类型，默认为"2"

        Returns:
            Dict: 包含积分信息、任务列表、签到信息等，失败返回None

        Response Example:
            {
                "code": 0,
                "msg": "success",
                "data": {
                    "signTitle": "已经连续签到 1 天",
                    "totalScore": 526,
                    "increaseScore": 526,
                    "reduceScore": 0,
                    "todayPoint": 526,
                    "todayIncreasePoint": 526,
                    "todayReducePoint": 0,
                    "jobs": [...],
                    "signs": [...],
                    "mallSetting": {...}
                }
            }
        """
        endpoint = "/media-basic-port/api/app/personal/score/info"

        data = {
            "orderBy": order_by,
            "requestType": request_type,
            "siteId": self.site_id
        }

        self.logger.info("正在获取积分信息和任务列表...")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            self.logger.info("成功获取积分信息")
            data = result.get("data", {})
            self.logger.info(f"总积分: {data.get('totalScore')}, 今日积分: {data.get('todayPoint')}")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.error(f"获取积分信息失败: {msg}")
            return None

    def parse_task_list(self, score_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析任务列表，提取关键信息

        Args:
            score_info: get_score_info返回的完整信息

        Returns:
            Dict: 包含解析后的任务信息
            {
                "total_score": 总积分,
                "today_point": 今日积分,
                "sign_status": 签到状态信息,
                "incomplete_tasks": 未完成的任务列表,
                "completed_tasks": 已完成的任务列表,
                "all_tasks": 所有任务列表
            }
        """
        if not score_info or score_info.get("code") != 0:
            self.logger.warning("无效的积分信息，无法解析任务列表")
            return {}

        data = score_info.get("data", {})
        jobs = data.get("jobs", [])
        signs = data.get("signs", [])

        # 分类任务
        incomplete_tasks = []
        completed_tasks = []

        for job in jobs:
            task_info = {
                "id": job.get("id"),
                "title": job.get("title"),
                "summary": job.get("summary"),
                "status": job.get("status"),
                "progress": job.get("progress"),
                "total_progress": job.get("totalProgress"),
                "all_progress": job.get("allProgress")
            }

            if job.get("status") == "1":  # 已完成
                completed_tasks.append(task_info)
            else:  # 未完成
                incomplete_tasks.append(task_info)

        # 解析签到状态
        sign_status = {
            "sign_title": data.get("signTitle"),
            "today_signed": any(s.get("status") == "signed" for s in signs),
            "signs": signs
        }

        result = {
            "total_score": data.get("totalScore"),
            "today_point": data.get("todayPoint"),
            "today_increase_point": data.get("todayIncreasePoint"),
            "sign_status": sign_status,
            "incomplete_tasks": incomplete_tasks,
            "completed_tasks": completed_tasks,
            "all_tasks": jobs
        }

        self.logger.info(f"任务统计 - 已完成: {len(completed_tasks)}, 未完成: {len(incomplete_tasks)}")

        return result

    def check_token_validity(self) -> bool:
        """
        检查token是否有效

        Returns:
            bool: token有效返回True，否则返回False
        """
        self.logger.info("正在检查token有效性...")
        result = self.get_score_info()

        if result and result.get("code") == 0:
            self.logger.info("Token有效")
            return True
        else:
            self.logger.error("Token无效或已过期")
            return False

    def get_article_list(self, channel_id: str = "a978f44b3e284e5e86777f9d4e3be7bb",
                        page_no: int = 1, page_size: int = 10,
                        order_by: str = "release_desc",
                        request_type: str = "1") -> Optional[Dict[str, Any]]:
        """
        获取文章列表

        Args:
            channel_id: 频道ID，默认为推荐频道
            page_no: 页码，默认为1
            page_size: 每页数量，默认为10
            order_by: 排序方式，默认为"release_desc"
            request_type: 请求类型，默认为"1"

        Returns:
            Dict: 文章列表数据，失败返回None
        """
        endpoint = "/media-basic-port/api/app/news/content/list"

        data = {
            "channel": {"id": channel_id},
            "pageNo": page_no,
            "pageSize": page_size,
            "orderBy": order_by,
            "requestType": request_type,
            "siteId": self.site_id
        }

        self.logger.info(f"正在获取文章列表 (页码: {page_no}, 每页: {page_size})...")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            data = result.get("data", {})
            total_count = data.get("totalCount", 0)
            records = data.get("records", [])
            self.logger.info(f"成功获取文章列表，共 {len(records)} 篇文章")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.error(f"获取文章列表失败: {msg}")
            return None

    def increase_read_count(self, article_id: str, count_type: str = "contentRead",
                           order_by: str = "release_desc",
                           request_type: str = "1") -> Optional[Dict[str, Any]]:
        """
        增加文章阅读计数

        Args:
            article_id: 文章ID
            count_type: 计数类型，默认为"contentRead"
            order_by: 排序方式，默认为"release_desc"
            request_type: 请求类型，默认为"1"

        Returns:
            Dict: API响应结果，失败返回None
        """
        endpoint = "/media-basic-port/api/app/common/count/usage/inc"

        data = {
            "countType": count_type,
            "id": article_id,
            "orderBy": order_by,
            "requestType": request_type,
            "siteId": self.site_id
        }

        self.logger.debug(f"正在增加文章阅读计数: {article_id}")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            self.logger.debug("成功增加阅读计数")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.warning(f"增加阅读计数失败: {msg}")
            return None

    def complete_read_task(self, order_by: str = "release_desc",
                          request_type: str = "1") -> Optional[Dict[str, Any]]:
        """
        完成阅读任务（提交阅读积分）

        Args:
            order_by: 排序方式，默认为"release_desc"
            request_type: 请求类型，默认为"1"

        Returns:
            Dict: API响应结果，失败返回None
        """
        endpoint = "/media-basic-port/api/app/points/read/add"

        data = {
            "orderBy": order_by,
            "requestType": request_type,
            "siteId": self.site_id
        }

        self.logger.debug("正在提交阅读任务...")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            self.logger.info("✅ 阅读任务完成")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.warning(f"完成阅读任务失败: {msg}")
            return None

    def get_video_list(self, channel_id: str = "d7036c2839e047b48fe64bc36987650c",
                      page_no: int = 1, page_size: int = 10,
                      order_by: str = "release_desc",
                      request_type: str = "1") -> Optional[Dict[str, Any]]:
        """
        获取视频列表

        Args:
            channel_id: 频道ID，默认为短视频频道
            page_no: 页码，默认为1
            page_size: 每页数量，默认为10
            order_by: 排序方式，默认为"release_desc"
            request_type: 请求类型，默认为"1"

        Returns:
            Dict: 视频列表数据，失败返回None
        """
        endpoint = "/media-basic-port/api/app/news/content/list"

        data = {
            "channel": {"id": channel_id},
            "pageNo": page_no,
            "pageSize": page_size,
            "orderBy": order_by,
            "requestType": request_type,
            "siteId": self.site_id
        }

        self.logger.info(f"正在获取视频列表 (页码: {page_no}, 每页: {page_size})...")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            data = result.get("data", {})
            records = data.get("records", [])
            self.logger.info(f"成功获取视频列表，共 {len(records)} 个视频")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.error(f"获取视频列表失败: {msg}")
            return None

    def get_video_detail(self, video_id: str, order_by: str = "release_desc",
                        request_type: str = "1") -> Optional[Dict[str, Any]]:
        """
        获取视频详情

        Args:
            video_id: 视频ID
            order_by: 排序方式，默认为"release_desc"
            request_type: 请求类型，默认为"1"

        Returns:
            Dict: 视频详情数据，失败返回None
        """
        endpoint = "/media-basic-port/api/app/multimedia/drama/get"

        data = {
            "id": video_id,
            "orderBy": order_by,
            "requestType": request_type,
            "siteId": self.site_id
        }

        self.logger.debug(f"正在获取视频详情: {video_id}")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            self.logger.debug("成功获取视频详情")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.warning(f"获取视频详情失败: {msg}")
            return None

    def complete_video_task(self, order_by: str = "release_desc",
                           request_type: str = "1") -> Optional[Dict[str, Any]]:
        """
        完成视频任务（提交视频积分）

        Args:
            order_by: 排序方式，默认为"release_desc"
            request_type: 请求类型，默认为"1"

        Returns:
            Dict: API响应结果，失败返回None
        """
        endpoint = "/media-basic-port/api/app/points/video/add"

        data = {
            "orderBy": order_by,
            "requestType": request_type,
            "siteId": self.site_id
        }

        self.logger.debug("正在提交视频任务...")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            self.logger.info("✅ 视频任务完成")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.warning(f"完成视频任务失败: {msg}")
            return None

    def favor_content(self, content_id: str) -> Optional[Dict[str, Any]]:
        """
        收藏内容

        Args:
            content_id: 内容ID

        Returns:
            Dict: API响应结果，失败返回None
        """
        endpoint = "/media-basic-port/api/app/news/content/favor"

        data = {
            "id": content_id
        }

        self.logger.debug(f"正在收藏内容: {content_id}")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            self.logger.info("✅ 收藏成功")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.warning(f"收藏失败: {msg}")
            return None

    def disfavor_content(self, content_id: str) -> Optional[Dict[str, Any]]:
        """
        取消收藏内容

        Args:
            content_id: 内容ID

        Returns:
            Dict: API响应结果，失败返回None
        """
        endpoint = "/media-basic-port/api/app/news/content/disfavor"

        data = {
            "id": content_id
        }

        self.logger.debug(f"正在取消收藏: {content_id}")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            self.logger.debug("取消收藏成功")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.warning(f"取消收藏失败: {msg}")
            return None

    def add_comment(self, target_id: str, content: str,
                   target_type: str = "content") -> Optional[Dict[str, Any]]:
        """
        添加评论

        Args:
            target_id: 目标ID（文章ID）
            content: 评论内容
            target_type: 目标类型，默认为"content"

        Returns:
            Dict: API响应结果，失败返回None
        """
        endpoint = "/media-basic-port/api/app/common/comment/add"

        data = {
            "displayResources": [],
            "content": content,
            "targetType": target_type,
            "targetId": target_id
        }

        self.logger.debug(f"正在评论内容: {target_id}, 评论: {content}")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            self.logger.info("✅ 评论成功")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.warning(f"评论失败: {msg}")
            return None

    def complete_share_task(self, order_by: str = "release_desc",
                           request_type: str = "1") -> Optional[Dict[str, Any]]:
        """
        完成分享任务（提交分享积分）

        Args:
            order_by: 排序方式，默认为"release_desc"
            request_type: 请求类型，默认为"1"

        Returns:
            Dict: API响应结果，失败返回None
        """
        endpoint = "/media-basic-port/api/app/points/share/add"

        data = {
            "orderBy": order_by,
            "requestType": request_type,
            "siteId": self.site_id
        }

        self.logger.debug("正在提交分享任务...")
        result = self._make_request("POST", endpoint, data=data)

        if result and result.get("code") == 0:
            self.logger.info("✅ 分享任务完成")
            return result
        else:
            msg = result.get("msg", "未知错误") if result else "请求失败"
            self.logger.warning(f"完成分享任务失败: {msg}")
            return None

