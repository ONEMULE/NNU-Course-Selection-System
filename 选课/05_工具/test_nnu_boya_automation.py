#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nnu_boya_automation.py 的离线单元测试；不访问 NNU，也不需要登录态。"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import tempfile
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

    def test_all_school_query_payload_matches_qxkc_frontend(self) -> None:
        payload = MODULE.build_all_school_query_payload(
            student_code="student",
            batch_code="batch",
            campus_code="2",
            keyword="人工智能",
            category="01",
            teaching_unit="19",
            page_size=20,
            page_number=2,
        )
        outer = json.loads(payload["querySetting"])
        self.assertEqual(outer["data"]["teachingClassType"], "QXKC")
        self.assertEqual(
            outer["data"]["queryContent"],
            "KKDWDM:19,XGXKLBDM:01,人工智能",
        )
        self.assertNotIn("checkConflict", outer["data"])
        self.assertNotIn("checkCapacity", outer["data"])
        self.assertEqual(outer["pageSize"], "20")
        self.assertEqual(outer["pageNumber"], "2")

    def test_school_course_parser_keeps_course_and_teaching_class_levels(self) -> None:
        course = MODULE.SchoolCourse.from_api(
            {
                "courseNumber": "1001",
                "courseName": "测试课程",
                "courseIndex": "01",
                "departmentName": "测试学院",
                "courseNatureName": "选修",
                "typeName": "全校课程",
                "credit": "2",
                "hours": "32",
                "teacherName": "张三|T1,李四|T2",
                "tcList": [
                    {
                        "teachingClassID": "tc-1",
                        "courseIndex": "01",
                        "teacherName": "张三",
                        "teachingPlace": "1-16周 星期一 1-2节",
                        "classCapacity": "40",
                        "numberOfFirstVolunteer": "10",
                        "isConflict": "0",
                        "isFull": "0",
                        "canSelect": "1",
                        "canOperate": "1",
                    }
                ],
            },
            campus_code="2",
            campus_name="仙林校区",
        )
        self.assertIsNotNone(course)
        assert course is not None
        self.assertEqual(course.teacher, "张三, 李四")
        self.assertEqual(len(course.teaching_classes), 1)
        self.assertTrue(course.teaching_classes[0].is_selectable_now())
        rows = MODULE.school_course_csv_rows([course])
        self.assertEqual(rows[0]["teachingClassId"], "tc-1")
        self.assertEqual(rows[0]["selectableNow"], True)

    def test_all_school_query_paginates_and_keeps_qxkc_path(self) -> None:
        class FakeApi:
            def __init__(self) -> None:
                self.calls = []

            async def post(self, path, payload):
                self.calls.append((path, payload))
                page = json.loads(payload["querySetting"])["pageNumber"]
                if page == "0":
                    return {
                        "code": "1",
                        "totalCount": 2,
                        "dataList": [
                            {
                                "courseNumber": "1001",
                                "courseName": "课程一",
                                "tcList": [
                                    {"teachingClassID": "tc-1"}
                                ],
                            }
                        ],
                    }
                return {
                    "code": "1",
                    "totalCount": 2,
                    "dataList": [
                        {
                            "courseNumber": "1002",
                            "courseName": "课程二",
                            "tcList": [
                                {"teachingClassID": "tc-2"}
                            ],
                        }
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
            teaching_class_type="QXKC",
        )
        result = asyncio.run(
            MODULE.query_all_school_courses(
                api,
                context,
                campus_code="2",
                page_size=1,
                max_pages=3,
                request_delay=0.5,
            )
        )
        self.assertEqual(result.pages_visited, 2)
        self.assertEqual([course.course_number for course in result.courses], ["1001", "1002"])
        self.assertEqual(
            [call[0] for call in api.calls],
            [MODULE.ALL_SCHOOL_COURSE_PATH, MODULE.ALL_SCHOOL_COURSE_PATH],
        )
        first_query = json.loads(api.calls[0][1]["querySetting"])
        self.assertEqual(first_query["data"]["teachingClassType"], "QXKC")

    def test_export_files_are_structured_and_do_not_include_student_code(self) -> None:
        context = MODULE.SessionContext(
            student_code="student-secret",
            batch_code="batch",
            batch_name="batch name",
            current_campus_code="2",
            current_campus_name="仙林校区",
            can_select_book="0",
            teaching_class_type="XGXK",
        )
        school_course = MODULE.SchoolCourse.from_api(
            {
                "courseNumber": "1001",
                "courseName": "测试课程",
                "tcList": [{"teachingClassID": "tc-1"}],
            },
            campus_code="2",
            campus_name="仙林校区",
        )
        selected_course = MODULE.SelectedCourse.from_api(
            {
                "teachingClassID": "selected-1",
                "courseNumber": "1001",
                "courseName": "已选课程",
                "isTest": "0",
                "publicCourseTypeName": "人文与社会",
            }
        )
        self.assertIsNotNone(school_course)
        self.assertIsNotNone(selected_course)
        assert school_course is not None
        assert selected_course is not None
        with tempfile.TemporaryDirectory() as directory:
            MODULE.write_open_course_exports(
                MODULE.Path(directory),
                context,
                [
                    MODULE.SchoolQueryResult(
                        campus_code="2",
                        campus_name="仙林校区",
                        total_count=1,
                        pages_visited=1,
                        courses=[school_course],
                    )
                ],
                [school_course],
            )
            MODULE.write_selected_course_exports(
                MODULE.Path(directory),
                context,
                [selected_course],
            )
            selected_json = (
                MODULE.Path(directory) / "selected_courses.json"
            ).read_text(encoding="utf-8")
            open_csv = (
                MODULE.Path(directory) / "all_open_courses.csv"
            ).read_text(encoding="utf-8-sig")
        self.assertIn("已选课程", selected_json)
        self.assertNotIn("student-secret", selected_json)
        self.assertIn("teachingClassId", open_csv)

    def test_selected_course_parser_and_experiment_link_shape(self) -> None:
        theory = MODULE.SelectedCourse.from_api(
            {
                "teachingClassID": "theory-1",
                "campus": "2",
                "campusName": "仙林校区",
                "courseNumber": "1001",
                "courseName": "博雅测试",
                "courseIndex": "01",
                "teacherName": "张三|T1",
                "teachingPlace": "1-16周 星期一 1-2节",
                "publicCourseTypeName": "人文与社会",
                "credit": "2",
                "isTest": "0",
                "hasTest": "1",
                "testTeachingClassID": "test-1",
            }
        )
        experiment = MODULE.SelectedCourse.from_api(
            {
                "teachingClassID": "test-1",
                "courseNumber": "1001",
                "courseName": "博雅测试实验",
                "isTest": "1",
            }
        )
        self.assertIsNotNone(theory)
        self.assertIsNotNone(experiment)
        assert theory is not None
        assert experiment is not None
        rows = MODULE.selected_course_csv_rows([theory, experiment])
        self.assertEqual(rows[0]["recordKind"], "theory")
        self.assertEqual(rows[0]["isBoya"], True)
        self.assertEqual(rows[1]["recordKind"], "experiment")
        self.assertEqual(rows[1]["parentTeachingClassId"], "theory-1")

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
        self.assertEqual(args.interval, 1.0)

        one_second = parser.parse_args(["--watch", "--interval", "1"])
        MODULE.validate_args(parser, one_second)

        with self.assertRaises(SystemExit):
            too_fast = parser.parse_args(["--watch", "--interval", "0.9"])
            MODULE.validate_args(parser, too_fast)

        with self.assertRaises(SystemExit):
            invalid = parser.parse_args(["--auto-select"])
            MODULE.validate_args(parser, invalid)

    def test_terminal_ui_is_bounded_and_shows_watch_metrics(self) -> None:
        ui = MODULE.TerminalUI("AUTO-SELECT", enabled=False)
        for index in range(20):
            ui.event(f"event-{index}", render=False)
        self.assertEqual(len(ui.events), 7)

        ui.selected(2, render=False)
        ui.cycle(
            [
                MODULE.QueryResult(
                    campus_code="2",
                    campus_name="仙林校区",
                    total_count=1,
                    pages_visited=1,
                    courses=[],
                )
            ],
            [],
            elapsed=0.25,
            render=False,
        )
        screen = ui.render_text()
        self.assertIn("UPTIME", screen)
        self.assertIn("BOYA THEORY", screen)
        self.assertIn("courseResult", screen)
        self.assertIn("events=7/7", screen)

    def test_terminal_ui_shows_scope_selector_policy_and_runtime_config(self) -> None:
        parser = MODULE.build_parser()
        args = parser.parse_args(
            [
                "--watch",
                "--auto-select",
                "--yes",
                "--need-book",
                "0",
                "--interval",
                "1",
                "--request-delay",
                "0.5",
                "--page-size",
                "50",
                "--max-pages",
                "3",
            ]
        )
        MODULE.validate_args(parser, args)

        ui = MODULE.TerminalUI("AUTO-SELECT", enabled=False)
        ui.configure(
            args,
            campus_codes=("2", "4"),
            expected_teaching_class_type=MODULE.BOYA_TEACHING_CLASS_TYPE,
        )
        screen = ui.render_text()
        self.assertIn("request-campus=仙林校区(2), 仙林新北(4)", screen)
        self.assertIn("AUTO: first safe Boya course", screen)
        self.assertIn("conflict=0 full=0 not-chosen=1", screen)
        self.assertIn("need-book=0 confirm=YES", screen)
        self.assertIn("interval=1.0s delay=0.5s page=50 max-pages=3", screen)
        self.assertIn("login=credential-fill", screen)

    def test_terminal_ui_mouse_config_changes_only_safe_runtime_options(self) -> None:
        parser = MODULE.build_parser()
        args = parser.parse_args(
            ["--watch", "--auto-select", "--yes", "--need-book", "0"]
        )
        MODULE.validate_args(parser, args)

        ui = MODULE.TerminalUI("AUTO-SELECT", enabled=False)
        ui._config_campus_codes = ["2"]
        ui.configure(
            args,
            campus_codes=ui._config_campus_codes,
            expected_teaching_class_type=MODULE.BOYA_TEACHING_CLASS_TYPE,
        )
        ui._config_args = args
        ui.view = "config"
        screen = ui.render_config_text(args)
        self.assertIn("MOUSE click rows to change", screen)
        self.assertIn("CAMPUS-4", screen)
        self.assertIn("[ APPLY & START ]", screen)
        self.assertIn("book", ui._config_regions)

        book_y = ui._config_regions["book"][2]
        ui._handle_config_event(("click", "left", 2, book_y), args)
        self.assertEqual(args.need_book, "1")

        message = ui._change_config("campus-4", args)
        self.assertIn("locked", message)
        self.assertEqual(ui._config_campus_codes, ["2"])

        ui._change_config("mode-watch", args)
        self.assertFalse(args.auto_select)
        self.assertFalse(args.yes)
        self.assertEqual(ui._config_campus_codes, ["2", "4"])
        ui._change_config("campus-4", args)
        self.assertEqual(ui._config_campus_codes, ["2"])

    def test_plain_output_flag_is_available(self) -> None:
        parser = MODULE.build_parser()
        args = parser.parse_args(["--watch", "--plain-output"])
        MODULE.validate_args(parser, args)
        self.assertTrue(args.plain_output)

    def test_collection_modes_are_read_only_and_composable(self) -> None:
        parser = MODULE.build_parser()
        args = parser.parse_args(
            ["--collect-open-courses", "--collect-selected-courses"]
        )
        MODULE.validate_args(parser, args)

        filtered = parser.parse_args(
            [
                "--collect-open-courses",
                "--school-keyword",
                "人工智能",
                "--school-category",
                "01",
                "--school-unit",
                "19",
            ]
        )
        MODULE.validate_args(parser, filtered)

        with self.assertRaises(SystemExit):
            invalid = parser.parse_args(
                ["--collect-selected-courses", "--school-keyword", "测试"]
            )
            MODULE.validate_args(parser, invalid)

        with self.assertRaises(SystemExit):
            invalid = parser.parse_args(
                ["--collect-open-courses", "--submit", "--course-id", "tc-1"]
            )
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
                        {"isTest": "0", "publicCourseType": "A01"},
                        {"isTest": "1", "publicCourseType": "A02"},
                        {"isTest": "0", "publicCourseTypeName": "-"},
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
        self.assertEqual(count, 1)
        self.assertTrue(api.path.startswith(MODULE.SELECTED_COURSE_PATH + "?timestamp="))

    def test_boya_classifier_uses_explicit_public_markers(self) -> None:
        self.assertTrue(
            MODULE.selected_course_is_boya(
                {"teachingClassType": "XGXK"}
            )
        )
        self.assertTrue(
            MODULE.selected_course_is_boya(
                {"publicCourseTypeName": "人文艺术"}
            )
        )
        self.assertTrue(
            MODULE.selected_course_is_boya(
                {"courseTypeName": "博雅教育课程"}
            )
        )
        self.assertFalse(
            MODULE.selected_course_is_boya(
                {"teachingClassType": "FANKC"}
            )
        )
        self.assertIsNone(MODULE.selected_course_is_boya({}))

    def test_boya_count_does_not_count_normal_courses(self) -> None:
        self.assertEqual(
            MODULE.count_boya_courses(
                [
                    {"isTest": "0", "publicCourseType": "01"},
                    {"isTest": "0", "courseTypeName": "方案内课程"},
                    {"isTest": "1", "publicCourseType": "02"},
                    {"isTest": "0", "courseType": "XGXK"},
                ]
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
