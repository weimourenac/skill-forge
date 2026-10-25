#!/usr/bin/env python3
"""把 JOURNAL.jsonl / FACT.md 压成短摘要，避免整份读入上下文。

用法:
    python scripts/memory_digest.py [路径] [--limit 10] [--grep 关键词]
    uv run python scripts/memory_digest.py <agent数据目录或memory目录>
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def resolve_sources(text: str):
    path = Path(text).resolve()
    if path.is_file():
        return [path]
    found = []
    for base in (path / "memory", path):
        for name in ("JOURNAL.jsonl", "FACT.md"):
            candidate = base / name
            if candidate.is_file() and candidate not in found:
                found.append(candidate)
    return found


def entry_text(entry) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for key in ("text", "content", "message", "summary"):
            value = entry.get(key)
            if isinstance(value, str):
                return value
        return json.dumps(entry, ensure_ascii=False)
    return str(entry)


def entry_tags(entry) -> list[str]:
    if not isinstance(entry, dict):
        return []
    tags = entry.get("tags", [])
    if isinstance(tags, str):
        tags = [item.strip(" '\"[]") for item in tags.split(",")]
    return [str(tag) for tag in tags if str(tag).strip()]


def entry_date(entry) -> str:
    if isinstance(entry, dict):
        for key in ("ts", "timestamp", "time", "date", "createdAt"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                return value[:10]
    return "????-??-??"


def digest_journal(path: Path, limit: int, grep: str) -> None:
    entries = []
    bad_lines = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            bad_lines += 1

    filtered = entries
    if grep:
        needle = grep.lower()
        filtered = [entry for entry in entries if needle in entry_text(entry).lower()]

    dates = sorted(date for date in (entry_date(entry) for entry in filtered) if not date.startswith("????"))
    tags = Counter(tag for entry in filtered for tag in entry_tags(entry))
    size_kb = path.stat().st_size / 1024
    print(f"== JOURNAL: {path}")
    print(
        f"条目 {len(entries)}（匹配 {len(filtered)}）· "
        f"{dates[0] if dates else '?'} → {dates[-1] if dates else '?'} · {size_kb:.1f} KB"
        + (f" · 坏行 {bad_lines}" if bad_lines else "")
    )
    if tags:
        top = "，".join(f"{tag}×{count}" for tag, count in tags.most_common(8))
        print(f"标签：{top}")
    for entry in filtered[-limit:]:
        text = " ".join(entry_text(entry).split())
        tag_text = "/".join(entry_tags(entry))
        prefix = f"[{entry_date(entry)}]" + (f"[{tag_text}]" if tag_text else "")
        print(f"{prefix} {text[:160]}")
    if len(filtered) > limit:
        print(f"提示：只打印最近 {limit} 条；用 --grep 过滤，不要整份读。")


def digest_markdown(path: Path, label: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    headings = [line.strip() for line in lines if line.lstrip().startswith("#")]
    size_kb = path.stat().st_size / 1024
    print(f"== {label}: {path}")
    print(f"行数 {len(lines)} · {size_kb:.1f} KB · 标题 {len(headings)} 个")
    for heading in headings[:30]:
        print(heading)
    if len(headings) > 30:
        print("提示：只打印前 30 个标题；用 rg 搜关键词定位。")


def main() -> int:
    parser = argparse.ArgumentParser(description="压缩工作记忆摘要")
    parser.add_argument("path", nargs="?", default=".", help="agent 数据目录 / memory 目录 / 文件")
    parser.add_argument("--limit", type=int, default=10, help="JOURNAL 最近条目数")
    parser.add_argument("--grep", default="", help="按关键词过滤 JOURNAL 文本")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit 必须 ≥1")

    sources = resolve_sources(args.path)
    if not sources:
        print(f"没有找到 JOURNAL.jsonl / FACT.md：{Path(args.path).resolve()}")
        return 1

    handled = False
    for source in sources:
        name = source.name.lower()
        if name == "journal.jsonl" or source.suffix.lower() == ".jsonl":
            digest_journal(source, args.limit, args.grep)
            handled = True
        elif source.suffix.lower() == ".md":
            label = "FACT" if name == "fact.md" else "MD"
            digest_markdown(source, label)
            handled = True
        else:
            print(f"不支持的文件：{source}（只处理 JOURNAL.jsonl / *.jsonl / *.md）")
    return 0 if handled else 1


if __name__ == "__main__":
    raise SystemExit(main())
