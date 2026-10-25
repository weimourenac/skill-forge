#!/usr/bin/env python3
"""对 Agent Skill 做静态体检：结构、token、重复、密钥、危险命令、脚本语法。

用法:
    python scripts/skill_doctor.py <skill目录> [--json]
    uv run python scripts/skill_doctor.py <skill目录>
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True

from validate_skill import parse_frontmatter, validate

SECRET_PATTERNS = [
    ("OpenAI 风格 key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("GitHub token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "通用密钥赋值",
        re.compile(
            r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"
        ),
    ),
]
DANGEROUS_PATTERNS = [
    ("管道执行远程脚本", re.compile(r"curl[^\n|]*\|\s*(sh|bash)", re.IGNORECASE)),
    (
        "PowerShell 编码命令",
        re.compile(r"powershell(\.exe)?[^\n]*-enc(odedcommand)?\b", re.IGNORECASE),
    ),
    ("Invoke-Expression", re.compile(r"\b(iex|Invoke-Expression)\b", re.IGNORECASE)),
    ("递归强删根目录", re.compile(r"rm\s+-rf\s+/(\*|\s|$)", re.IGNORECASE)),
]
GENERIC_DESC = [
    "本技能用于",
    "本技能介绍",
    "该技能用于",
    "该技能介绍",
    "用于帮助用户",
    "helps users",
    "this skill provides",
    "provides a",
]
TRIGGER_MARKERS = [
    "当用户",
    "当",
    "如果",
    "提到",
    "说",
    "时使用",
    "用户要求",
    "需要",
    "when",
    "whenever",
    "use when",
    "trigger",
]


def estimate_tokens(text: str) -> int:
    """粗估 token：中文按 1 字≈1 token，其他按 4 字符≈1 token。"""
    chinese = len(re.findall(r"[一-鿿]", text))
    other = len(text) - chinese
    return math.ceil(chinese + other / 4)


TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".py",
    ".ps1",
    ".sh",
    ".js",
    ".mjs",
}
SELF = Path(__file__).resolve()


def scan_files(skill_dir: Path):
    yield skill_dir / "SKILL.md"
    for sub in ("references", "assets", "examples", "scripts"):
        folder = skill_dir / sub
        if not folder.is_dir():
            continue
        for file in sorted(folder.rglob("*")):
            if file.is_file() and file.suffix.lower() in TEXT_SUFFIXES:
                yield file


def duplicate_lines(texts):
    counter = Counter()
    first_seen = {}
    for name, text in texts:
        in_code = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            normalized = re.sub(r"\s+", " ", stripped)
            if len(normalized) < 20:
                continue
            if normalized.startswith(("#", "|", "- [", "> ")):
                continue
            counter[normalized] += 1
            first_seen.setdefault(normalized, name)
    duplicates = [
        (line, count, first_seen[line])
        for line, count in counter.items()
        if count > 1
    ]
    return sorted(duplicates, key=lambda item: (-item[1], -len(item[0])))


def diagnose(skill_dir: Path):
    errors, warnings, stats = validate(skill_dir)
    info = {}

    if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
        return errors, warnings, info

    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    frontmatter, body, error = parse_frontmatter(text)
    if error:
        return errors, warnings, info

    description = frontmatter.get("description", "")
    lowered = description.lower()
    if any(marker.lower() in lowered for marker in GENERIC_DESC):
        warnings.append("description 含「本技能 / 用于帮助」这类介绍口吻，可能缺少触发词")
    if description and not any(marker.lower() in lowered for marker in TRIGGER_MARKERS):
        warnings.append("description 没有明显的触发标记（当用户 / 如果 / when ...）")
    if len(description) > 350:
        warnings.append(f"description {len(description)} 字符 > 350（目标；考虑精简）")

    body_tokens = estimate_tokens(body)
    references = sorted((skill_dir / "references").rglob("*.md")) if (skill_dir / "references").is_dir() else []
    reference_tokens = {}
    texts = [("SKILL.md", body)]
    for reference in references:
        relative = reference.relative_to(skill_dir).as_posix()
        content = reference.read_text(encoding="utf-8", errors="replace")
        reference_tokens[relative] = estimate_tokens(content)
        texts.append((relative, content))

    info["body_tokens"] = body_tokens
    info["body_lines"] = stats.get("lines", 0)
    info["reference_tokens"] = reference_tokens

    duplicates = duplicate_lines(texts)
    if duplicates:
        warnings.append(f"发现 {len(duplicates)} 条跨文件重复长行（一条规则只该写一次）")
        info["duplicates"] = [
            {"line": line[:100], "count": count, "first_seen": name}
            for line, count, name in duplicates[:5]
        ]

    secret_hits = 0
    for path in scan_files(skill_dir):
        if path.resolve() == SELF:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(content):
                secret_hits += 1
                errors.append(f"{path.relative_to(skill_dir).as_posix()} 疑似包含{label}")

    for path in scan_files(skill_dir):
        if path.resolve() == SELF:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in DANGEROUS_PATTERNS:
            if pattern.search(content):
                warnings.append(f"{path.relative_to(skill_dir).as_posix()} 出现「{label}」模式，确认是否必要")

    python_scripts = sorted((skill_dir / "scripts").rglob("*.py")) if (skill_dir / "scripts").is_dir() else []
    syntax_failures = []
    for script in python_scripts:
        try:
            compile(script.read_text(encoding="utf-8", errors="replace"), str(script), "exec")
        except SyntaxError as exc:
            syntax_failures.append(f"{script.name}: {exc.msg} (line {exc.lineno})")
    if syntax_failures:
        errors.extend(f"脚本语法错误：{failure}" for failure in syntax_failures)

    info["scripts_total"] = len(python_scripts)
    info["scripts_failed"] = len(syntax_failures)
    info["secrets"] = secret_hits
    info["resources"] = {
        sub: sum(
            1
            for item in (skill_dir / sub).rglob("*")
            if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc"
        )
        for sub in ("references", "scripts", "assets", "examples")
        if (skill_dir / sub).is_dir()
    }
    return errors, warnings, info


def main(argv: list[str]) -> int:
    json_output = "--json" in argv
    args = [item for item in argv[1:] if item != "--json"]
    if len(args) != 1:
        print("用法：python scripts/skill_doctor.py <skill目录> [--json]")
        return 2

    skill_dir = Path(args[0]).resolve()
    errors, warnings, info = diagnose(skill_dir)

    if json_output:
        print(
            json.dumps(
                {"ok": not errors, "errors": errors, "warnings": warnings, "info": info},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if errors else 0

    print(f"体检：{skill_dir}")
    for warning in warnings:
        print(f"[warn] {warning}")
    for error in errors:
        print(f"[error] {error}")
    if info:
        print(
            f"[info] 正文粗估 ~{info.get('body_tokens', 0)} tokens / "
            f"{info.get('body_lines', 0)} 行"
        )
        if info.get("reference_tokens"):
            parts = [f"{name} ~{tokens}" for name, tokens in info["reference_tokens"].items()]
            print("[info] 参考文件粗估：" + "，".join(parts) + " tokens")
        print(
            f"[info] 资源：references {info.get('resources', {}).get('references', 0)} / "
            f"scripts {info.get('resources', {}).get('scripts', 0)} / "
            f"assets {info.get('resources', {}).get('assets', 0)} / "
            f"examples {info.get('resources', {}).get('examples', 0)}"
        )
        print(
            f"[info] Python 脚本：{info.get('scripts_total', 0) - info.get('scripts_failed', 0)}"
            f"/{info.get('scripts_total', 0)} 可编译；密钥命中 {info.get('secrets', 0)} 处"
        )

    if errors:
        print(f"结果：失败（{len(errors)} error / {len(warnings)} warning）")
        return 1
    print(f"结果：通过（0 error / {len(warnings)} warning）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
