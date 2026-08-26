from contextlib import redirect_stdout
import yagmail
import requests
import ddddocr
from humanfriendly.testing import retry
from pyarrow import timestamp
import threading

import const
import time
import json
import os
from datetime import datetime

############################################################################
###  默认配置
############################################################################
# 默认选课速度  x --> 每x秒请求一次
DEFAULT_SELECT_RATE = 2

user_sessions = {}

# 轮询抢课任务管理
grab_tasks = {}  # {task_id: {"thread": thread, "status": "running"/"stopped"/"success", "count": 0, "last_result": ""}}
task_lock = threading.Lock()


def login(username: str, password: str):
    """登录函数"""
    try:
        # 获取验证码UUID
        timestamp = int(time.time() * 1000)
        url = const.VCODE_URL.format(timestamp=timestamp)
        response = requests.get(url, headers=const.VCODE_HEADERS)
        token = response.json()['data']['token']

        # 获取验证码图片
        url = const.CAPTCHA_URL.format(token=token)
        response = requests.get(url, headers=const.VCODE_HEADERS)

        # OCR识别验证码
        with open(os.devnull, 'w') as fnull:
            with redirect_stdout(fnull):
                ocr = ddddocr.DdddOcr()
        image_bytes = response.content
        code = ocr.classification(image_bytes)

        # 登录
        timestamp = int(time.time() * 1000)
        url = const.LOGIN_URL.format(timestamp=timestamp, username=username, password=password, code=code, token=token)
        headers = const.LOGIN_HEADERS
        response = requests.get(url, headers=headers)

        if response.status_code == 200 and str(response.json()['code']) == "1":
            token = response.json()['data']['token']
            WEU = response.cookies.get("_WEU")
            JSESSIONID = response.cookies.get("JSESSIONID")
            # 保存会话信息
            user_sessions[username] = {
                "token": token,
                "WEU": WEU,
                "JSESSIONID": JSESSIONID
            }
            return token, WEU, JSESSIONID
        else:
            print(f"Login failed: {str(response.json())}")
            return None, None, None

    except Exception as e:
        print(f"Login error: {str(e)}")
        return None, None, None


###################################
###  邮箱提醒
###################################
def send_email(email_user: str, email_auth: str, subject: str = "选课成功", message: str = "选课成功"):
    """发送邮件提醒"""
    try:
        yag = yagmail.SMTP(
            user=email_user,
            password=email_auth,
            host="smtp.qq.com",
            port=465
        )

        yag.send(
            to=email_user,
            subject=subject,
            contents=message
        )
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False


###################################
###  抢课
###################################
def select_class(username: str, password: str, elective_batch_code: str, teaching_class_id: str,
                 is_major: str = "1", campus: str = "02", teaching_class_type: str = "XGXK",
                 operation_type: str = "1"):
    """选课函数"""
    # 获取或刷新会话信息
    if username not in user_sessions:
        token, WEU, JSESSIONID = login(username, password)
        if token is None:
            return None, "登录失败，请检查用户名和密码"
    else:
        token = user_sessions[username]["token"]
        WEU = user_sessions[username]["WEU"]
        JSESSIONID = user_sessions[username]["JSESSIONID"]

    data = {
        "data": {
            "operationType": operation_type,
            "studentCode": username,
            "electiveBatchCode": elective_batch_code,
            "teachingClassId": teaching_class_id,
            "isMajor": is_major,
            "campus": campus,
            "teachingClassType": teaching_class_type
        }
    }

    url = "https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/elective/volunteer.do"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "token": token,
        "X-Requested-With": "XMLHttpRequest",
        "Priority": "u=0",
        "Origin": "https://xk.ynu.edu.cn",
        "Host": "xk.ynu.edu.cn"
    }
    cookies = {
        "_WEU": WEU,
        "JSESSIONID": JSESSIONID
    }
    body = "addParam=" + requests.utils.quote(json.dumps(data))

    try:
        response = requests.post(
            url,
            headers=headers,
            data=body,
            cookies=cookies,
        )

        if response.status_code != 200:
            return None, f"请求失败，状态码: {response.status_code}"

        result = response.json()
        code = str(result.get('code', ''))

        if code == "1":  # 选课成功
            return result, "选课成功！"
        elif code == "302":  # token过期,重新登录
            # 清除会话，下次重新登录
            if username in user_sessions:
                del user_sessions[username]
            return None, "登录已过期，请重新登录"
        else:
            return result, result.get('msg', '选课失败')
    except Exception as e:
        return None, f"选课请求出错: {str(e)}"


