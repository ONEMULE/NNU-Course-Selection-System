#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nnu_boya_automation.py 的离线单元测试；不访问 NNU，也不需要登录态。"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("nnu_boya_automation.py")
SPEC = importlib.util.spec_from_file_location("nnu_boya_automation", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("无法加载被测脚本")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class NnuBoyaAutomationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
