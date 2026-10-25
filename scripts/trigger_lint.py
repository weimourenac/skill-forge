#!/usr/bin/env python3
"""词面触发冒烟：用真实说法检查 description 是否覆盖关键词。

这不是模型实测，只是零成本的正则 / 词面近似；用于发现明显漏词。
用法:
    python scripts/trigger_lint.py <skill目录> --queries <queries.json> [--strict]
    uv run python scripts/trigger_lint.py <skill目录> --queries tests/trigger-queries.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from validate_skill import parse_frontmatter

CJK_RUN = re.compile(r"[一-鿿]+")
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,}")
STOPWORDS = set(
    """
    用户 使用 技能 时候 可以 需要 以及 或者 如果 这个 一个 进行 相关 用于 帮助
    什么 怎么 请把 的了 在和 与也 都就 你我 他她 它们 这那 有没 要会 能到
    对从 为上 下中 里时 后前 并而 但还 很更 最等 及其 之于 以被 让给 向跟
    同又 再只 才已 一些 一种 一次 一样 这里 那里 我们 你们 他们 她们 它们
    the and for with this that when use user users skill skills an of to in on
    is are be or as at by it its from you your if then than so such can will
    would should may might do does did not no but also more most into about
    after before while during including etc
    """.split()
)


def tokens(text: str) -> set[str]:
    text = text.lower()
    result = set()
    for run in CJK_RUN.findall(text):
        if len(run) == 1:
            result.add(run)
            continue
        for index in range(len(run) - 1):
            bigram = run[index : index + 2]
            if bigram not in STOPWORDS:
                result.add(bigram)
    for word in LATIN_WORD.findall(text):
        if word not in STOPWORDS:
            result.add(word)
    return result


def load_queries(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("queries")
        if not isinstance(data, list):
            raise ValueError("JSON 必须是数组，或包含 queries 数组")
        queries = []
        for item in data:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("query"), str)
                or not item["query"].strip()
            ):
                raise ValueError("每条 query 必须是 {query: 非空字符串, should_trigger: bool}")
            should_trigger = item.get("should_trigger", True)
            if not isinstance(should_trigger, bool):
                raise ValueError("should_trigger 必须是 true / false")
            queries.append(
                {
                    "query": item["query"],
                    "should_trigger": should_trigger,
                }
            )
        return queries
    queries = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        should_trigger = True
        if line[0] in "+-":
            should_trigger = line[0] == "+"
            line = line[1:].strip()
        if line:
            queries.append({"query": line, "should_trigger": should_trigger})
    return queries


def evaluate(skill_dir: Path, queries, min_coverage: float = 0.2, max_negative: float = 0.5):
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    frontmatter, _, error = parse_frontmatter(text)
    if error:
        raise ValueError(error)
    description = frontmatter.get("description", "")
    description_tokens = tokens(description)
    rows = []
    for item in queries:
        query_tokens = tokens(item["query"])
        if not query_tokens:
            coverage = 0.0
            missing = set()
        else:
            missing = query_tokens - description_tokens
            coverage = len(query_tokens & description_tokens) / len(query_tokens)
        if item["should_trigger"]:
            verdict = "PASS" if coverage >= min_coverage else "FAIL"
        else:
            verdict = "PASS" if coverage < max_negative else "WARN"
        rows.append(
            {
                "query": item["query"],
                "should_trigger": item["should_trigger"],
                "coverage": coverage,
                "missing": sorted(missing),
                "verdict": verdict,
            }
        )
    positive = [row for row in rows if row["should_trigger"]]
    negative = [row for row in rows if not row["should_trigger"]]
    positive_pass = sum(1 for row in positive if row["verdict"] == "PASS")
    negative_pass = sum(1 for row in negative if row["verdict"] == "PASS")
    has_both = bool(positive) and bool(negative)
    return {
        "description_tokens": len(description_tokens),
        "rows": rows,
        "positive_pass": positive_pass,
        "positive_total": len(positive),
        "negative_pass": negative_pass,
        "negative_total": len(negative),
        "has_both": has_both,
        "strict_ok": (
            has_both
            and (positive_pass / len(positive)) >= 0.8
            and (negative_pass / len(negative)) >= 0.8
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="词面触发冒烟")
    parser.add_argument("skill_dir")
    parser.add_argument("--queries", required=True, help="JSON 或每行一条（+/- 前缀）")
    parser.add_argument("--min-coverage", type=float, default=0.2)
    parser.add_argument("--max-negative", type=float, default=0.5)
    parser.add_argument("--strict", action="store_true", help="命中率不达标时退出 1")
    args = parser.parse_args()
    if not 0 <= args.min_coverage <= 1 or not 0 <= args.max_negative <= 1:
        parser.error("阈值必须在 0–1 之间")

    skill_dir = Path(args.skill_dir).resolve()
    try:
        queries = load_queries(Path(args.queries))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"读取 queries 失败：{exc}")
        return 2
    try:
        result = evaluate(skill_dir, queries, args.min_coverage, args.max_negative)
    except (OSError, ValueError) as exc:
        print(f"读取 skill 失败：{exc}")
        return 2

    print(f"触发冒烟：{skill_dir.name}（词面近似，不是模型实测）")
    print(f"description 词元：{result['description_tokens']}")
    for row in result["rows"]:
        prefix = "+" if row["should_trigger"] else "-"
        line = f"[{row['verdict']}] {prefix} {row['query']}  (覆盖 {row['coverage']:.0%})"
        if row["verdict"] in {"FAIL", "WARN"} and row["missing"]:
            line += "  缺: " + "、".join(row["missing"][:6])
        print(line)

    positive_rate = result["positive_pass"] / result["positive_total"] if result["positive_total"] else 1.0
    negative_rate = result["negative_pass"] / result["negative_total"] if result["negative_total"] else 1.0
    print(
        f"正例命中 {result['positive_pass']}/{result['positive_total']}（{positive_rate:.0%}）· "
        f"负例通过 {result['negative_pass']}/{result['negative_total']}（{negative_rate:.0%}）"
    )

    if args.strict and not result["has_both"]:
        print("结果：不达标（至少需要 1 条正例和 1 条负例）")
        return 1
    if args.strict and not result["strict_ok"]:
        print("结果：不达标（阈值：正例 ≥80% 且负例 ≥80%）")
        return 1
    print("结果：通过" if result["strict_ok"] else "结果：有风险（加 --strict 可将其作为门禁）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
