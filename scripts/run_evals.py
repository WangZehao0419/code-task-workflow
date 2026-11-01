# -*- coding: utf-8 -*-
"""eval runner：运行 eval 场景、判定断言、归档 run-log、mutation 测试、成本退化报警。

用法：
    python scripts/run_evals.py --list
    python scripts/run_evals.py --all --repeat 3 --baseline
    python scripts/run_evals.py --all --repeat 3 --with-skill
    python scripts/run_evals.py --case e2 --baseline
    python scripts/run_evals.py --all --evidence-dir evals/evidence/<run>   # manual 证据回填判定
    python scripts/run_evals.py --mutation                                  # 恒真断言检测
    python scripts/run_evals.py --all --baseline --strict                   # unrun>0 时 exit 2

语义约定（与 evals/schema.json 一致）：
  - runner_mode=script：沙盒内可纯脚本判定。
  - runner_mode=manual：无回填证据时只能标 unrun / manual_required，不得标 pass；
    会话内真实运行工作流后，把证据归档到 --evidence-dir/<case_id>/ 再跑判定。
  - human_unscored 断言永不机器判分。
  - 成本字段 tokens/tool_calls 不可得时保留键位、置 null 并在 notes 标注；
    latency 实测；与对照 config 最近 run-log 比较退化 >50% 报警。
"""
import argparse
import datetime
import fnmatch
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_lib

RUNS_DIR = os.path.join(eval_lib.SKILL_ROOT, "evals", "runs")
MUTATIONS_PATH = os.path.join(eval_lib.SKILL_ROOT, "evals", "mutations.json")
DEFAULT_TIMEOUT = 120


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id(config):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "%s-%s" % (stamp, config)


def _decode(b):
    if b is None:
        return ""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("gbk", errors="replace")


def run_cmd(cmd, cwd, timeout):
    """在 cwd 执行 shell 命令，返回 dict(cmd, exit, stdout, stderr, seconds)。

    stdin 置为 DEVNULL：被评估实现若含交互式读取（如重试循环），立即 EOF 而非阻塞。
    """
    import time
    t0 = time.time()
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=timeout)
        out, err, code = _decode(p.stdout), _decode(p.stderr), p.returncode
        timed_out = False
    except subprocess.TimeoutExpired as e:
        out, err = _decode(e.stdout or b""), _decode(e.stderr or b"")
        code, timed_out = -1, True
    seconds = round(time.time() - t0, 3)
    return {"cmd": cmd, "exit": code, "stdout": out, "stderr": err,
            "seconds": seconds, "timed_out": timed_out}


def _file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def expand_paths(root, paths):
    """paths 支持 glob（含 * ? [] 的项展开为相对命中列表），其余原样返回。"""
    out = []
    for rel in paths:
        full = os.path.join(root, rel)
        if any(ch in rel for ch in "*?["):
            for hit in glob.glob(full, recursive=True):
                out.append(os.path.relpath(hit, root).replace("\\", "/"))
        else:
            out.append(rel)
    return out


# ---------------------------------------------------------------------------
# 断言判定
# ---------------------------------------------------------------------------

