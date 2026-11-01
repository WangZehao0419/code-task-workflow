# -*- coding: utf-8 -*-
"""文档 lint：frontmatter、markdown 相对链接、协议技能路径、悬空引用、版本一致性。

用法：
    python scripts/lint_docs.py     # exit 0=通过 / 1=失败
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_lib

SKILL_MD = os.path.join(eval_lib.SKILL_ROOT, "SKILL.md")
PHASES_MD = os.path.join(eval_lib.SKILL_ROOT, "references", "phases.md")
SKILLS_ROOT = os.path.dirname(eval_lib.SKILL_ROOT)

# SKILL.md 引用的磁盘协议技能（逻辑名 → 物理目录；None=同名）
PROTO_SKILLS = {
    "grill-with-docs": "grill-with-docs",
    "to-spec": "to-spec",
    "to-tickets": "to-tickets",
    "implement": "implement",
    "implement-spec": "implement-spec",
    "retro": "retro",
    "domain-modeling": "domain-modeling-2",  # 逻辑名映射（references/invocation.md 解析规则第 3 条）
}

# SKILL.md 应引用的本技能内文件（交付完整性）
INTERNAL_FILES = [
    "references/phases.md",
    "evals/evals.json",
    "evals/schema.json",
    "scripts/validate_evals.py",
    "scripts/run_evals.py",
]

# 已删除/不得残留的悬空引用
DANGLING_PATTERNS = [
    (r"cost-profile-spec", "成本画像规格文件已删除（v1.6 迁移至 eval runner），引用须为残留"),
]

_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def check_frontmatter(errors):
    text = read(SKILL_MD)
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        errors.append("SKILL.md: 缺少 frontmatter")
        return None
    fm = m.group(1)
    name = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE)
    version = re.search(r"^version:\s*(\S+)", fm, re.MULTILINE)
    desc = re.search(r'^description:\s*"(.)', fm, re.MULTILINE)
    if not name or name.group(1) != "code-task-workflow":
        errors.append("SKILL.md frontmatter: name 缺失或不是 code-task-workflow")
    if not version:
        errors.append("SKILL.md frontmatter: 缺少 version")
    elif not re.match(r"^\d+\.\d+\.\d+$", version.group(1)):
        errors.append("SKILL.md frontmatter: version 格式须为 x.y.z（当前 %s）" % version.group(1))
    if not desc:
        errors.append("SKILL.md frontmatter: description 缺失或未加引号")
    # 撤占行为检查：description 不得再写抢占句式
    if re.search(r"任何代码任务都先经本技能路由", fm):
        errors.append("SKILL.md description: 仍含抢占句式「任何代码任务都先经本技能路由」（v1.6 已收窄）")
    # 与 evals.json contract_version 一致
    try:
        data = eval_lib.load_evals()
        cv = data.get("contract_version")
        if version and cv and cv != version.group(1):
            errors.append("版本不一致：SKILL.md version=%s，evals.json contract_version=%s"
                          % (version.group(1), cv))
    except (OSError, ValueError):
        errors.append("evals.json 无法加载，版本一致性未检")
    return version.group(1) if version else None


def check_links(errors):
    for path in (SKILL_MD, PHASES_MD):
        base = os.path.dirname(path)
        for target in _LINK_RE.findall(read(path)):
            if target.startswith(("http://", "https://", "file://", "#", "computer:")):
                continue
            resolved = os.path.normpath(os.path.join(base, target.split("#")[0]))
            if not os.path.exists(resolved):
                errors.append("%s: 链接目标不存在：%s" % (os.path.relpath(path, eval_lib.SKILL_ROOT), target))


def _skills_root_candidates():
    """协议技能候选安装根：环境变量 > 仓库同级目录（安装态布局） > 用户级安装目录。"""
    roots = []
    env_root = os.environ.get("SKILLS_ROOT")
    if env_root:
        roots.append(env_root)
    if SKILLS_ROOT not in roots:
        roots.append(SKILLS_ROOT)
    home = os.path.expanduser("~")
    for sub in (os.path.join(home, ".zcode", "skills"),
                os.path.join(home, ".workbuddy", "skills")):
        if sub not in roots:
            roots.append(sub)
    return roots


def check_proto_skills(errors):
    roots = _skills_root_candidates()
    for logical, physical in PROTO_SKILLS.items():
        hits = [r for r in roots if os.path.isfile(os.path.join(r, physical, "SKILL.md"))]
        if not hits:
            errors.append(
                "协议技能缺失：%s（已在以下根目录查找：%s）"
                % (logical, "；".join(os.path.abspath(r) for r in roots))
            )


def check_internal_refs(errors):
    text = read(SKILL_MD)
    for rel in INTERNAL_FILES:
        if rel not in text:
            errors.append("SKILL.md 未引用交付文件：%s" % rel)
        if not os.path.isfile(os.path.join(eval_lib.SKILL_ROOT, rel)):
            errors.append("引用的交付文件不存在：%s" % rel)


def check_dangling(errors):
    for path in (SKILL_MD, PHASES_MD):
        text = read(path)
        for pat, why in DANGLING_PATTERNS:
            if re.search(pat, text):
                errors.append("%s: 悬空引用残留（%s）：%s"
                              % (os.path.relpath(path, eval_lib.SKILL_ROOT), why, pat))


def check_mutation_assertions(errors):
    mut_path = os.path.join(eval_lib.SKILL_ROOT, "evals", "mutations.json")
    if not os.path.isfile(mut_path):
        errors.append("evals/mutations.json 不存在")
        return
    muts = eval_lib.load_json(mut_path).get("mutations", [])
    data = eval_lib.load_evals()
    by_case = {eval_lib.norm_case_id(c["id"]): {a["id"] for a in c.get("assertions", [])}
               for c in data.get("evals", [])}
    for m in muts:
        target = m.get("target_case")
        if target not in by_case:
            errors.append("mutations[%s]: 目标 case 不存在：%s" % (m.get("id"), target))
            continue
        for aid in m.get("expect_fail_assertions", []):
            if aid not in by_case[target]:
                errors.append("mutations[%s]: 断言 %s 不在 case %s 中" % (m.get("id"), aid, target))


def main():
    errors = []
    version = check_frontmatter(errors)
    check_links(errors)
    check_proto_skills(errors)
    check_internal_refs(errors)
    check_dangling(errors)
    check_mutation_assertions(errors)
    if errors:
        print("lint_docs: FAIL（%d 项）" % len(errors))
        for e in errors:
            print("  - %s" % e)
        return 1
    print("lint_docs: PASS（frontmatter 版本=%s；链接/协议路径/内部引用/悬空引用/mutation 断言均通过）"
          % (version or "?"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
