# PlayForge — 1.0 Beta 1 Integrated Reliability / 可靠性整合

Release identifier: `1.0.0-beta.1`. The 0.5 development snapshot was renamed without functional changes; the validation below was recorded on that baseline. Beta status does not guarantee arbitrary unseen-game success.

版本标识：`1.0.0-beta.1`。由 0.5 开发快照更名而来，功能不变；下方验证记录来自该基线。测试版定位不保证任意未知游戏成功。

This document preserves the integration baseline. Beta 2 changes and paid screening are in [CAPABILITY.md](CAPABILITY.md); the 143-test record below is historical, not the latest suite count.

本文保留整合基线；Beta 2 改进与付费筛查见 [CAPABILITY.md](CAPABILITY.md)。下方 143 项为历史记录，不是最新测试数量。

Latest Beta 3 planning changes / 最新 Beta 3 规划改进：[PLANNING.md](PLANNING.md)。

This version extends one controller loop rather than stacking independent agent frameworks. All game code is still generated from the supplied specification. No external coding-agent runtime, game engine, game template or solver is embedded.

本版本扩展同一条控制循环，不叠加多套 Agent 框架。游戏代码仍由输入需求生成，不嵌入外部 Coding Agent 运行器、游戏引擎、游戏模板或通关器。

## One coherent flow / 统一流程

~~~text
Spec → Frozen plan → Full first version
                       ↓
Version-bound edit → Artifact checks → Browser evidence → Completion gate
       ↑                                      ↓
       └── Best stable base ← Failure routing / optional diagnosis
                                              ↓
                              Optional recovery observations
~~~

原始需求与固定计划始终保留。修复基于已观察到的较好版本，编辑结果写入新候选目录；结构检查、浏览器观察、完成门禁和失败分流共用同一份证据与预算。

The original specification and frozen plans remain intact. Edits create new candidate directories from an observed repair base; artifact checks, browser observations, completion gates and routing share the same evidence and budgets.

## Safeguards and defaults / 默认行为与保护

| Area / 模块 | Default / 默认 | Boundary / 边界 |
|---|---|---|
| File repair / 文件修复 | Auto, with full responses accepted / 自动，仍接受完整输出 | Hash must match the base; no deletion, rename, path escape or ambiguous merge / 基础哈希必须匹配，不支持删除、重命名、越界或模糊合并 |
| Artifact checks / 结构检查 | On / 开启 | Local HTML references only; not proof of JavaScript semantics or gameplay / 检查本地 HTML 资源引用，不证明 JS 语义或玩法 |
| Failure routing / 失败分流 | On, zero additional API / 开启，无额外 API | Observations are not proven root causes / 失败现象不是确定根因 |
| Model diagnosis / 模型诊断 | Off / 关闭 | At most one actual extra attempt per run, from existing budget / 每次运行最多增加一次实际尝试，占原预算 |
| Browser repetitions / 浏览器重复 | One / 一次 | Optional 2–3; all must pass within one shared timeout / 可选 2–3 次，必须全通过，共用超时预算 |
| Temporal sampling / 时间序列观察 | Only if planned / 按计划使用 | Read-only snapshots, at most 8 samples and 2000ms per action / 只读，每步最多 8 个样本、2000ms |
| Recovery store / 修复经验 | Off / 关闭 | Whitelisted principles, verified recovery observations, no code/test answers / 内置原则和经过验证的恢复观察，不保存代码或测试答案 |
| Node syntax / Node 语法 | Off / 关闭 | Trusted `node --check`, no generated host-code execution; only external JS / 固定语法命令，不执行生成的宿主代码，仅检查外部 JS |

`--repair-mode full` restores whole-project response mode. Invalid partial edits request a full response on the next remaining round; they do not touch the base. This fallback consumes an existing round/call, not a hidden retry allowance.

`--repair-mode full` 保留完整项目输出路径。无效局部编辑会在下一剩余轮次要求完整输出，不修改基础版本；回退占用原有轮次和调用次数，不提供隐藏额度。

Previously passed checks from a stable, complete-evidence base are protected when selecting a newer candidate. A candidate that regresses one is retained as evidence but not selected merely because another test passed. This is conservative: it can restrict exploration, and does not prove the older version is semantically correct.

选优时保护稳定且证据完整版本中已通过的检查；新候选丢失通过项时只保留证据，不因另一个测试通过就替换基础版本。这是保守策略，可能限制探索，也不能证明旧版语义正确。

## Failure handling / 失败处理

- Missing resources/runtime errors → local implementation repair. 缺资源或运行错误 → 局部修复实现。
- DOM/state mismatch → align actual live state, never fake observations. 画面／状态不同步 → 对齐真实状态，不伪造观察。
- Assertion/goal/interaction uncertainty → examine original rules and actual evidence before editing. 断言、目标或操作不确定 → 先核对原规则和证据。
- Infrastructure or incomplete evidence → stop unverified; rewriting gameplay cannot establish missing observations. 环境错误或证据不完整 → 停止并标记未验证，不用改玩法补造证据。

Optional `--diagnose` runs only for an ambiguous failure with another repair round available, at least two remaining API attempts and 15 seconds. Its output must cite actual failed test IDs and may not contain edits. `test_issue` or `tool_limit` stops with `diagnosis_unverified`, never a pass. Invalid diagnosis structure is ignored; API failures preserve the existing candidate. Diagnosis is fallible and may stop too conservatively, so it remains optional.