def judge_assertion(a, project, fixture_src, cmd_res, timeout):
    """返回 (verdict, detail)。verdict ∈ pass|fail|unrun。"""
    forbidden = a.get("forbidden")
    if forbidden:
        hits = eval_lib.match_any_glob(project, forbidden)
        if hits:
            return "fail", "命中违规产物: %s" % hits
        return "pass", "无违规产物命中 forbidden=%s" % forbidden

    ev = a.get("evidence")
    if not isinstance(ev, dict):
        return "unrun", "断言无可判定依据（无 evidence / forbidden）"
    et = ev.get("type")

    if et == "file_exists":
        paths = expand_paths(project, ev.get("paths", []))
        expect = ev.get("expect", "present")
        states = [(p, os.path.exists(os.path.join(project, p))) for p in paths]
        if expect == "absent":
            present = [p for p, ok in states if ok]
            return ("fail", "以下路径不应存在但存在: %s" % present) if present \
                else ("pass", "确认路径均不存在")
        missing = [p for p, ok in states if not ok]
        return ("fail", "缺少产物: %s" % missing) if missing else ("pass", "产物齐全: %s" % paths)

    if et == "file_contains":
        paths, patterns = expand_paths(project, ev.get("paths", [])), ev.get("patterns", [])
        mode = ev.get("mode", "any")
        expect = ev.get("expect", "present")
        min_hits = ev.get("min_hits")
        if not paths:
            return "unrun", "file_contains 无命中文件（paths 展开为空）"
        hit_count, misses = 0, []
        for pat in patterns:
            rx = re.compile(pat)
            found = False
            for rel in paths:
                fp = os.path.join(project, rel)
                if os.path.isfile(fp):
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        if rx.search(f.read()):
                            found = True
                            break
            if found:
                hit_count += 1
            else:
                misses.append(pat)
        if expect == "absent":
            hit_pats = [p for p in patterns if p not in misses]
            return ("fail", "以下禁止模式命中: %s" % hit_pats) if hit_count \
                else ("pass", "禁止模式均未命中")
        if min_hits is not None:
            return ("pass", "命中 %d/%d 个模式（要求 ≥%d）" % (hit_count, len(patterns), min_hits)) \
                if hit_count >= min_hits else \
                ("fail", "仅命中 %d/%d 个模式（要求 ≥%d），未命中: %s" % (hit_count, len(patterns), min_hits, misses))
        if mode == "all":
            return ("fail", "以下模式未全部命中: %s" % misses) if misses else ("pass", "全部模式命中")
        return ("pass", "命中 %d/%d 个模式" % (hit_count, len(patterns))) if hit_count \
            else ("fail", "所有模式均未命中: %s" % patterns)

    if et == "semantic_fields":
        result = None
        for rel in expand_paths(project, ev.get("paths", [])):
            fp = os.path.join(project, rel)
            if os.path.isfile(fp):
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    ok, missing, _ = eval_lib.check_semantic_fields(f.read())
                if ok:
                    return "pass", "%s 四语义字段齐全" % rel
                result = (rel, missing)
        if result:
            return "fail", "%s 缺语义字段: %s" % result
        return "unrun", "semantic_fields 目标文件不存在: %s" % ev.get("paths")

    if et == "command_output":
        expect = ev.get("expect", "zero")
        res = run_cmd(ev["command"], project, timeout) if ev.get("command") else cmd_res
        if res is None:
            return "unrun", "command_output 无可执行命令"
        parts = ["exit=%s" % res["exit"], "stdout=%r" % res["stdout"][:400], "stderr=%r" % res["stderr"][:400]]
        if expect == "nonzero" and res["exit"] == 0:
            return "fail", "期望非零退出码，实际 0；" + "; ".join(parts)
        if expect == "zero" and res["exit"] != 0:
            return "fail", "期望零退出码；" + "; ".join(parts)
        for pat in ev.get("patterns", []):
            if not (re.search(pat, res["stdout"]) or re.search(pat, res["stderr"])):
                return "fail", "输出未命中模式 %r；" % pat + "; ".join(parts)
        return "pass", "; ".join(parts)

    if et == "event_log":
        fp = os.path.join(project, ev.get("file", "events.jsonl"))
        if not os.path.isfile(fp):
            return "unrun", "事件日志不存在: %s" % ev.get("file")
        events = []
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except ValueError:
                        pass
        names = [e.get("event") for e in events]
        for rule in ev.get("rules", []):
            r = rule.get("rule")
            with_fields = rule.get("with_fields") or []

            def _match(e):
                return e.get("event") == rule.get("event") and \
                    all(k in e for k in with_fields)

            if r == "no-event-before":
                ev_name, before = rule.get("event"), rule.get("before")
                if before in names:
                    first_before = names.index(before)
                    if ev_name in names[:first_before]:
                        return "fail", "事件 %s 出现在 %s 之前（规则 no-event-before）" % (ev_name, before)
            elif r == "count_max":
                c = sum(1 for e in events if _match(e))
                if c > rule.get("max", 0):
                    return "fail", "事件 %s 计数 %d 超过上限 %d" % (rule.get("event"), c, rule.get("max"))
            elif r == "count_min":
                c = sum(1 for e in events if _match(e))
                if c < rule.get("min", 1):
                    return "fail", "事件 %s（须含字段 %s）计数 %d 低于下限 %d" % (
                        rule.get("event"), with_fields or "-", c, rule.get("min"))
            elif r == "order":
                seq = [e for e in rule.get("events", []) if e in names]
                if seq != rule.get("events", []):
                    return "fail", "事件顺序不符：期望 %s，实际出现序 %s" % (rule.get("events"), seq)
        return "pass", "事件日志规则全部满足"

    if et == "diff_scope":
        allowed = ev.get("allowed_paths", [])
        changed = []
        if fixture_src and os.path.isdir(fixture_src):
            base_files = {}
            for root, _dirs, files in os.walk(fixture_src):
                for fn in files:
                    fp = os.path.join(root, fn)
                    base_files[os.path.relpath(fp, fixture_src)] = _file_hash(fp)
            for root, _dirs, files in os.walk(project):
                for fn in files:
                    fp = os.path.join(root, fn)
                    rel = os.path.relpath(fp, project)
                    if rel not in base_files or base_files[rel] != _file_hash(fp):
                        changed.append(rel.replace("\\", "/"))
        outside = [c for c in changed
                   if not any(fnmatch.fnmatch(c, pat) for pat in allowed)]
        if outside:
            return "fail", "改动触及允许范围外: %s（allowed=%s）" % (outside, allowed)
        return "pass", "改动仅触及 %s（allowed=%s）" % (changed, allowed)

    return "unrun", "未知 evidence type: %s" % et


