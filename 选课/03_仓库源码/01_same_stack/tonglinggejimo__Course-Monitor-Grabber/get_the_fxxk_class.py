import requests
import json
import time
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# 1. 【必须修改】请将这里的信息替换成你自己的
# ==================================================================
# -------- 身份与课程信息 --------
cookie_str = '_WEU=xxxxxxxxxxxxxxxxx; JSESSIONID=xxxxxxxxxxxxxxxxxx' # 从浏览器开发者工具中复制完整的Cookie字符串
token = '' # 从浏览器开发者工具中复制Token
student_code = '' # 你的学号
# {"data":{"operationType":"1","studentCode":"2023xxxxxxxx","electiveBatchCode":"xxxxxxxxxxxxx","teachingClassId":"xxxxxxxxxxxxxx","isMajor":"1","campus":"11","teachingClassType":"FANKC"}}
# 【新增】要抢的课程ID列表，按需添加多个课程
teaching_class_ids = [
    'xxxxxxxxxxxxxxxxx',  
    # 'xxxxxxxxxxxxxxxxx',    # 添加更多课程ID
]

elective_batch_code = '' # 课程批次号
teaching_class_type = '' 
# 课程类型，请根据实际情况修改
# 计划课程：TJKC，体育课程：TYKC，方案课程：FANKC，通识课程：XGXK，
# 跨专业课程：FAWKC，重修课程：CXKC，辅修：FXKC

# -------- 定时与抢课策略设置 --------
# 设置抢课目标日期和时间（北京时间，24小时制）
TARGET_DATE_STR = "2025-07-10"  # 【重要】修改为抢课当天的日期
TARGET_TIME_STR = "17:46:00"  # 【重要】修改为抢课开始的时间

# 提前几秒开始发送请求（为了应对网络延迟和服务器时间误差）
RUSH_START_SECONDS_BEFORE = 2

# 高频请求的持续时间（秒）。例如 300 秒 = 5 分钟
RUSH_DURATION_SECONDS = 50

# 每次请求之间的间隔时间（秒）。0.5秒较为合适
INTERVAL_SECONDS = 0.2
# ==================================================================


# 2. 脚本核心逻辑 (一般无需修改)
success_msgs = ["添加选课志愿成功", "该课程已经存在选课结果中"]

fail_count = 0  # 失败计数
successful_courses = set()  # 记录已成功选课的课程ID

def submit_post_request(teaching_class_id, course_name=""):
    """构造并发送单次选课请求，返回是否该课程选课成功"""
    global fail_count
    
    url = 'https://xsxk.xxx.edu.cn/xsxkapp/sys/xsxkapp/elective/volunteer.do'
    headers = {
        'Host': 'xsxk.xxx.edu.cn', 'Cookie': cookie_str,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.63 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': 'application/json, text/javascript, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest',
        'Token': token, 'Origin': 'https://xsxk.xxx.edu.cn', 'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty',
        'Referer': f'https://xsxk.xxx.edu.cn/xsxkapp/sys/xsxkapp/*default/grablessons.do?token={token}',
        'Accept-Encoding': 'gzip, deflate, br', 'Accept-Language': 'zh-CN,zh;q=0.9', 'Connection': 'close',
    }
    post_data = {
        "data": {
            "operationType": "1", "studentCode": student_code, "electiveBatchCode": elective_batch_code,
            "teachingClassId": teaching_class_id, "isMajor": "1", "campus": "11",
            "teachingClassType": teaching_class_type
        }
    }
    data_string = f"addParam={quote(json.dumps(post_data))}"

    try:
        response = requests.post(url, headers=headers, data=data_string.encode('utf-8'), timeout=5)
        response.raise_for_status()
        result = response.json()
        msg = result.get('msg')
        now_str = datetime.now(beijing_tz).strftime('%H:%M:%S.%f')[:-3]
        print(f"[{now_str}] {course_name}请求成功 - 响应: {msg}")
        if msg in success_msgs:
            print(f"[{now_str}] {course_name}抢课成功或已选上！")
            successful_courses.add(teaching_class_id)
            return True  # 该课程选课成功
    except requests.exceptions.Timeout:
        fail_count += 1
        now_str = datetime.now(beijing_tz).strftime('%H:%M:%S.%f')[:-3]
        print(f"[{now_str}] {course_name}请求超时（累计失败{fail_count}次），重试...")
    except requests.exceptions.RequestException as e:
        fail_count += 1
        now_str = datetime.now(beijing_tz).strftime('%H:%M:%S.%f')[:-3]
        # 502等错误
        print(f"[{now_str}] {course_name}请求出错: {e}（累计失败{fail_count}次），重试...")
    except json.JSONDecodeError:
        fail_count += 1
        now_str = datetime.now(beijing_tz).strftime('%H:%M:%S.%f')[:-3]
        print(f"[{now_str}] {course_name}服务器返回非JSON（累计失败{fail_count}次），重试...")
    return False  # 该课程未成功，继续抢课

