#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鸿星尔克API模块

提供鸿星尔克小程序相关的API接口
"""

import requests
import logging
import hashlib
import random
from typing import Dict, Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def get_gmt8_time() -> str:
    """
    获取GMT+8时间并格式化为字符串

    Returns:
        str: 格式化的时间字符串，如 "2025-11-28 11:36:14"
    """
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    return now.strftime('%Y-%m-%d %H:%M:%S')


def calculate_sign(appid: str, member_id: str, timestamp: str = None) -> dict:
    """
    计算请求签名

    根据JS代码逻辑:
    timestamp=时间戳
    transId=appid+时间戳
    secret=damogic8888
    random=随机数
    memberId=会员ID

    Args:
        appid: 小程序appid
        member_id: 会员ID
        timestamp: 时间戳，不传则自动生成

    Returns:
        dict: 包含sign和相关参数的字典
    """
    if timestamp is None:
        timestamp = get_gmt8_time()

    random_num = random.randint(0, 9999999)
    trans_id = appid + timestamp

    sign_str = f"timestamp={timestamp}"
    sign_str += f"transId={trans_id}"
    sign_str += "secret=damogic8888"
    sign_str += f"random={random_num}"
    sign_str += f"memberId={member_id}"

    sign = hashlib.md5(sign_str.encode()).hexdigest()

    return {
        'sign': sign,
        'timestamp': timestamp,
        'transId': trans_id,
        'random': random_num,
        'appid': appid,
        'memberId': member_id
    }


class ErkeAPI:
    """鸿星尔克API类"""

    def __init__(
        self,
        member_id: str,
        enterprise_id: str,
        unionid: str,
        openid: str,
        wx_openid: str,
        appid: str = "wxa1f1fa3785a47c7d",
        user_agent: Optional[str] = None
    ):
        """
        初始化API类

        Args:
            member_id: 会员ID
            enterprise_id: 企业ID
            unionid: 微信unionid
            openid: 小程序openid
            wx_openid: 微信wxOpenid
            appid: 小程序appid，默认为wxa1f1fa3785a47c7d
            user_agent: 用户代理字符串，可选
        """
        self.member_id = member_id
        self.enterprise_id = enterprise_id
        self.unionid = unionid
        self.openid = openid
        self.wx_openid = wx_openid
        self.appid = appid
        self.user_agent = user_agent or (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 '
            'MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI '
            'MiniProgramEnv/Windows WindowsWechat/WMPF '
            'WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541510) XWEB/17071'
        )
        self.base_url = 'https://hope.demogic.com/gic-wx-app'

    def get_headers(self, sign: str) -> Dict[str, str]:
        """
        获取请求头

        Args:
            sign: 签名参数

        Returns:
            Dict[str, str]: 请求头字典
        """
        return {
            'User-Agent': self.user_agent,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
            'sign': sign,
            'channelEntrance': 'wx_app',
            'xweb_xhr': '1',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://servicewechat.com/wxa1f1fa3785a47c7d/85/page-frame.html',
            'Accept-Language': 'zh-CN,zh;q=0.9'
        }

    def get_integral_record(
        self,
        current_page: int = 1,
        page_size: int = 20
    ) -> Dict:
        """
        获取积分明细

        Args:
            current_page: 当前页码，默认为1
            page_size: 每页大小，默认为20

        Returns:
            Dict: 接口返回结果
                {
                    'success': bool,  # 是否成功
                    'result': dict,   # 成功时的结果数据
                    'error': str      # 失败时的错误信息
                }
        """
        logger.info("开始获取积分明细...")

        # 计算签名
        sign_data = calculate_sign(self.appid, self.member_id)

        # 构建请求数据
        data = {
            'currentPage': current_page,
            'pageSize': page_size,
            'memberId': self.member_id,
            'cliqueId': '-1',
            'cliqueMemberId': '-1',
            'useClique': '0',
            'enterpriseId': self.enterprise_id,
            'unionid': self.unionid,
            'openid': self.openid,
            'wxOpenid': self.wx_openid,
            'random': sign_data['random'],
            'appid': sign_data['appid'],
            'transId': sign_data['transId'],
            'sign': sign_data['sign'],
            'timestamp': sign_data['timestamp'],
            'gicWxaVersion': '3.9.56',
            'launchOptions': '{"path":"pages/authorize/authorize","query":{},"scene":1101,"referrerInfo":{},"apiCategory":"default"}'
        }

        # 获取请求头（这里的sign用于header）
        headers = self.get_headers(self.enterprise_id)

        try:
            url = f"{self.base_url}/integral_record.json"
            response = requests.post(
                url,
                headers=headers,
                data=data,
                timeout=30
            )

            # 检查响应状态
            response.raise_for_status()

            # 解析响应
            result = response.json()

            logger.info(f"积分明细获取成功")
            return {
                'success': True,
                'result': result,
                'error': None
            }

        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'result': None,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'result': None,
                'error': error_msg
            }

    def member_sign(self) -> Dict:
        """
        会员签到

        Returns:
            Dict: 接口返回结果
                {
                    'success': bool,  # 是否成功
                    'result': dict,   # 成功时的结果数据
                    'error': str      # 失败时的错误信息
                }
        """
        logger.info("开始执行签到...")

        # 计算签名
        sign_data = calculate_sign(self.appid, self.member_id)

        # 构建请求数据（JSON格式）
        data = {
            'source': 'wxapp',
            'memberId': self.member_id,
            'cliqueId': '-1',
            'cliqueMemberId': '-1',
            'useClique': 0,
            'enterpriseId': self.enterprise_id,
            'unionid': self.unionid,
            'openid': self.openid,
            'wxOpenid': self.wx_openid,
            'sign': sign_data['sign'],
            'random': sign_data['random'],
            'appid': sign_data['appid'],
            'transId': sign_data['transId'],
            'timestamp': sign_data['timestamp'],
            'gicWxaVersion': '3.9.56',
            'launchOptions': '{"path":"pages/authorize/authorize","query":{},"scene":1101,"referrerInfo":{},"apiCategory":"default"}'
        }

        # 获取请求头
        headers = self.get_headers(self.enterprise_id)
        headers['Content-Type'] = 'application/json;charset=UTF-8'

        try:
            url = f"{self.base_url}/sign/member_sign.json"
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )

            # 检查响应状态
            response.raise_for_status()

            # 解析响应
            result = response.json()

            logger.info(f"签到成功")
            return {
                'success': True,
                'result': result,
                'error': None
            }

        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'result': None,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'result': None,
                'error': error_msg
            }
