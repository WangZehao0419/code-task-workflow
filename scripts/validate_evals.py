# -*- coding: utf-8 -*-
"""eval 契约校验器：按 evals/schema.json 手写校验 evals/evals.json。

用法：
    python scripts/validate_evals.py            # 校验契约，exit 0=通过 / 1=失败
    python scripts/validate_evals.py --quiet    # 只输出结论行
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import eval_lib


def main():
    import argparse
    parser = argparse.ArgumentParser(description="code-task-workflow eval 契约校验器")
    parser.add_argument("--quiet", action="store_true", help="只输出结论")
    args = parser.parse_args()

    errors = eval_lib.validate_all()
    if errors:
        if not args.quiet:
            print("契约校验：FAIL（%d 项）" % len(errors))
            for e in errors:
                print("  - %s" % e)
        print("validate_evals: FAIL")
        return 1
    data = eval_lib.load_evals()
    n = len(data.get("evals", []))
    ts = data.get("trigger_set") or {}
    n_trig = len(ts.get("cases", [])) if ts else 0
    if not args.quiet:
        print("契约校验：PASS（%d 个 eval case；触发测试集 %d 条）" % (n, n_trig))
    print("validate_evals: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
