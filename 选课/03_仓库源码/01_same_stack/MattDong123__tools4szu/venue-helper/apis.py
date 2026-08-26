#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @File    : apis.py
import json
import logging
import os

import requests

from settings import cookies, headers, stuid, stuname

os.environ['NO_PROXY'] = 'ehall.szu.edu.cn'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("venue.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def getSysConfig():
    """
    获取系统配置
    {
      "XMDM": "001",  # 项目代码
      "XMMC": "羽毛球",  # 项目名称
      "STORE_NAME": "317a6df934914473b49996840b305987.png",  # 插图(b用没有)
      "DCFS": "1.0",  # 订场方式(1: 包场,2: 散场 )
      "XQDM": "1"  # 校区代码(1:粤海, 2:丽湖)
    }
    """
    try:
        ret = requests.post(
            "https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/sportVenue/getSportVenueData.do",
            cookies=cookies,
            headers=headers,
        )
        logger.info(f"获取系统配置成功: {ret.text}")
        ret = json.loads(ret.text)
        return ret
    except requests.exceptions.RequestException as e:
        logger.error(f"获取系统配置失败: {e}")
    return None


def getTimeList(XQ, YYRQ, YYLX, XMDM):
    """
    获取时间列表
    :param XQ: 校区(代码)
    :param YYRQ: 预约日期 例如 2025-01-01
    :param YYLX: 预约类型 即订场方式(1.0: 包场, 2.0: 散场 )
    :param XMDM: 项目代码
    :return:
    """
    try:
        data = {
            'XQ': XQ,
            'YYRQ': YYRQ,
            'YYLX': YYLX,
            'XMDM': XMDM
        }
        ret = requests.post(
            "https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/sportVenue/getTimeList.do",
            cookies=cookies,
            headers=headers,
            data=data
        )
        logger.info(f"获取时间列表成功: {ret.text}")
        ret = json.loads(ret.text)
        return ret
    except requests.exceptions.RequestException as e:
        logger.error(f"获取时间列表失败: {e}")
    except KeyError as e:
        logger.error(f"获取时间列表失败: {e}")
    return None


def getRoom(XMDM, YYRQ, YYLX, KSSJ, JSSJ, XQDM):
    """
    获取场地列表
    :param XMDM: 项目代码
    :param YYRQ: 预约日期 例如 2025-01-01
    :param YYLX: 预约类型 即订场方式(1.0: 包场, 2.0: 散场 )
    :param KSSJ: 开始时间 例如 08:00
    :param JSSJ: 结束时间 例如 09:00
    :param XQDM: 校区代码 (1:粤海, 2:丽湖)
    :param CGBM: 场馆编码
    :return:
    """
    try:
        data = {
            'XMDM': XMDM,
            'YYRQ': YYRQ,
            'YYLX': YYLX,
            'KSSJ': KSSJ,
            'JSSJ': JSSJ,
            'XQDM': XQDM,
        }
        ret = requests.post(
            "https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/modules/sportVenue/getOpeningRoom.do",
            cookies=cookies,
            headers=headers,
            data=data
        )
        ret = json.loads(ret.text)
        ret = ret["datas"]["getOpeningRoom"]["rows"]
        logger.info(f"获取场地列表成功: {ret}")
        return ret
    except requests.exceptions.RequestException as e:
        logger.error(f"获取场地列表失败: {e}")
    except KeyError as e:
        logger.error(f"获取场地列表失败: {ret}")
    return None


def postBook(CGDM, CDWID, XMDM, XQWID, KYYSJD, YYRQ, YYLX):
    """
    预约场地
    :param CGDM: 场馆代码
    :param CDWID: 场地唯一标识
    :param XMDM: 项目代码
    :param XQWID: 校区唯一标识
    :param KYYSJD: 可预约时间段
    :param YYRQ: 预约日期 例如 2025-01-01
    :param YYLX: 预约类型 即订场方式(1.0: 包场, 2.0: 散场 )
    :return:
    """
    try:
        data = {
            'DHID': '',
            'CYRS': '',  # 参与人数
            'YYRGH': stuid,
            'YYRXM': stuname,
            'CGDM': CGDM,
            'CDWID': CDWID,
            'XMDM': XMDM,
            'XQWID': XQWID,
            'KYYSJD': KYYSJD,
            'YYRQ': YYRQ,
            'YYLX': YYLX,
            'PC_OR_PHONE': 'pc',
        }
        times = KYYSJD.split('-')
        data["YYKS"] = YYRQ + " " + times[0]
        data["YYJS"] = YYRQ + " " + times[1]
        '''
        data = {
        'DHID': '',
        'YYRGH': '2100271001',
        'CYRS': '',
        'YYRXM': '张三',
        'CGDM': '001',
        'CDWID': '0ea473755da04a588ebea78af2e8ef9b',
        'XMDM': '001',
        'XQWID': '1',
        'KYYSJD': '19:00-20:00',
        'YYRQ': '2025-04-28',
        'YYLX': '1.0',
        'YYKS': '2025-04-28 19:00',
        'YYJS': '2025-04-28 20:00',
        'PC_OR_PHONE': 'pc',
        }
        '''
        ret = requests.post(
            "https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/sportVenue/insertVenueBookingInfo.do",
            cookies=cookies,
            headers=headers,
            data=data
        )
        logger.info(f"预约结果: {ret.text}")
        ret = json.loads(ret.text)
        return ret
    except requests.exceptions.RequestException as e:
        logger.error(f"预约失败: {e}")
    return None
