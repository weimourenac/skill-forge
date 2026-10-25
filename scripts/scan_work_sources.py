#!/usr/bin/env python3
"""只列工作流 / 工作记忆的候选来源，不读文件内容。

用法:
    python scripts/scan_work_sources.py [目录 ...] [--max-files 2000] [--top 15]
    uv run python scripts/scan_work_sources.py D:/Skill
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".cache",
    ".next",
    ".idea",
    ".vscode",
    "site-packages",
}
EXTENSIONS = {
    ".md",
    ".txt",
    ".jsonl",
    ".json",
    ".ps1",
    ".sh",
    ".py",
    ".mjs",
    ".js",
    ".yaml",
    ".yml",
}
SPECIAL = {"AGENTS.md", "CLAUDE.md", "README.md", "FACT.md", "JOURNAL.jsonl", "SKILL.md"}


def classify(path: Path) -> str:
    if path.name in {"FACT.md", "JOURNAL.jsonl", "SOUL.md", "USER.md"} or "memory" in path.parts:
        return "记忆/状态"
    if path.name in {"AGENTS.md", "CLAUDE.md", "README.md"}:
        return "项目规则"
    if path.suffix.lower() in {".ps1", ".sh", ".py", ".mjs", ".js"}:
        return "脚本/命令"
    if path.suffix.lower() in {".jsonl", ".json", ".csv"}:
        return "数据"
    return "文档/交接"


def main() -> int:
    parser = argparse.ArgumentParser(description="列出工作流 / 记忆候选来源")
    parser.add_argument("roots", nargs="*", default=["."])
    parser.add_argument("--max-files", type=int, default=2000)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()
    if args.max_files < 1:
        parser.error("--max-files 必须 ≥1")
    if args.top < 1:
        parser.error("--top 必须 ≥1")

    found = []
    seen = set()
    truncated = False

    def add(path: Path) -> None:
        nonlocal truncated
        if truncated or path in seen:
            return
        if path.suffix.lower() not in EXTENSIONS and path.name not in SPECIAL:
            return
        try:
            stat = path.stat()
        except OSError:
            return
        if stat.st_size > 2 * 1024 * 1024:
            return
        seen.add(path)
        found.append((path, stat.st_size, stat.st_mtime, classify(path)))
        if len(found) >= args.max_files:
            truncated = True

    for root_text in args.roots:
        root = Path(root_text).resolve()
        if not root.exists():
            print(f"[warn] 不存在：{root}")
            continue
        if root.is_file():
            add(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
            for filename in filenames:
                add(Path(dirpath) / filename)
                if truncated:
                    break
            if truncated:
                break
        if truncated:
            break

    if not found:
        print("没有找到候选文件。")
        return 0

    groups = {}
    for item in found:
        groups.setdefault(item[3], []).append(item)

    total_size = sum(item[1] for item in found)
    print(f"扫描：{', '.join(str(Path(root).resolve()) for root in args.roots)}")
    print(f"候选文件：{len(found)} 个 / {total_size / 1024:.1f} KB")
    for label, items in sorted(groups.items()):
        size = sum(item[1] for item in items)
        print(f"- {label}: {len(items)} 个 / {size / 1024:.1f} KB")

    print("\n最近修改的候选（先看这些）：")
    for path, size, mtime, label in sorted(found, key=lambda item: -item[2])[: args.top]:
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
        print(f"  {stamp}  {size:>8}  {label:<6}  {path}")

    print("\n提示：先读规则 / 记忆小文件；大文件用 rg 搜关键词，不要整份读。")
    if truncated:
        print(f"[warn] 已达到 --max-files {args.max_files}，结果被截断。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
