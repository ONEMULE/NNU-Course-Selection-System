#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NNU 课程查询、已选课程采集与博雅课受控选课工具。

设计原则：

* 只查询仙林校区(code=2)和仙林新北(code=4)；
* 可只读采集 QXKC 全校课程和当前批次已选课程，输出脱敏 JSON/CSV；
* 可选从 Windows 凭据管理器读取并填入学号、密码；验证码/人机认证仍由用户完成；
* 会话 token 只在页面上下文内使用，不导出、不写盘、不打印；
* 无参数启动先进入 TUI，默认加载博雅课自动选择预设；点击应用后才运行；
* 提交前重新查询“不冲突 + 未满”，并刷新课程详情/容量；
* 自动模式先等待服务端确认选课轮次开放，开放前只保持武装轮询；
* 自动目标为 5 个不同 2024 模块，网络博雅最多 2 门，至少 3 门线下；
* 不自动重试 volunteer.do，避免网络不确定时重复提交。
* watch 模式使用固定屏幕 TUI 展示运行时长、轮询、接口和任务进度；
  事件历史有界，不连续刷屏。

该工具依赖 Playwright，但不会修改第三方源码目录，也不会尝试绕过验证码或
人机认证。每次启动都使用全新的临时浏览器会话，不复用上次的登录态。
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import ctypes
import getpass
import json
import os
import re
import shutil
import sys
import time
import unicodedata
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Optional, Sequence


for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


BASE_URL = "https://xsxk.nnu.edu.cn/xsxkapp"
API_PREFIX = "/sys/xsxkapp"
ENTRY_URL = f"{BASE_URL}{API_PREFIX}/*default/index.do"
GRAB_URL = f"{BASE_URL}{API_PREFIX}/*default/grablessons.do"

CREDENTIAL_SERVICE = "NNU-Course-Selection-System"
CREDENTIAL_ACCOUNT = "course-login"

PUBLIC_COURSE_PATH = f"{API_PREFIX}/elective/publicCourse.do"
ALL_SCHOOL_COURSE_PATH = f"{API_PREFIX}/elective/queryCourse.do"
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

BOYA_TEACHING_CLASS_TYPE = "XGXK"
ALL_SCHOOL_TEACHING_CLASS_TYPE = "QXKC"
AUTO_TARGET_COUNT = 5
MAX_NETWORK_COURSES = 2
MIN_OFFLINE_COURSES = AUTO_TARGET_COUNT - MAX_NETWORK_COURSES
REQUIRED_OFFLINE_COURSE = "中国民歌"
REQUIRED_OFFLINE_MODULE = "艺术鉴赏与审美体验"
PREFERRED_AUTO_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (REQUIRED_OFFLINE_MODULE, (REQUIRED_OFFLINE_COURSE,)),
    ("创新与创业", ("创新创业基础", "智能文明")),
    ("身心健康与生命关怀", ("揭秘大气污染",)),
    ("数理基础与科学技术", ("航空航天概论",)),
)
DEFAULT_EXPORT_DIR = Path(__file__).resolve().parent / ".runtime"

# 校园网偶发高延迟时，查询类请求允许有限重试；真正的选课提交永不自动重发。
API_REQUEST_TIMEOUT_MS = 15_000
API_QUERY_RETRIES = 3
API_RETRY_BASE_SECONDS = 0.75

# The mode buttons load a complete, conservative runtime preset.  The values
# are deliberately separate from argparse defaults so the TUI can explain and
# re-apply one coherent configuration after the user has edited individual
# controls.
AUTO_SELECT_PRESET = {
    "interval": 0.1,
    "request_delay": 0.5,
    "page_size": 50,
    "max_pages": 50,
    "timeout": 300,
    "need_book": "0",
    "no_auto_fill": False,
    "output": None,
}
WATCH_PRESET = {
    "interval": 1.0,
    "request_delay": 0.5,
    "page_size": 50,
    "max_pages": 50,
    "timeout": 300,
    "need_book": None,
    "no_auto_fill": False,
    "output": None,
}

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


class NetworkTransientError(AutomationError):
    """可重试的短暂网络故障、超时或上游临时错误。"""


class SubmissionUncertainError(AutomationError):
    """提交请求可能已经到达服务端，但最终结果无法安全确认。"""


class UnsafeSelectionError(AutomationError):
    """安全闸门拒绝提交。"""


class BatchNotOpenError(UnsafeSelectionError):
    """服务端尚未确认当前选课轮次开放。"""


_ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _display_width(value: Any) -> int:
    """计算终端显示宽度，兼容中文和 ANSI 控制序列。"""

    text = _ANSI_ESCAPE_PATTERN.sub("", str(value))
    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return width


def _truncate_display(value: Any, width: int) -> str:
    """按终端显示宽度截断字符串，不让状态栏撑破布局。"""

    text = _ANSI_ESCAPE_PATTERN.sub("", str(value))
    if width <= 0:
        return ""
    if _display_width(text) <= width:
        return text
    suffix = "…"
    suffix_width = _display_width(suffix)
    remaining = max(0, width - suffix_width)
    result: list[str] = []
    current_width = 0
    for char in text:
        char_width = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        if current_width + char_width > remaining:
            break
        result.append(char)
        current_width += char_width
    return "".join(result) + suffix


