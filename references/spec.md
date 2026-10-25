# Agent Skill 规范速查

> 快照：2026-10。冲突时以官方规范为准：https://agentskills.io/specification

## 目录结构

```
skill-name/
├── SKILL.md          # 必需
├── scripts/          # 可选：可执行代码
├── references/       # 可选：按需读取的长文档
├── assets/           # 可选：模板、图片等静态素材
└── examples/         # 可选：示例（约定，不是规范）
```

目录名 = `name`，必须一致。

## Frontmatter

| 字段 | 必需 | 约束 |
|---|---|---|
| `name` | 是 | 1–64；`a-z` `0-9` `-`；不能首尾 `-`、不能 `--`；必须等于目录名 |
| `description` | 是 | 1–1024；写「做什么 + 何时用」；含关键词；官方规范不限尖括号，Anthropic 校验器会拒绝，本工作区只 warning |
| `license` | 否 | 许可证名称或文件引用 |
| `compatibility` | 否 | 1–500；环境要求（产品、依赖、网络） |
| `metadata` | 否 | 字符串键值映射，客户端自定义 |
| `allowed-tools` | 否 | 空格分隔的预授权工具；实验性，各端支持不一 |

```yaml
---
name: pdf-extractor
description: 从 PDF 提取文本和表格。当用户给出 PDF 并要求提取、转换或分析内容时使用。
---
```

## 加载模型（为什么省 token）

1. **metadata**：`name + description` 常驻，约 100 词。
2. **body**：触发时整份 `SKILL.md` 进入上下文。
3. **resources**：只在正文指引下按需读取；`scripts/` 可直接执行，不必读入。

推论：正文越短越好；长内容拆到 `references/`；description 是唯一值得反复打磨的常驻文本。

## 正文

- 没有格式限制；推荐：步骤、输入输出示例、边界情况。
- 官方建议 <500 行；本工作区目标 ≤200 行。
- 用祈使句；解释「为什么」，少用全大写 MUST。
- 引用资源时写清路径和读取时机。

## 资源选择

- 确定性、可重复 → `scripts/`（自包含、错误信息清楚）
- 长知识、查表、领域资料 → `references/`（单文件聚焦）
- 输出模板、字体、图标 → `assets/`
- 完整示例 → `examples/`

## Cherry Studio 安装位置

```
技能库（源）：%CHERRY_STUDIO_SKILLS_DIR%
  默认 C:\Users\CPY\AppData\Roaming\CherryStudio\Data\Skills
运行时镜像：...\Data\Agents\.claude\skills   # 自动同步，不手改
产品源（本机工作区）：D:\Skill\products\<name>
```

新建 = 在技能库放一个含 `SKILL.md` 的目录；Cherry 自动注册，不需要 package / install 脚本（`skill-creator` 里的打包步骤在本环境不适用）。

## 校验清单

- [ ] 目录名 == `name`
- [ ] `description` 含触发词，≤1024
- [ ] 正文没有复述规范
- [ ] 每个 `references/` 文件在正文中被点名
- [ ] 脚本可直接运行，且不依赖未声明环境
- [ ] 负例能让校验器失败

## 官方资料

- 规范：https://agentskills.io/specification
- Claude Code：https://docs.claude.com/en/docs/claude-code/skills
- 示例仓库：https://github.com/anthropics/skills
- 设计文章：https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
