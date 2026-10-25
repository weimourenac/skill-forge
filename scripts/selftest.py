#!/usr/bin/env python3
"""skill-forge 自测：校验器 / 体检器 / 安装器的正例与负例回归。

用法:
    uv run python scripts/selftest.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURES = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(HERE))
from skill_doctor import diagnose
from trigger_lint import evaluate
from validate_skill import parse_frontmatter, validate


def check(name: str, condition: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {name}" + (f" — {detail}" if detail and not condition else ""))
    return condition


def main() -> int:
    results = []

    errors, warnings, _ = validate(FIXTURES / "valid-skill")
    results.append(check("validator: 合法技能 0 error", not errors, str(errors)))
    results.append(check("validator: 合法技能 0 warning", not warnings, str(warnings)))

    errors, _, _ = validate(FIXTURES / "bad-name")
    results.append(check("validator: 坏 name 至少 2 error", len(errors) >= 2, str(errors)))

    errors, _, _ = validate(FIXTURES / "missing-resource")
    results.append(
        check("validator: 缺资源报 error", any("不存在" in error for error in errors), str(errors))
    )

    errors, warnings, _ = validate(FIXTURES / "orphan-ref")
    results.append(
        check(
            "validator: 孤儿资源给 warning",
            not errors and any("未在正文" in warning for warning in warnings),
            str(warnings),
        )
    )

    errors, warnings, _ = validate(FIXTURES / "arrow-desc-skill")
    results.append(
        check(
            "validator: 箭头 -> 只给 warning",
            not errors and any("尖括号" in warning for warning in warnings),
            f"{errors} / {warnings}",
        )
    )

    errors, _, _ = validate(FIXTURES / "no-frontmatter")
    results.append(check("validator: 缺 frontmatter 报 error", bool(errors), str(errors)))

    errors, _, _ = validate(FIXTURES / "traverse-skill")
    results.append(
        check("validator: 越界引用报 error", any("目录之外" in error for error in errors), str(errors))
    )

    frontmatter, body, parse_error = parse_frontmatter(
        "---\nname: x\ndescription: >\n  第一行\n  ---\n  第二行\n---\n正文"
    )
    parser_ok = (
        parse_error is None
        and frontmatter is not None
        and "description" in frontmatter
        and "第二行" in frontmatter["description"]
        and "第二行" not in body
    )
    results.append(
        check(
            "parser: 缩进 --- 不结束 frontmatter",
            parser_ok,
            f"{parse_error} / {frontmatter} / {body}",
        )
    )

    trigger_result = evaluate(
        FIXTURES / "valid-skill",
        [{"query": "测试 valid skill 的正例", "should_trigger": True}],
    )
    results.append(
        check(
            "trigger_lint: 缺负例不算通过",
            not trigger_result["has_both"] and not trigger_result["strict_ok"],
            str(trigger_result),
        )
    )

    errors, _, _ = diagnose(FIXTURES / "secret-skill")
    results.append(
        check("doctor: 假密钥报 error", any("密钥" in error or "key" in error.lower() for error in errors), str(errors))
    )

    errors, _, _ = diagnose(FIXTURES / "script-secret-skill")
    results.append(
        check("doctor: 脚本内假密钥报 error", any("密钥" in error or "key" in error.lower() for error in errors), str(errors))
    )

    errors, _, _ = diagnose(FIXTURES / "valid-skill")
    results.append(check("doctor: 合法技能 0 error", not errors, str(errors)))

    errors, warnings, _ = diagnose(FIXTURES / "usage-marker-skill")
    results.append(
        check(
            "doctor: 「用户要求…时使用」算触发标记",
            not errors and not any("触发标记" in warning for warning in warnings),
            str(warnings),
        )
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.run(
            [
                sys.executable,
                str(HERE / "install_skill.py"),
                str(FIXTURES / "valid-skill"),
                "--dest",
                temp_dir,
                "--force",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        installed = Path(temp_dir) / "valid-skill" / "SKILL.md"
        results.append(check("installer: 退出 0", process.returncode == 0, process.stdout + process.stderr))
        results.append(check("installer: 文件已复制", installed.exists(), str(installed)))

    with tempfile.TemporaryDirectory() as temp_dir:
        overlap_source = Path(temp_dir) / "valid-skill"
        shutil.copytree(FIXTURES / "valid-skill", overlap_source)
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.run(
            [
                sys.executable,
                str(HERE / "install_skill.py"),
                str(overlap_source),
                "--dest",
                temp_dir,
                "--force",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        results.append(
            check(
                "installer: 源/目标重叠被拒",
                process.returncode != 0 and (overlap_source / "SKILL.md").exists(),
                process.stdout + process.stderr,
            )
        )

    passed = sum(results)
    print(f"\n结果：{passed}/{len(results)} 通过")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
