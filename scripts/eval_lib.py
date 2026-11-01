# -*- coding: utf-8 -*-
"""eval 契约共享库：schema 加载、语义字段映射、断言判定核心。

validate_evals.py 与 run_evals.py 共用本模块，避免两处实现漂移。
不依赖第三方库（标准库 only），Python 3.8+。
"""
import glob
import json
import os
import re
import shutil
import sys
import tempfile

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS_PATH = os.path.join(SKILL_ROOT, "evals", "evals.json")
SCHEMA_PATH = os.path.join(SKILL_ROOT, "evals", "schema.json")

# ---------------------------------------------------------------------------
# 规格语义字段（canonical schema 唯一机器事实源，与 evals/schema.json definitions.semantic_fields
# 及 references/phases.md 阶段② 保持一致；改动须三处同步）
# ---------------------------------------------------------------------------
SEMANTIC_FIELDS = {
    "User Behavior": ["Problem Statement", "Solution", "User Stories", "用户行为"],
    "Constraints": ["Constraints", "Implementation Decisions", "约束"],
    "Test Plan": ["Test Plan", "Testing Decisions", "测试方法", "测试方式"],
    "Out of Scope": [],  # 无别名，必须命中精确标题（大小写不敏感）
}

EVIDENCE_TYPES = {
    "file_exists", "file_contains", "semantic_fields",
    "command_output", "event_log", "diff_scope",
}
CASE_TYPES = {"machine", "human", "negative"}
RUNNER_MODES = {"script", "manual"}
PRIORITIES = {"P0", "P1", "P2"}
GATE_IDS = {"G1", "G2", "G3", "G4", "G5", "G6", "G7"}
USER_CONFIRMATION_GATES = {"G1", "G2", "G3", "G4", "G6", "G7"}  # G5 为 evidence-based


class ValidationError(Exception):
    """契约校验失败（聚合消息）。"""


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_evals():
    return load_json(EVALS_PATH)


def norm_case_id(cid):
    return str(cid)


# ---------------------------------------------------------------------------
# schema 校验（手写实现 schema.json 的约束，避免 jsonschema 依赖）
# ---------------------------------------------------------------------------

def _err(errors, path, msg):
    errors.append("%s: %s" % (path, msg))


def _check_assertion(errors, cpath, idx, a, seen_assertion_ids):
    apath = "%s.assertions[%d]" % (cpath, idx)
    if not isinstance(a, dict):
        _err(errors, apath, "必须是对象")
        return
    for field in ("id", "text", "kind"):
        if field not in a:
            _err(errors, apath, "缺少必填字段 %s" % field)
    aid = a.get("id")
    if aid is not None:
        if not isinstance(aid, str) or not re.match(r"^[a-z0-9][a-z0-9-]*$", aid):
            _err(errors, apath + ".id", "须为小写字母/数字/连字符（^[a-z0-9][a-z0-9-]*$）")
        if aid in seen_assertion_ids:
            _err(errors, apath + ".id", "断言 id 重复：%s" % aid)
        seen_assertion_ids.add(aid)
    kind = a.get("kind")
    if kind is not None and kind not in ("machine", "human_unscored"):
        _err(errors, apath + ".kind", "须为 machine | human_unscored")
    gate = a.get("gate")
    if gate is not None:
        if gate not in GATE_IDS:
            _err(errors, apath + ".gate", "门控编号须为 G1-G7")
        elif kind == "machine" and gate in USER_CONFIRMATION_GATES:
            _err(errors, apath, "%s 是 user-confirmation 门控，断言不得标为 machine（须 human_unscored）" % gate)
        elif kind == "human_unscored" and gate == "G5":
            _err(errors, apath, "G5 是 evidence-based 门控，断言不得标为 human_unscored（须 machine）")
    if kind == "machine":
        has_evidence = isinstance(a.get("evidence"), dict) and a["evidence"].get("type") in EVIDENCE_TYPES
        has_forbidden = isinstance(a.get("forbidden"), list) and len(a["forbidden"]) > 0
        if not has_evidence and not has_forbidden:
            _err(errors, apath, "machine 断言必须有可判定的 evidence（type 合法）或 forbidden 列表")
    if kind == "human_unscored" and isinstance(a.get("evidence"), dict):
        _err(errors, apath, "human_unscored 断言不得附 evidence（用户确认不伪装机器判定）")
    ev = a.get("evidence")
    if isinstance(ev, dict):
        if ev.get("type") not in EVIDENCE_TYPES:
            _err(errors, apath + ".evidence.type", "须为 %s 之一" % sorted(EVIDENCE_TYPES))
        if ev.get("type") in ("file_exists", "file_contains", "semantic_fields") \
                and not isinstance(ev.get("paths"), list):
            _err(errors, apath + ".evidence.paths", "该 evidence type 须提供 paths 列表")


