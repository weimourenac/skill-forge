---
name: skill-forge
description: 创建、修改、精简或从现有工作流/工作记忆中提炼 Agent Skill（技能）：把可复用流程、清单或领域知识封装成 SKILL.md 和按需加载的资源，并控制上下文开销。只要用户说「做一个 skill / 技能」「把这件事封装成 skill」「把刚才这套流程 / 项目记忆整理成 skill」「写个 SKILL.md」「正文太长，帮我精简这个 skill」「skill 怎么触发 / 怎么装 / 装到哪个目录」，或者想把反复粘贴的步骤沉淀成可复用能力，就使用本技能；用户没提 skill 二字、但明显在设计可复用工作流时也应考虑。也用于检查现有 skill 的结构、description、token 占用，以及 Cherry Studio 的安装位置。
license: MIT
---

# Skill Forge

Skill = 一个文件夹 + `SKILL.md`，用「按需加载」换低常驻成本。

## 1. 是什么

- 目录：`<name>/SKILL.md`，可选 `scripts/`、`references/`、`assets/`；示例见 `examples/meeting-notes/`。
- frontmatter 必填 `name` + `description`；正文触发时整份加载，资源按需读，脚本可直接执行。
- `description` 是唯一触发开关：写「做什么 + 何时用 + 关键词」，宁宽勿窄；≤1024 字符。
- `name` = 目录名：小写字母/数字/连字符，1–64；细节见 `references/spec.md`。

## 2. 查资料

1. `references/spec.md` — 字段/约束/目录。
2. `references/patterns.md` — 写法/token 预算/反模式。
3. `references/from-work.md` — 从工作流/记忆提炼。
4. 官方：https://agentskills.io/specification · https://docs.claude.com/en/docs/claude-code/skills
5. 完整评测：`%CHERRY_STUDIO_SKILLS_DIR%\skill-creator\SKILL.md`（35 KB，只做 A/B 或触发率优化时读）。

## 3. 工作流

1. 值得做才做：同一套步骤重复 ≥3 次，或有固定输出/领域知识。
2. 定意图：做什么、何时触发、输出什么；能从对话推断就别问。
3. 起名建目录：kebab-case、与目录同名；产品放 `D:\Skill\products\<name>`；骨架用 `assets/SKILL.template.md`。
4. 先写 description：做什么 + 触发场景 + 关键词，≤1024；只看它能否判断该不该用。
5. 再写正文：只放每次都要用的流程/规则/输出格式；长资料→`references/`，确定性操作→`scripts/`，模板→`assets/`。
6. 过门禁（第 5 节）；安装用 `uv run python scripts/install_skill.py <目录>`。

## 4. 从工作流/记忆提炼

1. `scripts/scan_work_sources.py <目录>` 列来源；`scripts/memory_digest.py <目录>` 看摘要；别整目录读入。
2. 找重复 ≥3 次的操作；一次性任务不做 skill。
3. 事实（路径/账号/项目状态）留记忆；流程（步骤/判断/输出）进 skill。
4. 用用户原话写 description；填 `assets/WORKFLOW-EXTRACT.template.md`，按 `references/from-work.md` 映射资源。
5. 回放 3 个历史任务，≥2 个复现才算可用；脱敏密钥/内网地址/人名。

## 5. 工程门禁（默认 0 模型调用）

```bash
uv run python scripts/validate_skill.py <目录>
uv run python scripts/skill_doctor.py <目录>
uv run python scripts/trigger_lint.py <目录> --queries tests/trigger-queries.json --strict
uv run python scripts/selftest.py
```

validate/doctor 0 error、trigger --strict 通过、selftest 全绿才安装；夹具在 `tests/fixtures/`。`trigger_lint` 是词面冒烟，不是模型实测；模型 A/B 默认不做，要做 ≤4 条 prompt × 1 次，见 `references/eval.md`。

## 6. 省 token

- 正文目标 ≤200 行 / ≤3000 字；超了拆 `references/`。
- 一条规则只写一遍；正文不复述 frontmatter/官方文档。
- `references/` 默认不加载；正文写清「何时读哪个文件」。
- 能脚本算的，不让模型读文件手算。
- 修改先删后加：删掉不改变行为的句子、重复规则、没人读的资源。
- 常驻成本只有 description：关键词塞进去，步骤留正文。

## 7. 常见坑

- name 与目录不一致 → 不注册。
- description 没有触发词 → 不触发。
- 正文复述规范 → 每次触发白付 token。
- `references/` 有文件但正文没提 → 永远不会被读。
- 把项目事实当流程 → 换项目就错。
- 为一次性任务做 skill → 维护成本大于收益。
