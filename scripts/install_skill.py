#!/usr/bin/env python3
"""校验并安装 Agent Skill 到 Cherry Studio 技能库。

用法:
    python scripts/install_skill.py <skill目录> [--dest DIR] [--force]
    uv run python scripts/install_skill.py <skill目录>
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from validate_skill import validate


def default_dest() -> Path:
    env = os.environ.get("CHERRY_STUDIO_SKILLS_DIR")
    if env:
        return Path(env)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "CherryStudio" / "Data" / "Skills"
    return Path.home() / ".cherrystudio" / "skills"


def main() -> int:
    parser = argparse.ArgumentParser(description="校验并安装 Agent Skill")
    parser.add_argument("skill_dir")
    parser.add_argument("--dest", help="目标技能库；默认取 CHERRY_STUDIO_SKILLS_DIR")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的同名技能")
    args = parser.parse_args()

    source = Path(args.skill_dir).resolve()
    errors, warnings, _ = validate(source)
    for warning in warnings:
        print(f"[warn] {warning}")
    for error in errors:
        print(f"[error] {error}")
    if errors:
        print(f"校验失败：{len(errors)} error，未安装")
        return 1

    dest_root = Path(args.dest).resolve() if args.dest else default_dest().resolve()
    if dest_root.exists() and not dest_root.is_dir():
        print(f"目标不是目录：{dest_root}")
        return 1
    destination_path = dest_root / source.name
    if destination_path.is_symlink():
        print(f"目标是符号链接，拒绝覆盖：{destination_path}")
        return 1
    destination = destination_path.resolve()
    if destination == source or source in destination.parents or destination in source.parents:
        print(f"目标与源目录重叠，拒绝安装：{destination}")
        return 1
    dest_root.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        if not destination.is_dir():
            print(f"目标已存在且不是目录：{destination}")
            return 1
        if not args.force:
            print(f"目标已存在：{destination}")
            print("加 --force 覆盖，或先手动删除")
            return 1
        shutil.rmtree(destination)

    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".DS_Store"),
    )
    files = [p for p in destination.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    print(f"已安装：{destination}")
    print(f"文件 {len(files)} 个 / {size / 1024:.1f} KB")
    print("Cherry Studio 会自动同步；运行时镜像不需要手动修改。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
