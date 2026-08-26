"""南京大学选课助手 —— 自动抢收藏课程模式

自动登录 → 循环拉取收藏列表 → 未满员的课程自动发起选课 → 抢到后推送通知并自动取消收藏 → 直到收藏清空。

满员的课程只查询不请求选课，避免频繁触发选课接口被风控。

用法:
  python xk_favorites.py           # 常规模式，每轮打印收藏状态
  python xk_favorites.py --silent  # 静默模式，不打印收藏数据，仅在发起选课请求时输出
"""

import json
import os
import random
import sys
import time
from typing import Any, Dict, List, Tuple

import requests
import urllib3

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.common import (
    COURSE_CONF_FILE,
    SESSION_CACHE_FILE,
    load_xk_config,
    load_json,
    encrypt_add_param,
    build_headers,
    build_proxies,
    clear_env_proxies,
    poll_process_result,
)
from lib.session_manager import acquire_session
from lib.serverchan import send_serverchan_notification

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp"
VOLUNTEER_URL = f"{BASE_URL}/elective/volunteer.do"
QUERY_FAV_URL = f"{BASE_URL}/elective/queryfavorite.do"
FAVORITE_URL = f"{BASE_URL}/elective/favorite.do"
STUDENT_URL = f"{BASE_URL}/student"

SILENT = "--silent" in sys.argv


def log(msg: str) -> None:
    """常规模式输出；--silent 时静默收藏轮询类的例行信息。"""
    if not SILENT:
        print(msg)


def _acquire_session_and_settle():
    """获取登录凭证；若期间发生了新登录，稍等片刻再返回。

    实测刚登录完成时后端会话可能未就绪，收藏接口会偶发返回空列表
    （曾导致空收藏误判退出），因此新登录后等待一小段时间。
    session_cache.json 仅在新登录成功时被重写，用其修改时间判断。
    """
    before = os.path.getmtime(SESSION_CACHE_FILE) if os.path.exists(SESSION_CACHE_FILE) else 0.0
    cookies, token = acquire_session()
    if cookies and token:
        try:
            after = os.path.getmtime(SESSION_CACHE_FILE)
        except OSError:
            after = before
        if after != before:
            print(">>> 刚完成新登录，等待 2~4s 让后端会话就绪...")
            time.sleep(random.uniform(2, 4))
    return cookies, token


def _is_session_expired(res_json: Dict[str, Any] | None) -> bool:
    """与前端 bh_utils.js / grablessons.min.js 保持一致的登录失效检测。

    前端两种判定方式:
    1. resp.loginURL 存在且非空  (bh_utils.js doAjax)
    2. resp.code == "302"         (grablessons.min.js)
    """
    if not isinstance(res_json, dict):
        return False
    login_url = res_json.get("loginURL")
    if login_url:  # not None / not ""
        return True
    if str(res_json.get("code", "")) == "302":
        return True
    return False


def _try_int(val):
    """纯数字字符串转 int，与浏览器前端 JSON 类型保持一致。"""
    try:
        return int(val)
    except (ValueError, TypeError):
        return val


# ================= 收藏列表 =================

def fetch_favorites(
    *,
    student_code: str,
    elective_batch_code: str,
    session_cookies: Dict[str, str],
    headers: Dict[str, str],
    proxies: Dict[str, str] | None,
) -> List[Dict[str, Any]] | None:
    """拉取收藏列表。返回 dataList；会话失效/响应异常时返回 None。"""
    query_setting = json.dumps({
        "data": {
            "studentCode": student_code,
            "electiveBatchCode": elective_batch_code,
        },
        "pageSize": "999",
        "pageNumber": "0",
        "order": "",
    }, ensure_ascii=False)

    try:
        r = requests.post(
            QUERY_FAV_URL,
            cookies=session_cookies,
            headers=headers,
            data={"querySetting": query_setting},
            proxies=proxies,
            verify=False,
            timeout=10,
        )
        r.encoding = "utf-8"
        data = r.json()
    except Exception as e:
        print(f"❌ 拉取收藏列表失败: {e}")
        return None

    if _is_session_expired(data):
        return None

    data_list = data.get("dataList")
    if data_list is None:
        return None
    return data_list


# ================= courseKind 反查 =================