可选诊断仅在模糊失败、有剩余修复轮次、至少两次调用及 15 秒时运行。输出必须引用真实失败测试，不允许包含修改。认为测试或工具有问题时停止并标记未验证，不能算成功；格式无效时忽略诊断，API 失败时保留已有结果。诊断可能误判并过早停止，因此不默认启用。

## Evidence and replay / 证据与回放

Each browser evidence directory has `replay.json`: fixed plan content, source hashes, environment/browser versions, viewport, actual inputs/results and before/after screenshots. Sampling adds bounded state sequences and `<name>_start` / `<name>_end` captures for explicit assertions. No hidden game-state setters are introduced.

每个浏览器证据目录保存回放清单：固定计划、源码哈希、环境与浏览器版本、窗口尺寸、实际输入和结果、前后截图。时间采样增加有界状态序列及首尾 capture，供明确断言使用，不引入隐藏状态修改接口。

`replay` uses the original run's active plan; `recheck` accepts a separately selected plan. Neither calls a model nor changes original scores. Replay is repeatable input execution, not a guarantee of identical scheduling. Repetitions use separate contexts; any failure prevents an all-pass result. Benchmark independent checks remain held out, including from diagnosis and lesson storage.

`replay` 使用原运行活动计划，`recheck` 接受另选的计划；两者不调用模型、不改原成绩。回放重现操作，不保证调度完全一致。重复使用独立上下文，任一次失败都会阻止全通过。benchmark 独立检查仍不提供给生成、诊断或经验记录。

## Bounded memory and reproducibility / 有界经验与复现

`--lessons runs/lessons.json` opts into a small local JSON store. Records require a failed check to pass after changed source under the same frozen plan and a clean completion gate. Only predefined general principles are retrieved for matching failure categories. These are recovery observations, not proof that a proposed diagnosis was the root cause. Arbitrary prose in the editable store cannot become model instructions. Corrupt or concurrently changed stores are preserved and ignored rather than overwritten. Benchmarks do not enable this cross-run store.

经验必须由同一固定计划下的失败检查在改码后通过、且完成门禁通过来支撑。只检索匹配失败类别的内置通用原则；恢复记录不证明某个诊断就是根因。文件里的任意文字不能进入模型指令。损坏或被并发修改的文件会保留，不覆盖；benchmark 不启用跨运行经验。

Full evidence stays on disk while repair prompts receive compact failures and recent actions; temporal sample arrays are not repeatedly copied into model context. Dependency versions are pinned in `requirements.txt`; runtime metadata includes Python, Playwright, browser and agent-source fingerprints. These support comparisons, not a claim that every OS/browser combination has been tested.

完整证据留在磁盘，修复提示仅接收紧凑失败与近期动作，不反复发送时间采样大数组。依赖固定版本，运行记录环境及 Agent 源码指纹；这支持受控比较，不代表已测试所有系统组合。

`export-run` copies current agent code and exact game/traces to a new folder, excludes local `.env` and caches, rejects linked artifacts, and records original/current agent versions separately. An existing PDF can be attached; without it the package lacks the report. Exporting does not turn an old or assisted game into a valid live autonomous submission. Final course command/layout, model and engine scope still require confirmation.

导出复制当前 Agent 与原样游戏、执行记录到新目录，排除 `.env` 和缓存，拒绝链接文件，区分原运行与当前 Agent 版本。可附带已有 PDF，未提供就仍缺报告。导出不把历史或协助修复的游戏变成合格自主现场提交；课程启动方式、模型和技术范围仍需确认。

## Validation boundaries / 验证边界

2026-10-14: final full regression **143/143 passed**, including **24 real-browser tests**, in 73.488 seconds on Windows / Python 3.11.9 / Edge. The previous 109 tests remain passing, with 34 added regressions. Tests use mock model responses; simulated API-attempt counters are not real charges.

2026-10-14：最终完整回归 **143/143 通过**，含 **24 项真实浏览器测试**，Windows / Python 3.11.9 / Edge 环境耗时 73.488 秒。原有 109 项保持通过，新增 34 项。模型响应模拟，模拟调用计数不是实际扣费。

Stage tests exercise edits, routing, repetition, immutable delivery and evidence-backed lessons before the combined regression. Model responses are simulated; real browser tests verify actual interaction. The composed test enables partial repair, repeated checks, optional diagnosis and lesson recording together. A separate synthetic comparison keeps full and auto repair outcomes aligned. These are compatibility checks, not real-model improvement measurements.

按阶段验证编辑、分流、重复、原样导出及有证据的经验，再做整合回归。模型响应模拟，浏览器交互真实；组合测试同时启用局部修复、重复检查、诊断和经验记录，另用合成案例对照完整／局部修复结果。这证明兼容性，不证明真实模型效果提升。

No paid model API was called during implementation. Unseen-game success, model-specific output reliability and cost improvements require later controlled paid trials. No performance percentage is inferred from framework tests. Multi-agent orchestration, game template libraries, trained specialist models, mandatory visual judges and a new OS sandbox are intentionally not introduced.

本次未调用付费模型。未知玩法成功率、模型输出可靠性及成本改善仍需后续受控实测，不能从框架测试推算。暂不引入多 Agent、游戏模板库、专用模型训练、强制视觉评审或新的 OS 沙箱。
