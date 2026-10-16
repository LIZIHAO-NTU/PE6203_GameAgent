# PlayForge — Test Reliability and Rehearsal / 测试可靠性与运行演练

Date / 日期：2026-10-16. Release / 版本：`1.0.0-beta.4`.

## 1. Outcome / 结论

The final framework passed **220/220 regression tests, including 37 real-browser tests**. Twenty-one new tests cover stability sampling, budgets, immutable assertions, test-basis metadata, temporal review and null unsupported-gameplay metadata. No prewritten game implementation or solver was added.

最终框架 **220/220 回归通过，含 37 项真实浏览器测试**；新增 21 项测试，不新增预写游戏或通关器。

The matched four-case comparison delivered games passing all selected independent checks in both conditions (**4/4 before, 4/4 after**). Self-authored acceptance stayed at **3/4 in both conditions**. The new mechanisms work, but this sample does NOT demonstrate a higher autonomous success rate or reduced cost. Resource arithmetic remains a test-oracle weakness.

可比的四类需求在前后版本均通过全部所选独立检查，**独立交付前后都是 4/4，自测前后都是 3/4**。本轮补上验证机制，但没有证据声称自主成功率提高或成本降低，资源数值推演仍是短板。

## 2. Implemented changes / 实施内容

- `assert_stable`: trusted observation starting after previous input, comparing 2–8 live samples over 100–2000 ms. Supports state or ordinary DOM observations, shares the existing 45-second plan wait budget, has no state setters or expected-value overrides. Sampling proves equality only at sampled times, not continuous stability or a correctly working pause/resume control.
- `evidence`: planner requests a short original-spec quote plus expected-outcome basis for each test. Supplied metadata is structurally validated; a non-verbatim quote produces an advisory warning, not an automatic failure or proof of correctness. Legacy plans without this optional field still work.
- Temporal review: real-time/hybrid tests comparing a state path with its old snapshot after intervening input receive a heuristic warning. A corresponding actual failure stops blind repairs while preserving the game and frozen tests. Invalid-action-labelled tests are excluded from this heuristic. Runtime, resource and infrastructure failures retain priority.
- Frozen stability assertions, including sample count/duration, cannot be weakened by late recovery or optional audit. Audit remains off by default. The source/test/plan hashes and repeated-check evidence are preserved in sanitized results.

中文说明：新增操作后的稳定性采样；测试请求可复核的需求依据；发现跨输入的旧快照比较时提醒，实际相关测试失败才停止盲修；冻结后的稳定性检查也不能随意放宽。需求依据仍是模型声明，既不是数学证明，也不是新增的通用游戏求解器。

Example / 例子（选择器和状态路径仍由实际需求决定）：

```json
[
  {"action":"click","selector":"#pause"},
  {"action":"assert","source":"state","path":"phase","op":"eq","value":"Paused"},
  {"action":"assert_stable","source":"state","path":"player.x","duration_ms":300,"samples":3}
]
```

Motion before pausing and after resuming still needs separate checks. This replaces a risky capture-before-pause comparison, not the game rules or other acceptance obligations.

仍需单独检查暂停前／恢复后的真实运动；上述机制不替代其他规则验收。

## 3. Frozen English-spec comparison / 英文需求对照

Baseline commit: `b6fbb8288b115933c8782afb9704e19893fc2bc0` (Beta 3). Four requirements in `examples/reliability_20261016/` cover resources, discrete teleportation, a color sequence and real-time lanes. They are concise functional specifications plus explicit observation contracts, not fully open-ended one-sentence teacher prompts. Independent checks were authored before generation and never sent to the planner, coder, audit or repair model.

基线为上述 Beta 3 提交。四份英文需求覆盖不同规则，包含必要观察接口约定；它们不是完全开放的一句话题目。独立验收事先编写，不向生成或修复模型提供。

For each comparable run: maximum 4 API attempts, 3 generation/repair rounds, 300 seconds, same configured `deepseek-flash`, audit/diagnosis/lessons/syntax checks off. All baseline runs preceded improved runs, with independent stochastic samples and no seed control. A single sample per condition cannot isolate improvement from model randomness.

每次可比运行均为最多 4 次 API 尝试、3 轮、300 秒；同一模型配置和功能开关，先基线后改进，未控制随机种子，不据单次结果作统计推断。

| Case / 样例 | Before self-plan / 原自测 | Before independent / 原独立检查 | After self-plan / 新自测 | After independent / 新独立检查 |
|---|---:|---:|---:|---:|
| Crystal Workshop | Fail | 6/6 | Fail | 6/6 |
| Portal Shortcut | Pass | 6/6 | Pass | 6/6 |
| Color Code | Pass | 6/6 | Pass | 6/6 |
| Three-Lane Runner, clarified spec / 澄清需求 | Pass | 6/6 | Pass | 6/6 |