def drop_class(username: str, password: str, elective_batch_code: str, teaching_class_id: str,
               is_major: str = "1"):
    """退课函数"""
    # 获取或刷新会话信息
    if username not in user_sessions:
        token, WEU, JSESSIONID = login(username, password)
        if token is None:
            return None, "登录失败，请检查用户名和密码"
    else:
        session = user_sessions[username]
        token = session["token"]
        WEU = session["WEU"]
        JSESSIONID = session["JSESSIONID"]

    data = {
        "data": {
            "operationType": "2",  # 退课操作类型为2
            "studentCode": username,
            "electiveBatchCode": elective_batch_code,
            "teachingClassId": teaching_class_id,
            "isMajor": is_major
        }
    }

    # 退课使用的是 GET 请求，URL参数
    timestamp = int(time.time() * 1000)
    delete_param = requests.utils.quote(json.dumps(data))
    url = f"https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/elective/deleteVolunteer.do?timestamp={timestamp}&deleteParam={delete_param}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "token": token,
        "X-Requested-With": "XMLHttpRequest",
        "Priority": "u=0",
        "Referer": "https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/*default/index.do",
        "Host": "xk.ynu.edu.cn"
    }
    cookies = {
        "_WEU": WEU,
        "JSESSIONID": JSESSIONID
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            cookies=cookies,
        )

        if response.status_code != 200:
            return None, f"请求失败，状态码: {response.status_code}"

        result = response.json()
        code = str(result.get('code', ''))

        if code == "1":  # 退课成功
            return result, "退课成功！"
        elif code == "302":  # token过期,重新登录
            # 清除会话，下次重新登录
            if username in user_sessions:
                del user_sessions[username]
            return None, "登录已过期，请重新登录"
        else:
            return result, result.get('msg', '退课失败')
    except Exception as e:
        return None, f"退课请求出错: {str(e)}"


def get_selected_courses(username: str, elective_batch_code: str, password: str = ""):
    """获取用户已选课程"""
    # 检查会话是否存在，如果不存在则先登录
    if username not in user_sessions:
        if not password:
            return None, "用户未登录，请先登录"
        token, WEU, JSESSIONID = login(username, password)
        if token is None:
            return None, "登录失败，请检查用户名和密码"
    
    # 获取会话信息
    session = user_sessions[username]
    token = session["token"]
    WEU = session["WEU"]
    JSESSIONID = session["JSESSIONID"]
    
    # 构建URL
    timestamp = int(time.time() * 1000)
    url = f"https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/elective/courseResult.do?timestamp={timestamp}&studentCode={username}&electiveBatchCode={elective_batch_code}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "token": token,
        "X-Requested-With": "XMLHttpRequest",
        "Priority": "u=0",
        "Referer": "https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/*default/index.do",
        "Host": "xk.ynu.edu.cn"
    }
    cookies = {
        "_WEU": WEU,
        "JSESSIONID": JSESSIONID
    }
    
    try:
        response = requests.get(
            url,
            headers=headers,
            cookies=cookies,
        )
        
        if response.status_code != 200:
            return None, f"请求失败，状态码: {response.status_code}"
        
        result = response.json()
        code = str(result.get('code', ''))
        
        if code == "1":  # 成功
            return result, "获取成功"
        elif code == "302":  # token过期,重新登录
            # 清除会话，下次重新登录
            if username in user_sessions:
                del user_sessions[username]
            # 如果提供了密码，尝试重新登录
            if password:
                token, WEU, JSESSIONID = login(username, password)
                if token:
                    # 重新请求
                    session = user_sessions[username]
                    headers["token"] = session["token"]
                    cookies["_WEU"] = session["WEU"]
                    cookies["JSESSIONID"] = session["JSESSIONID"]
                    response = requests.get(url, headers=headers, cookies=cookies)
                    if response.status_code == 200:
                        result = response.json()
                        if str(result.get('code', '')) == "1":
                            return result, "获取成功"
            return None, "登录已过期，请重新登录"
        else:
            return None, result.get('msg', '获取已选课程失败')
    except Exception as e:
        return None, f"获取已选课程出错: {str(e)}"