# ---------------------------------------------------------------------------
# case 运行
# ---------------------------------------------------------------------------

def judge_all_assertions(case, project, fixture_src, cmd_res, timeout):
    out = []
    for a in case.get("assertions", []):
        if a.get("kind") == "human_unscored":
            out.append({"id": a["id"], "verdict": "human_unscored",
                        "detail": "human_unscored：用户确认/走查类，不参与机器判分"})
            continue
        v, detail = judge_assertion(a, project, fixture_src, cmd_res, timeout)
        out.append({"id": a["id"], "verdict": v, "detail": detail})
    return out


def run_case_script(case, repeat, run_dir, timeout):
    results = []
    for it in range(1, repeat + 1):
        sandbox, project = eval_lib.make_sandbox(case.get("fixture"))
        fixture_src = os.path.join(eval_lib.SKILL_ROOT, case["fixture"]) if case.get("fixture") else None
        try:
            setup_res = []
            for cmd in case.get("setup", []):
                setup_res.append(run_cmd(cmd, project, timeout))
            cmd_res = run_cmd(case["command"], project, timeout) if case.get("command") else None
            assertions = judge_all_assertions(case, project, fixture_src, cmd_res, timeout)
            machine = [r for r in assertions if r["verdict"] != "human_unscored"]
            verdict = "pass" if all(r["verdict"] == "pass" for r in machine) else "fail"

            snap = os.path.join(run_dir, "sandbox", str(case["id"]), "iter%d" % it)
            os.makedirs(os.path.dirname(snap), exist_ok=True)
            shutil.copytree(project, snap)

            actual = ""
            if cmd_res:
                actual = "exit=%s; stdout=%r; stderr=%r" % (
                    cmd_res["exit"], cmd_res["stdout"][:300], cmd_res["stderr"][:300])
            results.append({
                "iteration": it, "verdict": verdict, "assertions": assertions,
                "actual_output": actual,
                "evidence_dir": os.path.relpath(snap, run_dir).replace("\\", "/"),
                "timing": {"seconds": (cmd_res or {}).get("seconds")},
                "cost": {"tokens": None, "tool_calls": None,
                         "notes": "script 运行不采集 tokens/tool_calls（会话内指标）"},
                "reviewer": None,
                "setup_fail": [r for r in setup_res if r["exit"] != 0],
            })
        except Exception as e:  # 单次迭代异常不中断整体，记 error 迭代
            results.append({"iteration": it, "verdict": "error",
                            "assertions": [], "actual_output": "异常: %r" % e,
                            "evidence_dir": None, "timing": {"seconds": None},
                            "cost": {"tokens": None, "tool_calls": None, "notes": None},
                            "reviewer": None})
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)
    return results


