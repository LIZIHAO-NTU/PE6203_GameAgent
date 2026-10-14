# Capability Screening / 小型能力评估

Date / 日期：2026-10-14. Current release / 当前版本：`1.0.0-beta.2`.

## 1. Decision / 结论

The agent generated working artifacts for six simple mechanic families and one new inventory/capacity variant. Every generated artifact passed the selected independent checks. However, self-authored planning remains unreliable: incorrect grid assumptions, cross-test state assumptions and overlong tests still occur. **Keep the offline 2D browser platform; improve planning semantics before promising broader or more complex game support.**

Agent 已为六类简单机制及一个库存／容量新变体生成可运行产物，全部通过所选独立检查。但自编测试计划仍会出现错误地图假设、跨测试状态依赖及步骤超限。**暂时保持离线二维网页平台，先改进规划语义，不承诺更复杂玩法或更多技术平台。**

These are feasibility samples, not proof of a 100% game-development success rate. One generation per case/version cannot establish stable generalization, and selected checks do not exhaust the specification.

这是可行性样本，不是“游戏开发成功率 100%”的证据。每个需求／版本只生成一次，不能证明稳定泛化；独立检查也未覆盖全部需求。

## 2. Protocol / 测试方法

- Baseline: Beta 1 at Git commit `854ee6b83598e6ec1431e7f81545722b303927ee`; six generated games, 24 API attempts.
- Optimized: Beta 2; the same six specifications, independent plans, per-case limits and feature settings; six generated games, 19 attempts.
- Transfer probe: one new finite-inventory/carrying-capacity variant, frozen before its first generation; four attempts.
- Configured model: `deepseek-flash` at the existing DeepSeek endpoint. Python 3.11.9, Playwright 1.63.0, Edge 155.0.4283.45 on Windows.
- Per case: at most five API attempts, three generation/repair rounds, 420 seconds; browser verification timeout 60 seconds. Transport/format retries count. Batch caps were 30, 24 and 5; actual use was **47 attempts**, within the task-wide 48-attempt cap.
- No manual game-code changes during generation. No game templates, solver, state setters, external agent runtime or engine were added. Independent plans were not supplied to generation or repair.

中文摘要：先固定 Beta 1 做六次基线，再以相同需求、独立计划、单次预算及功能设置复测 Beta 2，最后测试首次生成的新库存规则变体。单例最多 5 次调用、3 轮生成／修复及 420 秒；重试计入。三批实际 24＋19＋4＝**47 次 API 尝试**，未超过本次总上限 48。生成中没有人工修改游戏代码，也没有给生成模型独立测试答案。

The shared cap applies within each `benchmark` invocation, not automatically across separate commands. This task tracked the sum before starting each batch. There were no skipped cases or unknown-usage calls. Known usage: 244,811 input tokens and 127,727 output tokens. Pricing fields were not configured, so the actual billed amount is unknown; consult the provider bill.

`benchmark` 的共享调用上限只约束当前命令，不自动跨命令累计；本次在每批前核对总数。没有跳过样例或未知用量调用。已知输入 244,811 token、输出 127,727 token。未配置计价字段，无法给出可信费用金额，以服务商账单为准。

## 3. Paired results / 两轮逐类结果

“Self” means the agent's frozen plan passed, not complete human acceptance. “Independent” means all selected held-out checks passed; they remain partial coverage.

“自测”表示 Agent 的固定计划通过，不代表完整人工验收；“独立”表示所选隐藏检查通过，仍是部分覆盖。

| Case / 类型 | Baseline calls / 基线调用 | Beta 2 calls / 新版调用 | Self baseline → new / 自测变化 | Independent baseline → new / 独立变化 |
|---|---:|---:|---|---|
| Tic-tac-toe / 井字棋 | 5 | 2 | Fail → Pass / 失败→通过 | 5/5 → 5/5 |
| Sokoban / 推箱子 | 5 | 4 | Fail → Fail / 失败→失败 | 5/5 → 5/5 |
| Memory pairs / 记忆配对 | 2 | 2 | Pass → Pass / 通过→通过 | 5/5 → 5/5 |
| Brick breaker / 打砖块 | 5 | 3 | Fail → Pass / 失败→通过 | 5/5 → 5/5 |
| Resource shop / 购买升级 | 4 | 4 | Fail → Fail / 失败→失败 | 5/5 → 5/5 |
| Key maze / 钥匙门迷宫 | 3 | 4 | Pass → Fail / 通过→失败 | 5/5 → 5/5 |
| Total / 合计 | **24** | **19** | **2/6 → 3/6** | **30/30 → 30/30** |

