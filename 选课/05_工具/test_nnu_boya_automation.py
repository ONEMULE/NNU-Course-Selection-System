#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nnu_boya_automation.py 的离线单元测试；不访问 NNU，也不需要登录态。"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("nnu_boya_automation.py")
SPEC = importlib.util.spec_from_file_location("nnu_boya_automation", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("无法加载被测脚本")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class NnuBoyaAutomationTests(unittest.TestCase):
    def test_api_url_keeps_application_context(self) -> None:
        self.assertEqual(
            MODULE.build_api_url("/sys/xsxkapp/elective/courseResult.do"),
            "https://xsxk.nnu.edu.cn/xsxkapp/sys/xsxkapp/elective/courseResult.do",
        )
        self.assertEqual(
            MODULE.build_api_url(
                "https://xsxk.nnu.edu.cn/xsxkapp/sys/xsxkapp/elective/courseResult.do"
            ),
            "https://xsxk.nnu.edu.cn/xsxkapp/sys/xsxkapp/elective/courseResult.do",
        )

    def test_browser_api_passes_full_application_url_to_page(self) -> None:
        class FakePage:
            def __init__(self) -> None:
                self.arguments = None

            async def evaluate(self, script, arguments):
                self.arguments = arguments
                return {"status": 200, "text": '{"code":"1"}'}

        page = FakePage()
        response = asyncio.run(
            MODULE.BrowserApi(page).get(
                MODULE.SELECTED_COURSE_PATH,
                {"studentCode": "student", "electiveBatchCode": "batch"},
            )
        )
        self.assertEqual(response["code"], "1")
        self.assertEqual(
            page.arguments["requestUrl"],
            "https://xsxk.nnu.edu.cn/xsxkapp/sys/xsxkapp/elective/courseResult.do",
        )

    def test_timestamped_path_starts_with_timestamp_query(self) -> None:
        path = MODULE.timestamped_path(MODULE.SELECTED_COURSE_PATH)
        self.assertRegex(path, r"^/sys/xsxkapp/elective/courseResult\.do\?timestamp=\d+$")

    def test_login_credentials_round_trip(self) -> None:
        credentials = MODULE.LoginCredentials(
            student_code="20261234",
            password="test-password",
        )
        raw = MODULE.serialize_login_credentials(credentials)
        restored = MODULE.parse_login_credentials(raw)
        self.assertEqual(restored, credentials)

    def test_invalid_login_credentials_are_rejected(self) -> None:
        with self.assertRaises(MODULE.AutomationError):
            MODULE.parse_login_credentials('{"studentCode":"20261234"}')
        with self.assertRaises(MODULE.AutomationError):
            MODULE.parse_login_credentials("not-json")

    def test_login_form_autofill_only_fills_username_and_password(self) -> None:
        class FakeLocator:
            def __init__(self) -> None:
                self.filled = None

            async def wait_for(self, *, state, timeout):
                self.wait_arguments = (state, timeout)

            async def fill(self, value):
                self.filled = value

        class FakePage:
            def __init__(self) -> None:
                self.locators = {
                    "#loginName": FakeLocator(),
                    "#loginPwd": FakeLocator(),
                }

            def locator(self, selector):
                return self.locators[selector]

        page = FakePage()
        credentials = MODULE.LoginCredentials(
            student_code="20261234",
            password="test-password",
        )
        with patch.object(
            MODULE,
            "load_login_credentials",
            return_value=credentials,
        ):
            asyncio.run(MODULE.autofill_login_form(page))

        self.assertEqual(page.locators["#loginName"].filled, "20261234")
        self.assertEqual(page.locators["#loginPwd"].filled, "test-password")
        self.assertEqual(set(page.locators), {"#loginName", "#loginPwd"})

    def test_no_auto_fill_does_not_read_credentials(self) -> None:
        class FakePage:
            def locator(self, selector):
                raise AssertionError("disabled autofill must not inspect the page")

        with patch.object(MODULE, "load_login_credentials") as load:
            asyncio.run(MODULE.autofill_login_form(FakePage(), enabled=False))
        load.assert_not_called()

    def test_nnu_page_urls_include_sys_xsxkapp_prefix(self) -> None:
        self.assertEqual(
            MODULE.ENTRY_URL,
            "https://xsxk.nnu.edu.cn/xsxkapp/sys/xsxkapp/*default/index.do",
        )
        self.assertEqual(
            MODULE.GRAB_URL,
            "https://xsxk.nnu.edu.cn/xsxkapp/sys/xsxkapp/*default/grablessons.do",
        )

    def test_authenticated_navigation_keeps_token_in_page_context(self) -> None:
        class FakePage:
            def __init__(self) -> None:
                self.script = ""
                self.path = ""
                self.waited = False

            async def evaluate(self, script, path):
                self.script = script
                self.path = path

            async def wait_for_load_state(self, state, timeout):
                self.waited = state == "domcontentloaded" and timeout == 60_000

        page = FakePage()
        session = MODULE.BrowserSession(page)
        asyncio.run(session.goto_authenticated_page(MODULE.GRAB_URL))
        self.assertEqual(page.path, MODULE.GRAB_URL)
        self.assertIn('sessionStorage.getItem("token")', page.script)
        self.assertIn("target.searchParams.set(\"token\", token)", page.script)
        self.assertTrue(page.waited)

    def test_query_content_follows_frontend_order(self) -> None:
        self.assertEqual(
            MODULE.compose_query_content("人工智能", "A01", "B02"),
            "人工智能,XGXKLBDM:A01,KCBK:B02",
        )
        self.assertEqual(
            MODULE.compose_query_content("", "", ""),
            "",
        )

    def test_query_payload_is_form_encoded_json_field(self) -> None:
        payload = MODULE.build_query_payload(
            student_code="student",
            batch_code="batch",
            campus_code="2",
            page_size=10,
            page_number=3,
        )
        self.assertEqual(set(payload), {"querySetting"})
        outer = json.loads(payload["querySetting"])
        self.assertEqual(outer["data"]["studentCode"], "student")
        self.assertEqual(outer["data"]["campus"], "2")
        self.assertEqual(outer["data"]["teachingClassType"], "XGXK")
        self.assertEqual(outer["data"]["checkConflict"], "0")
        self.assertEqual(outer["data"]["checkCapacity"], "0")
        self.assertEqual(outer["pageNumber"], "3")

    def test_add_payload_matches_public_course_shape(self) -> None:
        payload = MODULE.build_add_payload(
            student_code="student",
            batch_code="batch",
            teaching_class_id="tc-1",
            campus_code="4",
            need_book="0",
        )
        self.assertEqual(set(payload), {"addParam"})
        data = json.loads(payload["addParam"])["data"]
        self.assertEqual(data["operationType"], "1")
        self.assertEqual(data["teachingClassId"], "tc-1")
        self.assertEqual(data["campus"], "4")
        self.assertEqual(data["teachingClassType"], "XGXK")
        self.assertEqual(data["needBook"], "0")

    def test_unknown_campus_is_rejected(self) -> None:
        with self.assertRaises(MODULE.UnsafeSelectionError):
            MODULE.build_add_payload(
                student_code="student",
                batch_code="batch",
                teaching_class_id="tc-1",
                campus_code="1",
            )

    def test_course_safety_requires_explicit_zero_flags(self) -> None:
        item = {
            "teachingClassID": "tc-1",
            "courseNumber": "100",
            "courseName": "测试课程",
            "isConflict": "0",
            "isFull": "0",
            "classCapacity": "40",
            "numberOfFirstVolunteer": "39",
            "hasTest": "0",
        }
        course = MODULE.Course.from_api(item, "2", "仙林校区")
        self.assertIsNotNone(course)
        self.assertTrue(course.is_safe_candidate())

        full_item = dict(item)
        full_item["isFull"] = "1"
        full_course = MODULE.Course.from_api(full_item, "2", "仙林校区")
        self.assertFalse(full_course.is_safe_candidate())
        self.assertFalse(
            MODULE.test_option_is_safe(
                {
                    "isConflict": "0",
                    "isFull": "0",
                    "isLimitKind": "0",
                    "extInfo": "0",
                    "classCapacity": "10",
                    "numberOfSelected": "10",
                }
            )
        )

    def test_course_match_and_log_redaction(self) -> None:
        item = {
            "teachingClassID": "tc-1",
            "courseNumber": "100",
            "courseName": "测试课程",
            "isConflict": "0",
            "isFull": "0",
            "hasTest": "0",
        }
        course = MODULE.Course.from_api(item, "4", "仙林新北")
        self.assertTrue(
            MODULE.course_matches(course, course_id="tc-1")
        )
        self.assertTrue(
            MODULE.course_matches(course, course_name="测试")
        )
        self.assertIn(
            "token=[REDACTED]",
            MODULE.safe_message("token=secret-value"),
        )
        self.assertIn(
            '"token":"[REDACTED]"',
            MODULE.safe_message('{"token":"secret-value"}'),
        )

    def test_auto_select_requires_watch_and_has_no_course_selector(self) -> None:
        parser = MODULE.build_parser()
        args = parser.parse_args(
            ["--watch", "--auto-select", "--yes", "--need-book", "0"]
        )
        MODULE.validate_args(parser, args)

        with self.assertRaises(SystemExit):
            invalid = parser.parse_args(["--auto-select"])
            MODULE.validate_args(parser, invalid)

    def test_credential_commands_are_separate_from_operations(self) -> None:
        parser = MODULE.build_parser()
        setup_args = parser.parse_args(["--setup-credentials"])
        MODULE.validate_args(parser, setup_args)
        clear_args = parser.parse_args(["--clear-credentials"])
        MODULE.validate_args(parser, clear_args)

        with self.assertRaises(SystemExit):
            invalid = parser.parse_args(["--setup-credentials", "--watch"])
            MODULE.validate_args(parser, invalid)

        with self.assertRaises(SystemExit):
            invalid = parser.parse_args(
                ["--watch", "--auto-select", "--course-name", "测试"]
            )
            MODULE.validate_args(parser, invalid)

    def test_single_campus_query_does_not_expand_to_other_campuses(self) -> None:
        class FakeApi:
            def __init__(self) -> None:
                self.calls = []

            async def post(self, path, payload):
                self.calls.append((path, payload))
                return {"code": "1", "totalCount": 0, "dataList": []}

        api = FakeApi()
        context = MODULE.SessionContext(
            student_code="student",
            batch_code="batch",
            batch_name="batch name",
            current_campus_code="2",
            current_campus_name="仙林校区",
            can_select_book="0",
            teaching_class_type="XGXK",
        )
        results, courses = asyncio.run(
            MODULE.run_query_cycle(
                api,
                context,
                page_size=10,
                max_pages=2,
                request_delay=0.5,
                campus_codes=("2",),
            )
        )
        self.assertEqual([result.campus_code for result in results], ["2"])
        self.assertEqual(courses, [])
        self.assertEqual(len(api.calls), 1)
        self.assertIn('"campus":"2"', api.calls[0][1]["querySetting"])

    def test_selected_course_count_excludes_test_courses(self) -> None:
        class FakeApi:
            async def get(self, path, params):
                self.path = path
                self.params = params
                return {
                    "code": "1",
                    "dataList": [
                        {"isTest": "0"},
                        {"isTest": "1"},
                        {},
                    ],
                }

        api = FakeApi()
        context = MODULE.SessionContext(
            student_code="student",
            batch_code="batch",
            batch_name="batch name",
            current_campus_code="2",
            current_campus_name="仙林校区",
            can_select_book="0",
            teaching_class_type="XGXK",
        )
        count = asyncio.run(
            MODULE.query_selected_course_count(api, context)
        )
        self.assertEqual(count, 2)
        self.assertTrue(api.path.startswith(MODULE.SELECTED_COURSE_PATH + "?timestamp="))


if __name__ == "__main__":
    unittest.main()