def check_contract(data, errors):
    """按 schema.json 校验 evals.json 数据结构，错误追加到 errors。"""
    if not isinstance(data, dict):
        _err(errors, "$", "顶层必须是对象")
        return
    if data.get("skill_name") != "code-task-workflow":
        _err(errors, "skill_name", "必须为 code-task-workflow")
    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        _err(errors, "evals", "必须为非空数组")
        return

    seen_ids, seen_assertion_ids = set(), set()
    for i, case in enumerate(evals):
        cpath = "evals[%d]" % i
        if not isinstance(case, dict):
            _err(errors, cpath, "必须是对象")
            continue
        for field in ("id", "name", "prompt", "expected_output", "files",
                      "assertions", "type", "runner_mode", "priority"):
            if field not in case:
                _err(errors, cpath, "缺少必填字段 %s" % field)
        cid = norm_case_id(case.get("id", i))
        if cid in seen_ids:
            _err(errors, cpath + ".id", "case id 重复：%s" % cid)
        seen_ids.add(cid)
        if case.get("type") not in CASE_TYPES:
            _err(errors, cpath + ".type", "须为 machine | human | negative")
        if case.get("runner_mode") not in RUNNER_MODES:
            _err(errors, cpath + ".runner_mode", "须为 script | manual")
        if case.get("priority") not in PRIORITIES:
            _err(errors, cpath + ".priority", "须为 P0 | P1 | P2")
        if not isinstance(case.get("files"), list):
            _err(errors, cpath + ".files", "须为数组（v1.5 兼容字段）")
        assertions = case.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            _err(errors, cpath + ".assertions", "须为非空数组")
        else:
            for j, a in enumerate(assertions):
                _check_assertion(errors, cpath, j, a, seen_assertion_ids)

        rmode = case.get("runner_mode")
        if rmode == "script" and not case.get("command"):
            _err(errors, cpath + ".command", "runner_mode=script 必须提供 command")
        if rmode == "script" and isinstance(assertions, list):
            if not any(isinstance(a, dict) and a.get("kind") == "machine" for a in assertions):
                _err(errors, cpath, "runner_mode=script 至少含一条 machine 断言（否则无可脚本判定内容）")
        fixture = case.get("fixture")
        if fixture:
            fpath = os.path.join(SKILL_ROOT, fixture)
            if not os.path.isdir(fpath):
                _err(errors, cpath + ".fixture", "fixture 目录不存在：%s" % fpath)
        if case.get("timeout") is not None:
            t = case["timeout"]
            if not isinstance(t, (int, float)) or t <= 0:
                _err(errors, cpath + ".timeout", "须为正数")

        # 类型相关约束
        ctype = case.get("type")
        if ctype == "human" and isinstance(assertions, list):
            if not any(isinstance(a, dict) and a.get("kind") == "human_unscored" for a in assertions):
                _err(errors, cpath, "type=human 至少含一条 human_unscored 断言")
        if ctype == "negative" and isinstance(assertions, list):
            neg_capable = any(
                isinstance(a, dict) and (
                    (isinstance(a.get("forbidden"), list) and a["forbidden"]) or
                    (isinstance(a.get("evidence"), dict) and (
                        a["evidence"].get("expect") == "absent" or
                        (a["evidence"].get("type") == "diff_scope" and "allowed_paths" in a["evidence"])
                    ))
                )
                for a in assertions
            )
            if not neg_capable:
                _err(errors, cpath, "type=negative 至少含一条 forbidden 或 expect=absent 断言")

    # depends_on 引用与环检查
    for i, case in enumerate(evals):
        if not isinstance(case, dict):
            continue
        cid = norm_case_id(case.get("id", i))
        deps = case.get("depends_on") or []
        if not isinstance(deps, list):
            _err(errors, "evals[%s].depends_on" % cid, "须为数组")
            continue
        for d in deps:
            if norm_case_id(d) not in seen_ids:
                _err(errors, "evals[%s].depends_on" % cid, "引用不存在的 case id：%s" % d)
    _check_no_cycle(errors, evals)

    # 触发测试集
    ts = data.get("trigger_set")
    if ts is not None:
        _check_trigger_set(errors, ts)


def _check_no_cycle(errors, evals):
    ids = {}
    for i, case in enumerate(evals):
        if isinstance(case, dict):
            ids[norm_case_id(case.get("id", i))] = case
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {cid: WHITE for cid in ids}

    def dfs(cid, stack):
        color[cid] = GRAY
        case = ids[cid]
        for d in (case.get("depends_on") or []):
            did = norm_case_id(d)
            if did not in ids:
                continue
            if color.get(did) == GRAY:
                _err(errors, "evals[%s].depends_on" % cid, "依赖环：%s" % (stack + [cid, did]))
            elif color.get(did) == WHITE:
                dfs(did, stack + [cid])
        color[cid] = BLACK

    for cid in ids:
        if color[cid] == WHITE:
            dfs(cid, [])