The new inventory/capacity variant passed 6/6 independent checks but failed planning with more than 18 steps per test, remaining `partial_game_plan_failed`. It must not be counted as a successful autonomous self-verified run.

新库存／容量变体通过 6/6 独立检查，但计划每项测试超过 18 步，最终仍为 `partial_game_plan_failed`，不能算自主自验收完成。

The observed reduction from 24 to 19 calls is descriptive, not a causal efficiency claim: one stochastic sample per case, changed prompts and changed verification behavior cannot isolate effects. The maze self-test regression is retained explicitly. Neither version received independent-check feedback during generation.

24 次降到 19 次只是本批观察，不是因果性效率结论：每例只有一次随机生成，且提示词与验证行为同时变化，无法拆分影响。迷宫自测退化明确保留；两版生成过程中都没有收到独立验收反馈。

## 4. Changes made / 已实施的共性改进

1. **Snapshot interoperability.** The planner describes paths such as `board.4`, but baseline code sometimes returned literal dotted keys while the verifier required nested arrays. `lookup` now reads either representation without mutating the snapshot. Conflicting flat/nested values fail closed; missing or incorrect values remain failures. Prompts prefer fresh nested snapshots.
2. **Actionable planning feedback.** Missing automated/manual requirement coverage now identifies the exact IDs. Prompts clarify individual wait/hold bounds, encourage short covered tests, and require expectations to follow the original grid/rules rather than genre assumptions or unspecified terminal internals.
3. **Evaluation integrity.** Reports separate scheduled, attempted and independently evaluated cases, retain both disagreement directions, record run fingerprints/limits, and reject changed specification/acceptance files. Errors during post-generation evaluation preserve call accounting and are marked as benchmark errors.

对应中文说明：

1. **状态快照兼容。**兼容嵌套对象／数组及字面点路径，不改动真实状态；双重表示冲突、缺字段和错误值仍然失败。提示词统一建议嵌套快照。
2. **更明确的规划反馈。**指出未覆盖需求编号，澄清单次等待／按键上限，鼓励短测试及完整需求覆盖，避免凭游戏名称或未规定的终止内部状态编造预期。
3. **更可信的统计。**区分预定／尝试／已独立验收，保留双向分歧、指纹与预算；冻结文件变化就停止，评估阶段错误仍保留 API 计数。

No acceptance thresholds, expected values or frozen model assertions were lowered. Existing generated games and original scores were not edited. New files under `examples/benchmark/` contain requirements and test plans only, not game implementations.

未降低验收门槛、预期值或冻结的模型断言；未修改原游戏及原成绩。新增 `examples/benchmark/` 文件只有需求与测试计划，没有游戏实现。

## 5. Verification / 验证

- **160/160 framework tests passed**, including **27 real-browser tests**; all prior 143 tests remain. Final full run: 137.681 seconds. Model calls in framework tests are simulated and cost zero API credits.
- Each of the seven Beta 2 artifacts passed **two repeated independent verifications**, within a shared 60-second budget per artifact. All source/plan integrity checks passed. These repetitions test the same artifacts, not seven additional generations.
- A zero-API replay of the original first-round flat-snapshot tic-tac-toe against its original self-plan improved from 0/6 to 3/6 checks after the reader fix. The remaining failures persisted. Original source/plan hashes and score remained unchanged; this isolates reader compatibility, not model-generation improvement.
- Screenshot spot checks covered key-maze terminal rendering, brick-breaker first collision and resource-shop winning counters. They supplement traces, not full interactive human acceptance.

中文摘要：**160/160 项框架测试通过，含 27 项真实浏览器测试**，保留原有 143 项。七个 Beta 2 产物的独立验收各重复两次均通过，源码／计划完整性校验全部通过；这是同一产物复测，不是新的生成样本。原始扁平快照井字棋零 API 复测由 0/6 变为 3/6，剩余错误未被隐藏，原源码、计划和成绩未改。截图只做抽查，不冒充完整人工试玩。