def run_case_manual(case, evidence_dir, run_dir, timeout):
    case_dir = os.path.join(evidence_dir, str(case["id"])) if evidence_dir else None
    if not case_dir or not os.path.isdir(case_dir):
        return [{
            "iteration": 1, "verdict": "unrun", "assertions": [],
            "actual_output": "",
            "evidence_dir": None,
            "timing": {"seconds": None},
            "cost": {"tokens": None, "tool_calls": None,
                     "notes": "manual case 未运行，不采集"},
            "reviewer": None,
        }], "MANUAL_REQUIRED: 须会话内真实运行工作流，把事件日志/产物/汇报归档到 <evidence-dir>/%s/ 后用 --evidence-dir 重跑判定" % case["id"]

    sandbox, project = eval_lib.make_sandbox(case.get("fixture"), case_dir)
    fixture_src = os.path.join(eval_lib.SKILL_ROOT, case["fixture"]) if case.get("fixture") else None
    try:
        cmd_res = run_cmd(case["command"], project, timeout) if case.get("command") else None
        assertions = judge_all_assertions(case, project, fixture_src, cmd_res, timeout)
        machine = [r for r in assertions if r["verdict"] != "human_unscored"]
        if not machine:
            # 无 machine 断言可判定：不能标 pass，标 unrun 并说明
            return [{
                "iteration": 1, "verdict": "unrun",
                "assertions": assertions, "actual_output": "",
                "evidence_dir": None, "timing": {"seconds": None},
                "cost": {"tokens": None, "tool_calls": None,
                         "notes": "回填证据中无 machine 断言可判定内容"},
                "reviewer": None,
            }], "回填证据下无 machine 断言可判定，标 unrun；human_unscored 断言需人工评审"
        verdict = "pass" if all(r["verdict"] == "pass" for r in machine) else "fail"

        snap = os.path.join(run_dir, "sandbox", str(case["id"]), "evidence")
        os.makedirs(os.path.dirname(snap), exist_ok=True)
        shutil.copytree(project, snap)

        human_ids = [r["id"] for r in assertions if r["verdict"] == "human_unscored"]
        notes = ("证据回填判定（评审方=脚本按证据判定，证据来源=会话归档）。"
                 if machine else "无 machine 断言可判定。")
        if human_ids:
            notes += "human_unscored 断言待人工评审: %s" % human_ids
        return [{
            "iteration": 1, "verdict": verdict, "assertions": assertions,
            "actual_output": cmd_res and ("exit=%s" % cmd_res["exit"]) or "见断言明细",
            "evidence_dir": os.path.relpath(snap, run_dir).replace("\\", "/"),
            "timing": {"seconds": (cmd_res or {}).get("seconds")},
            "cost": {"tokens": None, "tool_calls": None,
                     "notes": "会话成本未自动采集（如可从会话记录统计则回填）"},
            "reviewer": "script-by-archived-evidence",
        }], notes
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


# ---------------------------------------------------------------------------
# 报警与 mutation
# ---------------------------------------------------------------------------

def find_latest_run_log(config):
    if not os.path.isdir(RUNS_DIR):
        return None
    cands = []
    for d in os.listdir(RUNS_DIR):
        rl = os.path.join(RUNS_DIR, d, "run-log.json")
        if d.endswith("-%s" % config) and os.path.isfile(rl):
            cands.append(rl)
    return max(cands, key=os.path.getmtime) if cands else None


def case_latency_seconds(rl, case_id):
    for c in rl.get("cases", []):
        if eval_lib.norm_case_id(c.get("id")) == str(case_id):
            secs = [r.get("timing", {}).get("seconds") for r in c.get("repeat_results", [])]
            secs = [s for s in secs if isinstance(s, (int, float))]
            return sum(secs) / len(secs) if secs else None
    return None


def degradation_alert(current_log):
    """与对照 config 最近 run-log 比较：latency 相对退化 >50% 报警。tokens 未采集不产生假报警。"""
    cfg = current_log.get("config")
    other = "with-skill" if cfg == "baseline" else "baseline"
    base_path = find_latest_run_log(other)
    if not base_path:
        return {"triggered": False, "items": [],
                "notes": "无 %s 对照 run-log，跳过退化比较" % other}
    with open(base_path, "r", encoding="utf-8") as f:
        base = json.load(f)
    items = []
    for c in current_log.get("cases", []):
        cid = str(c.get("id"))
        new = case_latency_seconds(current_log, cid)
        old = case_latency_seconds(base, cid)
        if new is None or old is None or old <= 0:
            continue
        delta = abs(new - old) / old
        if delta > 0.5:
            items.append({"case": cid, "metric": "latency_seconds",
                          "baseline": round(old, 3), "current": round(new, 3),
                          "delta_pct": round(delta * 100, 1)})
    # tokens：当前与基线均未自动采集，键位保留、如实标注
    tokens_note = "tokens 未自动采集（null），不参与本次报警判定"
    return {"triggered": bool(items), "items": items, "notes": tokens_note}


