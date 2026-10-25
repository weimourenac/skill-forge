#!/usr/bin/env python3
"""零依赖 Agent Skill 校验器。

用法:
    python scripts/validate_skill.py <skill目录>
    uv run python scripts/validate_skill.py <skill目录>

退出码: 0 = 无 error（warning 不影响）; 1 = 有 error; 2 = 用法错误
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ALLOWED_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESOURCE_RE = re.compile(r"(?<![A-Za-z0-9_/])(?:references|scripts|assets)/[A-Za-z0-9._\-/]+")
TRAILING = ".,;:，。；：、)）】」』\"'"


def parse_frontmatter(text: str):
    """解析常见 YAML 子集；返回 (frontmatter, body, error)。"""
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "", "SKILL.md 必须以下列形式的 YAML frontmatter 开头：第一行 ---"
    end = next(
        (
            i
            for i in range(1, len(lines))
            if lines[i].strip() == "---" and not lines[i][:1].isspace()
        ),
        None,
    )
    if end is None:
        return None, "", "frontmatter 缺少结束的 ---"

    frontmatter = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0] in " \t":  # 嵌套字段（如 metadata）不参与顶层校验
            i += 1
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            i += 1
            continue
        key, value = match.group(1), match.group(2).strip()
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            block = []
            i += 1
            while i < end and (not lines[i].strip() or lines[i][0] in " \t"):
                block.append(lines[i])
                i += 1
            if value.startswith("|"):
                frontmatter[key] = "\n".join(x.strip() for x in block).strip()
            else:
                frontmatter[key] = " ".join(x.strip() for x in block if x.strip())
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        frontmatter[key] = value
        i += 1

    return frontmatter, "\n".join(lines[end + 1 :]), None


def validate(skill_dir: Path):
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, int] = {}

    if not skill_dir.is_dir():
        return [f"目录不存在：{skill_dir}"], warnings, stats

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return ["缺少 SKILL.md"], warnings, stats

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    frontmatter, body, error = parse_frontmatter(text)
    if error:
        return [error], warnings, stats

    unknown = set(frontmatter) - ALLOWED_KEYS
    if unknown:
        errors.append(
            "frontmatter 含未知字段："
            + ", ".join(sorted(unknown))
            + "（允许："
            + ", ".join(sorted(ALLOWED_KEYS))
            + "）"
        )

    name = frontmatter.get("name", "")
    if not name:
        errors.append("缺少 name")
    else:
        if not NAME_RE.match(name):
            errors.append(
                f"name '{name}' 不是 kebab-case（仅 a-z / 0-9 / -，不能首尾 - 或 --）"
            )
        if len(name) > 64:
            errors.append(f"name 长度 {len(name)} > 64")
        if name != skill_dir.name:
            errors.append(f"name '{name}' 与目录名 '{skill_dir.name}' 不一致")

    description = frontmatter.get("description", "")
    if not description:
        errors.append("缺少 description")
    else:
        if len(description) > 1024:
            errors.append(f"description 长度 {len(description)} > 1024")
        if "<" in description or ">" in description:
            warnings.append(
                "description 含尖括号 < >（部分平台会拒绝；箭头 -> 也会命中），建议改写"
            )
        if len(description) < 40:
            warnings.append(
                f"description 只有 {len(description)} 字符，可能缺少触发场景或关键词"
            )

    compatibility = frontmatter.get("compatibility", "")
    if compatibility and len(compatibility) > 500:
        errors.append(f"compatibility 长度 {len(compatibility)} > 500")

    body_lines = len(body.strip().splitlines())
    body_chars = len(body.strip())
    if body_lines > 500:
        errors.append(f"正文 {body_lines} 行 > 500（官方建议上限；请拆到 references/）")
    elif body_lines > 200:
        warnings.append(f"正文 {body_lines} 行 > 200（本工作区目标；考虑拆分）")
    if body_chars > 3000:
        warnings.append(
            f"正文 {body_chars} 字 > 3000（目标；检查是否有可移到 references/ 的内容）"
        )

    referenced: set[str] = set()
    for match in RESOURCE_RE.finditer(body):
        referenced.add(match.group(0).rstrip(TRAILING))

    skill_root = skill_dir.resolve()
    for ref in sorted(referenced):
        target = (skill_dir / ref).resolve()
        if target != skill_root and skill_root not in target.parents:
            errors.append(f"正文引用了 skill 目录之外的资源：{ref}")
            continue
        if not target.exists():
            errors.append(f"正文引用了不存在的资源：{ref}")

    for sub in ("references", "scripts"):
        folder = skill_dir / sub
        if not folder.is_dir():
            continue
        for file in sorted(folder.rglob("*")):
            if not file.is_file() or file.name == ".gitkeep":
                continue
            if "__pycache__" in file.parts or file.suffix == ".pyc":
                continue
            rel = file.relative_to(skill_dir).as_posix()
            if rel not in referenced:
                inner = file.relative_to(folder).as_posix()
                warnings.append(f"{sub}/ 下的 {inner} 未在正文中提及（可能永远不会被读）")

    stats = {
        "lines": body_lines,
        "chars": body_chars,
        "bytes": skill_md.stat().st_size,
        "refs": len(referenced),
    }
    return errors, warnings, stats


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("用法：python scripts/validate_skill.py <skill目录>")
        return 2

    skill_dir = Path(argv[1]).resolve()
    errors, warnings, stats = validate(skill_dir)

    print(f"检查：{skill_dir}")
    for warning in warnings:
        print(f"[warn] {warning}")
    for error in errors:
        print(f"[error] {error}")
    if stats:
        print(
            f"正文：{stats['lines']} 行 / {stats['chars']} 字 / "
            f"SKILL.md {stats['bytes']} 字节 / 引用资源 {stats['refs']} 个"
        )

    if errors:
        print(f"结果：失败（{len(errors)} error / {len(warnings)} warning）")
        return 1
    print(f"结果：通过（0 error / {len(warnings)} warning）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
