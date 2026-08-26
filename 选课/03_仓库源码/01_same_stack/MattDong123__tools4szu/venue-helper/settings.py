#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @File    : settings.py
'''
    CGDM: 场馆代码
    XMDM: 项目代码
    XQWID: 校区唯一标识 (1粤海, 2丽湖)
    KYYSJD: 可预约时间段 (形如20:00-21:00)
    YYRQ: 预约日期 例如 2025-01-01
    YYLX: 预约类型 即订场方式(1.0: 包场, 2.0: 散场 )
'''
# courses=[{"CGDM":"001","CDWID":"6fbd613382ef48db9d2a2d214e47bae3","XMDM":"001","XQWID":"1","KYYSJD":"20:00-21:00","YYRQ":"2025-04-29","YYLX":"1.0"}]  # 预约场次列表
counts = 10 # 预约总轮次
courses=[{"CGDM":"008","XMDM":"002","XQWID":"1","KYYSJD":"20:00-21:00","YYRQ":"2025-04-30","YYLX":"2.0"}]  # 预约场次列表
delay = 200  # 延迟时间, 单位毫秒
stuid = 2025101011
stuname = "张xx"
cookies = 'EMAP_LANG=zh; _WEU=172ad976'



if isinstance(cookies, str):
    cookie_list = cookies.split(';')
    cookies = {}
    for item in cookie_list:
        item = item.strip()
        items = item.split('=')
        cookies[items[0]] = items[1]
if not isinstance(cookies, dict):
    raise ValueError("invalid cookie!")

headers = {
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'https://ehall.szu.edu.cn',
    'Pragma': 'no-cache',
    'Referer': 'https://ehall.szu.edu.cn/qljfwapp/sys/lwSzuCgyy/index.do?t_s=1745831680729',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
    'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}
