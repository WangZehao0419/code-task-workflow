# -*- coding: utf-8 -*-
"""反馈工具 fixture 基线。

已知缺口（供 eval 场景使用，勿在基线上“顺手修复”）：
- 提交成功后无确认提示（e1 场景：加提交成功确认）；
- 提交失败（异常输入）直接崩溃、无重试引导（e1 场景：失败重试）；
- 无历史记录查看命令（e1 场景：查看历史提交记录）；
- 空文本提交抛 ValueError 且未被 CLI 捕获 → 真实 traceback、退出码非零（e2 场景：空输入崩溃 bug）。
"""
import sys


class FeedbackStore:
    """反馈存储：进程内列表。空文本在存储层拒绝。"""

    def __init__(self):
        self._items = []

    def add(self, text):
        if not isinstance(text, str) or not text.strip():
            # 基线 bug：空输入在存储层抛异常，CLI 层未捕获 → 崩溃
            raise ValueError("反馈内容不能为空")
        self._items.append(text.strip())
        return len(self._items)

    def all(self):
        return list(self._items)

    def __len__(self):
        return len(self._items)


def main(argv):
    store = FeedbackStore()
    if argv and argv[0] == "submit":
        # 参数缺失视为提交空内容（PowerShell 会吞掉 "" 空参数，两种 shell 行为一致）
        text = argv[1] if len(argv) >= 2 else ""
        index = store.add(text)  # 空输入在此崩溃（基线 bug）
        print("saved #%d" % index)
        return 0
    print("usage: python feedback_app.py submit <text>")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
