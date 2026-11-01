# -*- coding: utf-8 -*-
"""基线测试：只覆盖正常提交与读取。

注意：空输入回归测试不在基线中——由 e2 场景的被评估方补写并真实通过。
"""
import unittest

from feedback_app import FeedbackStore


class TestFeedbackStore(unittest.TestCase):
    def test_add_returns_index(self):
        store = FeedbackStore()
        self.assertEqual(store.add("页面加载慢"), 1)
        self.assertEqual(store.add("按钮错位"), 2)

    def test_read_back(self):
        store = FeedbackStore()
        store.add("第一条")
        store.add("第二条")
        self.assertEqual(store.all(), ["第一条", "第二条"])

    def test_strips_whitespace(self):
        store = FeedbackStore()
        store.add("  前后空格  ")
        self.assertEqual(store.all(), ["前后空格"])

    def test_empty_store(self):
        self.assertEqual(len(FeedbackStore()), 0)


if __name__ == "__main__":
    unittest.main()
