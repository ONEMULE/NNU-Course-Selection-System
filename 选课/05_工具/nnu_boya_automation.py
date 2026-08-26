#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NNU 博雅课查询与受控选课工具。

设计原则：

* 只查询仙林校区(code=2)和仙林新北(code=4)；
* 登录、密码填写、人机认证由用户在可见浏览器中完成；
* 会话 token 只在页面上下文内使用，不导出、不写盘、不打印；
* 默认只读查询；提交必须同时指定目标课程、--submit 和明确确认；
* 提交前重新查询“不冲突 + 未满”，并刷新课程详情/容量；
* 不自动重试 volunteer.do，避免网络不确定时重复提交。

该工具依赖 Playwright，但不会修改第三方源码目录，也不会尝试绕过验证码或
人机认证。每次启动都使用全新的临时浏览器会话，不复用上次的登录态。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


BASE_URL = "https://xsxk.nnu.edu.cn/xsxkapp"
ENTRY_URL = f"{BASE_URL}/*default/index.do"
GRAB_URL = f"{BASE_URL}/*default/grablessons.do"
API_PREFIX = "/sys/xsxkapp"

PUBLIC_COURSE_PATH = f"{API_PREFIX}/elective/publicCourse.do"
SELECTED_COURSE_PATH = f"{API_PREFIX}/elective/courseResult.do"
TEST_COURSE_PATH = f"{API_PREFIX}/elective/testCourse.do"
BATCH_OPEN_PATH = f"{API_PREFIX}/elective/batchisopen.do"
DETAIL_PATH = f"{API_PREFIX}/publicinfo/queryjxb.do"
CAPACITY_PATH = f"{API_PREFIX}/elective/teachingclass/capacity.do"
VOLUNTEER_PATH = f"{API_PREFIX}/elective/volunteer.do"
STUDENT_STATUS_PATH = f"{API_PREFIX}/elective/studentstatus.do"

CAMPUS = {
    "2": "仙林校区",
    "4": "仙林新北",
}

AUTO_TARGET_COUNT = 4

TOKEN_PATTERN = re.compile(
    r"(?i)([\"']?token[\"']?\s*[=:]\s*[\"']?)[^&\s,}\"']+"
)
COOKIE_PATTERN = re.compile(
    r"(?i)([\"']?cookie[\"']?\s*[=:]\s*[\"']?)[^&\s,}\"']+"
)


class AutomationError(RuntimeError):
    """可向用户展示的工具错误。"""


class SessionExpiredError(AutomationError):
    """登录态失效或服务端要求重新登录。"""


class UnsafeSelectionError(AutomationError):
    """安全闸门拒绝提交。"""


def safe_message(value: Any, limit: int = 360) -> str:
    """清理错误/提示文本，避免日志携带 token 或 cookie。"""

    text = "" if value is None else str(value)
    text = TOKEN_PATTERN.sub(r"\1[REDACTED]", text)
    text = COOKIE_PATTERN.sub(r"\1[REDACTED]", text)
    return text.replace("\r", " ").replace("\n", " ")[:limit]


def as_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value).strip()