def fetch_type_to_kind_map(
    *,
    student_code: str,
    session_cookies: Dict[str, str],
    headers: Dict[str, str],
    proxies: Dict[str, str] | None,
) -> Dict[str, Tuple[str, str]] | None:
    """从学生信息接口获取 teachingClassType → (courseKind, 类别名) 映射。

    queryfavorite.do 返回的收藏中 courseKind 为 None，
    但 teachingClassType 有值，选课请求需要通过此映射反推 courseKind。
    """
    url = f"{STUDENT_URL}/{student_code}.do"
    try:
        r = requests.post(url, cookies=session_cookies, headers=headers,
                          proxies=proxies, verify=False, timeout=10)
        r.encoding = "utf-8"
        data = r.json()
    except Exception as e:
        print(f"❌ 获取学生信息失败: {e}")
        return None

    batch_list = data.get("data", {}).get("electiveBatchList", [])
    if not batch_list:
        print("❌ 学生信息中未找到选课批次（electiveBatchList）")
        return None

    type_to_kind: Dict[str, Tuple[str, str]] = {}
    for batch in batch_list:
        for m in batch.get("limitMenuList", []):
            course_kind = m.get("courseKind")
            menu_code = m.get("menuCode")
            menu_name = m.get("menuName") or m.get("engMenuName") or "?"
            if not course_kind or course_kind == "-" or not menu_code:
                continue
            if menu_code not in type_to_kind:
                type_to_kind[menu_code] = (course_kind, menu_name)

    return type_to_kind or None


# ================= 选课 / 取消收藏 =================

def _do_select_one(
    *,
    student_code: str,
    elective_batch_code: str,
    class_id: str,
    course_kind: str,
    teaching_class_type: str,
    session_cookies: Dict[str, str],
    headers: Dict[str, str],
    proxies: Dict[str, str] | None,
) -> Tuple[Dict[str, Any] | None, str]:
    """对单门课发起一次选课请求（addParam 需 AES 加密）。返回 (json_or_none, raw_text)。"""
    payload = {
        "data": {
            "operationType": "1",
            "studentCode": student_code,
            "electiveBatchCode": elective_batch_code,
            "teachingClassId": class_id,
            "courseKind": _try_int(course_kind),
            "teachingClassType": teaching_class_type,
        }
    }

    r = requests.post(
        VOLUNTEER_URL,
        cookies=session_cookies,
        headers=headers,
        data={
            "addParam": encrypt_add_param(payload),
            "studentCode": student_code,
        },
        proxies=proxies,
        verify=False,
        timeout=10,
    )
    r.encoding = "utf-8"
    try:
        return r.json(), r.text
    except Exception:
        return None, r.text


def cancel_favorite(
    *,
    student_code: str,
    elective_batch_code: str,
    class_id: str,
    teaching_class_type: str,
    session_cookies: Dict[str, str],
    headers: Dict[str, str],
    proxies: Dict[str, str] | None,
) -> Dict[str, Any] | None:
    """取消收藏。

    注意：favorite.do 的 addParam 为明文 JSON（已实测验证），
    与 volunteer.do 的 AES 加密 addParam 不同。
    """
    payload = {
        "data": {
            "operationType": "2",
            "studentCode": student_code,
            "electiveBatchCode": elective_batch_code,
            "teachingClassId": class_id,
            "courseKind": "",
            "teachingClassType": teaching_class_type,
        }
    }

    try:
        r = requests.post(
            FAVORITE_URL,
            cookies=session_cookies,
            headers=headers,
            data={
                "addParam": json.dumps(payload, separators=(",", ":")),
                "studentCode": student_code,
            },
            proxies=proxies,
            verify=False,
            timeout=10,
        )
        r.encoding = "utf-8"
        return r.json()
    except Exception:
        return None


# ================= 主流程 =================