def run_mutations(evals, timeout):
    """mutation 测试：注入违规产物，被指断言必须 fail，否则视为恒真断言。"""
    if not os.path.isfile(MUTATIONS_PATH):
        return None, "evals/mutations.json 不存在，跳过 mutation 测试"
    with open(MUTATIONS_PATH, "r", encoding="utf-8") as f:
        muts = json.load(f).get("mutations", [])
    cases = {eval_lib.norm_case_id(c["id"]): c for c in evals}
    out = []
    for m in muts:
        target = cases.get(m.get("target_case"))
        if not target:
            out.append({"id": m.get("id"), "verdict": "error",
                        "detail": "目标 case 不存在: %s" % m.get("target_case")})
            continue
        sandbox, project = eval_lib.make_sandbox(target.get("fixture"))
        fixture_src = os.path.join(eval_lib.SKILL_ROOT, target["fixture"]) if target.get("fixture") else None
        try:
            for inj in m.get("inject", []):
                fp = os.path.join(project, inj["path"])
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(inj["content"])
            asserts = {a["id"]: a for a in target.get("assertions", [])}
            results = []
            for aid in m.get("expect_fail_assertions", []):
                a = asserts.get(aid)
                if not a:
                    results.append({"id": aid, "fail": False, "detail": "断言不存在"})
                    continue
                v, detail = judge_assertion(a, project, fixture_src, None, timeout)
                results.append({"id": aid, "fail": v == "fail", "detail": detail})
            ok = results and all(r["fail"] for r in results)
            out.append({"id": m.get("id"), "target_case": m.get("target_case"),
                        "description": m.get("description"),
                        "verdict": "mutation-pass" if ok else "mutation-fail",
                        "assertions": results})
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)
    return out, None


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="code-task-workflow eval runner")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="列出全部 case")
    g.add_argument("--all", action="store_true", help="运行全部 case")
    g.add_argument("--case", metavar="ID", help="运行指定 case")
    g.add_argument("--mutation", action="store_true", help="mutation 测试（恒真断言检测）")
    ap.add_argument("--repeat", type=int, default=1)
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--baseline", action="store_true")
    group.add_argument("--with-skill", dest="with_skill", action="store_true")
    ap.add_argument("--evidence-dir", metavar="DIR",
                    help="manual case 证据回填目录（按 <case_id>/ 分桶）")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument("--strict", action="store_true",
                    help="unrun/manual_required>0 时 exit 2")
    args = ap.parse_args()

    data = eval_lib.load_evals()
    evals = data.get("evals", [])
    timeout = args.timeout

    if args.list:
        for c in evals:
            print("%-4s %-32s type=%-8s runner=%-6s prio=%s fixture=%s" % (
                c["id"], c["name"], c.get("type"), c.get("runner_mode"),
                c.get("priority"), c.get("fixture") or "-"))
        return 0

    if args.mutation:
        results, note = run_mutations(evals, timeout)
        if note:
            print(note)
            return 0
        bad = [r for r in results if r["verdict"] != "mutation-pass"]
        for r in results:
            print("%-6s %-8s target=%s %s" % (r["id"], r["verdict"],
                  r.get("target_case"), r.get("description")))
            for a in r.get("assertions", []):
                print("        assertion %-24s fail=%s  %s" % (a["id"], a["fail"], a["detail"][:160]))
        if bad:
            print("mutation: FAIL（恒真断言，违规未被检测）：%s" % [r["id"] for r in bad])
            return 1
        print("mutation: PASS（全部违规注入均被断言检出）")
        return 0

    config = "with-skill" if args.with_skill else "baseline"
    selected = evals
    if args.case:
        selected = [c for c in evals if eval_lib.norm_case_id(c["id"]) == args.case]
        if not selected:
            print("case 不存在: %s" % args.case)
            return 2

    run_id = new_run_id(config)
    run_dir = os.path.join(RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    case_entries = []
    for case in selected:
        cid = eval_lib.norm_case_id(case["id"])
        rmode = case.get("runner_mode")
        deps = [str(d) for d in (case.get("depends_on") or [])]
        dep_unmet = [d for d in deps
                     if any(str(x["id"]) == d and x["verdict"] != "pass"
                            for x in case_entries)]
        if dep_unmet:
            reps = [{"iteration": 1, "verdict": "unrun", "assertions": [],
                     "actual_output": "", "evidence_dir": None,
                     "timing": {"seconds": None},
                     "cost": {"tokens": None, "tool_calls": None,
                              "notes": "前置未通过: %s" % dep_unmet},
                     "reviewer": None}]
            notes = "前置 case 未通过（%s），本 case 标 unrun" % dep_unmet
        elif rmode == "script":
            reps = run_case_script(case, args.repeat, run_dir, timeout)
            notes = ""
        else:
            reps, notes = run_case_manual(case, args.evidence_dir, run_dir, timeout)

        verdicts = [r["verdict"] for r in reps]
        if "fail" in verdicts or "error" in verdicts:
            status = "fail" if "fail" in verdicts else "error"
        elif "unrun" in verdicts:
            status = "manual_required" if rmode == "manual" else "unrun"
        else:
            status = "pass"
        log_verdict = "unrun" if status in ("unrun", "manual_required") else status
        case_entries.append({
            "id": case["id"], "name": case.get("name"),
            "runner_mode": rmode, "status": status, "verdict": log_verdict,
            "repeat_results": reps, "notes": notes,
        })
        print("[%-16s] %s %-30s verdict=%s" % (status, cid, case.get("name"), log_verdict))

    n = lambda k: sum(1 for c in case_entries if c["status"] == k)
    script_cases = [c for c in case_entries if c["runner_mode"] == "script"]
    script_pass = sum(1 for c in script_cases if c["verdict"] == "pass")
    # variance：script case 在 repeat 间结论是否一致
    inconsistent = [str(c["id"]) for c in case_entries
                    if len(set(r["verdict"] for r in c["repeat_results"])) > 1]
    # human_unscored 断言计数
    hu = 0
    for c in case_entries:
        for r in c["repeat_results"]:
            hu += sum(1 for a in r.get("assertions", []) if a["verdict"] == "human_unscored")

    run_log = {
        "run_id": run_id, "config": config, "repeat": args.repeat,
        "started_at": utcnow(), "python": sys.version.split()[0],
        "cases": case_entries,
        "summary": {
            "total": len(case_entries), "pass": n("pass"), "fail": n("fail"),
            "unrun": n("unrun"), "manual_required": n("manual_required"),
            "error": n("error"), "human_unscored_assertions": hu,
            "script_pass_rate": (round(script_pass / len(script_cases), 3)
                                 if script_cases else None),
            "variance": ("repeat 结论不一致的 case: %s" % inconsistent) if inconsistent
                        else ("repeat 结论一致（%d 个 script case）" % len(script_cases)
                              if script_cases else None),
        },
    }
    run_log["degradation_alert"] = degradation_alert(run_log)
    run_log["finished_at"] = utcnow()

    log_path = os.path.join(run_dir, "run-log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(run_log, f, ensure_ascii=False, indent=2)

    s = run_log["summary"]
    print("-" * 72)
    print("run_id=%s config=%s repeat=%d" % (run_id, config, args.repeat))
    print("summary: total=%d pass=%d fail=%d unrun=%d manual_required=%d error=%d" % (
        s["total"], s["pass"], s["fail"], s["unrun"], s["manual_required"], s["error"]))
    print("script_pass_rate=%s variance=%s" % (s["script_pass_rate"], s["variance"]))
    al = run_log["degradation_alert"]
    print("degradation_alert: triggered=%s items=%s" % (al["triggered"], al["items"] or "-"))
    print("run-log: %s" % os.path.relpath(log_path, eval_lib.SKILL_ROOT))
    if s["unrun"] + s["manual_required"] > 0:
        print("NOTE: unrun/manual_required 的 case 未运行，不得视为通过；"
              "manual case 请会话内运行后用 --evidence-dir 回填判定。")
    if s["fail"] > 0:
        print("run_evals: FAIL")
        return 1
    if args.strict and (s["unrun"] + s["manual_required"] > 0):
        print("run_evals: FAIL(strict)（存在未运行 case）")
        return 2
    print("run_evals: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