def first_value(item: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def parse_flag(value: Any) -> Optional[bool]:
    """将 NNU 常见的 0/1 标记转换为布尔值；未知值返回 None。"""

    text = as_text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n", ""}:
        return False
    return None


def parse_int(value: Any) -> Optional[int]:
    text = as_text(value)
    if text is None or text == "":
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def compose_query_content(
    keyword: str = "",
    category: str = "",
    section: str = "",
) -> str:
    """按 grablessons.js 的顺序构造 queryContent。"""

    parts: list[str] = []
    keyword = keyword.strip()
    category = category.strip()
    section = section.strip()
    if keyword:
        parts.append(keyword)
    if category:
        parts.append(f"XGXKLBDM:{category}")
    if section:
        parts.append(f"KCBK:{section}")
    return ",".join(parts)


def build_query_payload(
    *,
    student_code: str,
    batch_code: str,
    campus_code: str,
    check_conflict: str = "0",
    check_capacity: str = "0",
    keyword: str = "",
    category: str = "",
    section: str = "",
    page_size: int = 10,
    page_number: int = 0,
    order: str = "",
) -> dict[str, str]:
    """构造 publicCourse.do 的表单字段。

    该结构对应本地脱敏源码 grablessons.js 的 buildQueryTCParam：
    querySetting 是一个 JSON 字符串，而不是直接提交 JSON body。
    """

    data = {
        "studentCode": str(student_code),
        "campus": str(campus_code),
        "electiveBatchCode": str(batch_code),
        "isMajor": "1",
        "teachingClassType": "XGXK",
        "checkConflict": str(check_conflict),
        "checkCapacity": str(check_capacity),
        "queryContent": compose_query_content(keyword, category, section),
    }
    outer = {
        "data": data,
        "pageSize": str(page_size),
        "pageNumber": str(page_number),
        "order": order or "",
    }
    return {
        "querySetting": json.dumps(
            outer,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    }


def build_add_payload(
    *,
    student_code: str,
    batch_code: str,
    teaching_class_id: str,
    campus_code: str,
    need_book: Optional[str] = None,
    test_teaching_class_id: Optional[str] = None,
) -> dict[str, str]:
    """构造 NNU 页面实际使用的 volunteer.do 表单字段。"""

    if campus_code not in CAMPUS:
        raise UnsafeSelectionError(f"拒绝未知校区代码：{campus_code}")
    if need_book not in {None, "0", "1"}:
        raise UnsafeSelectionError("need_book 只能是 0、1 或省略")

    data: dict[str, str] = {
        "operationType": "1",
        "studentCode": str(student_code),
        "electiveBatchCode": str(batch_code),
        "teachingClassId": str(teaching_class_id),
        "isMajor": "1",
        "campus": str(campus_code),
        "teachingClassType": "XGXK",
    }
    if need_book is not None:
        data["needBook"] = need_book
    if test_teaching_class_id:
        data["testTeachingClassID"] = str(test_teaching_class_id)

    return {
        "addParam": json.dumps(
            {"data": data},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    }


@dataclass
class SessionContext:
    """只保留脚本实际需要的会话上下文，不包含 token。"""

    student_code: str
    batch_code: str
    batch_name: str
    current_campus_code: str
    current_campus_name: str
    can_select_book: str
    teaching_class_type: str


@dataclass
class Course:
    campus_code: str
    campus_name: str
    teaching_class_id: str
    course_number: str
    course_name: str
    course_index: str
    teacher: str
    teaching_place: str
    time: str
    class_capacity: Optional[int]
    first_volunteer: Optional[int]
    selected: Optional[int]
    is_conflict: Any
    conflict_desc: str
    is_full: Any
    is_choose: Any
    capacity_suffix: str
    has_test: Any
    need_book: Any
    test_teaching_class_id: str
    raw: Mapping[str, Any]

    @classmethod
    def from_api(
        cls,
        item: Mapping[str, Any],
        campus_code: str,
        campus_name: str,
    ) -> Optional["Course"]:
        teaching_class_id = as_text(
            first_value(item, "teachingClassID", "teachingClassId", "jxbid")
        )
        if not teaching_class_id:
            return None
        return cls(
            campus_code=campus_code,
            campus_name=campus_name,
            teaching_class_id=teaching_class_id,
            course_number=as_text(
                first_value(item, "courseNumber", "courseNum")
            )
            or "",
            course_name=as_text(
                first_value(item, "courseName", "name")
            )
            or "",
            course_index=as_text(
                first_value(item, "courseIndex", "classIndex")
            )
            or "",
            teacher=as_text(
                first_value(item, "teacherName", "teacher", "subTeacher")
            )
            or "",
            teaching_place=as_text(
                first_value(
                    item,
                    "teachingPlace",
                    "teachPlace",
                    "classroom",
                    "place",
                )
            )
            or "",
            time=as_text(first_value(item, "time", "courseTime", "wid")) or "",
            class_capacity=parse_int(
                first_value(item, "classCapacity", "capacity")
            ),
            first_volunteer=parse_int(
                first_value(item, "numberOfFirstVolunteer", "firstVolunteer")
            ),
            selected=parse_int(
                first_value(item, "numberOfSelected", "selected")
            ),
            is_conflict=first_value(item, "isConflict"),
            conflict_desc=as_text(
                first_value(item, "conflictDesc", "conflictDescription")
            )
            or "",
            is_full=first_value(item, "isFull"),
            is_choose=first_value(item, "isChoose"),
            capacity_suffix=as_text(
                first_value(item, "capacitySuffix")
            )
            or "",
            has_test=first_value(item, "hasTest"),
            need_book=first_value(item, "needBook"),
            test_teaching_class_id=as_text(
                first_value(item, "testTeachingClassID", "testTeachingClassId")
            )
            or "",
            raw=item,
        )

    def is_safe_candidate(self) -> bool:
        """只接受服务端明确标记为不冲突且未满的行。"""

        if parse_flag(self.is_conflict) is not False:
            return False
        if parse_flag(self.is_full) is not False:
            return False
        if parse_flag(self.is_choose) is True:
            return False
        if self.class_capacity is not None:
            for count in (self.first_volunteer, self.selected):
                if count is not None and count >= self.class_capacity:
                    return False
        return True

    def public_dict(self) -> dict[str, Any]:
        """可写入日志/快照的脱敏课程字段，不含 raw 响应。"""

        return {
            "campusCode": self.campus_code,
            "campus": self.campus_name,
            "teachingClassId": self.teaching_class_id,
            "courseNumber": self.course_number,
            "courseName": self.course_name,
            "courseIndex": self.course_index,
            "teacher": self.teacher,
            "teachingPlace": self.teaching_place,
            "time": self.time,
            "classCapacity": self.class_capacity,
            "numberOfFirstVolunteer": self.first_volunteer,
            "numberOfSelected": self.selected,
            "isConflict": self.is_conflict,
            "isFull": self.is_full,
            "isChoose": self.is_choose,
            "conflictDesc": self.conflict_desc,
            "hasTest": self.has_test,
            "needBook": self.need_book,
            "capacitySuffix": self.capacity_suffix,
        }

    def short_label(self) -> str:
        return (
            f"{self.campus_name} | {self.course_name or '-'} | "
            f"{self.course_number or '-'} | "
            f"{self.teaching_class_id}"
        )


@dataclass
class QueryResult:
    campus_code: str
    campus_name: str
    total_count: int
    pages_visited: int
    courses: list[Course]


def merge_course_data(
    course: Course,
    extra: Mapping[str, Any],
) -> Course:
    merged = dict(course.raw)
    merged.update(extra)
    return Course.from_api(merged, course.campus_code, course.campus_name) or course


def course_matches(
    course: Course,
    *,
    course_id: str = "",
    course_number: str = "",
    course_name: str = "",
) -> bool:
    if course_id and course.teaching_class_id != course_id:
        return False
    if course_number and course.course_number != course_number:
        return False
    if course_name and course_name.casefold() not in course.course_name.casefold():
        return False
    return bool(course_id or course_number or course_name)


FETCH_SCRIPT = """
async ({path, method, params}) => {
  const token = sessionStorage.getItem("token");
  if (!token) {
    return {status: 0, text: "missing-session"};
  }
  const url = new URL(path, window.location.origin);
  const options = {
    method: method || "GET",
    credentials: "include",
    headers: {
      "X-Requested-With": "XMLHttpRequest",
      "token": token
    }
  };
  const values = params || {};
  if ((method || "GET").toUpperCase() === "GET") {
    for (const [key, value] of Object.entries(values)) {
      if (value !== null && value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  } else {
    options.headers["Content-Type"] =
      "application/x-www-form-urlencoded; charset=UTF-8";
    options.body = new URLSearchParams(
      Object.entries(values).map(([key, value]) => [key, String(value)])
    ).toString();
  }
  const response = await fetch(url.toString(), options);
  return {status: response.status, text: await response.text()};
}
"""


class BrowserApi:
    """通过同源页面 fetch 调用 API，token 留在 sessionStorage 页面上下文。"""

    def __init__(self, page: Any):
        self.page = page

    async def call(
        self,
        path: str,
        *,
        method: str = "GET",
        params: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        result = await self.page.evaluate(
            FETCH_SCRIPT,
            {
                "path": path,
                "method": method,
                "params": dict(params or {}),
            },
        )
        status = int(result.get("status", 0))
        raw_text = result.get("text", "")
        if status in {401, 403}:
            raise SessionExpiredError(f"服务端拒绝请求（HTTP {status}）")
        if status == 0:
            raise SessionExpiredError("浏览器页面没有可用登录态，请重新登录")
        try:
            payload = json.loads(raw_text)
        except (TypeError, ValueError) as exc:
            raise AutomationError(
                f"服务返回非 JSON（HTTP {status}）"
            ) from exc
        if not isinstance(payload, dict):
            raise AutomationError("服务返回结构不是对象")
        if payload.get("loginURL"):
            raise SessionExpiredError("服务端要求重新登录")
        if as_text(payload.get("code")) == "302":
            raise SessionExpiredError("登录态已失效（code=302）")
        return payload

    async def get(
        self,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        return await self.call(path, method="GET", params=params)

    async def post(
        self,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        return await self.call(path, method="POST", params=params)


class BrowserSession:
    """可见浏览器和会话状态管理。"""

    READY_EXPRESSION = """
      () => Boolean(
        sessionStorage.getItem("token") &&
        (() => {
          try {
            const info = JSON.parse(sessionStorage.getItem("studentInfo"));
            return info && info.code && info.electiveBatch &&
                   info.electiveBatch.code;
          } catch (_) {
            return false;
          }
        })()
      )
    """

    def __init__(self, page: Any):
        self.page = page

    async def wait_until_ready(self, timeout_seconds: int) -> None:
        try:
            await self.page.wait_for_function(
                self.READY_EXPRESSION,
                timeout=timeout_seconds * 1000,
            )
        except Exception as exc:
            raise AutomationError(
                "等待登录态超时；请在打开的可见浏览器中完成登录和人机认证"
            ) from exc

    async def read_context(self) -> SessionContext:
        data = await self.page.evaluate(
            """
            () => {
              const parse = (key) => {
                try { return JSON.parse(sessionStorage.getItem(key)); }
                catch (_) { return null; }
              };
              const student = parse("studentInfo") || {};
              const batch = student.electiveBatch || parse("currentBatch") || {};
              const campus = parse("currentCampus") || {};
              const book = parse("bookParam") || {};
              return {
                studentCode: student.code || "",
                batchCode: batch.code || "",
                batchName: batch.name || "",
                campusCode: campus.code || "",
                campusName: campus.name || "",
                canSelectBook: book.canSelectBook || "0",
                teachingClassType:
                  sessionStorage.getItem("teachingClassType") || ""
              };
            }
            """
        )
        required = {
            "studentCode": data.get("studentCode"),
            "batchCode": data.get("batchCode"),
        }
        if not all(required.values()):
            raise SessionExpiredError("页面未提供完整的学生/轮次登录态")
        return SessionContext(
            student_code=str(data["studentCode"]),
            batch_code=str(data["batchCode"]),
            batch_name=str(data.get("batchName") or ""),
            current_campus_code=str(data.get("campusCode") or ""),
            current_campus_name=str(data.get("campusName") or ""),
            can_select_book=str(data.get("canSelectBook") or "0"),
            teaching_class_type=str(data.get("teachingClassType") or ""),
        )

    async def ensure_ui_campus(self, campus_code: str) -> SessionContext:
        """提交前通过页面原生校区切换逻辑对齐 currentCampus。"""

        if campus_code not in CAMPUS:
            raise UnsafeSelectionError(f"拒绝非目标校区：{campus_code}")
        current = await self.read_context()
        if current.current_campus_code == campus_code:
            return current

        switcher = None
        option_selectors: tuple[str, ...] = ()
        for switch_selector, campus_selector in (
            ("#changeCampus:visible", ".campusList"),
            (".home-change-campus:visible", ".campusListHome"),
        ):
            candidate = self.page.locator(switch_selector)
            if await candidate.count() > 0:
                switcher = candidate.first
                option_selectors = (campus_selector,)
                break

        if switcher is None:
            raise UnsafeSelectionError(
                "页面没有可用的校区切换控件，拒绝跨校区直接提交"
            )
        await switcher.click()

        option = None
        for campus_selector in option_selectors:
            candidate = self.page.locator(
                f"{campus_selector}[code='{campus_code}']:visible"
            )
            if await candidate.count() > 0:
                option = candidate.first
                break

        if option is None:
            raise UnsafeSelectionError(
                f"页面校区菜单中没有 {CAMPUS[campus_code]}（{campus_code}）"
            )
        await option.click()
        await self.page.wait_for_timeout(1200)
        updated = await self.read_context()
        if updated.current_campus_code != campus_code:
            raise UnsafeSelectionError("页面校区切换未生效，拒绝提交")
        return updated


async def open_visible_browser(
    timeout_seconds: int,
) -> tuple[Any, Any, Any]:
    """启动全新可见浏览器；返回 (playwright, context, page)。"""

    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise AutomationError(
            "缺少 Playwright。先运行："
            "python -m pip install -r 选课/05_工具/requirements-automation.txt"
            "，再运行：python -m playwright install chromium"
        ) from exc

    playwright = await async_playwright().start()
    try:
        # 不使用 persistent context，确保每次启动都没有 Cookie、
        # sessionStorage 或上一次运行留下的登录态。
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(
                ENTRY_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
        except Exception as exc:
            print(f"[提示] 登录入口加载提示：{safe_message(exc)}")

        session = BrowserSession(page)
        print(
            "[等待] 本次启动必须由本人在可见浏览器中手动登录并完成"
            "人机认证；脚本不会读取或填写密码。"
        )
        await session.wait_until_ready(timeout_seconds=timeout_seconds)
        try:
            await page.goto(
                GRAB_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
        except Exception as exc:
            print(f"[提示] 选课页返回提示：{safe_message(exc)}")
        await session.wait_until_ready(timeout_seconds=timeout_seconds)
        return playwright, context, page
    except Exception:
        await playwright.stop()
        raise


async def query_public_courses(
    api: BrowserApi,
    context: SessionContext,
    *,
    campus_code: str,
    page_size: int,
    max_pages: int,
    request_delay: float,
) -> QueryResult:
    if campus_code not in CAMPUS:
        raise AutomationError(f"脚本只允许查询仙林/仙林新北，收到：{campus_code}")

    all_courses: list[Course] = []
    seen_ids: set[str] = set()
    total_count = 0
    pages_visited = 0
    page_number = 0

    while True:
        if pages_visited >= max_pages:
            raise AutomationError(
                f"{CAMPUS[campus_code]} 查询超过 max_pages={max_pages}，"
                "为避免无限请求已停止"
            )
        payload = build_query_payload(
            student_code=context.student_code,
            batch_code=context.batch_code,
            campus_code=campus_code,
            check_conflict="0",
            check_capacity="0",
            page_size=page_size,
            page_number=page_number,
        )
        response = await api.post(PUBLIC_COURSE_PATH, payload)
        if as_text(response.get("code")) != "1":
            raise AutomationError(
                f"{CAMPUS[campus_code]} 查询失败："
                f"{safe_message(response.get('msg')) or '未知原因'}"
            )

        rows = response.get("dataList") or []
        if not isinstance(rows, list):
            raise AutomationError("publicCourse.do 的 dataList 不是数组")
        parsed_total = parse_int(
            response.get("totalCount", response.get("total"))
        )
        if parsed_total is not None:
            total_count = parsed_total
        elif total_count == 0:
            total_count = len(rows)

        pages_visited += 1
        for item in rows:
            if not isinstance(item, Mapping):
                continue
            course = Course.from_api(item, campus_code, CAMPUS[campus_code])
            if course is None or course.teaching_class_id in seen_ids:
                continue
            seen_ids.add(course.teaching_class_id)
            all_courses.append(course)

        if not rows or len(all_courses) >= total_count:
            break
        page_number += 1
        await asyncio.sleep(request_delay)

    return QueryResult(
        campus_code=campus_code,
        campus_name=CAMPUS[campus_code],
        total_count=total_count,
        pages_visited=pages_visited,
        courses=all_courses,
    )


async def run_query_cycle(
    api: BrowserApi,
    context: SessionContext,
    *,
    page_size: int,
    max_pages: int,
    request_delay: float,
    campus_codes: Sequence[str] = ("2", "4"),
) -> tuple[list[QueryResult], list[Course]]:
    results: list[QueryResult] = []
    for index, campus_code in enumerate(campus_codes):
        result = await query_public_courses(
            api,
            context,
            campus_code=campus_code,
            page_size=page_size,
            max_pages=max_pages,
            request_delay=request_delay,
        )
        results.append(result)
        print(
            f"[查询] {result.campus_name}：服务端返回 {result.total_count} 条，"
            f"本次读取 {len(result.courses)} 条（访问 {result.pages_visited} 页）"
        )
        if index < len(campus_codes) - 1:
            await asyncio.sleep(request_delay)

    all_courses = [
        course
        for result in results
        for course in result.courses
    ]
    return results, all_courses


async def query_selected_course_count(
    api: BrowserApi,
    context: SessionContext,
) -> int:
    """按 NNU 页面口径统计当前轮次已选的非实验课程数量。"""

    response = await api.get(
        SELECTED_COURSE_PATH,
        {
            "studentCode": context.student_code,
            "electiveBatchCode": context.batch_code,
            "timestamp": str(int(datetime.now().timestamp() * 1000)),
        },
    )
    if as_text(response.get("code")) != "1":
        raise AutomationError(
            "已选课程数量查询失败："
            f"{safe_message(response.get('msg')) or '未知原因'}"
        )
    data_list = response.get("dataList") or []
    if not isinstance(data_list, list):
        raise AutomationError("courseResult.do 的 dataList 不是数组")
    return sum(
        1
        for item in data_list
        if isinstance(item, Mapping) and as_text(item.get("isTest")) != "1"
    )


def test_option_is_safe(item: Mapping[str, Any]) -> bool:
    """复刻页面对实验教学班的冲突/限制/容量判断。"""

    if parse_flag(first_value(item, "isConflict")) is not False:
        return False
    if parse_flag(first_value(item, "isFull")) is not False:
        return False
    if parse_flag(first_value(item, "isLimitKind")) is True:
        return False
    if parse_flag(first_value(item, "extInfo")) is True:
        return False
    capacity = parse_int(first_value(item, "classCapacity"))
    selected = parse_int(first_value(item, "numberOfSelected"))
    if capacity is not None and selected is not None and selected >= capacity:
        return False
    return True


def write_snapshot(
    path: Path,
    context: SessionContext,
    results: Sequence[QueryResult],
    courses: Sequence[Course],
) -> None:
    payload = {
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "batchName": context.batch_name,
        "filters": {
            "teachingClassType": "XGXK",
            "checkConflict": "0",
            "checkCapacity": "0",
            "keyword": "",
            "category": "",
            "section": "",
        },
        "campuses": [
            {
                "campusCode": result.campus_code,
                "campus": result.campus_name,
                "totalCount": result.total_count,
                "pagesVisited": result.pages_visited,
                "rowsRead": len(result.courses),
            }
            for result in results
        ],
        "courses": [course.public_dict() for course in courses],
    }
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[保存] 已写入脱敏查询快照：{path}")


async def preflight_course(
    api: BrowserApi,
    browser_session: BrowserSession,
    context: SessionContext,
    course: Course,
    *,
    page_size: int,
    max_pages: int,
    request_delay: float,
    need_book: Optional[str],
    test_teaching_class_id: Optional[str],
) -> tuple[SessionContext, Course, Optional[str], Optional[str]]:
    """提交前的最后一次页面对齐、查询、详情、容量和轮次检查。"""

    context = await browser_session.ensure_ui_campus(course.campus_code)
    fresh = await query_public_courses(
        api,
        context,
        campus_code=course.campus_code,
        page_size=page_size,
        max_pages=max_pages,
        request_delay=request_delay,
    )
    fresh_matches = [
        item
        for item in fresh.courses
        if item.teaching_class_id == course.teaching_class_id
    ]
    if len(fresh_matches) != 1:
        raise UnsafeSelectionError(
            "提交前重新查询已找不到唯一的目标教学班，未提交"
        )
    course = fresh_matches[0]

    detail_response = await api.get(
        DETAIL_PATH,
        {
            "xklcdm": context.batch_code,
            "jxbid": course.teaching_class_id,
        },
    )
    if as_text(detail_response.get("code")) != "1":
        raise UnsafeSelectionError(
            "教学班详情刷新未返回成功状态，拒绝提交"
        )
    detail = detail_response.get("data")
    if isinstance(detail, Mapping):
        course = merge_course_data(course, detail)

    capacity_response = await api.get(
        CAPACITY_PATH,
        {
            "teachingClassId": course.teaching_class_id,
            "capacitySuffix": course.capacity_suffix,
            "xh": context.student_code,
            "timestamp": str(int(datetime.now().timestamp() * 1000)),
        },
    )
    if as_text(capacity_response.get("code")) != "1":
        raise UnsafeSelectionError(
            "容量刷新接口未返回成功状态，拒绝提交"
        )
    capacity_data = capacity_response.get("data")
    if isinstance(capacity_data, Mapping):
        course = merge_course_data(course, capacity_data)

    if not course.is_safe_candidate():
        raise UnsafeSelectionError(
            "提交前校验失败：目标课程已冲突、已满或容量字段不一致"
        )
    has_test = parse_flag(course.has_test)
    if has_test is None:
        raise UnsafeSelectionError(
            "未能确认该教学班是否需要实验课，拒绝提交"
        )
    if has_test:
        selected_test_id = (
            test_teaching_class_id or course.test_teaching_class_id
        )
        if not selected_test_id:
            raise UnsafeSelectionError(
                "该教学班需要实验课，但没有明确的实验教学班 ID"
            )
        test_response = await api.post(
            TEST_COURSE_PATH,
            {
                "jxbid": course.teaching_class_id,
                "electiveBatchCode": context.batch_code,
                "studentCode": context.student_code,
                "isMajor": "1",
                "teachingClassType": "XGXK",
                "campus": course.campus_code,
                "checkCapacity": "0",
                "checkConflict": "0",
            },
        )
        if as_text(test_response.get("code")) != "1":
            raise UnsafeSelectionError(
                "实验教学班查询未返回成功状态，拒绝提交"
            )
        test_options: list[Mapping[str, Any]] = []
        for theory in test_response.get("dataList") or []:
            if isinstance(theory, Mapping):
                for option in theory.get("tcList") or []:
                    if isinstance(option, Mapping):
                        test_options.append(option)
        selected_option = next(
            (
                option
                for option in test_options
                if as_text(
                    first_value(
                        option,
                        "teachingClassID",
                        "teachingClassId",
                    )
                )
                == selected_test_id
            ),
            None,
        )
        if selected_option is None or not test_option_is_safe(selected_option):
            raise UnsafeSelectionError(
                "指定的实验教学班不存在、冲突、受限或已满，拒绝提交"
            )
    else:
        if test_teaching_class_id:
            raise UnsafeSelectionError(
                "当前目标课程已确认不含实验课，不接受多余的实验教学班参数"
            )
        selected_test_id = None

    if as_text(context.can_select_book) == "1":
        if need_book not in {"0", "1"}:
            raise UnsafeSelectionError(
                "该轮次允许选择教材，提交前必须明确指定 --need-book 0 或 1"
            )
        selected_need_book = need_book
    else:
        selected_need_book = None

    batch_response = await api.post(
        BATCH_OPEN_PATH,
        {"xklcdm": context.batch_code},
    )
    if as_text(batch_response.get("msg")) != "1":
        raise UnsafeSelectionError(
            "选课轮次当前未确认开放，未提交"
        )
    return context, course, selected_need_book, selected_test_id


async def submit_course(
    api: BrowserApi,
    context: SessionContext,
    course: Course,
    *,
    need_book: Optional[str],
    test_teaching_class_id: Optional[str],
    yes: bool,
) -> int:
    add_payload = build_add_payload(
        student_code=context.student_code,
        batch_code=context.batch_code,
        teaching_class_id=course.teaching_class_id,
        campus_code=course.campus_code,
        need_book=need_book,
        test_teaching_class_id=test_teaching_class_id,
    )
    print("[提交前确认]")
    print(f"  {course.short_label()}")
    print(f"  教师：{course.teacher or '-'}")
    print(f"  时间地点：{course.time or '-'} / {course.teaching_place or '-'}")
    print(
        f"  容量：{course.first_volunteer if course.first_volunteer is not None else '-'}"
        f"/{course.class_capacity if course.class_capacity is not None else '-'}"
    )
    print(f"  教材：{'订购' if need_book == '1' else '不订购'}")
    if test_teaching_class_id:
        print(f"  实验教学班：{test_teaching_class_id}")

    if not yes:
        answer = input(
            f"若确认向 NNU 提交该教学班，请原样输入 "
            f"{course.teaching_class_id}："
        ).strip()
        if answer != course.teaching_class_id:
            print("[停止] 确认文本不匹配，未提交")
            return 0

    response = await api.post(VOLUNTEER_PATH, add_payload)
    code = as_text(response.get("code"))
    if code != "1":
        print(
            "[结果] 服务端未接受提交："
            f"{safe_message(response.get('msg')) or '未知原因'}"
        )
        return 2

    print("[结果] volunteer.do 已接受，等待 studentstatus.do 最终状态")
    for attempt in range(1, 11):
        if attempt > 1:
            await asyncio.sleep(1.0)
        status = await api.post(
            STUDENT_STATUS_PATH,
            {"studentCode": context.student_code},
        )
        status_code = as_text(status.get("code"))
        if status_code == "1":
            print("[结果] 添加选课成功")
            return 0
        if status_code == "-1":
            print(
                "[结果] 添加选课失败："
                f"{safe_message(status.get('msg')) or '未知原因'}"
            )
            return 3
        print(f"[等待] 操作状态仍在处理（第 {attempt}/10 次）")

    print("[结果] 状态轮询超时，请登录页面人工核对选课结果")
    return 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NNU 博雅课：只查询仙林/仙林新北，默认只读"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="没有目标时持续轮询；默认间隔 30 秒",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=30.0,
        help="watch 模式轮询间隔，至少 10 秒",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=1.0,
        help="分页/校区请求之间的间隔，至少 0.5 秒",
    )
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="等待人工登录/认证的秒数",
    )
    parser.add_argument("--course-id", default="", help="精确教学班 ID")
    parser.add_argument("--course-number", default="", help="精确课程号")
    parser.add_argument("--course-name", default="", help="课程名包含匹配")
    parser.add_argument(
        "--submit",
        action="store_true",
        help="启用 volunteer.do 提交；必须同时指定课程筛选",
    )
    parser.add_argument(
        "--auto-select",
        action="store_true",
        help=(
            "配合 --watch/--yes 使用：只轮询仙林，直到已选非实验课程达到 4 门；"
            "期间发现安全候选就自动提交"
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help=(
            "跳过终端二次输入；仅适用于明确指定 --submit 或"
            " --auto-select 的任务"
        ),
    )
    parser.add_argument(
        "--need-book",
        choices=("0", "1"),
        help="轮次允许教材选择时，0=不订购，1=订购",
    )
    parser.add_argument(
        "--test-teaching-class-id",
        default="",
        help="需要实验课时指定实验教学班 ID，脚本会先重新核验",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="可选：写入不含会话信息的 JSON 查询快照",
    )
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    has_selector = bool(
        args.course_id or args.course_number or args.course_name
    )
    if args.submit and not has_selector:
        parser.error("--submit 必须配合 --course-id、--course-number 或 --course-name")
    if args.auto_select and args.submit:
        parser.error("--auto-select 不需要再同时指定 --submit")
    if args.auto_select and not args.watch:
        parser.error("--auto-select 必须配合 --watch，脚本才会持续轮询")
    if args.auto_select and has_selector:
        parser.error("--auto-select 不接受 --course-id、--course-number 或 --course-name")
    if args.auto_select and args.test_teaching_class_id:
        parser.error("--auto-select 不接受固定的 --test-teaching-class-id")
    if args.auto_select and not args.yes:
        parser.error("--auto-select 必须同时指定 --yes 才会自动提交")
    if args.auto_select and args.need_book is None:
        parser.error("--auto-select 必须明确指定 --need-book 0 或 1")
    if args.yes and not (args.submit or args.auto_select):
        parser.error("--yes 只能与 --submit 或 --auto-select 一起使用")
    if args.watch and args.interval < 10:
        parser.error("--watch 的 --interval 不能小于 10 秒")
    if args.request_delay < 0.5:
        parser.error("--request-delay 不能小于 0.5 秒")
    if not 1 <= args.page_size <= 100:
        parser.error("--page-size 必须在 1 到 100 之间")
    if args.max_pages < 1:
        parser.error("--max-pages 必须大于 0")
    if args.timeout < 30:
        parser.error("--timeout 不能小于 30 秒")


async def async_main(args: argparse.Namespace) -> int:
    playwright = context = page = None
    try:
        playwright, context, page = await open_visible_browser(
            args.timeout,
        )
        browser_session = BrowserSession(page)
        session_context = await browser_session.read_context()
        if session_context.teaching_class_type not in {"", "XGXK"}:
            print(
                "[提示] 当前页面教学班类型不是 XGXK；"
                "本工具仍只发送明确的 XGXK 博雅课查询"
            )
        api = BrowserApi(page)
        campus_codes = ("2",) if args.auto_select else ("2", "4")

        while True:
            if args.auto_select:
                selected_count = await query_selected_course_count(
                    api,
                    session_context,
                )
                print(
                    f"[进度] 当前已选非实验课程：{selected_count}/"
                    f"{AUTO_TARGET_COUNT}"
                )
                if selected_count >= AUTO_TARGET_COUNT:
                    print(
                        f"[完成] 已选课程数量已达到 {AUTO_TARGET_COUNT} 门，"
                        "停止自动选课"
                    )
                    return 0

            results, courses = await run_query_cycle(
                api,
                session_context,
                page_size=args.page_size,
                max_pages=args.max_pages,
                request_delay=args.request_delay,
                campus_codes=campus_codes,
            )
            if args.output:
                write_snapshot(
                    args.output,
                    session_context,
                    results,
                    courses,
                )

            if courses:
                print("[候选]")
                for course in courses:
                    print(
                        "  "
                        + json.dumps(
                            course.public_dict(),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    )
            else:
                if args.auto_select:
                    print("[等待] 仙林当前没有服务端返回的“无冲突 + 未满”教学班")
                else:
                    print("[候选] 当前两个校区没有服务端返回的“无冲突 + 未满”教学班")

            if args.auto_select:
                safe_candidates = [
                    course for course in courses if course.is_safe_candidate()
                ]
                if safe_candidates:
                    candidate = safe_candidates[0]
                    print(
                        "[自动选课] 发现安全候选，将按服务端顺序尝试第一门："
                        f" {candidate.short_label()}"
                    )
                    (
                        context_for_submit,
                        fresh_course,
                        selected_need_book,
                        selected_test_id,
                    ) = await preflight_course(
                        api,
                        browser_session,
                        session_context,
                        candidate,
                        page_size=args.page_size,
                        max_pages=args.max_pages,
                        request_delay=args.request_delay,
                        need_book=args.need_book,
                        test_teaching_class_id=None,
                    )
                    submit_result = await submit_course(
                        api,
                        context_for_submit,
                        fresh_course,
                        need_book=selected_need_book,
                        test_teaching_class_id=selected_test_id,
                        yes=args.yes,
                    )
                    if submit_result != 0:
                        return submit_result
                    session_context = await browser_session.read_context()
                    selected_count = await query_selected_course_count(
                        api,
                        session_context,
                    )
                    print(
                        f"[进度] 本次操作后已选非实验课程：{selected_count}/"
                        f"{AUTO_TARGET_COUNT}"
                    )
                    if selected_count >= AUTO_TARGET_COUNT:
                        print(
                            f"[完成] 已选课程数量已达到 {AUTO_TARGET_COUNT} 门，"
                            "停止自动选课"
                        )
                        return 0
                else:
                    print(
                        "[等待] 仙林本轮没有可安全提交的候选，继续轮询"
                    )
            elif args.submit:
                matched = [
                    course
                    for course in courses
                    if course_matches(
                        course,
                        course_id=args.course_id,
                        course_number=args.course_number,
                        course_name=args.course_name,
                    )
                ]
                safe_matched = [
                    course for course in matched if course.is_safe_candidate()
                ]
                if len(safe_matched) == 1:
                    (
                        context_for_submit,
                        fresh_course,
                        selected_need_book,
                        selected_test_id,
                    ) = (
                        await preflight_course(
                            api,
                            browser_session,
                            session_context,
                            safe_matched[0],
                            page_size=args.page_size,
                            max_pages=args.max_pages,
                            request_delay=args.request_delay,
                            need_book=args.need_book,
                            test_teaching_class_id=(
                                args.test_teaching_class_id or None
                            ),
                        )
                    )
                    return await submit_course(
                        api,
                        context_for_submit,
                        fresh_course,
                        need_book=selected_need_book,
                        test_teaching_class_id=selected_test_id,
                        yes=args.yes,
                    )
                if len(safe_matched) > 1:
                    print("[停止] 目标筛选匹配多个教学班，未提交：")
                    for course in safe_matched:
                        print(f"  {course.short_label()}")
                    return 5
                if matched and not safe_matched:
                    print("[停止] 目标课程存在，但当前不满足无冲突/未满，未提交")
                elif args.watch:
                    print("[等待] 目标课程尚未出现，继续按间隔查询")
                else:
                    print("[停止] 没有唯一的安全目标课程，未提交")

            if not args.watch:
                return 0
            await asyncio.sleep(args.interval)
            session_context = await browser_session.read_context()
    except AutomationError as exc:
        print(f"[错误] {safe_message(exc)}", file=sys.stderr)
        return 10
    except KeyboardInterrupt:
        print("\n[停止] 用户中断")
        return 130
    finally:
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                pass


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    validate_args(parser, args)
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