def main() -> None:
    # 0. 加载配置
    try:
        config = load_xk_config()
        student_code = str(config.get("USER") or "").strip()
        if not student_code:
            print("❌ xk.conf 中缺少 USER (学号)")
            return
        proxy_url = (config.get("PROXY") or "").strip() or None
    except Exception as e:
        print(f"❌ 读取 xk.conf 失败: {e}")
        return

    # 收藏流程不读 course.conf 的课程列表，但批次代码仍从其获取
    try:
        elective_batch_code = str(load_json(COURSE_CONF_FILE).get("electiveBatchCode") or "").strip()
        if not elective_batch_code:
            raise ValueError("缺少 electiveBatchCode")
    except Exception as e:
        print(f"❌ 读取 course.conf 失败: {e}（请先运行 tools/get_batch_code.py 获取选课批次）")
        return

    # 1. 代理设置
    clear_env_proxies()
    proxies = build_proxies(proxy_url)
    if proxies:
        print(f">>> 启用代理: {proxy_url}")

    # 2. 获取 Session
    print(">>> 正在获取登录凭证...")
    session_cookies, token = _acquire_session_and_settle()
    if not (session_cookies and token):
        print(">>> 登录失败或 Session 无效，无法继续。")
        return
    headers = build_headers(token)
    print(f">>> 凭证获取成功，Token: {str(token)[:10]}...")

    # 3. 获取 teachingClassType → courseKind 映射
    print(">>> 正在获取课程参数映射...")
    type_to_kind = fetch_type_to_kind_map(
        student_code=student_code,
        session_cookies=session_cookies,
        headers=headers,
        proxies=proxies,
    )
    if type_to_kind is None:
        print(">>> 无法获取课程参数映射，无法继续。")
        return
    print(f">>> 成功获取 {len(type_to_kind)} 条类别映射")

    if SILENT:
        print(">>> 静默模式：不打印收藏轮询数据，仅在发起选课请求时输出\n")
    else:
        print()

    # 4. 循环抢收藏课程
    round_no = 0
    while True:
        round_no += 1
        log(f"\n========== 第 {round_no} 轮，正在拉取收藏列表 ==========")

        favs = fetch_favorites(
            student_code=student_code,
            elective_batch_code=elective_batch_code,
            session_cookies=session_cookies,
            headers=headers,
            proxies=proxies,
        )

        if favs is None:
            print(">>> ⚠️ 检测到登录失效，重新获取登录凭证...")
            session_cookies, token = _acquire_session_and_settle()
            if not (session_cookies and token):
                print(">>> ❌ 重新获取登录凭证失败，稍后重试")
                time.sleep(random.uniform(1, 3))
                continue
            headers = build_headers(token)
            new_map = fetch_type_to_kind_map(
                student_code=student_code,
                session_cookies=session_cookies,
                headers=headers,
                proxies=proxies,
            )
            if new_map:
                type_to_kind = new_map
            favs = fetch_favorites(
                student_code=student_code,
                elective_batch_code=elective_batch_code,
                session_cookies=session_cookies,
                headers=headers,
                proxies=proxies,
            )
            if favs is None:
                print(">>> ❌ 重新登录后仍无法拉取收藏列表")
                time.sleep(random.uniform(1, 3))
                continue

        # 空列表需连续确认：queryfavorite 偶发返回空列表（实测出现在刚重登后），
        # 只凭一次空列表就退出会导致收藏未清空时误退出、停止监控
        if not favs:
            for attempt in (1, 2):
                print(f">>> 收藏列表为空，稍后再次确认以免误判 ({attempt}/2)...")
                time.sleep(random.uniform(3, 5))
                favs = fetch_favorites(
                    student_code=student_code,
                    elective_batch_code=elective_batch_code,
                    session_cookies=session_cookies,
                    headers=headers,
                    proxies=proxies,
                )
                if favs is None:
                    break  # 会话可能又失效，交给下一轮顶部的重登逻辑
                if favs:
                    break  # 确认有数据，继续本轮
            else:
                print(">>> 连续 3 次拉取到空收藏列表（都抢到了），退出。")
                return
            if favs is None:
                continue

        for idx, fav in enumerate(favs, 1):
            class_id = str(fav.get("teachingClassID") or "")
            ctype = str(fav.get("teachingClassType") or "")
            name = fav.get("courseName") or "?"
            teacher = fav.get("teacherName") or "?"
            is_full = str(fav.get("isFull") or "")
            occupancy = fav.get("numberOfFirstVolunteer") or "?"
            capacity = fav.get("classCapacity") or "?"

            # 已在课表中的收藏直接跳过，不再发起选课请求
            if str(fav.get("isChoose") or "") == "1":
                log(f"[{idx}/{len(favs)}] {name} ({teacher}) 已在课表中，跳过")
                continue

            # 满员的只跳过不请求，避免频繁请求选课接口触发风控
            # 实测：满员 isFull="1"；未满为 null/空串（此时 numberOfFirstVolunteer 为人数）
            if is_full == "1":
                log(f"[{idx}/{len(favs)}] {name} ({teacher}) 已满 [{occupancy}/{capacity}]，跳过")
                continue

            # 未满员 → 反查 courseKind
            kind_entry = type_to_kind.get(ctype)
            if not kind_entry:
                log(f"[{idx}/{len(favs)}] {name} ({teacher}) 未满! "
                    f"但无法映射 teachingClassType={ctype!r}，跳过")
                continue
            kind, _ = kind_entry

            # 发起选课请求（静默模式下也会输出）
            print(f"\n[{idx}/{len(favs)}] {name} ({teacher}) 未满 [{occupancy}/{capacity}]，"
                  f"发起选课: 班级ID={class_id}, courseKind={kind}, "
                  f"teachingClassType={ctype}")

            try:
                res_json, raw = _do_select_one(
                    student_code=student_code,
                    elective_batch_code=elective_batch_code,
                    class_id=class_id,
                    course_kind=kind,
                    teaching_class_type=ctype,
                    session_cookies=session_cookies,
                    headers=headers,
                    proxies=proxies,
                )
            except Exception as e:
                print(f"    ❌ 请求发生网络错误: {e}")
                time.sleep(random.uniform(1, 3))
                continue

            # 登录失效检测与重试
            if _is_session_expired(res_json):
                print("    ⚠️ 检测到登录失效（loginURL/302），重新获取登录凭证...")
                session_cookies, token = _acquire_session_and_settle()
                if not (session_cookies and token):
                    print("    ❌ 重新获取登录凭证失败，跳过本次")
                    time.sleep(random.uniform(1, 3))
                    continue
                headers = build_headers(token)
                new_map = fetch_type_to_kind_map(
                    student_code=student_code,
                    session_cookies=session_cookies,
                    headers=headers,
                    proxies=proxies,
                )
                if new_map:
                    type_to_kind = new_map

                try:
                    res_json, raw = _do_select_one(
                        student_code=student_code,
                        elective_batch_code=elective_batch_code,
                        class_id=class_id,
                        course_kind=kind,
                        teaching_class_type=ctype,
                        session_cookies=session_cookies,
                        headers=headers,
                        proxies=proxies,
                    )
                except Exception as e:
                    print(f"    ❌ 重试请求发生网络错误: {e}")
                    time.sleep(random.uniform(1, 3))
                    continue

            # 解析结果 —— 与前端 initProcessInterval 逻辑一致
            code = res_json.get("code") if isinstance(res_json, dict) else None

            if str(code) == "1":
                print("    ⏳ 请求已提交，轮询处理结果...")
                poll = poll_process_result(
                    student_code=student_code,
                    teaching_class_id=class_id,
                    session_cookies=session_cookies,
                    headers=headers,
                    proxies=proxies,
                )
                poll_code = str(poll.get("code", ""))
                poll_msg = poll.get("msg", "")

                if poll_code == "1":
                    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"    ✅ 选课成功: {name} ({teacher}) @ {now_str}")
                    if poll_msg:
                        print(f"       服务器消息: {poll_msg}")

                    desp = (f"课程: {name}\n教师: {teacher}\n时间地点: "
                            f"{fav.get('teachingPlace') or '?'}\n"
                            f"teachingClassId: {class_id}\ntime: {now_str}")
                    send_serverchan_notification("✅ 选课成功", desp)

                    # 选到后自动取消收藏
                    cancel_res = cancel_favorite(
                        student_code=student_code,
                        elective_batch_code=elective_batch_code,
                        class_id=class_id,
                        teaching_class_type=ctype,
                        session_cookies=session_cookies,
                        headers=headers,
                        proxies=proxies,
                    )
                    if isinstance(cancel_res, dict) and str(cancel_res.get("code")) == "1":
                        print("    >>> 已自动取消收藏")
                    else:
                        print(f"    !!! 取消收藏失败，请手动处理: {cancel_res}")
                    # 收藏是否已清空由下一轮的"空列表连续确认"逻辑判定退出

                elif poll_code == "-1":
                    print(f"    ❌ 选课失败: {poll_msg}")
                elif poll_code == "timeout":
                    print(f"    ⚠️ 轮询超时，未能确认结果: {poll_msg}")
                else:
                    print(f"    ⚠️ 轮询返回未知状态: code={poll_code}, msg={poll_msg}")

            else:
                if res_json is not None:
                    print(f"    >>> 返回: {res_json}")
                else:
                    print(f"    >>> 返回(非JSON): {str(raw)[:200]}...")

            time.sleep(random.uniform(0.5, 1.2))

        sleep_s = random.uniform(3, 8)
        log(f"\n>>> 本轮结束，休息 {sleep_s:.1f}s 后进入下一轮...")
        time.sleep(sleep_s)


if __name__ == "__main__":
    main()