All eight comparable artifacts passed their unchanged independent checks twice in zero-API replays, with game and plan integrity checks passing. These are repeat observations of eight artifacts, not sixteen extra generated games. Screenshot spot checks showed visible English interfaces for the improved portal and runner; they are not complete human gameplay acceptance.

八份可比产物的原独立检查各重复两遍全部通过，源码与计划哈希一致；这不是额外生成十六个游戏。截图抽查了传送和跑道的英文界面，不冒充完整人工试玩。

### Protocol correction / 方案纠正

The first runner wording did not explicitly fix state-hook field placement/phase casing or which control resumes Paused. Its independent plan made assumptions and failed against the artifact. That original run used 3 API attempts and remains recorded as an excluded pilot; it is not silently relabelled a success. The wording was clarified before either final-condition runner evaluation, keeping the independent plan unchanged. The clarified baseline was rerun using a temporary archive of the original commit, not the improved agent; its spec hash matches the improved run.

第一份跑道需求的内部状态字段层级、大小写与恢复按钮不够明确，独立测试存在假设。原来 3 次调用的试运行保留为排除项，不改为成功；在最终两条件跑道测试前澄清需求，独立测试不变，基线使用原提交的临时源码副本补跑。脱敏数据明确记录两份需求哈希及排除原因。

### Remaining oracle errors / 尚未解决的预期错误

After two crafts, energy is `7 - 3 - 3 = 1`; charging makes it `3`, not `4`. The improved workshop test's textual explanation correctly stated this ledger, but its assertion expected `4` and later expected residual energy `1` instead of `0`. The game and independent checks followed the actual rules. This shows why an explanation is not a verified oracle. The color planner also omitted the requested basis on all six tests; optional metadata keeps compatibility but does not ensure model adherence.

新资源测试出现“文字推演正确、数字断言写错”：两次制作后能量 1，充能后应为 3 而非 4，第三次制作获胜后应为 0 而非 1。颜色样例还遗漏了全部六项测试的依据字段。因此不能声称模型每次遵从提示词或已自动证明规则。

## 4. Single-command rehearsal / 单命令演练

```powershell
python -B -m agent examples/reliability_20261016/pulse_runner.md --output .codex-tmp/dress_rehearsal --max-calls 4 --max-rounds 3 --max-seconds 300
```

This was a separately recorded real-model run from a new output directory, not a replacement for a failed comparison. It used **3 API attempts**, selected round 2 after one repair, finished in **54.547 seconds**, recorded **zero manual interventions**, and returned `automated_passed_manual_pending`. Its original frozen self-plan and the independent six-check plan each passed twice under final-source read-only replay; HTTP returned 200. Local doctor/preflight succeeded, but doctor alone does not test provider connectivity. The real generation is the API connectivity evidence.

另行记录的一条命令演练使用 3 次真实 API 调用、一轮修复，约 55 秒完成，人工干预为零；不代替失败对照。原冻结自测和六项独立检查均各复跑两遍通过，页面 HTTP 200。仍有人工待验收项，不宣称完整游戏验收。

After paid runs, a defensive type guard was added for null gameplay metadata in unsupported plans. Final full regression and rehearsal replays use that final source. Valid compared gameplay paths are unchanged; candidate and final source fingerprints are separately recorded rather than falsely reported identical.

付费运行后补了一处不支持题目返回空玩法元数据时的防崩溃处理；最终完整回归及演练复测使用最终源码。报告分别保留候选与最终代码指纹，不伪称所有实测均在完全相同源码上进行。

Instructor endpoint/model/options are still unknown and untested. Once provided, repeat the provider-specific configuration and fresh-directory rehearsal; current DeepSeek results do not prove instructor-model compatibility.

老师最终模型尚未确定，当前只验证已配置 DeepSeek，不能外推兼容性。

## 5. Usage and retained evidence / 用量与保留证据

Total: **27/32 API attempts**, **138,941 input tokens**, **63,203 output tokens**, zero unknown-usage calls. Matched before/after runs used 10/11 attempts; the excluded pilot used 3 and the separate rehearsal 3. No calls were made merely to spend the unused budget. Actual monetary cost is unknown because price fields are not configured; provider billing is authoritative.

总计 27 次实际尝试，包含排除的试运行和独立演练；金额未知，以服务商账单为准。没有为用满额度追加调用。

Retained: this report, `RELIABILITY_RESULTS.json`, the four English specification/acceptance pairs and suite, new framework tests, updated source/docs, and the proposal-only `EXTENSION_PLAN.md`. Temporary dependencies, source archive, generated games, screenshots and raw API logs are cleaned up; existing games/runs are untouched. Sanitized JSON retains hashes, failed frozen tests, observations, outcomes and usage, not API keys or user-specific absolute paths.

后半部分仅写方案，没有实施新的输入工具、平台跳跃适配、复杂引擎、联网、三维或 UI。
