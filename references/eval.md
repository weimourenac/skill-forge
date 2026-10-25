# 评测阶梯与资源预算

从便宜到贵，够用就停。默认只跑前两级，**不调用模型**。

## 0. 预算

| 级别 | 模型调用 | 耗时 | 何时用 |
|---|---|---|---|
| 静态门禁 | 0 | <1 秒 | 每次改完 |
| 词面触发冒烟 | 0 | <1 秒 | 每次改 description |
| 行为 A/B | ≤4 条 prompt × 1 次 | 数分钟 | 要证明输出更好 |
| 完整 harness | 多子代理 | 十几分钟 | 用户明确要求 |

## 1. 静态门禁（0 模型调用）

```bash
uv run python scripts/validate_skill.py <skill目录>
uv run python scripts/skill_doctor.py <skill目录>
uv run python scripts/selftest.py
```

- `validate_skill`：结构、frontmatter、资源引用、正文体积。
- `skill_doctor`：重复长行、description 启发式、密钥 / 危险命令、Python 语法、token 粗估。
- `selftest`：用 fixtures 跑正例与负例，防止判据本身失效。**只跑正例不算验证。**

## 2. 词面触发冒烟（0 模型调用）

```bash
uv run python scripts/trigger_lint.py <skill目录> \
  --queries tests/trigger-queries.json --strict
```

- 10 条真实说法：5 条应触发、5 条近似但不应触发。
- 阈值：正例命中 ≥80%，负例通过 ≥80%。
- 这是词面近似，**不是模型实测**；它只负责发现明显漏词，不证明真实触发率。
- 出现 FAIL 时，把缺的关键词补进 description，再跑一次。

## 3. 行为 A/B（默认不做）

只有在需要证明「新版本更好」时：

- 最多 4 条 prompt，每条只跑 1 次。
- 同一 prompt 跑「带 skill / 不带 skill」两份。
- 比较：验收标准是否满足、token、耗时、是否读了不该读的 references。
- 子代理通知里有 `total_tokens` / `duration_ms`，记下来。
- 超过 4 条先问用户；不要跑全矩阵。

## 4. 完整 harness（用户明确要求时）

读本机 `%CHERRY_STUDIO_SKILLS_DIR%\skill-creator\SKILL.md` 的评测章节，使用其 `scripts/` 与 `eval-viewer/`。

- 评测产物放 skill 目录**之外**（如 `D:\Skill\misc\<name>-workspace\`）。
- 它会跑很多子代理；token 成本通常高于收益，别为小改动跑。
- 触发率优化用它的 `run_loop.py`，不要自己重写。

## 5. 记录

把「改了什么 / 指标变化」写进提交信息或工作区笔记，下次不用重跑。