## 6. Unresolved weaknesses / 未解决短板

### Priority 1: planning semantics / 首要：测试计划语义

Sokoban still assumes an inner floor is a wall. Resource-shop tests assume the previous test's state survives, although every test starts on a fresh page. Maze planning includes incompatible expectations about a locked door. The inventory probe still exceeds the DSL step limit. Structural validation and stronger prompts alone do not reliably catch these errors.

推箱子仍把内部地板当成墙；购买升级测试假设能继承上一项测试的状态，而实际每项测试都打开新页面；迷宫测试对锁门出现相互矛盾的预期；库存变体仍超出步骤限制。仅靠结构校验与加强提示词，无法稳定解决这些错误。

Next useful work: require each test to declare/reproduce its own initial setup, review legal transition sequences before freezing, and use bounded diagnosis when fixed-test failures are ambiguous. Such review is itself fallible and must never rewrite expectations to match generated code or turn uncertainty into success.

下一步应优先明确每项测试的独立初始化、冻结前核查合法状态转换，并在失败存在歧义时进行有预算的诊断。诊断本身也会错，不能为了迎合游戏实现改测试或把不确定算作成功。本次未增加新的付费审查阶段。

### Priority 2: depth and variability / 其次：难度与变化覆盖

The independent brick checks cover startup, movement, pause, one collision and reset—not all-brick victory or every life-loss scenario. The tiny maze and one-crate Sokoban do not establish larger-level planning. There is only one requirement per family per version; model/backend sampling variation is not characterized.

打砖块只独立检查启动、移动、暂停、一次碰撞和重置，未穷尽全砖通关及掉命分支；小迷宫、单箱推箱子不能证明复杂关卡能力。每类每版只有一个需求的一次生成，尚未刻画模型波动。

## 7. Expansion decision / 扩展决策

Keep vanilla offline local 2D browser games. Resource economy, key/door combination and finite inventory/capacity are promising **evaluation directions**, not newly guaranteed supported genres. Do not add 3D, networking, a backend, remote assets or an engine on the strength of these samples.

保持原生离线本机二维网页游戏范围。资源经济、钥匙门组合及有限库存／容量是值得继续评估的方向，不是新增“保证支持”的游戏类别。不能据此扩展到 3D、联网、后端、外部素材或新引擎。

Before deeper expansion, choose two new requirements for a target family and generate each three times with fixed budgets. A possible internal gate is at least 5/6 full mandatory-check passes with no repeated critical-rule bug and no regression in established cases. This is a small engineering gate, not statistical proof of reliability. Agree on a new API budget before running it.

进一步扩展前，为目标机制准备两个新需求，各在固定预算下独立生成三次。可暂用至少 5/6 次通过必选检查、没有重复严重规则错误且旧类不退化作为内部工程门槛；不是统计可靠性证明。下一轮需重新确定 API 预算。

## 8. Evidence and reuse / 证据与复用

[CAPABILITY_RESULTS.json](CAPABILITY_RESULTS.json) contains sanitized per-run usage, hashes, settings, outcomes and repeat-verification summaries. Full API traces, generated games and screenshots stay local under these ignored directories:

脱敏逐次证据见上述 JSON；完整 API 记录、游戏和截图仅保留在以下本地忽略目录，不上传密钥或原始日志：

~~~text
runs/capability_baseline_20261014/
runs/capability_beta2_20261014/
runs/capability_transfer_20261014/
runs/capability_repeat_20261014/
runs/capability_snapshot_recheck_20261014/
~~~

Current-version screening commands / 当前版筛查命令（会重新付费；独立命令各自计数，不自动共享总预算）：

~~~powershell
python -m agent benchmark examples/benchmark/capability_suite.json --max-total-calls 24 --max-calls-per-case 5 --max-rounds 3 --max-seconds 420
python -m agent benchmark examples/benchmark/transfer_suite.json --max-total-calls 5 --max-calls-per-case 5 --max-rounds 3 --max-seconds 420
~~~

To reproduce the baseline, use its recorded commit in a separate checkout; do not reset or overwrite an active teammate's work. A fresh GitHub clone contains fixtures and sanitized results, not the historical generated games.

复现基线需另建检出目录使用记录的提交，不要重置或覆盖队友工作。GitHub 新克隆只有评估样例及脱敏结果，没有本地历史游戏。
