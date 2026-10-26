（用deepseek做的，这个也是用deepseek写的）

# skill-forge

> 一个专门造 skill 的 skill。

`skill-forge` 是一个 Agent Skill：它教 AI 如何创建、修改、精简 Agent Skill，也教它把已有的工作流和工作记忆提炼成可复用的 skill。它不是提示词模板，而是一份带流程、参考资料、模板和工程门禁的说明书。

## 为什么

- 同一个流程，重复教十遍
- 提示词越写越长，结果还是不稳定
- 每个 skill 的结构、触发词、资源引用都不一样

skill-forge 把这些固定下来：

- `description` 负责触发
- 正文只放每次都要用的流程
- 长资料放 `references/`，按需读取
- 确定性操作放 `scripts/`，直接执行
- 用零依赖脚本做结构、密钥、触发词、回归检查

## 安装

### Cherry Studio（推荐）

1. 设置 → 技能 → GitHub
2. 粘贴：

   ```text
   https://github.com/weimourenac/skill-forge/blob/main/SKILL.md
   ```

3. 安装后打开全局开关
4. 工作 → Agent 菜单 → 编辑 → 技能 → 启用

也可以下载 ZIP 后：设置 → 技能 → 从本地 ZIP 安装。

## 用法

直接说：

- 「把这套流程整理成 skill」
- 「体检并精简这个 skill」
- 「从我的工作记忆里提炼一个 skill」
- 「SKILL.md 怎么写才能被触发」
- 「这个 skill 为什么没有触发」

它会先读 `SKILL.md`，再按需读 `references/`，必要时运行 `scripts/`。

## 三种能力

| 能力 | 说明 |
|---|---|
| CREATE | 从零创建：定意图、起名、写 description、写正文、加资源 |
| REFINE | 精简旧 skill：先删后加，去掉重复规则、孤儿资源、过长正文 |
| EXTRACT | 从工作流/记忆提炼：列来源、找重复、分离事实与流程、回放验收 |

## 工程门禁

所有检查默认不调用模型：

```bash
uv run python scripts/validate_skill.py .
uv run python scripts/skill_doctor.py .
uv run python scripts/trigger_lint.py . --queries tests/trigger-queries.json --strict
uv run python scripts/selftest.py
```

当前版本：

- `validate_skill`：0 error / 0 warning
- `skill_doctor`：0 error / 0 warning
- `trigger_lint`：正例 5/5，负例 4/5，`--strict` 通过
- `selftest`：17/17

## 包含什么

```text
skill-forge/
├─ SKILL.md
├─ references/
│  ├─ spec.md
│  ├─ patterns.md
│  ├─ from-work.md
│  └─ eval.md
├─ assets/
│  ├─ SKILL.template.md
│  └─ WORKFLOW-EXTRACT.template.md
├─ examples/meeting-notes/
├─ scripts/
│  ├─ validate_skill.py
│  ├─ skill_doctor.py
│  ├─ trigger_lint.py
│  ├─ scan_work_sources.py
│  ├─ memory_digest.py
│  ├─ install_skill.py
│  └─ selftest.py
└─ tests/
   ├─ fixtures/
   └─ trigger-queries.json
```

## 设计原则

- **按需加载**：常驻的只有 `description`；正文触发时才读；资源按需读。
- **正文要短**：目标 ≤200 行 / ≤3000 字；当前 64 行 / 约 2,100 字。
- **脚本优先**：能确定性执行的事，不靠模型手算。
- **先删后加**：精简时先删不改变行为的句子、重复规则、没人读的资源。
- **明文**：Markdown + Python，无加密、无编译产物、无混淆。

## 实测

2 条任务 × 2 组 × 1 次：

| 指标 | with skill | baseline |
|---|---:|---:|
| 无 warning 输出 | 2/2 | 1/2 |
| 正文 tokens | 1,167 | 1,515 |
| 产物字节 | 18,462 | 22,644 |
| 子代理 tokens | 140,522 | 127,472 |

- 正文 tokens -23.0%
- 产物字节 -18.5%
- 子代理 tokens +10.2%

单次运行，仅作方向参考，不是统计结论。

## 环境

- Cherry Studio（技能安装与管理）
- Windows + PowerShell（当前脚本按本机路径编写）
- `uv run python` 或 `python`（脚本零第三方依赖）
- 字体、图片、音频不随 skill 分发

## License

MIT，见 [LICENSE](LICENSE)。