def _check_trigger_set(errors, ts):
    if ts.get("runner_mode") != "manual":
        _err(errors, "trigger_set.runner_mode", "触发测试集必须为 manual（路由行为须真实会话判定）")
    if not isinstance(ts.get("repeat"), int) or ts.get("repeat", 0) < 1:
        _err(errors, "trigger_set.repeat", "须为正整数")
    cases = ts.get("cases")
    if not isinstance(cases, list) or len(cases) < 20:
        _err(errors, "trigger_set.cases", "至少 20 条（10 should-trigger + 10 should-not-trigger）")
        return
    pos = [c for c in cases if c.get("expect_trigger") is True]
    neg = [c for c in cases if c.get("expect_trigger") is False]
    if len(pos) < 10:
        _err(errors, "trigger_set.cases", "should-trigger 正例不足 10 条（当前 %d）" % len(pos))
    if len(neg) < 10:
        _err(errors, "trigger_set.cases", "should-not-trigger 反例不足 10 条（当前 %d）" % len(neg))
    seen = set()
    for idx, c in enumerate(cases):
        if not isinstance(c, dict):
            _err(errors, "trigger_set.cases[%d]" % idx, "必须是对象")
            continue
        for field in ("id", "query", "expect_trigger"):
            if field not in c:
                _err(errors, "trigger_set.cases[%d]" % idx, "缺少必填字段 %s" % field)
        if c.get("id") in seen:
            _err(errors, "trigger_set.cases[%d].id" % idx, "id 重复：%s" % c.get("id"))
        seen.add(c.get("id"))


def validate_all():
    """全量校验，返回错误列表（空列表=通过）。"""
    errors = []
    try:
        data = load_evals()
    except (OSError, ValueError) as e:
        return ["evals/evals.json 无法加载：%s" % e]
    try:
        schema = load_json(SCHEMA_PATH)
    except (OSError, ValueError) as e:
        return ["evals/schema.json 无法加载：%s" % e]
    if not isinstance(schema, dict) or "definitions" not in schema:
        errors.append("evals/schema.json 结构异常：缺少 definitions")
    check_contract(data, errors)
    return errors


# ---------------------------------------------------------------------------
# 语义字段校验（规格文档四语义字段：经 alias 表映射后存在且非空）
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")


def check_semantic_fields(text):
    """检查 markdown 文本是否满足四语义字段。返回 (ok, missing_fields, found_heads)。"""
    heads = []
    current = {"name": None, "lines": []}
    sections = []
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if current["name"] is not None:
                sections.append(current)
            current = {"name": m.group(1).strip(), "lines": []}
        else:
            current["lines"].append(line)
    if current["name"] is not None:
        sections.append(current)

    covered = set()
    for field, aliases in SEMANTIC_FIELDS.items():
        candidates = [field] + list(aliases)
        for sec in sections:
            sec_name = sec["name"].lower()
            for cand in candidates:
                if sec_name == cand.lower():
                    if any(l.strip() for l in sec["lines"]):
                        covered.add(field)
                    break
            if field in covered:
                break
    missing = [f for f in SEMANTIC_FIELDS if f not in covered]
    return (not missing), missing, [s["name"] for s in sections]


# ---------------------------------------------------------------------------
# 沙盒工具
# ---------------------------------------------------------------------------

def make_sandbox(fixture_rel, evidence_case_dir=None):
    """创建临时沙盒：先复制 fixture（或空 project），再覆盖复制回填证据。

    返回 (沙盒路径, project 路径)，调用方负责 shutil.rmtree 清理。
    """
    sandbox = tempfile.mkdtemp(prefix="ctw-eval-")
    project = os.path.join(sandbox, "project")
    if fixture_rel:
        src = os.path.join(SKILL_ROOT, fixture_rel)
        if os.path.isdir(src):
            shutil.copytree(src, project)
        else:
            os.makedirs(project, exist_ok=True)
    else:
        os.makedirs(project, exist_ok=True)
    if evidence_case_dir and os.path.isdir(evidence_case_dir):
        # 证据后复制：覆盖 fixture 同名文件（被评估方的修改副本以证据为准）
        for item in os.listdir(evidence_case_dir):
            s = os.path.join(evidence_case_dir, item)
            d = os.path.join(project, item)
            if os.path.isdir(s):
                if os.path.isdir(d):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
    return sandbox, project


def match_any_glob(root, patterns):
    """root 下任一文件/目录命中 patterns（glob）即返回命中列表。"""
    hits = []
    for pat in patterns:
        for p in glob.glob(os.path.join(root, pat), recursive=True):
            hits.append(os.path.relpath(p, root))
    return hits


if __name__ == "__main__":
    print("Python:", sys.version.split()[0])
    print("SKILL_ROOT:", SKILL_ROOT)
    errors = validate_all()
    print("validate:", "OK" if not errors else errors)