def get_courses(username: str, elective_batch_code: str, password: str = "", is_major: str = "1", campus: str = "02", teaching_class_type: str = "XGXK", query_content: str = "", check_conflict: str = "2", check_capacity: str = "2"):
    data = {
        "data": {
            "studentCode": username,
            "electiveBatchCode": elective_batch_code,
            "isMajor": is_major,
            "campus": campus,
            "teachingClassType": teaching_class_type,
            "queryContent": query_content,
            "checkConflict": check_conflict,
            "checkCapacity": check_capacity
        },
        "pageSize":"10",
        "pageNumber":"0",
        "order":"null"
    }

    # 检查会话是否存在，如果不存在则先登录
    if username not in user_sessions:
        if not password:
            return None, "用户未登录，请先登录"
        token, WEU, JSESSIONID = login(username, password)
        if token is None:
            return None, "登录失败，请检查用户名和密码"
    
    # 获取会话信息
    session = user_sessions[username]
    token = session["token"]
    WEU = session["WEU"]
    JSESSIONID = session["JSESSIONID"]

    """获取课程列表"""
    url = const.REC_URL
    headers = const.REC_HEADERS.copy() if hasattr(const.REC_HEADERS, 'copy') else dict(const.REC_HEADERS)
    headers.update({
        "token": token
    })
    cookies = {
        "_WEU": WEU,
        "JSESSIONID": JSESSIONID
    }
    body = "querySetting=" + requests.utils.quote(json.dumps(data))

    try:
        response = requests.post(
            url,
            headers=headers,
            data=body,
            cookies=cookies,
        )

        if response.status_code != 200:
            return None, f"请求失败，状态码: {response.status_code}"

        result = response.json()
        code = str(result.get('code', ''))

        if code == "1":  # 选课成功
            return result, "获取成功！"
        elif code == "302":  # token过期,重新登录
            # 清除会话，下次重新登录
            if username in user_sessions:
                del user_sessions[username]
            return None, "登录已过期，请重新登录"
        else:
            return result, result.get('msg', '选课失败')
    except Exception as e:
        return None, f"选课请求出错: {str(e)}"

def get_batches(username: str, password: str):
    # 检查会话是否存在，如果不存在则先登录
    if username not in user_sessions:
        token, WEU, JSESSIONID = login(username, password)
        if token is None:
            return None, "登录失败，请检查用户名和密码"
    
    # 正确获取会话信息（字典访问方式）
    session = user_sessions[username]
    token = session["token"]
    WEU = session["WEU"]
    JSESSIONID = session["JSESSIONID"]
    
    # 检查 token 是否有效
    if not token or not WEU or not JSESSIONID:
        # 如果会话信息不完整，尝试重新登录
        token, WEU, JSESSIONID = login(username, password)
        if token is None:
            return None, "会话信息不完整，请重新登录"
    
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Connection": "keep-alive",
        "Host": "xk.ynu.edu.cn",
        "Priority": "u=0",
        "Referer": "https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/*default/index.do",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
        "X-Requested-With": "XMLHttpRequest",
        "token": token,  # 注意：应该是小写的 "token" 而不是 "Token"
    }
    cookies = {
        "_WEU": WEU,
        "JSESSIONID": JSESSIONID
    }
    
    retries = 4
    while retries > 0:
        time.sleep(1)
        try:
            timestamp = int(time.time() * 1000)
            url = f"https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/student/{username}.do?timestamp={timestamp}"
            response = requests.get(
                url,
                headers=headers,
                cookies=cookies,
            )

            print(f"Response status: {response.status_code}, Response: {response.text[:200]}")

            # if response.status_code == 401:
            #
            
            if response.status_code != 200:
                retries -= 1
                print(f"请求失败，状态码: {response.status_code}，剩余重试次数: {retries}")
                continue

            result = response.json()
            code = str(result.get('code', ''))

            if code == "1":  # 获取成功
                return result['data']['electiveBatchList'], "获取成功！"
            elif code == "302":  # token过期
                if username in user_sessions:
                    del user_sessions[username]
                return None, "登录已过期，请重新登录"
            else:
                retries -= 1
                print(f"API 返回错误，code: {code}, msg: {result.get('msg', '')}，剩余重试次数: {retries}")

        except Exception as e:
            retries -= 1
            print(f"请求异常: {str(e)}，剩余重试次数: {retries}")

    return None, "获取失败"