def _pad_display(value: Any, width: int) -> str:
    text = _truncate_display(value, width)
    return text + (" " * max(0, width - _display_width(text)))


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class _ConsoleCoord(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class _ConsoleChar(ctypes.Union):
    _fields_ = [
        ("UnicodeChar", ctypes.c_wchar),
        ("AsciiChar", ctypes.c_char),
    ]


class _ConsoleKeyEvent(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", ctypes.c_int32),
        ("wRepeatCount", ctypes.c_ushort),
        ("wVirtualKeyCode", ctypes.c_ushort),
        ("wVirtualScanCode", ctypes.c_ushort),
        ("uChar", _ConsoleChar),
        ("dwControlKeyState", ctypes.c_uint32),
    ]


class _ConsoleMouseEvent(ctypes.Structure):
    _fields_ = [
        ("dwMousePosition", _ConsoleCoord),
        ("dwButtonState", ctypes.c_uint32),
        ("dwControlKeyState", ctypes.c_uint32),
        ("dwEventFlags", ctypes.c_uint32),
    ]


class _ConsoleEventUnion(ctypes.Union):
    _fields_ = [
        ("KeyEvent", _ConsoleKeyEvent),
        ("MouseEvent", _ConsoleMouseEvent),
    ]


class _ConsoleInputRecord(ctypes.Structure):
    _fields_ = [
        ("EventType", ctypes.c_ushort),
        ("Event", _ConsoleEventUnion),
    ]


class ConsoleInput:
    """Windows 控制台输入适配器：读取点击和按键并在退出时恢复模式。"""

    STD_INPUT_HANDLE = -10
    KEY_EVENT = 0x0001
    MOUSE_EVENT = 0x0002
    MOUSE_MOVED = 0x0001
    DOUBLE_CLICK = 0x0002
    MOUSE_WHEELED = 0x0004
    LEFT_BUTTON_PRESSED = 0x0001
    CTRL_PRESSED = 0x0008
    VK_RETURN = 0x000D
    VK_ESCAPE = 0x001B
    VK_TAB = 0x0009
    VK_SPACE = 0x0020
    VK_UP = 0x0026
    VK_DOWN = 0x0028
    VK_LEFT = 0x0025
    VK_RIGHT = 0x0027
    ENABLE_MOUSE_INPUT = 0x0010
    ENABLE_EXTENDED_FLAGS = 0x0080
    ENABLE_QUICK_EDIT_MODE = 0x0040

    def __init__(self) -> None:
        self._kernel32: Any = None
        self._handle: Any = None
        self._original_mode: Optional[int] = None
        self.active = False
        self._left_button_down = False

    def start(self) -> bool:
        if os.name != "nt" or not sys.stdin.isatty():
            return False
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetStdHandle.argtypes = [ctypes.c_int32]
            kernel32.GetStdHandle.restype = ctypes.c_void_p
            kernel32.GetConsoleMode.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            kernel32.GetConsoleMode.restype = ctypes.c_int32
            kernel32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel32.SetConsoleMode.restype = ctypes.c_int32
            kernel32.GetNumberOfConsoleInputEvents.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            kernel32.GetNumberOfConsoleInputEvents.restype = ctypes.c_int32
            kernel32.ReadConsoleInputW.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(_ConsoleInputRecord),
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            kernel32.ReadConsoleInputW.restype = ctypes.c_int32

            handle = kernel32.GetStdHandle(self.STD_INPUT_HANDLE)
            invalid_handle = ctypes.c_void_p(-1).value
            if handle in {None, invalid_handle}:
                return False
            mode = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            new_mode = (
                mode.value | self.ENABLE_EXTENDED_FLAGS | self.ENABLE_MOUSE_INPUT
            ) & ~self.ENABLE_QUICK_EDIT_MODE
            if not kernel32.SetConsoleMode(handle, new_mode):
                return False
        except (AttributeError, OSError, TypeError):
            return False

        self._kernel32 = kernel32
        self._handle = handle
        self._original_mode = mode.value
        self._left_button_down = False
        self.active = True
        return True

    def _key_name(self, event: _ConsoleKeyEvent) -> str:
        if event.dwControlKeyState & self.CTRL_PRESSED and (
            event.wVirtualKeyCode == ord("C")
        ):
            return "ctrl-c"
        if event.wVirtualKeyCode == self.VK_RETURN:
            return "enter"
        if event.wVirtualKeyCode == self.VK_ESCAPE:
            return "escape"
        if event.wVirtualKeyCode == self.VK_TAB:
            return "tab"
        if event.wVirtualKeyCode == self.VK_SPACE:
            return "space"
        if event.wVirtualKeyCode == self.VK_UP:
            return "up"
        if event.wVirtualKeyCode == self.VK_DOWN:
            return "down"
        if event.wVirtualKeyCode == self.VK_LEFT:
            return "left"
        if event.wVirtualKeyCode == self.VK_RIGHT:
            return "right"
        char = event.uChar.UnicodeChar
        if char == "\x03":
            return "ctrl-c"
        if char and ord(char) >= 32:
            return char.lower()
        return ""

    def poll(self) -> list[tuple[str, str, int, int]]:
        """非阻塞读取，事件格式为 (kind, value, x, y)。"""

        if not self.active or self._kernel32 is None:
            return []
        events: list[tuple[str, str, int, int]] = []
        pending = ctypes.c_uint32()
        for _ in range(64):
            if not self._kernel32.GetNumberOfConsoleInputEvents(
                self._handle, ctypes.byref(pending)
            ) or pending.value == 0:
                break
            record = _ConsoleInputRecord()
            read = ctypes.c_uint32()
            if not self._kernel32.ReadConsoleInputW(
                self._handle, ctypes.byref(record), 1, ctypes.byref(read)
            ) or read.value == 0:
                break
            if record.EventType == self.KEY_EVENT:
                key_event = record.Event.KeyEvent
                if key_event.bKeyDown:
                    key = self._key_name(key_event)
                    if key:
                        events.append(("key", key, 0, 0))
            elif record.EventType == self.MOUSE_EVENT:
                mouse_event = record.Event.MouseEvent
                flags = mouse_event.dwEventFlags
                left_pressed = bool(
                    mouse_event.dwButtonState & self.LEFT_BUTTON_PRESSED
                )
                if flags in {0, self.DOUBLE_CLICK}:
                    if left_pressed and not self._left_button_down:
                        events.append(
                            (
                                "click",
                                "left",
                                mouse_event.dwMousePosition.X + 1,
                                mouse_event.dwMousePosition.Y + 1,
                            )
                        )
                    self._left_button_down = left_pressed
                elif flags == self.MOUSE_WHEELED:
                    wheel_delta = ctypes.c_short(
                        (mouse_event.dwButtonState >> 16) & 0xFFFF
                    ).value
                    events.append(
                        (
                            "wheel",
                            "up" if wheel_delta > 0 else "down",
                            mouse_event.dwMousePosition.X + 1,
                            mouse_event.dwMousePosition.Y + 1,
                        )
                    )
        return events

    def close(self) -> None:
        if self.active and self._kernel32 is not None and self._original_mode is not None:
            try:
                self._kernel32.SetConsoleMode(self._handle, self._original_mode)
            except (OSError, TypeError):
                pass
        self.active = False
        self._kernel32 = None
        self._handle = None
        self._original_mode = None


class TerminalUI:
    """不刷屏的轻量 TUI；只保留固定数量的事件，避免日志无限增长。"""

    def __init__(
        self,
        mode: str,
        *,
        enabled: Optional[bool] = None,
        target_count: int = AUTO_TARGET_COUNT,
    ) -> None:
        if enabled is None:
            enabled = bool(sys.stdout.isatty())
        self.enabled = bool(enabled)
        self.color = self.enabled and bool(sys.stdout.isatty()) and not os.environ.get(
            "NO_COLOR"
        )
        self.mode = mode
        self.target_count = target_count
        self.started_at = time.monotonic()
        self.phase = "BOOT"
        self.browser_state = "STARTING"
        self.auth_state = "WAITING"
        self.batch_name = "-"
        self.batch_open_status = "N/A"
        self.campus_name = "-"
        self.teaching_class_type = "-"
        self.expected_teaching_class_type = BOYA_TEACHING_CLASS_TYPE
        self.target_campuses = "-"
        self.selector = "-"
        self.policy = (
            "conflict=0 full=0 not-chosen=1 unique-2024-module "
            "network<=2 offline>=3 capacity=checked"
        )
        self.need_book = "-"
        self.interval = "-"
        self.request_delay = "-"
        self.page_size = "-"
        self.max_pages = "-"
        self.login_timeout = "-"
        self.login_mode = "-"
        self.confirmation = "-"
        self.test_teaching_class_id = "-"
        self.snapshot = "-"
        self.tick = 0
        self.selected_boya = 0
        self.selected_network = 0
        self.selected_offline = 0
        self.selected_delivery_unknown = 0
        self.selected_credits: Optional[float] = None
        self.selected_status = "WAIT"
        self.query_status = "WAIT"
        self.query_returned = 0
        self.query_read = 0
        self.query_pages = 0
        self.query_requests = 0
        self.query_errors = 0
        self.query_campuses = "-"
        self.candidate_total = 0
        self.safe_candidate_total = 0
        self.candidate_label = "NONE"
        self.network_monitored = 0
        self.network_leaders = "-"
        self.priority_reason = "-"
        self.submit_attempts = 0
        self.submit_successes = 0
        self.submit_failures = 0
        self.last_action = "IDLE"
        self.next_poll_at: Optional[float] = None
        self.events: deque[tuple[str, str, str]] = deque(maxlen=7)
        self._last_render = 0.0
        self._has_rendered = False
        self._closed = False
        self.view = "status"
        self.mouse_enabled = False
        self.config_notice = ""
        self._config_regions: dict[str, tuple[int, int, int, int]] = {}
        self._config_campus_codes: list[str] = []
        self._config_input: Optional[ConsoleInput] = None
        self._config_args: Any = None

    def configure(
        self,
        args: Any,
        *,
        campus_codes: Sequence[str],
        expected_teaching_class_type: str = BOYA_TEACHING_CLASS_TYPE,
    ) -> None:
        """把本次运行的全部关键参数投影到 TUI，不显示凭据。"""

        self.expected_teaching_class_type = expected_teaching_class_type
        self.target_campuses = ", ".join(
            f"{CAMPUS.get(code, code)}({code})" for code in campus_codes
        ) or "-"
        if getattr(args, "auto_select", False):
            self.selector = (
                "AUTO: 中国民歌 > 创新创业基础|智能文明 > "
                "揭秘大气污染 > 航空航天概论 > 网络热度兜底"
            )
        elif getattr(args, "course_id", ""):
            self.selector = f"teachingClassId={args.course_id}"
        elif getattr(args, "course_number", ""):
            self.selector = f"courseNumber={args.course_number}"
        elif getattr(args, "course_name", ""):
            self.selector = f"courseName~{args.course_name}"
        else:
            self.selector = "READ-ONLY QUERY"
        self.need_book = getattr(args, "need_book", None) or "-"
        self.interval = f"{getattr(args, 'interval', 0):.1f}s"
        self.request_delay = f"{getattr(args, 'request_delay', 0):.1f}s"
        self.page_size = str(getattr(args, "page_size", "-"))
        self.max_pages = str(getattr(args, "max_pages", "-"))
        self.login_timeout = f"{getattr(args, 'timeout', 0)}s"
        self.confirmation = "YES" if getattr(args, "yes", False) else "MANUAL"
        self.test_teaching_class_id = (
            getattr(args, "test_teaching_class_id", "") or "none"
        )
        output = getattr(args, "output", None)
        self.snapshot = str(output) if output else "off"
        self.login_mode = (
            "manual" if getattr(args, "no_auto_fill", False) else "credential-fill"
        )
        self.policy = (
            "safe-only + unique-2024-module + network<=2 + offline>=3 "
            "+ reserve-offline-slot"
        )
        self.batch_open_status = (
            "CHECK" if getattr(args, "auto_select", False) else "N/A"
        )

    @staticmethod
    def _mode_for_args(args: Any) -> str:
        if getattr(args, "auto_select", False):
            return "AUTO-SELECT"
        if getattr(args, "submit", False) and getattr(args, "watch", False):
            return "TARGET WATCH"
        return "WATCH"

    def _config_row(
        self,
        lines: list[str],
        key: str,
        text: str,
    ) -> None:
        row = len(lines)
        lines.append(text)
        # _box() adds one border row before content; terminal coordinates are 1-based.
        terminal_row = row + 2
        self._config_regions[key] = (1, 1000, terminal_row, terminal_row)

    def render_config_text(self, args: Any) -> str:
        """绘制启动前配置页；参数仍写回 argparse.Namespace，不显示凭据。"""

        self._config_regions = {}
        current_mode = self._mode_for_args(args)
        mode_name = {
            "AUTO-SELECT": "自动选课",
            "TARGET WATCH": "目标提交",
            "WATCH": "只监控",
        }.get(current_mode, current_mode)
        campus_2 = "2" in self._config_campus_codes
        campus_4 = "4" in self._config_campus_codes
        raw_need_book = getattr(args, "need_book", None)
        need_book = {
            "0": "不订教材",
            "1": "订购教材",
        }.get(raw_need_book, "未指定")
        confirmation = "是" if getattr(args, "yes", False) else "否"
        login_mode = "手动输入" if getattr(args, "no_auto_fill", False) else "自动填入"
        snapshot = getattr(args, "output", None)
        auto_selected = current_mode == "AUTO-SELECT"
        auto_radio = self._paint(
            "[*] 自动选课" if auto_selected else "[ ] 自动选课",
            "32;1" if auto_selected else "90",
        )
        watch_radio = self._paint(
            "[*] 只监控" if not auto_selected else "[ ] 只监控",
            "36;1" if not auto_selected else "90",
        )
        campus_2_mark = self._paint("[开]", "32;1") if campus_2 else self._paint("[关]", "90")
        campus_4_mark = self._paint("[开]", "32;1") if campus_4 else self._paint("[关]", "90")
        locked_mark = self._paint("[锁定]", "33;1")
        preset_name = "自动选课" if auto_selected else "只监控"
        preset_button = self._paint(f"[恢复{preset_name}预设]", "35;1")
        snapshot_label = "关闭" if snapshot is None else "开启"
        test_class_id = getattr(args, "test_teaching_class_id", "") or "无"
        interval_value = self.interval.replace("s", "秒")
        request_delay_value = self.request_delay.replace("s", "秒")
        login_timeout_value = self.login_timeout.replace("s", "秒")
        test_class_button = (
            self._paint("[锁定]", "33;1")
            if auto_selected
            else self._paint(
                "[编辑]" if getattr(args, "submit", False) else "[不可用]",
                "36;1" if getattr(args, "submit", False) else "90",
            )
        )
        lines = [
            self._paint(
                "NNU // 博雅课控制台   |   启动配置（鼠标可操作）",
                "36;1",
            ),
            self._paint(
                f"阶段 CONFIG   当前模式={mode_name}({current_mode})  "
                "点击应用后打开登录页",
                "36",
            ),
            self._paint(
                "鼠标：左键切换/循环·滚轮调数值  [*]当前  R预设  A/回车应用  Q/Esc退出",
                "90",
            ),
            self._paint(
                "快捷键：S/W模式·R预设·E目标·2/4校区·B教材·I/D/P/M/T参数",
                "90",
            ),
            self._paint(
                "         L登录填充·Y确认·O快照·X实验班",
                "90",
            ),
        ]
        self._config_row(
            lines,
            "selector",
            f"目标课程 [编辑] {_truncate_display(self.selector, 54)}  "
            f"查询类型={self.expected_teaching_class_type}  点击/E编辑",
        )
        self._config_row(
            lines,
            "mode-auto",
            f"模式 A   {auto_radio}  指定课优先·2024模块互斥·网络热度兜底 (S/点击)",
        )
        self._config_row(
            lines,
            "mode-watch",
            f"模式 W   {watch_radio}  只查询不提交，适合先观察 (W/点击)",
        )
        self._config_row(
            lines,
            "preset",
            f"完整预设 {preset_button}  1秒·0.5秒·50条/页·50页·登录300秒·自动填充·快照关",
        )
        self._config_row(
            lines,
            "campus-2",
            f"校区 2   {campus_2_mark}  仙林校区 (2)"
            + ("  自动模式锁定" if current_mode == "AUTO-SELECT" else "  点击切换"),
        )
        self._config_row(
            lines,
            "campus-4",
            f"校区 4   {campus_4_mark}  仙林新北 (4)"
            + ("  自动模式锁定" if current_mode == "AUTO-SELECT" else "  点击切换"),
        )
        self._config_row(
            lines,
            "policy",
            f"安全规则 {locked_mark} 无冲突·未满·未选·不同模块·中国民歌保留位·"
            f"网络≤{MAX_NETWORK_COURSES}·线下≥{MIN_OFFLINE_COURSES}·<{AUTO_TARGET_COUNT}门",
        )
        self._config_row(
            lines,
            "book",
            f"教材选择 [{need_book}]  点击/B：切换不订教材/订购教材",
        )
        self._config_row(
            lines,
            "interval",
            f"轮询间隔 [{interval_value}]  点击/滚轮：0.1·0.2·0.5·1·2·5秒",
        )
        self._config_row(
            lines,
            "request-delay",
            f"请求间隔 [{request_delay_value}]  点击/滚轮：0.5·1·2·5秒",
        )
        self._config_row(
            lines,
            "page-size",
            f"每页数量 [{self.page_size}条]  点击/滚轮：10·20·50·100条",
        )
        self._config_row(
            lines,
            "max-pages",
            f"最大页数 [{self.max_pages}页]  点击/滚轮：10·50·100·200页",
        )
        self._config_row(
            lines,
            "timeout",
            f"登录等待 [{login_timeout_value}]  点击/滚轮：60·120·300·600秒",
        )
        self._config_row(
            lines,
            "login",
            f"登录填充 [{login_mode}]  点击/L切换；只填学号密码，认证始终人工",
        )
        self._config_row(
            lines,
            "confirm",
            f"自动确认 [当前={confirmation}]  "
            + (
                "自动模式固定为是（安全锁定）"
                if current_mode == "AUTO-SELECT"
                else "仅目标提交模式可点击切换"
            ),
        )
        self._config_row(
            lines,
            "output",
            f"快照输出 [{snapshot_label}]  点击/O：保存 .runtime/latest.json / 关闭",
        )
        self._config_row(
            lines,
            "test-class",
            f"实验班ID {test_class_button} 当前={_truncate_display(test_class_id, 24)}  "
            + (
                "自动模式不使用实验班"
                if auto_selected
                else (
                    "仅目标提交模式有效；点击/X编辑"
                    if getattr(args, "submit", False)
                    else "先编辑目标课程后才可设置"
                )
            ),
        )
        lines.extend(
            [
                (
                    "说明  优先：中国民歌 > 创新创业基础/智能文明 > 揭秘大气污染 > 航空航天概论。"
                ),
                (
                    f"说明  目标{AUTO_TARGET_COUNT}个不同2024模块；网络最多{MAX_NETWORK_COURSES}门、"
                    f"线下至少{MIN_OFFLINE_COURSES}门；网络人数增量只用于热度兜底；认证人工。"
                ),
                (
                    f"提示  {_truncate_display(self.config_notice or '准备就绪', 92)}"
                ),
            ]
        )
        self._config_row(
            lines,
            "apply",
            self._paint(
                "[ 应用并启动 ]  使用当前设置并打开登录浏览器",
                "32;1",
            ),
        )
        self._config_row(
            lines,
            "cancel",
            self._paint(
                "[ 取消退出 ]      不打开浏览器并退出",
                "31;1",
            ),
        )
        lines.append(
            "安全  查询使用页面上下文XHR；提交只能由自动选课或明确的目标提交模式触发。"
        )
        return "\n".join(self._box(lines))

    def _config_refresh(self, args: Any) -> None:
        self.mode = self._mode_for_args(args)
        self.configure(args, campus_codes=self._config_campus_codes)

    def _set_config_mode(self, args: Any, mode: str) -> str:
        preset = AUTO_SELECT_PRESET if mode == "AUTO-SELECT" else WATCH_PRESET
        args.interval = preset["interval"]
        args.request_delay = preset["request_delay"]
        args.page_size = preset["page_size"]
        args.max_pages = preset["max_pages"]
        args.timeout = preset["timeout"]
        args.need_book = preset["need_book"]
        args.no_auto_fill = preset["no_auto_fill"]
        args.output = preset["output"]
        args.course_id = ""
        args.course_number = ""
        args.course_name = ""
        args.test_teaching_class_id = ""
        if mode == "AUTO-SELECT":
            args.watch = True
            args.auto_select = True
            args.submit = False
            args.yes = True
            self._config_campus_codes = ["2"]
            return (
                "已加载自动选课完整预设：0.1秒轮询、0.5秒分页间隔、每页50条、"
                "最多50页、登录等待300秒、自动填充、关闭快照；范围锁定仙林校区(2)"
            )

        args.watch = True
        args.auto_select = False
        args.submit = False
        args.yes = False
        self._config_campus_codes = ["2", "4"]
        return (
            "已加载只监控完整预设：1秒轮询、0.5秒请求间隔、每页50条、"
            "最多50页、登录等待300秒、自动填充、关闭快照；不会自动提交"
        )

    def _cycle_config_value(
        self,
        current: Any,
        values: Sequence[Any],
        delta: int,
    ) -> Any:
        try:
            index = list(values).index(current)
        except ValueError:
            index = 0
        return values[(index + (1 if delta >= 0 else -1)) % len(values)]

    def _change_config(self, key: str, args: Any, *, delta: int = 1) -> str:
        if key == "mode-auto":
            message = self._set_config_mode(args, "AUTO-SELECT")
        elif key == "mode-watch":
            message = self._set_config_mode(args, "WATCH")
        elif key == "preset":
            message = self._set_config_mode(
                args,
                "AUTO-SELECT" if args.auto_select else "WATCH",
            )
        elif key in {"campus-2", "campus-4"}:
            code = "2" if key == "campus-2" else "4"
            if args.auto_select:
                return "自动选课已锁定请求校区为仙林校区(2)"
            if code in self._config_campus_codes:
                if len(self._config_campus_codes) == 1:
                    return "至少保留一个请求校区"
                self._config_campus_codes.remove(code)
                message = f"已关闭校区：{CAMPUS[code]}"
            else:
                self._config_campus_codes.append(code)
                self._config_campus_codes.sort()
                message = f"已开启校区：{CAMPUS[code]}"
        elif key == "book":
            args.need_book = "1" if getattr(args, "need_book", None) != "1" else "0"
            message = f"教材选择：{'订购' if args.need_book == '1' else '不订购'}"
        elif key == "interval":
            args.interval = self._cycle_config_value(
                float(args.interval), (0.1, 0.2, 0.5, 1.0, 2.0, 5.0), delta
            )
            message = f"轮询间隔：{args.interval:.1f}秒"
        elif key == "request-delay":
            args.request_delay = self._cycle_config_value(
                float(args.request_delay), (0.5, 1.0, 2.0, 5.0), delta
            )
            message = f"请求间隔：{args.request_delay:.1f}秒"
        elif key == "page-size":
            args.page_size = self._cycle_config_value(
                int(args.page_size), (10, 20, 50, 100), delta
            )
            message = f"每页数量：{args.page_size}条"
        elif key == "max-pages":
            args.max_pages = self._cycle_config_value(
                int(args.max_pages), (10, 50, 100, 200), delta
            )
            message = f"最大页数：{args.max_pages}页"
        elif key == "timeout":
            args.timeout = self._cycle_config_value(
                int(args.timeout), (60, 120, 300, 600), delta
            )
            message = f"登录等待：{args.timeout}秒"
        elif key == "login":
            args.no_auto_fill = not args.no_auto_fill
            message = "登录填充：手动输入" if args.no_auto_fill else "登录填充：自动填入"
        elif key == "confirm":
            if args.auto_select:
                return "自动选课确认已锁定为是"
            if not args.submit:
                return "只监控模式不会提交，确认按钮不可用"
            args.yes = not args.yes
            message = f"提交确认：{'自动确认' if args.yes else '每次询问'}"
        elif key == "policy":
            return (
                "安全规则已锁定：无冲突、未满、未选、2024模块互斥、"
                "中国民歌线下保留位、提交前容量复核"
            )
        elif key == "output":
            args.output = (
                None
                if getattr(args, "output", None)
                else DEFAULT_EXPORT_DIR / "latest.json"
            )
            message = "查询快照已关闭" if args.output is None else "查询快照已开启"
        elif key == "selector":
            return "目标课程将打开编辑输入：auto、watch、id:、number: 或 name:"
        elif key == "test-class":
            return "实验班ID将打开编辑输入，仅目标提交模式有效"
        else:
            return ""
        self._config_refresh(args)
        return message

    def _config_hit(self, x: int, y: int) -> Optional[str]:
        for key, (left, right, top, bottom) in self._config_regions.items():
            if left <= x <= right and top <= y <= bottom:
                return key
        return None

    def _handle_config_event(
        self,
        event: tuple[str, str, int, int],
        args: Any,
    ) -> Optional[str]:
        kind, value, x, y = event
        if kind == "key":
            if value in {"ctrl-c", "escape", "q"}:
                return "cancel"
            if value in {"enter", "a"}:
                return "apply"
            key_map = {
                "s": "mode-auto",
                "w": "mode-watch",
                "r": "preset",
                "e": "selector",
                "2": "campus-2",
                "4": "campus-4",
                "b": "book",
                "i": "interval",
                "d": "request-delay",
                "p": "page-size",
                "m": "max-pages",
                "t": "timeout",
                "l": "login",
                "y": "confirm",
                "o": "output",
                "x": "test-class",
                "space": "book",
            }
            key = key_map.get(value)
            if key is None:
                return None
            if key == "selector":
                return "edit-selector"
            if key == "test-class":
                if args.auto_select or not args.submit:
                    message = self._change_config(key, args)
                else:
                    return "edit-test-class"
            else:
                message = self._change_config(key, args)
        elif kind == "click":
            key = self._config_hit(x, y)
            if key in {"apply", "cancel"}:
                return key
            if key is None:
                return None
            if key == "selector":
                return "edit-selector"
            if key == "test-class":
                if args.auto_select or not args.submit:
                    message = self._change_config(key, args)
                else:
                    return "edit-test-class"
            else:
                message = self._change_config(key, args)
        elif kind == "wheel":
            key = self._config_hit(x, y)
            if key not in {
                "interval",
                "request-delay",
                "page-size",
                "max-pages",
                "timeout",
            }:
                return None
            message = self._change_config(
                key,
                args,
                delta=1 if value == "up" else -1,
            )
        else:
            return None
        self.config_notice = message
        self.event(message, "CFG", render=False)
        self.render(force=True)
        return None

    async def _edit_selector(
        self,
        args: Any,
        console_input: ConsoleInput,
    ) -> bool:
        """鼠标点击目标行后进入短暂文本编辑，再恢复鼠标事件读取。"""

        console_input.close()
        self.mouse_enabled = False
        self.pause_for_input()
        try:
            choice = await asyncio.to_thread(
                input,
                "\n[TUI] 目标课程（auto|watch|id:<ID>|number:<课程号>|name:<课程名>）：",
            )
        except (EOFError, KeyboardInterrupt):
            self.config_notice = "目标课程编辑已取消"
        else:
            spec = choice.strip()
            lowered = spec.lower()
            if not spec:
                self.config_notice = "目标课程未修改"
            elif lowered == "auto":
                self.config_notice = self._set_config_mode(args, "AUTO-SELECT")
                self._config_refresh(args)
            elif lowered in {"watch", "readonly", "read-only"}:
                self.config_notice = self._set_config_mode(args, "WATCH")
                self._config_refresh(args)
            elif ":" not in spec:
                self.config_notice = "目标格式错误：请输入 auto、watch、id:、number: 或 name:"
            else:
                kind, value = spec.split(":", 1)
                value = value.strip()
                field = {
                    "id": "course_id",
                    "number": "course_number",
                    "name": "course_name",
                }.get(kind.lower())
                if field is None or not value:
                    self.config_notice = (
                        "目标格式错误：请输入 id:<ID>、number:<课程号> 或 name:<课程名>"
                    )
                else:
                    args.watch = True
                    args.auto_select = False
                    args.submit = True
                    args.yes = False
                    args.course_id = ""
                    args.course_number = ""
                    args.course_name = ""
                    setattr(args, field, value)
                    self._config_refresh(args)
                    self.config_notice = f"已启用目标提交：{field}={value}"
        finally:
            self.resume_after_input()
            self.mouse_enabled = console_input.start()
            if not self.mouse_enabled:
                self.config_notice = (
                    "鼠标输入无法恢复，配置已取消"
                )
        self.event(self.config_notice, "CFG", render=False)
        self.render(force=True)
        return self.mouse_enabled

    async def _edit_test_class(
        self,
        args: Any,
        console_input: ConsoleInput,
    ) -> bool:
        """编辑明确目标提交所需的实验教学班 ID；自动模式不允许猜选。"""

        console_input.close()
        self.mouse_enabled = False
        self.pause_for_input()
        try:
            choice = await asyncio.to_thread(
                input,
                "\n[TUI] 实验教学班ID（留空清除，仅目标提交模式可用）：",
            )
        except (EOFError, KeyboardInterrupt):
            self.config_notice = "实验班ID编辑已取消"
        else:
            value = choice.strip()
            if args.auto_select:
                self.config_notice = "自动选课模式不使用实验教学班ID"
            elif not args.submit:
                self.config_notice = "请先在目标课程中选择具体课程，实验班ID才可设置"
            else:
                args.test_teaching_class_id = value
                self.config_notice = (
                    "实验班ID已清除" if not value else f"已设置实验班ID：{value}"
                )
        finally:
            self.resume_after_input()
            self.mouse_enabled = console_input.start()
            if not self.mouse_enabled:
                self.config_notice = "鼠标输入无法恢复，配置已取消"
        self.event(self.config_notice, "CFG", render=False)
        self.render(force=True)
        return self.mouse_enabled

    async def configure_interactively(
        self,
        args: Any,
        *,
        campus_codes: Sequence[str],
        expected_teaching_class_type: str = BOYA_TEACHING_CLASS_TYPE,
    ) -> Optional[tuple[str, ...]]:
        """在打开浏览器前提供鼠标配置页；非交互终端直接沿用命令行参数。"""

        selected_campuses = tuple(campus_codes)
        if not self.enabled or not sys.stdin.isatty():
            return selected_campuses

        self._config_args = args
        self._config_campus_codes = list(campus_codes)
        self.expected_teaching_class_type = expected_teaching_class_type
        self.view = "config"
        self.phase = "CONFIG"
        self.config_notice = "准备就绪；检查设置后点击“应用并启动”"
        self.configure(args, campus_codes=self._config_campus_codes)
        console_input = ConsoleInput()
        self._config_input = console_input
        self.mouse_enabled = console_input.start()
        if self.mouse_enabled:
            self.config_notice = "鼠标已启用；可点击按钮或使用键盘快捷键"
        else:
            self.config_notice = "鼠标不可用；可使用键盘快捷键或回车/Q"
        self.render(force=True)
        applied = False
        cancelled = False
        try:
            if not self.mouse_enabled:
                self.pause_for_input()
                try:
                    choice = await asyncio.to_thread(
                        input,
                        "\n[TUI] 鼠标不可用；回车应用，Q取消：",
                    )
                except (EOFError, KeyboardInterrupt):
                    cancelled = True
                else:
                    cancelled = choice.strip().lower() in {"q", "quit", "cancel"}
                    applied = not cancelled
                finally:
                    self.resume_after_input()
            else:
                while not applied and not cancelled:
                    for event in console_input.poll():
                        action = self._handle_config_event(event, args)
                        if action == "apply":
                            applied = True
                            break
                        if action == "cancel":
                            cancelled = True
                            break
                        if action == "edit-selector":
                            if not await self._edit_selector(args, console_input):
                                cancelled = True
                                break
                        if action == "edit-test-class":
                            if not await self._edit_test_class(args, console_input):
                                cancelled = True
                                break
                    if not applied and not cancelled:
                        await asyncio.sleep(0.05)
        finally:
            console_input.close()
            self._config_input = None
            self.mouse_enabled = False
            self.view = "status"
            self._config_args = None
            self._config_regions = {}

        if cancelled:
            self.phase = "STOP"
            self.event("配置已取消", "STOP", render=False)
            self.render(force=True)
            return None
        self.mode = self._mode_for_args(args)
        self.phase = "BOOT"
        self.configure(args, campus_codes=self._config_campus_codes)
        self.event("配置已应用；正在打开登录浏览器", "OK", render=False)
        self.render(force=True)
        return tuple(self._config_campus_codes)

    def _paint(self, value: str, code: str) -> str:
        if not self.color:
            return value
        return f"\x1b[{code}m{value}\x1b[0m"

    def set_phase(self, phase: str, *, render: bool = True) -> None:
        self.phase = phase
        if render:
            self.render(force=True)

    def set_session(
        self,
        *,
        browser: Optional[str] = None,
        auth: Optional[str] = None,
        context: Optional["SessionContext"] = None,
        render: bool = True,
    ) -> None:
        if browser is not None:
            self.browser_state = browser
        if auth is not None:
            self.auth_state = auth
        if context is not None:
            self.batch_name = context.batch_name or "-"
            self.campus_name = context.current_campus_name or "-"
            self.teaching_class_type = context.teaching_class_type or "-"
        if render:
            self.render(force=True)

    def event(
        self,
        message: str,
        level: str = "INFO",
        *,
        render: bool = True,
    ) -> None:
        self.events.append(
            (format_duration(time.monotonic() - self.started_at), level, message)
        )
        if render:
            self.render(force=True)

    def selected(
        self,
        count: int,
        *,
        credits: Optional[float] = None,
        network_count: Optional[int] = None,
        offline_count: Optional[int] = None,
        unknown_count: Optional[int] = None,
        status: str = "OK",
        render: bool = True,
    ) -> None:
        self.selected_boya = max(0, count)
        self.selected_credits = credits
        if network_count is not None:
            self.selected_network = max(0, network_count)
        if offline_count is not None:
            self.selected_offline = max(0, offline_count)
        if unknown_count is not None:
            self.selected_delivery_unknown = max(0, unknown_count)
        self.selected_status = status
        if render:
            self.render(force=True)

    def batch_open(self, is_open: bool, *, render: bool = True) -> None:
        self.batch_open_status = "OPEN" if is_open else "WAIT"
        if render:
            self.render(force=True)

    def query(
        self,
        result: "QueryResult",
        *,
        status: str = "OK",
        render: bool = True,
    ) -> None:
        self.query_status = status
        self.query_requests += 1
        self.query_returned = result.total_count
        self.query_read = len(result.courses)
        self.query_pages = result.pages_visited
        self.query_campuses = (
            f"{result.campus_name} {result.total_count}/{len(result.courses)}"
        )
        if status != "OK":
            self.query_errors += 1
        if render:
            self.render(force=True)

    def cycle(
        self,
        results: Sequence["QueryResult"],
        courses: Sequence["Course"],
        *,
        safe_candidates: Sequence["Course"] = (),
        elapsed: Optional[float] = None,
        render: bool = True,
    ) -> None:
        self.tick += 1
        self.query_status = "OK"
        self.query_returned = sum(result.total_count for result in results)
        self.query_read = len(courses)
        self.query_pages = sum(result.pages_visited for result in results)
        self.query_campuses = ", ".join(
            f"{result.campus_name} {result.total_count}/{len(result.courses)}"
            for result in results
        ) or "-"
        self.candidate_total = len(courses)
        self.safe_candidate_total = len(safe_candidates)
        if safe_candidates:
            self.candidate_label = safe_candidates[0].short_label()
        else:
            self.candidate_label = "NONE"
        elapsed_label = "-" if elapsed is None else f"{elapsed:.2f}s"
        self.event(
            f"cycle #{self.tick:04d} complete | returned={self.query_returned} "
            f"read={self.query_read} safe={self.safe_candidate_total} "
            f"elapsed={elapsed_label}",
            "POLL",
            render=False,
        )
        if render:
            self.render(force=True)

    def network_metrics(
        self,
        courses: Sequence["Course"],
        growth: Mapping[str, int],
        ranked: Sequence["AutoCandidate"],
        *,
        render: bool = True,
    ) -> None:
        network_courses = [course for course in courses if course.is_network_course()]
        leaders = network_growth_leaders(network_courses, growth, limit=3)
        self.network_monitored = len(network_courses)
        self.network_leaders = " | ".join(
            f"{course.course_name} Δ+{growth.get(course.teaching_class_id, 0)} "
            f"{course.demand_count()}/{course.class_capacity or '-'}"
            for course in leaders
        ) or "-"
        self.priority_reason = ranked[0].reason if ranked else "WAIT"
        if render:
            self.render(force=True)

    def action(self, message: str, *, level: str = "ACT", render: bool = True) -> None:
        self.last_action = message
        self.event(message, level, render=render)

    def error(self, message: str, *, render: bool = True) -> None:
        self.query_errors += 1
        self.query_status = "ERR"
        self.phase = "ERROR"
        self.event(message, "ERR", render=render)

    def submission(self, state: str, *, render: bool = True) -> None:
        self.last_action = state
        if state.startswith("SUCCESS"):
            self.submit_successes += 1
        elif state.startswith("FAILED"):
            self.submit_failures += 1
        if render:
            self.render(force=True)

    def _progress_bar(self) -> str:
        width = 18
        ratio = min(1.0, self.selected_boya / self.target_count) if self.target_count else 1
        filled = int(width * ratio)
        return "[" + ("█" * filled) + ("░" * (width - filled)) + "]"

    def _credit_progress(self) -> str:
        if self.selected_credits is None:
            return "?"
        return f"{self.selected_credits:g}"

    def _box(self, lines: Sequence[str]) -> list[str]:
        columns = shutil.get_terminal_size((108, 30)).columns
        total_width = max(80, min(120, columns))
        inner_width = total_width - 2
        body_width = inner_width - 2
        output = ["┌" + ("─" * inner_width) + "┐"]
        for line in lines:
            output.append("│ " + _pad_display(line, body_width) + " │")
        output.append("└" + ("─" * inner_width) + "┘")
        return output

    def render_text(self) -> str:
        elapsed = time.monotonic() - self.started_at
        if self.next_poll_at is None:
            next_poll = "NOW"
        else:
            next_poll = f"{max(0.0, self.next_poll_at - time.monotonic()):04.1f}s"
        terminal_rows = shutil.get_terminal_size((108, 30)).lines
        # Keep the fixed dashboard inside a small terminal whenever possible;
        # one event is preferable to letting the screen scroll on every poll.
        event_slots = max(1, min(7, terminal_rows - 20))
        events = list(self.events)[-event_slots:]
        event_lines = [
            f"{stamp} [{level:<4}] {_truncate_display(message, 90)}"
            for stamp, level, message in events
        ]
        while len(event_lines) < event_slots:
            event_lines.insert(0, "-")
        lines = [
            self._paint(
                "NNU // BOYA WATCHDOG   |   LIVE COURSE SELECTION MONITOR",
                "36;1",
            ),
            (
                f"MODE {self.mode:<12} PHASE {self.phase:<12} "
                f"UPTIME {format_duration(elapsed)}   CYCLE {self.tick:04d}   "
                f"NEXT {next_poll}"
            ),
            (
                f"SESSION  browser={self.browser_state:<10} auth={self.auth_state:<10} "
                f"ui-campus={self.campus_name}"
            ),
            (
                f"BATCH    {_truncate_display(self.batch_name, 54)}  "
                f"pageType={self.teaching_class_type} "
                f"expected={self.expected_teaching_class_type} "
                f"open={self.batch_open_status}"
            ),
            (
                f"SCOPE    request-campus={_truncate_display(self.target_campuses, 56)} "
                f"query-type={self.expected_teaching_class_type}"
            ),
            (
                f"SELECTOR {_truncate_display(self.selector, 92)}"
            ),
            (
                f"POLICY   {self.policy}"
            ),
            (
                f"PROGRESS BOYA THEORY {self._progress_bar()} "
                f"{self.selected_boya}/{self.target_count}  "
                f"NET {self.selected_network}/{MAX_NETWORK_COURSES} "
                f"OFF {self.selected_offline}/{MIN_OFFLINE_COURSES} "
                f"UNK {self.selected_delivery_unknown}  "
                f"CREDITS {self._credit_progress()}"
            ),
            (
                f"SELECTED courseResult.do status={self.selected_status:<4} "
                f"boya-theory={self.selected_boya}/{self.target_count} "
                f"need-book={self.need_book} confirm={self.confirmation}"
            ),
            (
                f"QUERY    XGXK/publicCourse.do  status={self.query_status:<4} "
                f"returned={self.query_returned:<4} read={self.query_read:<4} "
                f"pages={self.query_pages:<3} req={self.query_requests:<5}"
            ),
            (
                f"CONFIG   interval={self.interval} delay={self.request_delay} "
                f"page={self.page_size} max-pages={self.max_pages} "
                f"login-timeout={self.login_timeout} login={self.login_mode} "
                f"test-class={_truncate_display(self.test_teaching_class_id, 20)}"
            ),
            f"CAMPUS   result={_truncate_display(self.query_campuses, 92)}",
            (
                f"CANDIDATE total={self.candidate_total:<3} "
                f"safe={self.safe_candidate_total:<3}  "
                f"current={_truncate_display(self.candidate_label, 62)}"
            ),
            (
                f"NETWORK  monitored={self.network_monitored:<3} "
                f"next={_truncate_display(self.priority_reason, 34)}  "
                f"movers={_truncate_display(self.network_leaders, 48)}"
            ),
            (
                f"SUBMIT   attempts={self.submit_attempts:<3} "
                f"success={self.submit_successes:<3} failures={self.submit_failures:<3} "
                f"last={_truncate_display(self.last_action, 28)} "
                f"snapshot={_truncate_display(self.snapshot, 24)}"
            ),
            (
                f"HEALTH   errors={self.query_errors:<3}  memory=bounded-per-cycle  "
                f"events={len(self.events)}/7  transport=page-context-XHR"
            ),
            "─ ACTIVITY ─────────────────────────────────────────────────────────────",
            *event_lines,
            "CTRL     Ctrl+C stop  |  browser login/CAPTCHA is manual  |  no DOM scraping",
        ]
        return "\n".join(self._box(lines))

    def render(self, *, force: bool = False) -> None:
        if not self.enabled or self._closed:
            return
        now = time.monotonic()
        if not force and now - self._last_render < 0.15:
            return
        if self.view == "config" and self._config_args is not None:
            text = self.render_config_text(self._config_args)
        else:
            text = self.render_text()
        lines = text.splitlines()
        if self.color:
            for index in range(len(lines)):
                if index in {1, 2}:
                    lines[index] = self._paint(lines[index], "36")
        prefix = "\x1b[H\x1b[J"
        if not self._has_rendered:
            prefix = "\x1b[2J\x1b[H\x1b[?25l"
            self._has_rendered = True
        sys.stdout.write(prefix + "\n".join(lines) + "\n")
        sys.stdout.flush()
        self._last_render = now

    def start(self) -> None:
        self.render(force=True)

    def pause_for_input(self) -> None:
        if self.enabled:
            sys.stdout.write("\x1b[?25h\n")
            sys.stdout.flush()

    def resume_after_input(self) -> None:
        if self.enabled:
            self._has_rendered = True
            self.render(force=True)

    async def wait(self, seconds: float) -> None:
        if not self.enabled:
            await asyncio.sleep(seconds)
            return
        self.next_poll_at = time.monotonic() + max(0.0, seconds)
        self.phase = "SLEEP"
        while True:
            remaining = self.next_poll_at - time.monotonic()
            if remaining <= 0:
                break
            self.render()
            await asyncio.sleep(min(0.2, remaining))
        self.next_poll_at = None

    def close(self) -> None:
        if not self.enabled or self._closed:
            return
        self._closed = True
        if self._config_input is not None:
            self._config_input.close()
            self._config_input = None
        sys.stdout.write("\x1b[?25h\x1b[0m\n")
        sys.stdout.flush()


@dataclass(frozen=True)
class LoginCredentials:
    """只在当前进程内短暂保存的登录字段；不写入脚本或普通配置文件。"""

    student_code: str
    password: str


def _load_keyring(*, required: bool) -> Any:
    """加载 keyring；Windows 上由 keyring 选择系统凭据管理器后端。"""

    try:
        import keyring
    except ModuleNotFoundError as exc:
        if required:
            raise AutomationError(
                "缺少 keyring。先运行："
                "python -m pip install -r 选课/05_工具/requirements-automation.txt"
            ) from exc
        return None

    if sys.platform != "win32":
        if required:
            raise AutomationError("自动保存登录凭据仅支持 Windows 凭据管理器")
        return None

    try:
        backend = keyring.get_keyring()
    except Exception as exc:
        if required:
            raise AutomationError(
                "无法初始化 Windows 凭据管理器后端"
            ) from exc
        return None
    backend_type = type(backend)
    if (
        backend_type.__module__ != "keyring.backends.Windows"
        or backend_type.__name__ != "WinVaultKeyring"
    ):
        if required:
            raise AutomationError(
                "当前 keyring 未使用 Windows 凭据管理器后端；"
                "为避免明文保存，未读写登录凭据"
            )
        return None
    return keyring


def serialize_login_credentials(credentials: LoginCredentials) -> str:
    """生成放入系统凭据库的单个密文值，不用于普通文件存储。"""

    return json.dumps(
        {
            "studentCode": credentials.student_code,
            "password": credentials.password,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def parse_login_credentials(raw: str) -> LoginCredentials:
    """校验并解析从系统凭据库取出的值，错误信息不回显原文。"""

    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise AutomationError("保存的登录凭据格式无效，请重新运行 --setup-credentials") from exc

    if not isinstance(value, Mapping):
        raise AutomationError("保存的登录凭据格式无效，请重新运行 --setup-credentials")
    student_code = value.get("studentCode")
    password = value.get("password")
    if not isinstance(student_code, str) or not student_code.strip():
        raise AutomationError("保存的学号凭据无效，请重新运行 --setup-credentials")
    if not isinstance(password, str) or not password:
        raise AutomationError("保存的密码凭据无效，请重新运行 --setup-credentials")
    return LoginCredentials(student_code=student_code.strip(), password=password)


def load_login_credentials() -> Optional[LoginCredentials]:
    """读取系统凭据库中的登录字段；未配置时返回 None。"""

    keyring = _load_keyring(required=False)
    if keyring is None:
        return None
    try:
        raw = keyring.get_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT)
    except Exception as exc:
        raise AutomationError(
            "无法读取 Windows 凭据管理器；将继续使用手动登录"
        ) from exc
    if raw is None:
        return None
    return parse_login_credentials(raw)


def save_login_credentials(student_code: str, password: str) -> None:
    """将登录字段保存到系统凭据库，不输出密码。"""

    student_code = student_code.strip()
    if not student_code:
        raise AutomationError("学号不能为空")
    if not password:
        raise AutomationError("密码不能为空")
    keyring = _load_keyring(required=True)
    try:
        keyring.set_password(
            CREDENTIAL_SERVICE,
            CREDENTIAL_ACCOUNT,
            serialize_login_credentials(
                LoginCredentials(student_code=student_code, password=password)
            ),
        )
    except Exception as exc:
        raise AutomationError(
            "无法写入 Windows 凭据管理器；凭据未写入脚本"
        ) from exc


def delete_login_credentials() -> bool:
    """删除已保存的登录字段，返回是否存在可删除的凭据。"""

    keyring = _load_keyring(required=True)
    try:
        existing = keyring.get_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT)
        if existing is None:
            return False
        keyring.delete_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT)
    except Exception as exc:
        raise AutomationError("无法删除 Windows 凭据管理器中的登录凭据") from exc
    return True


