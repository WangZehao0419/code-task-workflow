# -*- coding: utf-8 -*-
"""e9 起始状态：一个失败测试（基线缺口：历史记录功能未实现）。

e9 场景由 setup 命令把本文件复制进 tests/，使测试套件变红。
"""
import unittest

from feedback_app import FeedbackStore


class TestHistoryBaseline(unittest.TestCase):
    def test_store_has_history_api(self):
        # 基线缺口：FeedbackStore 没有历史查询 API，此测试失败（e9 起始红态）
        store = FeedbackStore()
        self.assertTrue(hasattr(store, "history"), "缺少 history 查询方法")


if __name__ == "__main__":
    unittest.main()