def get_sys_params(username: str, password: str = ""):
    """获取系统参数（包含课程类型名称）"""
    # 检查会话是否存在，如果不存在则先登录
    if username not in user_sessions:
        if not password:
            return None, "用户未登录，请先登录"
        token, WEU, JSESSIONID = login(username, password)
        if token is None:
            return None, "登录失败，请检查用户名和密码"
    
    # 获取会话信息
    session = user_sessions[username]
    token = session["token"]
    WEU = session["WEU"]
    JSESSIONID = session["JSESSIONID"]
    
    # 构建URL（带时间戳）
    timestamp = int(time.time() * 1000)
    url = f"{const.SYS_PARAM_URL}?timestamp={timestamp}&_={timestamp - 580}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "token": token,
        "X-Requested-With": "XMLHttpRequest",
        "Priority": "u=0",
        "Referer": "https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/*default/index.do",
        "Host": "xk.ynu.edu.cn"
    }
    cookies = {
        "_WEU": WEU,
        "JSESSIONID": JSESSIONID
    }
    
    try:
        response = requests.get(url, headers=headers, cookies=cookies)
        
        if response.status_code != 200:
            return None, f"请求失败，状态码: {response.status_code}"
        
        result = response.json()
        code = str(result.get('code', ''))
        
        if code == "1":
            # 提取 displayName* 字段
            data = result.get('data', {})
            tab_names = {}
            
            # 遍历所有 displayName* 字段
            for key, value in data.items():
                if key.startswith('displayName') and value:
                    # 提取大写字母部分（去掉 displayName 前缀）
                    # 例如：displayNameTJKC -> TJKC, displayNameALLKC -> ALLKC
                    tab_code = key.replace('displayName', '')
                    # 只保存非空的值
                    if tab_code and value:
                        tab_names[tab_code] = value
            
            return tab_names, "获取成功"
        elif code == "302":  # token过期
            if username in user_sessions:
                del user_sessions[username]
            return None, "登录已过期，请重新登录"
        else:
            return None, result.get('msg', '获取系统参数失败')
    except Exception as e:
        return None, f"获取系统参数出错: {str(e)}"