def setup_login_credentials() -> int:
    """交互式设置系统凭据，不接受命令行密码。"""

    student_code = input("学号（仅保存到 Windows 凭据管理器）：").strip()
    if not student_code:
        raise AutomationError("学号不能为空")
    password = getpass.getpass("密码（输入时不显示）：")
    confirmation = getpass.getpass("再次输入密码：")
    try:
        if password != confirmation:
            raise AutomationError("两次输入的密码不一致")
        save_login_credentials(student_code, password)
    finally:
        password = ""
        confirmation = ""
    print(
        "[完成] 学号和密码已保存到 Windows 凭据管理器；"
        "脚本不会打印或写入密码。"
    )
    return 0


def safe_message(value: Any, limit: int = 360) -> str:
    """清理错误/提示文本，避免日志携带 token 或 cookie。"""

    text = "" if value is None else str(value)
    text = TOKEN_PATTERN.sub(r"\1[REDACTED]", text)
    text = COOKIE_PATTERN.sub(r"\1[REDACTED]", text)
    return text.replace("\r", " ").replace("\n", " ")[:limit]


def build_api_url(path: str) -> str:
    """把 NNU API 相对路径挂到实际应用上下文 /xsxkapp 下。"""

    if path.startswith(("http://", "https://")):
        return path
    return f"{BASE_URL}/{path.lstrip('/')}"