def submit_all_courses():
    """为所有未成功的课程并行发送选课请求，返回是否应该停止所有抢课"""
    course_names = {
        'xxxxxxxxxxxxx': '深度学习'
    }
    
    # 只为未成功的课程发送请求
    remaining_courses = [cid for cid in teaching_class_ids if cid not in successful_courses]
    
    if not remaining_courses:
        print("所有课程都已选课成功！")
        query_course_result()
        return True  # 停止抢课
    
    # 使用线程池并行发送请求
    with ThreadPoolExecutor(max_workers=len(remaining_courses)) as executor:
        # 提交所有任务
        future_to_course = {}
        for teaching_class_id in remaining_courses:
            course_name = course_names.get(teaching_class_id, f"课程ID:{teaching_class_id[-6:]}")
            future = executor.submit(submit_post_request, teaching_class_id, course_name)
            future_to_course[future] = (teaching_class_id, course_name)
        
        # 等待所有请求完成并处理结果
        for future in as_completed(future_to_course):
            teaching_class_id, course_name = future_to_course[future]
            try:
                success = future.result()
                # 结果已在submit_post_request函数中处理，这里不需要额外操作
            except Exception as exc:
                print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S.%f')[:-3]}] {course_name}并行请求异常: {exc}")
    
    # 检查是否所有课程都成功了
    if len(successful_courses) == len(teaching_class_ids):
        print("所有课程都已选课成功！")
        query_course_result()
        return True  # 停止抢课
    
    return False  # 继续抢课

def query_course_result():
    """抢课成功后查询选课结果，自动重试，健壮处理"""
    url = (
        f"https://xsxk.xxx.edu.cn/xsxkapp/sys/xsxkapp/elective/courseResult.do"
        f"?timestamp={int(time.time() * 1000) + random.randint(0,999)}"
        f"&studentCode={student_code}"
        f"&electiveBatchCode={elective_batch_code}"
    )
    headers = {
        'Host': 'xsxk.xxx.edu.cn',
        'Cookie': cookie_str,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.63 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
        'Token': token,
        'Referer': f'https://xsxk.xxx.edu.cn/xsxkapp/sys/xsxkapp/*default/grablessons.do?token={token}',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'close',
    }
    max_retry = 10
    for attempt in range(1, max_retry + 1):
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            result = response.json()
            msg = result.get('msg', '')
            if result.get('code') == '1' and result.get('dataList'):
                print(f"选课结果查询成功：{msg}")
                for course in result['dataList']:
                    print(f"课程名称：{course.get('courseName')}")
                    print(f"教师：{course.get('teacherName')}")
                    print(f"上课时间地点：{course.get('teachingPlace')}")
                    print(f"学分：{course.get('credit')}")
                    print(f"选课状态：{course.get('selectStatus')}")
                return
            else:
                print(f"第{attempt}次查询失败，返回信息：{msg}，重试中...")
        except requests.exceptions.Timeout:
            print(f"第{attempt}次查询超时，重试中...")
        except requests.exceptions.RequestException as e:
            print(f"第{attempt}次查询出错: {e}，重试中...")
        except json.JSONDecodeError:
            print(f"第{attempt}次查询返回非JSON，重试中...")
        time.sleep(1)
    print("多次查询未成功，请稍后手动查询！")

# 3. 定时启动与循环执行 (一般无需修改)
if __name__ == '__main__':
    # 定义北京时区 (UTC+8)
    beijing_tz = timezone(timedelta(hours=8))

    # 解析设定的目标时间字符串，并附加时区信息
    try:
        target_datetime_str = f"{TARGET_DATE_STR} {TARGET_TIME_STR}"
        target_datetime_beijing = datetime.strptime(target_datetime_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=beijing_tz)
    except ValueError:
        print("错误：日期或时间格式不正确，请使用 'YYYY-MM-DD' 和 'HH:MM:SS' 格式。")
        exit()

    # 计算抢课的开始时间（目标时间 - 提前量）
    start_rush_time = target_datetime_beijing - timedelta(seconds=RUSH_START_SECONDS_BEFORE)
    
    print("=" * 50)
    print("定时抢课脚本已启动（v3多课程版）")
    print(f"要抢的课程数量: {len(teaching_class_ids)}")
    for i, course_id in enumerate(teaching_class_ids, 1):
        print(f"  {i}. 课程ID: {course_id}")
    print(f"将在北京时间 {start_rush_time.strftime('%Y-%m-%d %H:%M:%S')} 自动开始抢课")
    print("=" * 50)

    # 等待循环：直到当前时间到达设定的开始时间
    while True:
        now_beijing = datetime.now(beijing_tz)
        if now_beijing >= start_rush_time:
            print("\n时间到！开始高频发送抢课请求...")
            break
        
        remaining_time = start_rush_time - now_beijing
        # \r 让光标回到行首，实现动态刷新倒计时
        print(f"等待中... 倒计时: {str(remaining_time).split('.')[0]}", end='\r') 
        time.sleep(0.5) # 每0.5秒检查一次时间

    # 抢课循环：在指定的时间段内高频发送请求
    rush_end_time = datetime.now(beijing_tz) + timedelta(seconds=RUSH_DURATION_SECONDS)
    while datetime.now(beijing_tz) < rush_end_time:
        should_stop = submit_all_courses()
        if should_stop:
            break
        time.sleep(INTERVAL_SECONDS)

    print("-" * 50)
    if len(successful_courses) > 0:
        print(f"成功选上 {len(successful_courses)} 门课程！")
        course_names = {
            'xxxxxxxxxxxxxxxx': '自然语言处理'
        }
        for course_id in successful_courses:
            course_name = course_names.get(course_id, f"课程ID:{course_id[-6:]}")
            print(f"  ✓ {course_name}")
    else:
        print("未能成功选上任何课程。")
    
    if fail_count > 0:
        print(f"抢课已持续 {RUSH_DURATION_SECONDS} 秒，脚本自动停止。期间失败请求次数：{fail_count}")
    else:
        print(f"抢课已持续 {RUSH_DURATION_SECONDS} 秒，脚本自动停止。无失败请求。")