###################################
###  轮询抢课
###################################
def grab_course_loop(task_id: str, username: str, password: str, elective_batch_code: str, 
                     teaching_class_id: str, is_major: str = "1", campus: str = "02", 
                     teaching_class_type: str = "XGXK", select_rate: int = 2,
                     email_user: str = None, email_auth: str = None, email_msg: str = "选课成功"):
    """轮询抢课循环函数"""
    global grab_tasks
    
    count = 0
    
    while True:
        # 检查任务是否被停止
        with task_lock:
            if task_id not in grab_tasks or grab_tasks[task_id]["status"] != "running":
                break
        
        # 执行选课
        result, message = select_class(
            username=username,
            password=password,
            elective_batch_code=elective_batch_code,
            teaching_class_id=teaching_class_id,
            is_major=is_major,
            campus=campus,
            teaching_class_type=teaching_class_type,
            operation_type="1"
        )
        
        count += 1
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 更新任务状态
        with task_lock:
            if task_id in grab_tasks:
                grab_tasks[task_id]["count"] = count
                grab_tasks[task_id]["last_result"] = message
                grab_tasks[task_id]["last_time"] = current_time
        
        print(f"[{current_time}] 任务 {task_id} - 第 {count} 次尝试: {message}")
        
        # 检查选课结果
        if result:
            result_code = str(result.get('code', ''))
            if result_code == "1":  # 选课成功
                with task_lock:
                    if task_id in grab_tasks:
                        grab_tasks[task_id]["status"] = "success"
                        grab_tasks[task_id]["last_result"] = "选课成功！"
                
                # 发送邮件通知（如果配置了邮箱）
                if email_user and email_auth:
                    send_email(email_user, email_auth, "选课成功", email_msg)
                
                print(f"[{current_time}] 任务 {task_id} - 选课成功！")
                break
            elif result_code == "302":  # token过期，需要重新登录
                # select_class 函数会自动清除会话，下次调用时会重新登录
                print(f"[{current_time}] 任务 {task_id} - Token过期，将重新登录")
        
        # 等待指定时间后继续下一次尝试
        time.sleep(select_rate)
    
    # 任务结束，清理
    with task_lock:
        if task_id in grab_tasks:
            if grab_tasks[task_id]["status"] == "running":
                grab_tasks[task_id]["status"] = "stopped"


def start_grab_course(username: str, password: str, elective_batch_code: str, 
                      teaching_class_id: str, is_major: str = "1", campus: str = "02",
                      teaching_class_type: str = "XGXK", select_rate: int = 2,
                      email_user: str = None, email_auth: str = None, email_msg: str = "选课成功"):
    """启动轮询抢课任务"""
    global grab_tasks
    
    # 检查是否已有该课程的成功任务（但允许重新启动，因为可能已经退课了）
    # 只检查是否有正在运行的任务，如果有则不允许重复启动
    with task_lock:
        for task_id, task_info in grab_tasks.items():
            if (task_info.get("username") == username and 
                task_info.get("teaching_class_id") == teaching_class_id and
                task_info.get("status") == "running"):
                return None  # 已有运行中的任务，不启动新任务
    
    # 生成任务ID
    task_id = f"{username}_{teaching_class_id}_{int(time.time())}"
    
    # 创建线程
    thread = threading.Thread(
        target=grab_course_loop,
        args=(task_id, username, password, elective_batch_code, teaching_class_id,
              is_major, campus, teaching_class_type, select_rate, email_user, email_auth, email_msg),
        daemon=True
    )
    
    # 保存任务信息
    with task_lock:
        grab_tasks[task_id] = {
            "thread": thread,
            "status": "running",
            "count": 0,
            "last_result": "",
            "last_time": "",
            "username": username,
            "teaching_class_id": teaching_class_id
        }
    
    # 启动线程
    thread.start()
    
    return task_id


def stop_grab_course(task_id: str):
    """停止轮询抢课任务"""
    global grab_tasks   
    
    with task_lock:
        if task_id in grab_tasks:
            grab_tasks[task_id]["status"] = "stopped"
            return True
        return False


def get_grab_task_status(task_id: str):
    """获取轮询抢课任务状态"""
    global grab_tasks
    
    with task_lock:
        if task_id in grab_tasks:
            task = grab_tasks[task_id]
            return {
                "task_id": task_id,
                "status": task["status"],
                "count": task["count"],
                "last_result": task["last_result"],
                "last_time": task.get("last_time", ""),
                "username": task.get("username", ""),
                "teaching_class_id": task.get("teaching_class_id", "")
            }
        return None


def get_all_grab_tasks():
    """获取所有轮询抢课任务"""
    global grab_tasks
    
    with task_lock:
        return {
            task_id: {
                "task_id": task_id,
                "status": task["status"],
                "count": task["count"],
                "last_result": task["last_result"],
                "last_time": task.get("last_time", ""),
                "username": task.get("username", ""),
                "teaching_class_id": task.get("teaching_class_id", "")
            }
            for task_id, task in grab_tasks.items()
        }