def timestamped_path(path: str) -> str:
    """按 NNU 页面习惯把缓存戳放在接口 URL 的 query 开头。"""

    separator = "&" if "?" in path else "?"
    timestamp = int(datetime.now().timestamp() * 1000)
    return f"{path}{separator}timestamp={timestamp}"


def request_diagnostic_message(value: Any) -> str:
    """只输出请求环境的脱敏状态，不输出 URL 查询值、Cookie 或 token。"""

    if not isinstance(value, Mapping):
        return ""
    path = as_text(value.get("path")) or "-"
    referrer_path = as_text(value.get("referrerPath")) or "-"
    transport = as_text(value.get("transport")) or "-"
    has_session_token = bool(value.get("hasSessionToken"))
    has_url_token = bool(value.get("hasUrlToken"))
    has_jquery = bool(value.get("hasJquery"))
    return (
        f"当前页={path}，URL令牌={'有' if has_url_token else '无'}，"
        f"页面令牌={'有' if has_session_token else '无'}，"
        f"jQuery={'有' if has_jquery else '无'}，传输={transport}，"
        f"来源页={referrer_path}"
    )


def as_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value).strip()


def first_value(item: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def _meaningful_classification_value(value: Any) -> Optional[str]:
    """把分类字段中的空值/占位符统一视为“没有分类”。"""

    text = as_text(value)
    if text is None or text.casefold() in {"", "-", "null", "none", "nan"}:
        return None
    return text


def delivery_mode_from_fields(
    course_flag: Any,
    teaching_place: Any,
) -> Optional[str]:
    """从页面字段保守判断课程是网络、线下，还是无法确认。

    当前 NNU 列表中网络课通常在 ``courseFlag`` 显示“超星网络”或
    “校际联盟网络”，线下课通常有实际教学地点。线上/线下混合标记不做
    猜测，返回 ``None``，避免把不确定课程计入“网络最多两门”的预算。
    """

    flag = _meaningful_classification_value(course_flag) or ""
    place = _meaningful_classification_value(teaching_place) or ""
    combined = f"{flag} {place}"
    network_markers = ("网络", "线上", "在线")
    offline_markers = ("线下", "面授", "实体")
    has_network_marker = any(marker in combined for marker in network_markers)
    has_offline_marker = any(marker in combined for marker in offline_markers)
    if has_network_marker and has_offline_marker:
        return None
    if has_network_marker:
        return "network"
    if has_offline_marker:
        return "offline"
    if place:
        return "offline"
    return None


def selected_course_is_boya(item: Mapping[str, Any]) -> Optional[bool]:
    """根据 NNU 已选结果字段判断一条理论课是否属于博雅课。

    ``courseResult.do`` 的前端渲染没有把当前页面 tab 的
    ``sessionStorage.teachingClassType`` 回传到结果行，所以不能用已选行数
    直接当作博雅数量。优先使用明确的教学班类型；在该字段缺失时，使用
    ``publicCourseType``/``publicCourseTypeName`` 这组博雅专有字段，再兼容
    课程类型字段中出现的 XGXK/中文名称。没有任何分类证据时返回 None，调用
    方会按“非博雅”处理，避免把普通课程计入目标数。
    """

    teaching_class_type = _meaningful_classification_value(
        first_value(item, "teachingClassType", "teachingclasstype")
    )
    if teaching_class_type is not None:
        return teaching_class_type.upper() == BOYA_TEACHING_CLASS_TYPE

    public_type = _meaningful_classification_value(
        first_value(item, "publicCourseType", "publiccoursetype")
    )
    public_type_name = _meaningful_classification_value(
        first_value(item, "publicCourseTypeName", "publiccoursetypename")
    )
    if public_type is not None or public_type_name is not None:
        return True

    for value in (
        first_value(item, "courseType", "coursetype"),
        first_value(item, "courseTypeName", "coursetypename"),
    ):
        text = _meaningful_classification_value(value)
        if text is None:
            continue
        if text.upper() == BOYA_TEACHING_CLASS_TYPE:
            return True
        if any(marker in text for marker in ("博雅", "校公选", "公共选修")):
            return True

    return None


def count_boya_courses(data_list: Sequence[Any]) -> int:
    """只统计 courseResult.do 中的博雅理论课，不统计实验行或普通课程。"""

    count = 0
    for item in data_list:
        if not isinstance(item, Mapping) or as_text(item.get("isTest")) == "1":
            continue
        if selected_course_is_boya(item) is True:
            count += 1
    return count


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


def parse_float(value: Any) -> Optional[float]:
    text = as_text(value)
    if text is None or text == "":
        return None
    try:
        return float(text)
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


def compose_all_school_query_content(
    keyword: str = "",
    category: str = "",
    teaching_unit: str = "",
) -> str:
    """按 QXKC 页面源码的顺序构造全校课程查询条件。"""

    parts: list[str] = []
    keyword = keyword.strip()
    category = category.strip()
    teaching_unit = teaching_unit.strip()
    if teaching_unit:
        parts.append(f"KKDWDM:{teaching_unit}")
    if category:
        parts.append(f"XGXKLBDM:{category}")
    if keyword:
        parts.append(keyword)
    return ",".join(parts)


def build_all_school_query_payload(
    *,
    student_code: str,
    batch_code: str,
    campus_code: str,
    keyword: str = "",
    category: str = "",
    teaching_unit: str = "",
    page_size: int = 10,
    page_number: int = 0,
    order: str = "",
) -> dict[str, str]:
    """构造全校课程查询 ``queryCourse.do`` 的页面原生参数。"""

    data = {
        "studentCode": str(student_code),
        "campus": str(campus_code),
        "electiveBatchCode": str(batch_code),
        "isMajor": "1",
        "teachingClassType": ALL_SCHOOL_TEACHING_CLASS_TYPE,
        "queryContent": compose_all_school_query_content(
            keyword=keyword,
            category=category,
            teaching_unit=teaching_unit,
        ),
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
    course_flag: str
    module_legacy: str
    module_2024: str
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
            course_flag=as_text(first_value(item, "courseFlag")) or "",
            module_legacy=as_text(
                first_value(item, "publicCourseTypeName")
            )
            or "",
            module_2024=as_text(
                first_value(item, "publicCourseTypeName2")
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

    def module_key(self) -> str:
        """只返回 2024 博雅模块；旧分类不能用于模块互斥判断。"""

        return self.module_2024.strip()

    def delivery_mode(self) -> Optional[str]:
        return delivery_mode_from_fields(
            self.course_flag,
            self.teaching_place,
        )

    def is_network_course(self) -> bool:
        return self.delivery_mode() == "network"

    def is_offline_course(self) -> bool:
        return self.delivery_mode() == "offline"

    def demand_count(self) -> int:
        values = [
            value
            for value in (self.first_volunteer, self.selected)
            if value is not None
        ]
        return max(values, default=0)

    def occupancy_ratio(self) -> float:
        if not self.class_capacity or self.class_capacity <= 0:
            return 0.0
        return self.demand_count() / self.class_capacity

    def public_dict(self) -> dict[str, Any]:
        """可写入日志/快照的脱敏课程字段，不含 raw 响应。"""

        return {
            "campusCode": self.campus_code,
            "campus": self.campus_name,
            "teachingClassId": self.teaching_class_id,
            "courseNumber": self.course_number,
            "courseName": self.course_name,
            "courseIndex": self.course_index,
            "courseFlag": self.course_flag,
            "deliveryMode": self.delivery_mode(),
            "publicCourseTypeName": self.module_legacy,
            "publicCourseTypeName2": self.module_2024,
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


def teacher_names(value: Any) -> str:
    """提取 QXKC 返回的 ``姓名|教师代码, ...`` 中的姓名。"""

    text = as_text(value)
    if not text:
        return ""
    names: list[str] = []
    for part in text.split(","):
        name = part.split("|", 1)[0].strip()
        if name and name not in names:
            names.append(name)
    return ", ".join(names)


@dataclass
class SchoolTeachingClass:
    """QXKC 全校课程中的一个可展开教学班。"""

    campus_code: str
    campus_name: str
    teaching_class_id: str
    course_number: str
    course_index: str
    teacher: str
    teaching_place: str
    class_capacity: Optional[int]
    first_volunteer: Optional[int]
    selected: Optional[int]
    is_conflict: Any
    conflict_desc: str
    is_full: Any
    is_choose: Any
    can_select: Any
    can_operate: Any
    has_test: Any
    need_book: Any
    capacity_suffix: str
    raw: Mapping[str, Any]

    @classmethod
    def from_api(
        cls,
        item: Mapping[str, Any],
        *,
        campus_code: str,
        campus_name: str,
        course_number: str,
        course_index: str,
    ) -> Optional["SchoolTeachingClass"]:
        teaching_class_id = as_text(
            first_value(item, "teachingClassID", "teachingClassId", "jxbid")
        )
        if not teaching_class_id:
            return None
        return cls(
            campus_code=as_text(first_value(item, "campus")) or campus_code,
            campus_name=as_text(first_value(item, "campusName")) or campus_name,
            teaching_class_id=teaching_class_id,
            course_number=(
                as_text(first_value(item, "courseNumber", "courseNum"))
                or course_number
            ),
            course_index=(
                as_text(first_value(item, "courseIndex", "classIndex"))
                or course_index
            ),
            teacher=teacher_names(
                first_value(item, "teacherName", "teacher", "subTeacher")
            ),
            teaching_place=(
                as_text(
                    first_value(
                        item,
                        "teachingPlace",
                        "teachPlace",
                        "classroom",
                        "place",
                    )
                )
                or ""
            ),
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
            can_select=first_value(item, "canSelect"),
            can_operate=first_value(item, "canOperate"),
            has_test=first_value(item, "hasTest"),
            need_book=first_value(item, "needBook"),
            capacity_suffix=as_text(first_value(item, "capacitySuffix")) or "",
            raw=item,
        )

    def is_selectable_now(self) -> bool:
        """按服务端显式状态给出当前是否可操作的保守标记。"""

        for flag in (self.can_select, self.can_operate):
            parsed = parse_flag(flag)
            if parsed is False:
                return False
        if parse_flag(self.is_choose) is True:
            return False
        if parse_flag(self.is_conflict) is True:
            return False
        if parse_flag(self.is_full) is True:
            return False
        if self.class_capacity is not None:
            for count in (self.first_volunteer, self.selected):
                if count is not None and count >= self.class_capacity:
                    return False
        return True

    def public_dict(self) -> dict[str, Any]:
        return {
            "campusCode": self.campus_code,
            "campus": self.campus_name,
            "teachingClassId": self.teaching_class_id,
            "courseNumber": self.course_number,
            "courseIndex": self.course_index,
            "teacher": self.teacher,
            "teachingPlace": self.teaching_place,
            "classCapacity": self.class_capacity,
            "numberOfFirstVolunteer": self.first_volunteer,
            "numberOfSelected": self.selected,
            "isConflict": self.is_conflict,
            "conflictDesc": self.conflict_desc,
            "isFull": self.is_full,
            "isChoose": self.is_choose,
            "canSelect": self.can_select,
            "canOperate": self.can_operate,
            "hasTest": self.has_test,
            "needBook": self.need_book,
            "capacitySuffix": self.capacity_suffix,
            "selectableNow": self.is_selectable_now(),
        }


@dataclass
class SchoolCourse:
    """QXKC 返回的课程汇总及其教学班列表。"""

    campus_code: str
    campus_name: str
    course_number: str
    course_name: str
    course_index: str
    department_name: str
    course_nature_name: str
    course_type_name: str
    credit: Any
    hours: Any
    teacher: str
    selected: Any
    course_flag: Any
    teaching_classes: list[SchoolTeachingClass]
    raw: Mapping[str, Any]

    @classmethod
    def from_api(
        cls,
        item: Mapping[str, Any],
        *,
        campus_code: str,
        campus_name: str,
    ) -> Optional["SchoolCourse"]:
        course_number = as_text(
            first_value(item, "courseNumber", "courseNum")
        ) or ""
        course_name = as_text(first_value(item, "courseName", "name")) or ""
        course_index = as_text(
            first_value(item, "courseIndex", "classIndex")
        ) or ""
        nested = item.get("tcList")
        nested_items = (
            [value for value in nested if isinstance(value, Mapping)]
            if isinstance(nested, list)
            else []
        )
        if not nested_items and first_value(
            item, "teachingClassID", "teachingClassId", "jxbid"
        ):
            nested_items = [item]

        teaching_classes: list[SchoolTeachingClass] = []
        for nested_item in nested_items:
            teaching_class = SchoolTeachingClass.from_api(
                nested_item,
                campus_code=campus_code,
                campus_name=campus_name,
                course_number=course_number,
                course_index=course_index,
            )
            if teaching_class is not None:
                teaching_classes.append(teaching_class)

        teachers = teacher_names(first_value(item, "teacherName", "teacher"))
        if not teachers:
            teachers = ", ".join(
                value.teacher
                for value in teaching_classes
                if value.teacher
            )
        return cls(
            campus_code=campus_code,
            campus_name=campus_name,
            course_number=course_number,
            course_name=course_name,
            course_index=course_index,
            department_name=as_text(
                first_value(item, "departmentName", "department")
            )
            or "",
            course_nature_name=as_text(
                first_value(item, "courseNatureName", "nature")
            )
            or "",
            course_type_name=as_text(
                first_value(item, "courseTypeName", "typeName", "type")
            )
            or "",
            credit=first_value(item, "credit"),
            hours=first_value(item, "hours"),
            teacher=teachers,
            selected=first_value(item, "selected", "isChoose"),
            course_flag=first_value(item, "courseFlag"),
            teaching_classes=teaching_classes,
            raw=item,
        )

    def key(self) -> str:
        class_ids = tuple(
            sorted(value.teaching_class_id for value in self.teaching_classes)
        )
        if class_ids:
            return "tc:" + "|".join(class_ids)
        return "course:" + "|".join(
            (
                self.campus_code,
                self.course_number,
                self.course_index,
                self.course_name,
            )
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "campusCode": self.campus_code,
            "campus": self.campus_name,
            "courseNumber": self.course_number,
            "courseName": self.course_name,
            "courseIndex": self.course_index,
            "departmentName": self.department_name,
            "courseNatureName": self.course_nature_name,
            "courseTypeName": self.course_type_name,
            "credit": self.credit,
            "hours": self.hours,
            "teacher": self.teacher,
            "selected": self.selected,
            "courseFlag": self.course_flag,
            "teachingClasses": [
                value.public_dict() for value in self.teaching_classes
            ],
        }


@dataclass
class SchoolQueryResult:
    campus_code: str
    campus_name: str
    total_count: int
    pages_visited: int
    courses: list[SchoolCourse]


@dataclass
class SelectedCourse:
    """courseResult.do 返回的一条当前轮次已选记录。"""

    teaching_class_id: str
    campus_code: str
    campus_name: str
    course_number: str
    course_name: str
    course_index: str
    teacher: str
    teaching_place: str
    course_nature: Any
    course_nature_name: str
    course_type: Any
    course_type_name: str
    public_course_type: Any
    public_course_type_name: str
    public_course_type_name2: str
    course_flag: str
    credit: Any
    hours: Any
    school_term: str
    is_test: Any
    has_test: Any
    test_teaching_class_id: str
    need_book: Any
    is_conflict: Any
    conflict_desc: str
    is_need_pay: Any
    payment_status: str
    raw: Mapping[str, Any]

    @classmethod
    def from_api(cls, item: Mapping[str, Any]) -> Optional["SelectedCourse"]:
        teaching_class_id = as_text(
            first_value(item, "teachingClassID", "teachingClassId", "jxbid")
        )
        if not teaching_class_id:
            return None
        return cls(
            teaching_class_id=teaching_class_id,
            campus_code=as_text(first_value(item, "campus")) or "",
            campus_name=as_text(first_value(item, "campusName")) or "",
            course_number=as_text(
                first_value(item, "courseNumber", "courseNum")
            )
            or "",
            course_name=as_text(first_value(item, "courseName", "name")) or "",
            course_index=as_text(
                first_value(item, "courseIndex", "classIndex")
            )
            or "",
            teacher=teacher_names(
                first_value(item, "teacherName", "teacher", "subTeacher")
            ),
            teaching_place=as_text(
                first_value(item, "teachingPlace", "teachPlace", "classroom")
            )
            or "",
            course_nature=first_value(item, "courseNature"),
            course_nature_name=as_text(
                first_value(item, "courseNatureName")
            )
            or "",
            course_type=first_value(item, "courseType"),
            course_type_name=as_text(first_value(item, "courseTypeName")) or "",
            public_course_type=first_value(item, "publicCourseType"),
            public_course_type_name=as_text(
                first_value(item, "publicCourseTypeName")
            )
            or "",
            public_course_type_name2=as_text(
                first_value(item, "publicCourseTypeName2")
            )
            or "",
            course_flag=as_text(first_value(item, "courseFlag")) or "",
            credit=first_value(item, "credit"),
            hours=first_value(item, "hours"),
            school_term=as_text(first_value(item, "schoolTerm")) or "",
            is_test=first_value(item, "isTest"),
            has_test=first_value(item, "hasTest"),
            test_teaching_class_id=as_text(
                first_value(item, "testTeachingClassID", "testTeachingClassId")
            )
            or "",
            need_book=first_value(item, "needBook"),
            is_conflict=first_value(item, "isConflict"),
            conflict_desc=as_text(
                first_value(item, "conflictDesc", "conflictDescription")
            )
            or "",
            is_need_pay=first_value(item, "isNeedPay"),
            payment_status=as_text(first_value(item, "paymentStatus")) or "",
            raw=item,
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "teachingClassId": self.teaching_class_id,
            "campusCode": self.campus_code,
            "campus": self.campus_name,
            "courseNumber": self.course_number,
            "courseName": self.course_name,
            "courseIndex": self.course_index,
            "teacher": self.teacher,
            "teachingPlace": self.teaching_place,
            "courseNature": self.course_nature,
            "courseNatureName": self.course_nature_name,
            "courseType": self.course_type,
            "courseTypeName": self.course_type_name,
            "publicCourseType": self.public_course_type,
            "publicCourseTypeName": self.public_course_type_name,
            "publicCourseTypeName2": self.public_course_type_name2,
            "courseFlag": self.course_flag,
            "deliveryMode": self.delivery_mode(),
            "credit": self.credit,
            "hours": self.hours,
            "schoolTerm": self.school_term,
            "isTest": self.is_test,
            "hasTest": self.has_test,
            "testTeachingClassId": self.test_teaching_class_id,
            "needBook": self.need_book,
            "isConflict": self.is_conflict,
            "conflictDesc": self.conflict_desc,
            "isNeedPay": self.is_need_pay,
            "paymentStatus": self.payment_status,
            "isBoya": selected_course_is_boya(self.raw) is True,
        }

    def is_boya_theory(self) -> bool:
        return (
            parse_flag(self.is_test) is not True
            and selected_course_is_boya(self.raw) is True
        )

    def module_key(self) -> str:
        return self.public_course_type_name2.strip()

    def delivery_mode(self) -> Optional[str]:
        return delivery_mode_from_fields(
            self.course_flag,
            self.teaching_place,
        )

    def is_network_course(self) -> bool:
        return self.delivery_mode() == "network"

    def is_offline_course(self) -> bool:
        return self.delivery_mode() == "offline"


def hydrate_selected_modules(
    records: Sequence[SelectedCourse],
    courses: Sequence[Course],
) -> None:
    """用同轮 XGXK 清单补齐已选接口可能省略的课程元数据。"""

    by_id = {
        course.teaching_class_id: course
        for course in courses
        if course.teaching_class_id
    }
    by_identity = {
        (course.course_number, course.course_index, course.course_name):
        course
        for course in courses
        if course.module_key()
        and (course.course_number or course.course_index or course.course_name)
    }
    for record in records:
        course = by_id.get(record.teaching_class_id) or by_identity.get(
            (record.course_number, record.course_index, record.course_name)
        )
        if course is None:
            continue
        if not record.public_course_type_name2.strip() and course.module_key():
            record.public_course_type_name2 = course.module_key()
        if not _meaningful_classification_value(record.course_flag):
            record.course_flag = course.course_flag
        if not _meaningful_classification_value(record.teaching_place):
            record.teaching_place = course.teaching_place


@dataclass(frozen=True)
class AutoCandidate:
    course: Course
    reason: str
    growth: int


def candidate_fits_delivery_budget(
    course: Course,
    selected_records: Sequence[SelectedCourse],
) -> bool:
    """判断加入一门课程后仍有机会满足线上/线下比例。

    允许当前课程恰好用掉最后一个网络预算，只要剩余名额仍足够填满
    线下最低数；下一轮会自然屏蔽继续的网络候选。
    """

    mode = course.delivery_mode()
    if mode is None:
        return False
    selected_boya = selected_boya_theory_courses(selected_records)
    network_count, offline_count, unknown_count = selected_boya_delivery_counts(
        selected_records
    )
    if unknown_count:
        return False
    if mode == "network" and network_count >= MAX_NETWORK_COURSES:
        return False

    remaining_after = max(
        0,
        AUTO_TARGET_COUNT - (len(selected_boya) + 1),
    )
    offline_after = offline_count + (1 if mode == "offline" else 0)
    if offline_after + remaining_after < MIN_OFFLINE_COURSES:
        return False
    return True


def selected_boya_theory_courses(
    records: Sequence[SelectedCourse],
) -> list[SelectedCourse]:
    return [record for record in records if record.is_boya_theory()]


def selected_boya_modules(
    records: Sequence[SelectedCourse],
) -> list[str]:
    return [
        record.module_key()
        for record in selected_boya_theory_courses(records)
    ]


def selected_boya_delivery_counts(
    records: Sequence[SelectedCourse],
) -> tuple[int, int, int]:
    """返回已选博雅理论课的网络、线下、未知数量。"""

    network_count = 0
    offline_count = 0
    unknown_count = 0
    for record in selected_boya_theory_courses(records):
        mode = record.delivery_mode()
        if mode == "network":
            network_count += 1
        elif mode == "offline":
            offline_count += 1
        else:
            unknown_count += 1
    return network_count, offline_count, unknown_count


def selected_boya_credit_total(
    records: Sequence[SelectedCourse],
) -> Optional[float]:
    """返回已选博雅理论课总学分；任何一门缺失学分时返回 None。"""

    selected = selected_boya_theory_courses(records)
    credits = [parse_float(record.credit) for record in selected]
    if any(credit is None for credit in credits):
        return None
    return sum(credit for credit in credits if credit is not None)


def auto_selection_goal_met(
    records: Sequence[SelectedCourse],
) -> bool:
    selected = selected_boya_theory_courses(records)
    modules = [record.module_key() for record in selected]
    network_count, offline_count, unknown_count = selected_boya_delivery_counts(
        records
    )
    return (
        len(selected) >= AUTO_TARGET_COUNT
        and all(modules)
        and len(set(modules)) == len(modules)
        and unknown_count == 0
        and network_count <= MAX_NETWORK_COURSES
        and offline_count >= MIN_OFFLINE_COURSES
        and any(
            record.course_name == REQUIRED_OFFLINE_COURSE
            and record.is_offline_course()
            for record in selected
        )
    )


def network_demand_growth(
    courses: Sequence[Course],
    previous_counts: Mapping[str, int],
) -> tuple[dict[str, int], dict[str, int]]:
    """计算本轮网络博雅人数增量；返回的新快照完全替换旧快照。"""

    current_counts = {
        course.teaching_class_id: course.demand_count()
        for course in courses
        if course.is_network_course()
    }
    growth = {
        teaching_class_id: max(
            0,
            count - previous_counts.get(teaching_class_id, count),
        )
        for teaching_class_id, count in current_counts.items()
    }
    return growth, current_counts


def network_growth_leaders(
    courses: Sequence[Course],
    growth: Mapping[str, int],
    *,
    limit: int = 3,
) -> list[Course]:
    network_courses = [course for course in courses if course.is_network_course()]
    return sorted(
        network_courses,
        key=lambda course: (
            growth.get(course.teaching_class_id, 0),
            course.occupancy_ratio(),
            course.demand_count(),
            course.course_name,
        ),
        reverse=True,
    )[: max(0, limit)]


def rank_auto_candidates(
    courses: Sequence[Course],
    selected_records: Sequence[SelectedCourse],
    growth: Mapping[str, int],
    *,
    allow_network_fallback: bool = True,
) -> list[AutoCandidate]:
    """按优先级排序，并硬性执行模块互斥与线上/线下数量预算。"""

    selected_boya = selected_boya_theory_courses(selected_records)
    occupied_modules = {
        record.module_key()
        for record in selected_boya
        if record.module_key()
    }
    _, _, unknown_delivery_count = selected_boya_delivery_counts(
        selected_records
    )
    if unknown_delivery_count:
        return []
    safe = [
        course
        for course in courses
        if course.is_safe_candidate()
        and course.module_key()
        and course.module_key() not in occupied_modules
        and course.delivery_mode() is not None
    ]
    ranked: list[AutoCandidate] = []
    seen_ids: set[str] = set()

    for priority, (module, preferred_names) in enumerate(
        PREFERRED_AUTO_GROUPS,
        start=1,
    ):
        if module in occupied_modules:
            continue
        for name in preferred_names:
            matches = [
                course
                for course in safe
                if course.course_name == name
                and course.module_key() == module
                and (
                    course.is_offline_course()
                    if name == REQUIRED_OFFLINE_COURSE
                    else course.is_network_course()
                )
                and candidate_fits_delivery_budget(course, selected_records)
            ]
            for course in sorted(
                matches,
                key=lambda item: (
                    item.occupancy_ratio(),
                    item.demand_count(),
                ),
                reverse=True,
            ):
                if course.teaching_class_id in seen_ids:
                    continue
                seen_ids.add(course.teaching_class_id)
                ranked.append(
                    AutoCandidate(
                        course=course,
                        reason=f"优先{priority}:{name}",
                        growth=growth.get(course.teaching_class_id, 0),
                    )
                )

    # 中国民歌模块始终保留给线下必选目标；若只剩最后一个名额且它尚未
    # 选中，禁止任何网络兜底占用最后名额。
    remaining_slots = AUTO_TARGET_COUNT - len(selected_boya)
    reserve_offline_slot = REQUIRED_OFFLINE_MODULE not in occupied_modules
    if reserve_offline_slot and remaining_slots <= 1:
        return [
            decision
            for decision in ranked
            if decision.course.course_name == REQUIRED_OFFLINE_COURSE
            and decision.course.module_key() == REQUIRED_OFFLINE_MODULE
            and decision.course.is_offline_course()
        ]

    # 线下兜底用于满足“5 门中至少 3 门线下”；它不依赖网络人数基线。
    offline_fallback = [
        course
        for course in safe
        if course.teaching_class_id not in seen_ids
        and course.is_offline_course()
        and course.module_key() != REQUIRED_OFFLINE_MODULE
    ]
    offline_fallback.sort(
        key=lambda course: (
            course.occupancy_ratio(),
            course.demand_count(),
            course.course_name,
        ),
        reverse=True,
    )
    for course in offline_fallback:
        if not candidate_fits_delivery_budget(course, selected_records):
            continue
        ranked.append(
            AutoCandidate(
                course=course,
                reason=(
                    "线下兜底:"
                    f"{course.module_key()} "
                    f"{course.demand_count()}/"
                    f"{course.class_capacity if course.class_capacity is not None else '-'}"
                ),
                growth=growth.get(course.teaching_class_id, 0),
            )
        )

    # 第一轮只建立人数基线；没有前后两个样本时不能判断“上升最快”。
    if not allow_network_fallback:
        return ranked

    network_fallback = [
        course
        for course in safe
        if course.teaching_class_id not in seen_ids
        and course.is_network_course()
        and course.module_key() != REQUIRED_OFFLINE_MODULE
    ]
    network_fallback.sort(
        key=lambda course: (
            growth.get(course.teaching_class_id, 0),
            course.occupancy_ratio(),
            course.demand_count(),
            course.course_name,
        ),
        reverse=True,
    )
    for course in network_fallback:
        if not candidate_fits_delivery_budget(course, selected_records):
            continue
        ranked.append(
            AutoCandidate(
                course=course,
                reason=(
                    "网络热度兜底:"
                    f"{course.module_key()} Δ+"
                    f"{growth.get(course.teaching_class_id, 0)} "
                    f"{course.demand_count()}/"
                    f"{course.class_capacity if course.class_capacity is not None else '-'}"
                ),
                growth=growth.get(course.teaching_class_id, 0),
            )
        )
    return ranked


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
async ({requestUrl, method, params, timeoutMs}) => {
  const token = sessionStorage.getItem("token");
  const diagnostics = (transport) => ({
    path: window.location.pathname,
    referrerPath: document.referrer ? new URL(document.referrer).pathname : "",
    hasSessionToken: Boolean(sessionStorage.getItem("token")),
    hasUrlToken: new URL(window.location.href).searchParams.has("token"),
    hasJquery: typeof window.jQuery === "function",
    transport
  });
  if (!token) {
    return {
      status: 0,
      text: "missing-session",
      errorType: "missing-session",
      diagnostics: diagnostics("none")
    };
  }
  const values = params || {};

  // NNU 自己的前端使用 jQuery XHR；优先沿用同一传输方式，
  // 避免服务端根据 Fetch Metadata/请求头差异拒绝原生 fetch。
  if (typeof window.jQuery === "function") {
    const url = new URL(requestUrl, window.location.origin).toString();
    return await new Promise((resolve) => {
      window.jQuery.ajax({
        url,
        type: method || "GET",
        data: values,
        timeout: timeoutMs,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "token": token
        },
        dataType: "json",
        success: (data, _textStatus, xhr) => {
          resolve({
            status: xhr.status || 200,
            text: JSON.stringify(data == null ? null : data),
            diagnostics: diagnostics("jquery")
          });
        },
        error: (xhr, textStatus) => {
          resolve({
            status: xhr.status || 0,
            text: String(xhr.responseText || ""),
            errorType: textStatus === "timeout" ? "timeout" : (textStatus || "network"),
            diagnostics: diagnostics("jquery")
          });
        }
      });
    });
  }

  const url = new URL(requestUrl, window.location.origin);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const options = {
    method: method || "GET",
    mode: "same-origin",
    credentials: "include",
    signal: controller.signal,
    headers: {
      "Accept": "application/json, text/javascript, */*; q=0.01",
      "X-Requested-With": "XMLHttpRequest",
      "token": token
    }
  };
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
  try {
    const response = await fetch(url.toString(), options);
    return {
      status: response.status,
      text: await response.text(),
      diagnostics: diagnostics("fetch")
    };
  } catch (error) {
    return {
      status: 0,
      text: "",
      errorType: error && error.name === "AbortError" ? "timeout" : "network",
      diagnostics: diagnostics("fetch")
    };
  } finally {
    clearTimeout(timer);
  }
}
"""


class BrowserApi:
    """通过应用上下文内的页面 XHR 调用 API，token 留在页面上下文。"""

    def __init__(
        self,
        page: Any,
        *,
        reauth_handler: Optional[Callable[[], Awaitable[None]]] = None,
        request_timeout_ms: int = API_REQUEST_TIMEOUT_MS,
        max_retries: int = API_QUERY_RETRIES,
        retry_base_seconds: float = API_RETRY_BASE_SECONDS,
    ):
        self.page = page
        self.reauth_handler = reauth_handler
        self.request_timeout_ms = max(1_000, int(request_timeout_ms))
        self.max_retries = max(0, int(max_retries))
        self.retry_base_seconds = max(0.0, float(retry_base_seconds))

    async def call(
        self,
        path: str,
        *,
        method: str = "GET",
        params: Optional[Mapping[str, Any]] = None,
        retryable: bool = True,
        allow_reauth: bool = True,
    ) -> dict[str, Any]:
        retry_index = 0
        reauth_used = False
        while True:
            result = await self.page.evaluate(
                FETCH_SCRIPT,
                {
                    "requestUrl": build_api_url(path),
                    "method": method,
                    "params": dict(params or {}),
                    "timeoutMs": self.request_timeout_ms,
                },
            )
            status = int(result.get("status", 0))
            raw_text = result.get("text", "")
            error_type = as_text(result.get("errorType")) or ""
            try:
                if status in {401, 403}:
                    raise SessionExpiredError(
                        f"服务端拒绝请求（HTTP {status}，接口 {path}；"
                        f"{request_diagnostic_message(result.get('diagnostics'))}）"
                    )
                if status == 0:
                    if error_type == "missing-session":
                        raise SessionExpiredError(
                            "浏览器页面没有可用登录态，请重新登录"
                        )
                    raise NetworkTransientError(
                        f"接口 {path} 网络异常（{error_type or 'network'}；"
                        f"{request_diagnostic_message(result.get('diagnostics'))}）"
                    )
                if status in {408, 429, 500, 502, 503, 504}:
                    raise NetworkTransientError(
                        f"接口 {path} 暂时不可用（HTTP {status}）"
                    )
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
            except SessionExpiredError:
                if (
                    allow_reauth
                    and not reauth_used
                    and self.reauth_handler is not None
                ):
                    await self.reauth_handler()
                    reauth_used = True
                    retry_index = 0
                    continue
                raise
            except NetworkTransientError:
                if not retryable or retry_index >= self.max_retries:
                    raise
                delay = self.retry_base_seconds * (2 ** retry_index)
                retry_index += 1
                if delay > 0:
                    await asyncio.sleep(delay)

    async def get(
        self,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        *,
        retryable: bool = True,
        allow_reauth: bool = True,
    ) -> dict[str, Any]:
        return await self.call(
            path,
            method="GET",
            params=params,
            retryable=retryable,
            allow_reauth=allow_reauth,
        )

    async def post(
        self,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        *,
        retryable: bool = True,
        allow_reauth: bool = True,
    ) -> dict[str, Any]:
        return await self.call(
            path,
            method="POST",
            params=params,
            retryable=retryable,
            allow_reauth=allow_reauth,
        )


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

    async def goto_authenticated_page(
        self,
        path: str,
        timeout_milliseconds: int = 60_000,
    ) -> None:
        """按 NNU 页面自身的方式带当前 token 打开受保护页面。

        NNU 的 sidebar.js 会把 sessionStorage.token 拼到页面 URL；
        这里在页面上下文内完成同样的导航，token 不回传给 Python。
        """

        await self.page.evaluate(
            """
            (targetPath) => {
              const token = sessionStorage.getItem("token");
              if (!token) {
                throw new Error("missing-session-token");
              }
              const target = new URL(targetPath, window.location.origin);
              target.searchParams.set("token", token);
              window.location.assign(target.toString());
            }
            """,
            path,
        )
        await self.page.wait_for_load_state(
            "domcontentloaded",
            timeout=timeout_milliseconds,
        )

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


async def autofill_login_form(
    page: Any,
    *,
    enabled: bool = True,
    ui: Optional[TerminalUI] = None,
) -> None:
    """把系统凭据库字段填入 NNU 登录框，但不填写验证码或点击登录。"""

    if not enabled:
        if ui is not None:
            ui.event("credential autofill disabled; enter login fields manually")
        else:
            print("[提示] 本次运行已关闭学号/密码自动填充，请手动输入")
        return

    try:
        username = page.locator("#loginName")
        password = page.locator("#loginPwd")
        await username.wait_for(state="visible", timeout=10_000)
        await password.wait_for(state="visible", timeout=5_000)
    except Exception:
        if ui is not None:
            ui.event("login form not ready; enter login fields manually", "WARN")
        else:
            print("[提示] 登录表单尚未出现，继续手动输入学号和密码")
        return

    try:
        credentials = load_login_credentials()
    except AutomationError as exc:
        message = f"credential autofill unavailable: {safe_message(exc)}"
        if ui is not None:
            ui.event(message, "WARN")
        else:
            print(f"[提示] 自动填充未启用：{safe_message(exc)}")
        return

    if credentials is None:
        print(
            "[提示] 尚未设置自动填充凭据；请先运行 --setup-credentials，"
            "本次继续手动登录"
        )
        return

    try:
        await username.fill(credentials.student_code)
        await password.fill(credentials.password)
    except Exception as exc:
        message = f"login autofill failed: {safe_message(exc)}"
        if ui is not None:
            ui.event(message, "WARN")
        else:
            print(f"[提示] 登录框自动填充失败：{safe_message(exc)}；请手动输入")
        return

    message = "credentials filled; manual CAPTCHA/human verification required"
    if ui is not None:
        ui.event(message)
    else:
        print(
            "[准备] 已自动填入学号和密码；请手动填写验证码/完成人机认证，"
            "脚本不会自动点击登录"
        )


async def reauthenticate_visible_browser(
    page: Any,
    browser_session: BrowserSession,
    *,
    timeout_seconds: int,
    auto_fill_credentials: bool,
    ui: Optional[TerminalUI] = None,
) -> SessionContext:
    """在同一个可见浏览器中恢复登录态，成功后返回新的会话上下文。

    只清理当前页面 sessionStorage 中的旧登录态，再回到登录入口；学号密码可
    从 Windows 凭据管理器重新填入，但验证码/人机认证仍由用户本人完成。
    """

    if ui is not None:
        ui.set_phase("REAUTH", render=False)
        ui.set_session(auth="EXPIRED", render=False)
        ui.event("session expired; reopening login page for manual re-auth", "AUTH")
    else:
        print("[登录] 当前会话已失效，正在原浏览器中重新打开登录页")

    try:
        await page.evaluate(
            """
            () => {
              for (const key of [
                "token", "studentInfo", "currentBatch", "currentCampus",
                "teachingClassType", "electiveIsOpen"
              ]) {
                sessionStorage.removeItem(key);
              }
            }
            """
        )
    except Exception:
        # 页面可能刚被服务端重定向；导航到入口后仍会重新建立会话。
        pass

    try:
        await page.goto(
            ENTRY_URL,
            wait_until="domcontentloaded",
            timeout=60_000,
        )
    except Exception as exc:
        message = f"re-auth login entry load warning: {safe_message(exc)}"
        if ui is not None:
            ui.event(message, "WARN")
        else:
            print(f"[提示] 重新登录入口加载提示：{safe_message(exc)}")

    await autofill_login_form(
        page,
        enabled=auto_fill_credentials,
        ui=ui,
    )
    if ui is not None:
        ui.set_session(auth="MANUAL", render=False)
        ui.event("complete CAPTCHA/human verification to resume", "AUTH")
    else:
        print("[等待] 请在保留的浏览器里完成验证码/人机认证；成功后脚本会自动继续")

    try:
        await browser_session.wait_until_ready(timeout_seconds=timeout_seconds)
        await browser_session.goto_authenticated_page(GRAB_URL)
        await browser_session.wait_until_ready(timeout_seconds=timeout_seconds)
        context = await browser_session.read_context()
    except AutomationError as exc:
        raise SessionExpiredError(
            "重新登录未在等待时间内恢复完整会话；浏览器将保留供人工检查"
        ) from exc

    if ui is not None:
        ui.set_phase("READY", render=False)
        ui.set_session(auth="READY", context=context, render=False)
        ui.event("re-authentication complete; monitoring resumed", "AUTH")
    else:
        print("[恢复] 重新登录成功，继续原来的监控/选课任务")
    return context


async def hold_browser_for_manual_control(
    page: Any,
    *,
    ui: Optional[TerminalUI],
    message: str,
    phase: str = "DONE_HOLD",
) -> None:
    """任务完成或结果不确定时保留浏览器，直到用户明确要求关闭。"""

    if page is None or not sys.stdin.isatty():
        return
    if ui is not None:
        ui.set_phase(phase, render=False)
        ui.set_session(browser="OPEN", render=False)
        ui.event(message, "HOLD", render=True)
        ui.pause_for_input()
    try:
        await asyncio.to_thread(
            input,
            "\n[保持] 浏览器和当前登录页不会自动关闭，可直接人工检查/操作；"
            "确认不再需要后按回车关闭脚本：",
        )
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        if ui is not None:
            ui.resume_after_input()


async def open_visible_browser(
    timeout_seconds: int,
    *,
    auto_fill_credentials: bool = True,
    ui: Optional[TerminalUI] = None,
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
            message = f"login entry load warning: {safe_message(exc)}"
            if ui is not None:
                ui.event(message, "WARN")
            else:
                print(f"[提示] 登录入口加载提示：{safe_message(exc)}")

        await autofill_login_form(
            page,
            enabled=auto_fill_credentials,
            ui=ui,
        )
        session = BrowserSession(page)
        if ui is not None:
            ui.set_phase("LOGIN", render=False)
            ui.set_session(browser="OPEN", auth="MANUAL", render=False)
            ui.event("waiting for manual login and human verification")
        else:
            print(
                "[等待] 本次启动必须由本人在可见浏览器中手动登录并完成"
                "人机认证；脚本不会自动提交登录。"
            )
        await session.wait_until_ready(timeout_seconds=timeout_seconds)
        if ui is not None:
            ui.set_phase("AUTH OK", render=False)
            ui.set_session(auth="READY", render=False)
            ui.event("login session ready")
        try:
            await session.goto_authenticated_page(
                GRAB_URL,
            )
        except Exception as exc:
            message = f"course page navigation warning: {safe_message(exc)}"
            if ui is not None:
                ui.event(message, "WARN")
            else:
                print(f"[提示] 选课页返回提示：{safe_message(exc)}")
        await session.wait_until_ready(timeout_seconds=timeout_seconds)
        if ui is not None:
            ui.set_phase("READY", render=False)
            ui.event("course page session ready")
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
    check_conflict: str = "0",
    check_capacity: str = "0",
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
            check_conflict=check_conflict,
            check_capacity=check_capacity,
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
    ui: Optional[TerminalUI] = None,
    check_conflict: str = "0",
    check_capacity: str = "0",
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
            check_conflict=check_conflict,
            check_capacity=check_capacity,
        )
        results.append(result)
        if ui is not None:
            ui.query(result, render=False)
        else:
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


async def query_all_school_courses(
    api: BrowserApi,
    context: SessionContext,
    *,
    campus_code: str,
    page_size: int,
    max_pages: int,
    request_delay: float,
    keyword: str = "",
    category: str = "",
    teaching_unit: str = "",
) -> SchoolQueryResult:
    """通过 QXKC/queryCourse.do 分页读取当前批次全校课程。"""

    if campus_code not in CAMPUS:
        raise AutomationError(f"脚本只允许查询仙林/仙林新北，收到：{campus_code}")

    courses: list[SchoolCourse] = []
    seen_keys: set[str] = set()
    total_count = 0
    pages_visited = 0
    page_number = 0

    while True:
        if pages_visited >= max_pages:
            raise AutomationError(
                f"{CAMPUS[campus_code]} 全校课程查询超过 max_pages={max_pages}，"
                "为避免无限请求已停止"
            )
        payload = build_all_school_query_payload(
            student_code=context.student_code,
            batch_code=context.batch_code,
            campus_code=campus_code,
            keyword=keyword,
            category=category,
            teaching_unit=teaching_unit,
            page_size=page_size,
            page_number=page_number,
        )
        response = await api.post(ALL_SCHOOL_COURSE_PATH, payload)
        if as_text(response.get("code")) != "1":
            raise AutomationError(
                f"{CAMPUS[campus_code]} 全校课程查询失败："
                f"{safe_message(response.get('msg')) or '未知原因'}"
            )

        rows = response.get("dataList") or []
        if not isinstance(rows, list):
            raise AutomationError("queryCourse.do 的 dataList 不是数组")
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
            course = SchoolCourse.from_api(
                item,
                campus_code=campus_code,
                campus_name=CAMPUS[campus_code],
            )
            if course is None or course.key() in seen_keys:
                continue
            seen_keys.add(course.key())
            courses.append(course)

        if not rows or len(courses) >= total_count:
            break
        page_number += 1
        await asyncio.sleep(request_delay)

    return SchoolQueryResult(
        campus_code=campus_code,
        campus_name=CAMPUS[campus_code],
        total_count=total_count,
        pages_visited=pages_visited,
        courses=courses,
    )


async def run_all_school_query_cycle(
    api: BrowserApi,
    context: SessionContext,
    *,
    page_size: int,
    max_pages: int,
    request_delay: float,
    campus_codes: Sequence[str] = ("2", "4"),
    keyword: str = "",
    category: str = "",
    teaching_unit: str = "",
) -> tuple[list[SchoolQueryResult], list[SchoolCourse]]:
    """按目标校区上下文查询 QXKC，并合并重复课程。"""

    results: list[SchoolQueryResult] = []
    courses: list[SchoolCourse] = []
    seen_keys: set[str] = set()
    for index, campus_code in enumerate(campus_codes):
        result = await query_all_school_courses(
            api,
            context,
            campus_code=campus_code,
            page_size=page_size,
            max_pages=max_pages,
            request_delay=request_delay,
            keyword=keyword,
            category=category,
            teaching_unit=teaching_unit,
        )
        results.append(result)
        print(
            f"[全校课程] {result.campus_name}：服务端返回 {result.total_count} 条，"
            f"本次读取 {len(result.courses)} 条（访问 {result.pages_visited} 页）"
        )
        for course in result.courses:
            if course.key() not in seen_keys:
                seen_keys.add(course.key())
                courses.append(course)
        if index < len(campus_codes) - 1:
            await asyncio.sleep(request_delay)
    return results, courses


async def fetch_selected_course_items(
    api: BrowserApi,
    context: SessionContext,
) -> list[Mapping[str, Any]]:
    """读取 courseResult.do 的当前批次已选课程原始行（仅留内存）。"""

    response = await api.get(
        timestamped_path(SELECTED_COURSE_PATH),
        {
            "studentCode": context.student_code,
            "electiveBatchCode": context.batch_code,
        },
    )
    if as_text(response.get("code")) != "1":
        raise AutomationError(
            "已选课程查询失败："
            f"{safe_message(response.get('msg')) or '未知原因'}"
        )
    data_list = response.get("dataList") or []
    if not isinstance(data_list, list):
        raise AutomationError("courseResult.do 的 dataList 不是数组")
    return [item for item in data_list if isinstance(item, Mapping)]


async def query_selected_courses(
    api: BrowserApi,
    context: SessionContext,
) -> list[SelectedCourse]:
    """读取并整理当前选课批次的理论课/实验课记录。"""

    records: list[SelectedCourse] = []
    seen_ids: set[str] = set()
    for item in await fetch_selected_course_items(api, context):
        record = SelectedCourse.from_api(item)
        if record is None or record.teaching_class_id in seen_ids:
            continue
        seen_ids.add(record.teaching_class_id)
        records.append(record)
    return records


async def query_selected_course_count(
    api: BrowserApi,
    context: SessionContext,
) -> int:
    """统计当前轮次已选的博雅理论课数量，而不是全部已选课程。"""

    return count_boya_courses(
        await fetch_selected_course_items(api, context)
    )


async def query_batch_open(
    api: BrowserApi,
    context: SessionContext,
) -> bool:
    """以服务端轮次状态为准；列表提前可见不等于已经允许提交。"""

    response = await api.post(
        BATCH_OPEN_PATH,
        {"xklcdm": context.batch_code},
    )
    return as_text(response.get("msg")) == "1"


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
    *,
    quiet: bool = False,
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
    if not quiet:
        print(f"[保存] 已写入脱敏查询快照：{path}")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fieldnames),
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


SCHOOL_COURSE_CSV_FIELDS = (
    "campusCode",
    "campus",
    "courseNumber",
    "courseName",
    "courseIndex",
    "departmentName",
    "courseNatureName",
    "courseTypeName",
    "credit",
    "hours",
    "courseTeacher",
    "selected",
    "courseFlag",
    "teachingClassId",
    "teachingClassIndex",
    "teacher",
    "teachingPlace",
    "classCapacity",
    "numberOfFirstVolunteer",
    "numberOfSelected",
    "isConflict",
    "conflictDesc",
    "isFull",
    "isChoose",
    "canSelect",
    "canOperate",
    "hasTest",
    "needBook",
    "capacitySuffix",
    "selectableNow",
)


def school_course_csv_rows(
    courses: Sequence[SchoolCourse],
) -> list[dict[str, Any]]:
    """把课程汇总和教学班展开成一行一个教学班的表格。"""

    rows: list[dict[str, Any]] = []
    for course in courses:
        base = {
            "campusCode": course.campus_code,
            "campus": course.campus_name,
            "courseNumber": course.course_number,
            "courseName": course.course_name,
            "courseIndex": course.course_index,
            "departmentName": course.department_name,
            "courseNatureName": course.course_nature_name,
            "courseTypeName": course.course_type_name,
            "credit": course.credit,
            "hours": course.hours,
            "courseTeacher": course.teacher,
            "selected": course.selected,
            "courseFlag": course.course_flag,
        }
        if not course.teaching_classes:
            rows.append(dict(base))
            continue
        for teaching_class in course.teaching_classes:
            detail = teaching_class.public_dict()
            rows.append(
                {
                    **base,
                    "teachingClassId": detail["teachingClassId"],
                    "teachingClassIndex": detail["courseIndex"],
                    "teacher": detail["teacher"],
                    "teachingPlace": detail["teachingPlace"],
                    "classCapacity": detail["classCapacity"],
                    "numberOfFirstVolunteer": detail[
                        "numberOfFirstVolunteer"
                    ],
                    "numberOfSelected": detail["numberOfSelected"],
                    "isConflict": detail["isConflict"],
                    "conflictDesc": detail["conflictDesc"],
                    "isFull": detail["isFull"],
                    "isChoose": detail["isChoose"],
                    "canSelect": detail["canSelect"],
                    "canOperate": detail["canOperate"],
                    "hasTest": detail["hasTest"],
                    "needBook": detail["needBook"],
                    "capacitySuffix": detail["capacitySuffix"],
                    "selectableNow": detail["selectableNow"],
                }
            )
    return rows


def write_open_course_exports(
    export_dir: Path,
    context: SessionContext,
    results: Sequence[SchoolQueryResult],
    courses: Sequence[SchoolCourse],
    *,
    keyword: str = "",
    category: str = "",
    teaching_unit: str = "",
) -> tuple[Path, Path]:
    """写入全校开放课程的脱敏 JSON 与可用表格 CSV。"""

    export_dir = export_dir.expanduser().resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "all_open_courses.json"
    csv_path = export_dir / "all_open_courses.csv"
    payload = {
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "batchName": context.batch_name,
        "query": {
            "endpoint": ALL_SCHOOL_COURSE_PATH,
            "teachingClassType": ALL_SCHOOL_TEACHING_CLASS_TYPE,
            "campuses": [result.campus_code for result in results],
            "filters": {
                "keyword": keyword,
                "category": category,
                "teachingUnit": teaching_unit,
            },
        },
        "campusResults": [
            {
                "campusCode": result.campus_code,
                "campus": result.campus_name,
                "totalCount": result.total_count,
                "pagesVisited": result.pages_visited,
                "rowsRead": len(result.courses),
            }
            for result in results
        ],
        "courseCount": len(courses),
        "teachingClassCount": sum(
            len(course.teaching_classes) for course in courses
        ),
        "courses": [course.public_dict() for course in courses],
    }
    _write_json(json_path, payload)
    _write_csv(
        csv_path,
        SCHOOL_COURSE_CSV_FIELDS,
        school_course_csv_rows(courses),
    )
    print(f"[保存] 全校开放课程 JSON：{json_path}")
    print(f"[保存] 全校开放课程 CSV：{csv_path}")
    return json_path, csv_path


SELECTED_COURSE_CSV_FIELDS = (
    "recordKind",
    "parentTeachingClassId",
    "teachingClassId",
    "campusCode",
    "campus",
    "courseNumber",
    "courseName",
    "courseIndex",
    "teacher",
    "teachingPlace",
    "courseNature",
    "courseNatureName",
    "courseType",
    "courseTypeName",
    "publicCourseType",
    "publicCourseTypeName",
    "publicCourseTypeName2",
    "courseFlag",
    "deliveryMode",
    "credit",
    "hours",
    "schoolTerm",
    "isTest",
    "hasTest",
    "testTeachingClassId",
    "needBook",
    "isConflict",
    "conflictDesc",
    "isNeedPay",
    "paymentStatus",
    "isBoya",
)


def selected_course_csv_rows(
    records: Sequence[SelectedCourse],
) -> list[dict[str, Any]]:
    parent_by_test_id = {
        record.test_teaching_class_id: record.teaching_class_id
        for record in records
        if as_text(record.is_test) != "1" and record.test_teaching_class_id
    }
    rows: list[dict[str, Any]] = []
    for record in records:
        row = record.public_dict()
        rows.append(
            {
                "recordKind": (
                    "experiment"
                    if as_text(record.is_test) == "1"
                    else "theory"
                ),
                "parentTeachingClassId": parent_by_test_id.get(
                    record.teaching_class_id, ""
                ),
                **row,
            }
        )
    return rows


def write_selected_course_exports(
    export_dir: Path,
    context: SessionContext,
    records: Sequence[SelectedCourse],
) -> tuple[Path, Path]:
    """写入当前批次已选课程的脱敏 JSON 与 CSV。"""

    export_dir = export_dir.expanduser().resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "selected_courses.json"
    csv_path = export_dir / "selected_courses.csv"
    theory = [record for record in records if as_text(record.is_test) != "1"]
    experiments = [
        record for record in records if as_text(record.is_test) == "1"
    ]
    experiment_by_id = {
        record.teaching_class_id: record.public_dict()
        for record in experiments
    }
    courses: list[dict[str, Any]] = []
    for record in theory:
        course = record.public_dict()
        if record.test_teaching_class_id:
            course["experimentCourse"] = experiment_by_id.get(
                record.test_teaching_class_id
            )
        courses.append(course)
    payload = {
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "batchName": context.batch_name,
        "selectedTheoryCount": len(theory),
        "selectedExperimentCount": len(experiments),
        "selectedBoyaTheoryCount": sum(
            selected_course_is_boya(record.raw) is True for record in theory
        ),
        "courses": courses,
        "experimentCourses": [record.public_dict() for record in experiments],
    }
    _write_json(json_path, payload)
    _write_csv(
        csv_path,
        SELECTED_COURSE_CSV_FIELDS,
        selected_course_csv_rows(records),
    )
    print(f"[保存] 当前已选课程 JSON：{json_path}")
    print(f"[保存] 当前已选课程 CSV：{csv_path}")
    print(
        f"[已选课程] 理论课 {len(theory)} 门，实验记录 {len(experiments)} 条，"
        f"其中博雅理论课 {payload['selectedBoyaTheoryCount']} 门"
    )
    return json_path, csv_path


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
        timestamped_path(CAPACITY_PATH),
        {
            "teachingClassId": course.teaching_class_id,
            "capacitySuffix": course.capacity_suffix,
            "xh": context.student_code,
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

    if not await query_batch_open(api, context):
        raise BatchNotOpenError(
            "选课轮次当前未确认开放，未提交"
        )
    return context, course, selected_need_book, selected_test_id


async def selected_course_present(
    api: BrowserApi,
    context: SessionContext,
    teaching_class_id: str,
) -> bool:
    """用 courseResult.do 核验指定教学班是否已经出现在当前批次已选结果中。"""

    for item in await fetch_selected_course_items(api, context):
        current_id = as_text(
            first_value(item, "teachingClassID", "teachingClassId", "JXBID")
        )
        if current_id == teaching_class_id:
            return True
    return False


async def submit_course(
    api: BrowserApi,
    context: SessionContext,
    course: Course,
    *,
    need_book: Optional[str],
    test_teaching_class_id: Optional[str],
    yes: bool,
    ui: Optional[TerminalUI] = None,
) -> int:
    add_payload = build_add_payload(
        student_code=context.student_code,
        batch_code=context.batch_code,
        teaching_class_id=course.teaching_class_id,
        campus_code=course.campus_code,
        need_book=need_book,
        test_teaching_class_id=test_teaching_class_id,
    )
    if ui is not None:
        ui.set_phase("CONFIRM", render=False)
        ui.action(
            f"candidate ready: {course.short_label()}",
            render=False,
        )
        ui.render(force=True)
    else:
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
        if ui is not None:
            ui.pause_for_input()
        try:
            answer = input(
                f"若确认向 NNU 提交该教学班，请原样输入 "
                f"{course.teaching_class_id}："
            ).strip()
        finally:
            if ui is not None:
                ui.resume_after_input()
        if answer != course.teaching_class_id:
            if ui is not None:
                ui.submission("CANCELLED", render=False)
                ui.event("confirmation mismatch; no submission", "WARN")
            else:
                print("[停止] 确认文本不匹配，未提交")
            return 6

    if ui is not None:
        ui.submit_attempts += 1
        ui.set_phase("SUBMIT", render=False)
        ui.action("POST volunteer.do", render=True)
    submission_uncertain = False
    try:
        # volunteer.do 是唯一的写请求：网络超时、5xx 或登录态异常时绝不
        # 自动重发，避免“第一次已到达服务端、第二次又重复提交”。
        response = await api.post(
            VOLUNTEER_PATH,
            add_payload,
            retryable=False,
            allow_reauth=False,
        )
    except (NetworkTransientError, SessionExpiredError) as exc:
        submission_uncertain = True
        response = None
        message = safe_message(exc)
        if ui is not None:
            ui.set_phase("VERIFY", render=False)
            ui.event(
                f"submission transport uncertain; no resend: {message}",
                "WARN",
            )
        else:
            print(
                "[警告] 提交请求结果不确定，脚本不会重发 volunteer.do；"
                "开始只读核验已选结果"
            )

    if response is not None:
        code = as_text(response.get("code"))
        if code != "1":
            message = safe_message(response.get("msg")) or "未知原因"
            if ui is not None:
                ui.submission(f"FAILED: {message}", render=False)
                ui.event(f"server rejected submission: {message}", "ERR")
            else:
                print(f"[结果] 服务端未接受提交：{message}")
            return 2

    if ui is not None:
        ui.set_phase("STATUS", render=False)
        ui.event(
            "checking final status without resubmitting volunteer.do"
            if submission_uncertain
            else "volunteer.do accepted; checking final status"
        )
    else:
        if not submission_uncertain:
            print("[结果] volunteer.do 已接受，等待 studentstatus.do 最终状态")
    for attempt in range(1, 11):
        if attempt > 1:
            if ui is not None:
                await ui.wait(1.0)
                ui.set_phase("STATUS", render=False)
            else:
                await asyncio.sleep(1.0)
        if ui is not None:
            ui.action(f"status check {attempt}/10", render=True)

        # 对“提交请求本身超时/断网”的情况，courseResult.do 是更可靠的
        # 只读事实来源；一旦目标教学班已出现即可确认成功。
        try:
            if submission_uncertain and await selected_course_present(
                api,
                context,
                course.teaching_class_id,
            ):
                if ui is not None:
                    ui.submission("SUCCESS: VERIFIED", render=False)
                    ui.set_phase("READY", render=False)
                    ui.event("uncertain submission verified in courseResult.do", "OK")
                else:
                    print("[结果] 已通过 courseResult.do 确认目标课程选课成功")
                return 0

            status = await api.post(
                STUDENT_STATUS_PATH,
                {"studentCode": context.student_code},
            )
        except NetworkTransientError as exc:
            message = safe_message(exc)
            if ui is not None:
                ui.event(
                    f"verification network error ({attempt}/10): {message}",
                    "WARN",
                )
            else:
                print(f"[等待] 结果核验网络异常（{attempt}/10），继续只读重试")
            continue
        status_code = as_text(status.get("code"))
        if status_code == "1":
            if submission_uncertain:
                # studentstatus.do 可能反映最近一次操作；运输层不确定时仍以
                # courseResult.do 出现目标教学班为最终确认，避免误报成功。
                if ui is not None:
                    ui.event(
                        "studentstatus reports success; waiting for courseResult verification",
                        "WAIT",
                    )
                continue
            if ui is not None:
                ui.submission("SUCCESS", render=False)
                ui.set_phase("READY", render=False)
                ui.event("course selection confirmed", "OK")
            else:
                print("[结果] 添加选课成功")
            return 0
        if status_code == "-1" and not submission_uncertain:
            message = safe_message(status.get("msg")) or "未知原因"
            if ui is not None:
                ui.submission(f"FAILED: {message}", render=False)
                ui.event(f"course selection failed: {message}", "ERR")
            else:
                print(f"[结果] 添加选课失败：{message}")
            return 3
        if ui is not None:
            ui.event(f"status pending ({attempt}/10)", "WAIT")
        else:
            print(f"[等待] 操作状态仍在处理（第 {attempt}/10 次）")

    if ui is not None:
        ui.submission("UNCERTAIN: VERIFY MANUALLY", render=False)
        ui.event("status verification timeout; browser will remain open", "ERR")
    raise SubmissionUncertainError(
        "提交后 10 次只读核验仍无法确认最终结果；未重发 volunteer.do，"
        "请在保留的浏览器中人工核对"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NNU 课程查询与博雅课受控选课：只查询仙林/仙林新北"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="没有目标时持续轮询；默认间隔 0.1 秒",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="watch 模式轮询间隔，至少 0.1 秒",
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
    credential_group = parser.add_mutually_exclusive_group()
    credential_group.add_argument(
        "--setup-credentials",
        action="store_true",
        help="交互式保存学号/密码到 Windows 凭据管理器",
    )
    credential_group.add_argument(
        "--clear-credentials",
        action="store_true",
        help="删除 Windows 凭据管理器中已保存的学号/密码",
    )
    parser.add_argument(
        "--no-auto-fill",
        action="store_true",
        help="本次运行不从 Windows 凭据管理器自动填充登录框",
    )
    parser.add_argument(
        "--plain-output",
        action="store_true",
        help="禁用 watch 模式 TUI，保留传统逐行输出",
    )
    parser.add_argument("--course-id", default="", help="精确教学班 ID")
    parser.add_argument("--course-number", default="", help="精确课程号")
    parser.add_argument("--course-name", default="", help="课程名包含匹配")
    parser.add_argument(
        "--collect-open-courses",
        "--all-open-courses",
        dest="collect_open_courses",
        action="store_true",
        help="只读采集当前批次 QXKC 全校课程并导出 JSON/CSV",
    )
    parser.add_argument(
        "--collect-selected-courses",
        "--selected-courses",
        dest="collect_selected_courses",
        action="store_true",
        help="只读采集当前批次已选课程并导出 JSON/CSV",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="采集结果输出目录（默认：05_工具/.runtime）",
    )
    parser.add_argument(
        "--school-keyword",
        default="",
        help="全校课程查询关键字，仅与 --collect-open-courses 一起使用",
    )
    parser.add_argument(
        "--school-category",
        default="",
        help="全校课程通识类别代码（XGXKLBDM），仅用于采集",
    )
    parser.add_argument(
        "--school-unit",
        default="",
        help="全校课程开课单位代码（KKDWDM），仅用于采集",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="启用 volunteer.do 提交；必须同时指定课程筛选",
    )
    parser.add_argument(
        "--auto-select",
        action="store_true",
        help=(
            "配合 --watch/--yes 使用：只轮询仙林；按中国民歌、创新创业基础/"
            "智能文明、揭秘大气污染优先，严格保证 2024 模块互异并以网络热度兜底"
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
    if args.setup_credentials or args.clear_credentials:
        has_operational_options = any(
            (
                args.watch,
                args.course_id,
                args.course_number,
                args.course_name,
                args.collect_open_courses,
                args.collect_selected_courses,
                args.submit,
                args.auto_select,
                args.yes,
                args.need_book is not None,
                args.test_teaching_class_id,
                args.output is not None,
                args.export_dir != DEFAULT_EXPORT_DIR,
                args.school_keyword,
                args.school_category,
                args.school_unit,
                args.no_auto_fill,
                args.plain_output,
            )
        )
        if has_operational_options:
            parser.error(
                "--setup-credentials/--clear-credentials 不能与查询或提交参数一起使用"
            )
        return

    if args.watch and args.interval < 0.1:
        parser.error("--watch 的 --interval 不能小于 0.1 秒")
    if args.request_delay < 0.5:
        parser.error("--request-delay 不能小于 0.5 秒")
    if not 1 <= args.page_size <= 100:
        parser.error("--page-size 必须在 1 到 100 之间")
    if args.max_pages < 1:
        parser.error("--max-pages 必须大于 0")
    if args.timeout < 30:
        parser.error("--timeout 不能小于 30 秒")

    collecting = args.collect_open_courses or args.collect_selected_courses
    if collecting:
        if any(
            (
                args.watch,
                args.course_id,
                args.course_number,
                args.course_name,
                args.submit,
                args.auto_select,
                args.yes,
                args.need_book is not None,
                args.test_teaching_class_id,
                args.output is not None,
            )
        ):
            parser.error(
                "课程采集模式是只读一次性任务，不能与轮询、筛选提交或 --output 混用"
            )
        if (
            (args.school_keyword or args.school_category or args.school_unit)
            and not args.collect_open_courses
        ):
            parser.error(
                "--school-keyword/--school-category/--school-unit "
                "必须与 --collect-open-courses 一起使用"
            )
        return

    if args.school_keyword or args.school_category or args.school_unit:
        parser.error(
            "--school-keyword/--school-category/--school-unit "
            "必须与 --collect-open-courses 一起使用"
        )
    if args.export_dir != DEFAULT_EXPORT_DIR:
        parser.error("--export-dir 必须与课程采集模式一起使用")

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


def is_default_tui_request(args: argparse.Namespace) -> bool:
    """判断是否是无操作参数的启动，让可见终端进入鼠标配置页。"""

    return not any(
        (
            args.watch,
            args.course_id,
            args.course_number,
            args.course_name,
            args.collect_open_courses,
            args.collect_selected_courses,
            args.submit,
            args.auto_select,
            args.yes,
            args.need_book is not None,
            args.test_teaching_class_id,
            args.output is not None,
            args.export_dir != DEFAULT_EXPORT_DIR,
            args.school_keyword,
            args.school_category,
            args.school_unit,
            args.plain_output,
            args.setup_credentials,
            args.clear_credentials,
        )
    )


async def async_main(args: argparse.Namespace) -> int:
    playwright = context = page = None
    default_tui = (
        is_default_tui_request(args)
        and bool(sys.stdin.isatty())
        and bool(sys.stdout.isatty())
    )
    if default_tui:
        # 无参数默认加载自动选课完整预设；提交仍须点击“应用并启动”。
        args.watch = True
    mode = (
        "AUTO-SELECT"
        if args.auto_select or default_tui
        else "TARGET WATCH"
        if args.submit and args.watch
        else "WATCH"
    )
    ui = TerminalUI(
        mode,
        enabled=(
            (args.watch or default_tui)
            and not args.plain_output
            and bool(sys.stdout.isatty())
        ),
    )
    active_ui = ui if ui.enabled else None
    if active_ui is not None and not sys.stdin.isatty():
        active_ui.start()
    if default_tui:
        # Direct no-argument startup opens the complete auto-selection preset.
        # The browser is still not opened until the user applies the TUI.
        ui._set_config_mode(args, "AUTO-SELECT")
    expected_teaching_class_type = (
        ALL_SCHOOL_TEACHING_CLASS_TYPE
        if args.collect_open_courses
        else BOYA_TEACHING_CLASS_TYPE
    )
    campus_codes = ("2",) if args.auto_select else ("2", "4")
    try:
        if active_ui is not None:
            active_ui.configure(
                args,
                campus_codes=campus_codes,
                expected_teaching_class_type=expected_teaching_class_type,
            )
            selected_campuses = await active_ui.configure_interactively(
                args,
                campus_codes=campus_codes,
                expected_teaching_class_type=expected_teaching_class_type,
            )
            if selected_campuses is None:
                return 130
            campus_codes = selected_campuses
        playwright, context, page = await open_visible_browser(
            args.timeout,
            auto_fill_credentials=not args.no_auto_fill,
            ui=active_ui,
        )
        browser_session = BrowserSession(page)
        session_context = await browser_session.read_context()
        last_batch_open: Optional[bool] = None
        previous_network_counts: dict[str, int] = {}
        last_course_snapshot: list[Course] = []

        async def recover_session() -> None:
            nonlocal session_context
            nonlocal last_batch_open
            nonlocal previous_network_counts
            nonlocal last_course_snapshot

            session_context = await reauthenticate_visible_browser(
                page,
                browser_session,
                timeout_seconds=args.timeout,
                auto_fill_credentials=not args.no_auto_fill,
                ui=active_ui,
            )
            # 新 token/轮次上下文建立后，不沿用旧会话的轮次状态和人数增量。
            last_batch_open = None
            previous_network_counts = {}
            last_course_snapshot = []
            if active_ui is not None:
                active_ui.set_session(context=session_context, render=False)

        if active_ui is not None:
            active_ui.set_session(context=session_context, render=False)
        if (
            not args.collect_selected_courses
            and session_context.teaching_class_type
            not in {"", expected_teaching_class_type}
        ):
            message = (
                f"page type is not {expected_teaching_class_type}; "
                f"requests remain explicitly {expected_teaching_class_type}"
            )
            if active_ui is not None:
                active_ui.event(message, "WARN")
            else:
                print(
                    f"[提示] 当前页面教学班类型不是 {expected_teaching_class_type}；"
                    f"本工具仍只发送明确的 {expected_teaching_class_type} 查询"
                )
        api = BrowserApi(page, reauth_handler=recover_session)

        if args.collect_open_courses or args.collect_selected_courses:
            if args.collect_open_courses:
                school_results, school_courses = await run_all_school_query_cycle(
                    api,
                    session_context,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                    request_delay=args.request_delay,
                    campus_codes=("2", "4"),
                    keyword=args.school_keyword,
                    category=args.school_category,
                    teaching_unit=args.school_unit,
                )
                write_open_course_exports(
                    args.export_dir,
                    session_context,
                    school_results,
                    school_courses,
                    keyword=args.school_keyword,
                    category=args.school_category,
                    teaching_unit=args.school_unit,
                )
            if args.collect_selected_courses:
                selected_records = await query_selected_courses(
                    api,
                    session_context,
                )
                write_selected_course_exports(
                    args.export_dir,
                    session_context,
                    selected_records,
                )
            return 0

        while True:
            if active_ui is not None:
                active_ui.set_phase("SELECTED", render=False)
            if args.auto_select:
                selected_records = await query_selected_courses(
                    api,
                    session_context,
                )
                hydrate_selected_modules(selected_records, last_course_snapshot)
                selected_boya = selected_boya_theory_courses(selected_records)
                selected_count = len(selected_boya)
                selected_modules = selected_boya_modules(selected_records)
                (
                    selected_network_count,
                    selected_offline_count,
                    selected_delivery_unknown,
                ) = selected_boya_delivery_counts(selected_records)
                selected_credit_total = selected_boya_credit_total(selected_records)
                if all(selected_modules) and (
                    len(set(selected_modules)) != len(selected_modules)
                ):
                    raise UnsafeSelectionError(
                        "当前已选博雅课存在 2024 模块重复，"
                        "为避免违反不同模块要求，自动模式已停止"
                    )
                if (
                    selected_delivery_unknown == 0
                    and selected_network_count > MAX_NETWORK_COURSES
                ):
                    raise UnsafeSelectionError(
                        f"当前已选博雅网络课程为 {selected_network_count} 门，"
                        f"超过最多 {MAX_NETWORK_COURSES} 门限制；自动模式已停止"
                    )
                if active_ui is not None:
                    active_ui.selected(
                        selected_count,
                        credits=selected_credit_total,
                        network_count=selected_network_count,
                        offline_count=selected_offline_count,
                        unknown_count=selected_delivery_unknown,
                        status="OK",
                        render=False,
                    )
                    active_ui.event(
                        f"selected Boya theory={selected_count}/{AUTO_TARGET_COUNT} "
                        f"net={selected_network_count}/{MAX_NETWORK_COURSES} "
                        f"off={selected_offline_count}/{MIN_OFFLINE_COURSES} "
                        f"credits={selected_credit_total if selected_credit_total is not None else '?'}",
                        "STAT",
                        render=False,
                    )
                else:
                    credit_label = (
                        "?"
                        if selected_credit_total is None
                        else f"{selected_credit_total:g}"
                    )
                    print(
                        f"[进度] 当前已选博雅理论课：{selected_count}/"
                        f"{AUTO_TARGET_COUNT}；网络：{selected_network_count}/"
                        f"{MAX_NETWORK_COURSES}；线下：{selected_offline_count}/"
                        f"{MIN_OFFLINE_COURSES}；学分：{credit_label}"
                    )
                if (
                    selected_count >= AUTO_TARGET_COUNT
                    and all(selected_modules)
                    and selected_delivery_unknown == 0
                ):
                    if not auto_selection_goal_met(selected_records):
                        raise UnsafeSelectionError(
                            f"已选博雅课已达到 {AUTO_TARGET_COUNT} 门，但未同时满足"
                            f"中国民歌必选、2024 模块互异、网络不超过 {MAX_NETWORK_COURSES} 门、"
                            f"线下至少 {MIN_OFFLINE_COURSES} 门，"
                            "不能再自动追加课程"
                        )
                    if active_ui is not None:
                        active_ui.set_phase("DONE", render=False)
                        active_ui.event(
                            f"target reached: {AUTO_TARGET_COUNT} Boya theory courses",
                            "DONE",
                        )
                    else:
                        print(
                            f"[完成] 已选博雅理论课数量已达到 {AUTO_TARGET_COUNT} 门，"
                            "停止自动选课"
                        )
                    await hold_browser_for_manual_control(
                        page,
                        ui=active_ui,
                        message="自动选课目标已完成；停止自动提交并保留浏览器供人工检查",
                    )
                    return 0

                batch_is_open = await query_batch_open(api, session_context)
                if active_ui is not None:
                    active_ui.batch_open(batch_is_open, render=False)
                if batch_is_open != last_batch_open:
                    if batch_is_open:
                        message = "selection batch is OPEN; starting Boya query"
                        if active_ui is not None:
                            active_ui.event(message, "OPEN", render=False)
                        else:
                            print("[开放] 服务端已确认选课轮次开放，开始查询博雅课")
                    else:
                        message = (
                            "armed; batch not open yet, submission is blocked"
                        )
                        if active_ui is not None:
                            active_ui.event(message, "ARM", render=False)
                        else:
                            print("[待命] 选课轮次尚未开放；已武装，禁止提前提交")
                last_batch_open = batch_is_open
                if not batch_is_open:
                    if active_ui is not None:
                        active_ui.set_phase("ARMED", render=True)
                        await active_ui.wait(args.interval)
                    else:
                        await asyncio.sleep(args.interval)
                    session_context = await browser_session.read_context()
                    if active_ui is not None:
                        active_ui.set_session(
                            context=session_context,
                            render=False,
                        )
                    continue

            if active_ui is not None:
                active_ui.set_phase("QUERY", render=True)
            cycle_started = time.monotonic()
            results, courses = await run_query_cycle(
                api,
                session_context,
                page_size=args.page_size,
                max_pages=args.max_pages,
                request_delay=args.request_delay,
                campus_codes=campus_codes,
                ui=active_ui,
                check_conflict="" if args.auto_select else "0",
                check_capacity="" if args.auto_select else "0",
            )
            last_course_snapshot = list(courses)
            safe_candidates = [
                course for course in courses if course.is_safe_candidate()
            ]
            if args.auto_select:
                hydrate_selected_modules(selected_records, courses)
                selected_modules = selected_boya_modules(selected_records)
                (
                    selected_network_count,
                    selected_offline_count,
                    selected_delivery_unknown,
                ) = selected_boya_delivery_counts(selected_records)
                if (
                    any(not module for module in selected_modules)
                    or len(set(selected_modules)) != len(selected_modules)
                ):
                    raise UnsafeSelectionError(
                        "无法确认全部已选博雅课的 2024 模块，或检测到模块重复；"
                        "为避免误选，自动模式已停止"
                    )
                if selected_delivery_unknown:
                    raise UnsafeSelectionError(
                        "无法确认全部已选博雅课的线上/线下属性；"
                        "为避免突破网络最多两门限制，自动模式已停止"
                    )
                if selected_network_count > MAX_NETWORK_COURSES:
                    raise UnsafeSelectionError(
                        f"已选博雅网络课程为 {selected_network_count} 门，"
                        f"超过最多 {MAX_NETWORK_COURSES} 门限制；自动模式已停止"
                    )
                if active_ui is not None:
                    active_ui.selected(
                        selected_count,
                        credits=selected_credit_total,
                        network_count=selected_network_count,
                        offline_count=selected_offline_count,
                        unknown_count=selected_delivery_unknown,
                        status="OK",
                        render=False,
                    )
                if selected_count >= AUTO_TARGET_COUNT:
                    if not auto_selection_goal_met(selected_records):
                        raise UnsafeSelectionError(
                            f"已选博雅课已达到 {AUTO_TARGET_COUNT} 门，但未同时满足"
                            f"中国民歌必选、2024 模块互异、网络不超过 {MAX_NETWORK_COURSES} 门、"
                            f"线下至少 {MIN_OFFLINE_COURSES} 门，"
                            "不能再自动追加课程"
                        )
                    if active_ui is not None:
                        active_ui.set_phase("DONE", render=False)
                        active_ui.event(
                            f"target reached: {AUTO_TARGET_COUNT} courses, "
                            "unique modules, "
                            "offline 中国民歌 selected",
                            "DONE",
                        )
                    else:
                        print(
                            f"[完成] 已选 {AUTO_TARGET_COUNT} 门不同模块博雅课，"
                            "且包含线下中国民歌"
                        )
                    await hold_browser_for_manual_control(
                        page,
                        ui=active_ui,
                        message="自动选课目标已完成；停止自动提交并保留浏览器供人工检查",
                    )
                    return 0
                has_network_baseline = bool(previous_network_counts)
                growth, previous_network_counts = network_demand_growth(
                    courses,
                    previous_network_counts,
                )
                ranked_candidates = rank_auto_candidates(
                    courses,
                    selected_records,
                    growth,
                    allow_network_fallback=has_network_baseline,
                )
            else:
                growth = {}
                ranked_candidates = []
            display_candidates = (
                [decision.course for decision in ranked_candidates]
                if args.auto_select
                else safe_candidates
            )
            if active_ui is not None:
                active_ui.cycle(
                    results,
                    courses,
                    safe_candidates=display_candidates,
                    elapsed=time.monotonic() - cycle_started,
                    render=False,
                )
                if args.auto_select:
                    active_ui.network_metrics(
                        courses,
                        growth,
                        ranked_candidates,
                        render=False,
                    )
            if args.output:
                write_snapshot(
                    args.output,
                    session_context,
                    results,
                    courses,
                    quiet=active_ui is not None,
                )

            if active_ui is not None:
                if courses:
                    active_ui.event(
                        f"courses returned; safe candidates={len(safe_candidates)}",
                        "DATA",
                        render=False,
                    )
                elif args.auto_select:
                    active_ui.event(
                        "no course returned by Boya query; continuing",
                        "WAIT",
                        render=False,
                    )
                else:
                    active_ui.event(
                        "no course returned by selected query",
                        "WAIT",
                        render=False,
                    )
                active_ui.render(force=True)
            elif courses:
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
                submitted = False
                batch_rearmed = False
                occupied_modules = set(selected_modules)
                for decision in ranked_candidates:
                    candidate = decision.course
                    if active_ui is not None:
                        active_ui.set_phase("PREFLIGHT", render=False)
                        active_ui.action(
                            f"{decision.reason}: {candidate.short_label()}"
                        )
                    else:
                        print(
                            f"[自动选课] {decision.reason}："
                            f"{candidate.short_label()}"
                        )
                    try:
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
                    except BatchNotOpenError:
                        last_batch_open = False
                        batch_rearmed = True
                        if active_ui is not None:
                            active_ui.batch_open(False, render=False)
                            active_ui.set_phase("ARMED", render=False)
                            active_ui.event(
                                "batch closed during preflight; re-armed without submission",
                                "ARM",
                            )
                        else:
                            print("[待命] 提交预检时轮次尚未开放，重新进入武装等待")
                        break
                    except UnsafeSelectionError as exc:
                        message = (
                            f"skip {candidate.course_name}: "
                            f"{safe_message(exc)}"
                        )
                        if active_ui is not None:
                            active_ui.event(message, "SKIP", render=False)
                        else:
                            print(f"[跳过] {message}")
                        continue

                    fresh_module = fresh_course.module_key()
                    fresh_delivery_mode = fresh_course.delivery_mode()
                    if (
                        not fresh_module
                        or fresh_module != candidate.module_key()
                        or fresh_module in occupied_modules
                        or fresh_delivery_mode is None
                        or fresh_delivery_mode != candidate.delivery_mode()
                        or not candidate_fits_delivery_budget(
                            fresh_course,
                            selected_records,
                        )
                        or (
                            candidate.course_name == REQUIRED_OFFLINE_COURSE
                            and not fresh_course.is_offline_course()
                        )
                    ):
                        message = (
                            f"skip {candidate.course_name}: module/delivery-budget "
                            "constraint changed during preflight"
                        )
                        if active_ui is not None:
                            active_ui.event(message, "SKIP", render=False)
                        else:
                            print(f"[跳过] {message}")
                        continue

                    submit_result = await submit_course(
                        api,
                        context_for_submit,
                        fresh_course,
                        need_book=selected_need_book,
                        test_teaching_class_id=selected_test_id,
                        yes=args.yes,
                        ui=active_ui,
                    )
                    if submit_result == 3:
                        message = (
                            f"server rejected {candidate.course_name}; "
                            "trying the next ranked candidate"
                        )
                        if active_ui is not None:
                            active_ui.event(message, "SKIP", render=False)
                        else:
                            print(f"[跳过] {message}")
                        continue
                    if submit_result != 0:
                        return submit_result
                    submitted = True
                    break

                if batch_rearmed:
                    continue
                if submitted:
                    session_context = await browser_session.read_context()
                    if active_ui is not None:
                        active_ui.set_session(
                            context=session_context,
                            render=False,
                        )
                    selected_records = await query_selected_courses(
                        api,
                        session_context,
                    )
                    hydrate_selected_modules(
                        selected_records,
                        [*courses, fresh_course],
                    )
                    selected_boya = selected_boya_theory_courses(selected_records)
                    selected_count = len(selected_boya)
                    selected_modules = selected_boya_modules(selected_records)
                    (
                        selected_network_count,
                        selected_offline_count,
                        selected_delivery_unknown,
                    ) = selected_boya_delivery_counts(selected_records)
                    selected_credit_total = selected_boya_credit_total(selected_records)
                    if (
                        any(not module for module in selected_modules)
                        or len(set(selected_modules)) != len(selected_modules)
                    ):
                        raise UnsafeSelectionError(
                            "提交后检测到模块缺失或重复，自动模式已停止"
                        )
                    if selected_delivery_unknown:
                        raise UnsafeSelectionError(
                            "提交后无法确认全部已选博雅课的线上/线下属性；"
                            "自动模式已停止"
                        )
                    if selected_network_count > MAX_NETWORK_COURSES:
                        raise UnsafeSelectionError(
                            f"提交后网络博雅课为 {selected_network_count} 门，"
                            f"超过最多 {MAX_NETWORK_COURSES} 门限制；自动模式已停止"
                        )
                    if active_ui is not None:
                        active_ui.selected(
                            selected_count,
                            credits=selected_credit_total,
                            network_count=selected_network_count,
                            offline_count=selected_offline_count,
                            unknown_count=selected_delivery_unknown,
                            status="OK",
                            render=False,
                        )
                        active_ui.event(
                            f"after submit Boya theory={selected_count}/{AUTO_TARGET_COUNT} "
                            f"net={selected_network_count}/{MAX_NETWORK_COURSES} "
                            f"off={selected_offline_count}/{MIN_OFFLINE_COURSES} "
                            f"credits={selected_credit_total if selected_credit_total is not None else '?'} "
                            f"modules={','.join(selected_modules)}",
                            "STAT",
                            render=False,
                        )
                    else:
                        credit_label = (
                            "?"
                            if selected_credit_total is None
                            else f"{selected_credit_total:g}"
                        )
                        print(
                            f"[进度] 本次操作后已选博雅理论课：{selected_count}/"
                            f"{AUTO_TARGET_COUNT}；网络：{selected_network_count}/"
                            f"{MAX_NETWORK_COURSES}；线下：{selected_offline_count}/"
                            f"{MIN_OFFLINE_COURSES}；学分：{credit_label}；"
                            f"模块：{','.join(selected_modules)}"
                        )
                    if selected_count >= AUTO_TARGET_COUNT:
                        if not auto_selection_goal_met(selected_records):
                            raise UnsafeSelectionError(
                                f"达到 {AUTO_TARGET_COUNT} 门后仍未满足"
                                f"中国民歌必选、模块互异、网络不超过 {MAX_NETWORK_COURSES} 门、"
                                f"线下至少 {MIN_OFFLINE_COURSES} 门，已停止"
                            )
                        if active_ui is not None:
                            active_ui.set_phase("DONE", render=False)
                            active_ui.event(
                                f"target reached: {AUTO_TARGET_COUNT} courses, "
                                "unique modules, "
                                "offline 中国民歌 selected",
                                "DONE",
                            )
                        else:
                            print(
                                f"[完成] 已选 {AUTO_TARGET_COUNT} 门不同模块博雅课，"
                                "且包含线下中国民歌"
                            )
                        await hold_browser_for_manual_control(
                            page,
                            ui=active_ui,
                            message="自动选课目标已完成；停止自动提交并保留浏览器供人工检查",
                        )
                        return 0
                else:
                    if active_ui is not None:
                        active_ui.event(
                            "no candidate satisfies priority/module rules; continue polling",
                            "WAIT",
                            render=True,
                        )
                    else:
                        print("[等待] 本轮没有满足优先级与模块约束的安全候选，继续轮询")
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
                    if active_ui is not None:
                        active_ui.set_phase("PREFLIGHT", render=False)
                        active_ui.action(
                            f"target matched: {safe_matched[0].short_label()}"
                        )
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
                    submit_result = await submit_course(
                        api,
                        context_for_submit,
                        fresh_course,
                        need_book=selected_need_book,
                        test_teaching_class_id=selected_test_id,
                        yes=args.yes,
                        ui=active_ui,
                    )
                    if submit_result == 0:
                        await hold_browser_for_manual_control(
                            page,
                            ui=active_ui,
                            message="目标课程提交已确认成功；保留浏览器供人工检查",
                        )
                    return submit_result
                if len(safe_matched) > 1:
                    if active_ui is not None:
                        active_ui.set_phase("STOP", render=False)
                        active_ui.event(
                            f"multiple target matches ({len(safe_matched)}); no submission",
                            "ERR",
                        )
                    else:
                        print("[停止] 目标筛选匹配多个教学班，未提交：")
                        for course in safe_matched:
                            print(f"  {course.short_label()}")
                    return 5
                if matched and not safe_matched:
                    if active_ui is not None:
                        active_ui.event(
                            "target exists but is unsafe; no submission",
                            "WAIT",
                        )
                    else:
                        print("[停止] 目标课程存在，但当前不满足无冲突/未满，未提交")
                elif args.watch:
                    if active_ui is not None:
                        active_ui.event("target not found; continue polling", "WAIT")
                    else:
                        print("[等待] 目标课程尚未出现，继续按间隔查询")
                else:
                    if active_ui is not None:
                        active_ui.set_phase("STOP", render=False)
                        active_ui.event("no unique safe target; no submission", "ERR")
                    else:
                        print("[停止] 没有唯一的安全目标课程，未提交")

            if not args.watch:
                return 0
            if active_ui is not None:
                await active_ui.wait(args.interval)
            else:
                await asyncio.sleep(args.interval)
            session_context = await browser_session.read_context()
            if active_ui is not None:
                active_ui.set_session(context=session_context, render=False)
    except SubmissionUncertainError as exc:
        message = safe_message(exc)
        if active_ui is not None:
            active_ui.error(message)
        else:
            print(f"[警告] {message}", file=sys.stderr)
        await hold_browser_for_manual_control(
            page,
            ui=active_ui,
            message="提交结果无法自动确认；未重复提交，请人工核对当前页面",
            phase="VERIFY_HOLD",
        )
        return 11
    except SessionExpiredError as exc:
        message = safe_message(exc)
        if active_ui is not None:
            active_ui.error(message)
        else:
            print(f"[错误] {message}", file=sys.stderr)
        await hold_browser_for_manual_control(
            page,
            ui=active_ui,
            message="自动重新登录未能恢复；保留浏览器供人工处理",
            phase="REAUTH_HOLD",
        )
        return 10
    except AutomationError as exc:
        message = safe_message(exc)
        if active_ui is not None:
            active_ui.error(message)
        else:
            print(f"[错误] {message}", file=sys.stderr)
        return 10
    except asyncio.CancelledError:
        if active_ui is not None:
            active_ui.phase = "STOP"
            active_ui.event("user interrupted", "STOP")
        return 130
    except KeyboardInterrupt:
        if active_ui is not None:
            active_ui.phase = "STOP"
            active_ui.event("user interrupted", "STOP")
        else:
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
        if active_ui is not None:
            active_ui.close()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    validate_args(parser, args)
    if args.setup_credentials:
        try:
            return setup_login_credentials()
        except AutomationError as exc:
            print(f"[错误] {safe_message(exc)}", file=sys.stderr)
            return 10
        except KeyboardInterrupt:
            print("\n[停止] 用户中断")
            return 130
    if args.clear_credentials:
        try:
            if delete_login_credentials():
                print("[完成] 已删除 Windows 凭据管理器中的登录凭据")
            else:
                print("[提示] Windows 凭据管理器中没有已保存的登录凭据")
            return 0
        except AutomationError as exc:
            print(f"[错误] {safe_message(exc)}", file=sys.stderr)
            return 10
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\n[停止] 用户中断")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
