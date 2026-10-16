# PlayForge 1.2.1 — Reliability Closure / 可靠性收尾

Date / 日期: 2026-10-17. Full title / 完整题目: **PlayForge: Build a Coding Agent That Can Build a Game**.

## 1. Scope and implementation / 范围与实现

This patch implements the agreed next step: bounded multi-issue draft feedback, adequately budgeted platform/resource trials, and real-model checks of normal repair versus stopping on a contradictory frozen test. It does not change model settings, game rules, acceptance thresholds, existing DSL limits or the read-only UI.

本版实施跨测试错误汇总、给平台／资源样本更完整的调用预算，并真实验证代码修复与测试冲突停止。模型设置、游戏规则、断言阈值、DSL 上限及只读 UI 均保持不变。

### Draft diagnostics / 草稿诊断

`validation_feedback(error, draft)` keeps the original error and scans at most ten isolated tests, collecting up to eight distinct first-known errors. The complete requirement/contract metadata remains in each diagnostic probe. Global coverage errors introduced by isolating a test are excluded; only test-local findings are added. Scanned/unscanned counts and the non-exhaustive scope are explicit. One test may still contain more errors than its first reported issue.

保留原错误，最多扫描十项测试、收集八条不同的已知首错。诊断保留完整需求及状态约定，排除隔离测试人为造成的全局覆盖错误；明确扫描数量和非穷尽边界，同一测试仍可能有其他尚未报告的错误。

These probes never accept, rewrite or weaken a plan. Full `validate_plan` still decides whether the complete draft can be frozen. Details are supplied to both initial planning retries and late structural recovery. Invalid JSON still follows the existing bounded provider retry; this patch does not guess or rewrite malformed JSON.

隔离扫描不接受、不改写、不放宽计划；完整校验仍决定能否冻结。初次重试和晚期结构恢复都会收到详情。非法 JSON 仍按原有有限重试处理，不猜测补全内容。

### Blocked-response compatibility / 待复核响应格式兼容

The live runner and repair evaluation share `validate_blocked_repair`. It accepts the required `blocked` object plus an optional string `summary` of at most 1,500 characters. The summary is ignored as an action; it cannot modify files or acceptance. Unknown fields, `files`, `changes`, invalid summaries, fabricated failed-test references and `code_error` blocks remain rejected.

主闭环与评估共用校验，允许附带最长 1,500 字符的字符串说明，但摘要不作为动作执行。文件修改、其他字段、非法摘要、虚构失败测试及将代码错误当作停止理由，仍会拒绝。冻结断言和原始产物不变。

This compatibility change was motivated by actual model output: a correctly recognized test conflict included a short summary and was rejected by the initial strict envelope. The original failure is retained. An older platform response has a 1,998-character summary and remains rejected even under the final policy; the limit was not relaxed to make it pass.

真实模型曾正确识别测试冲突，却因附带简短说明被首版严格格式拒绝，因此增加非动作元数据兼容。原失败保留；另一个平台响应的摘要长达 1,998 字符，最终规则下仍拒绝，没有为通过而放宽上限。

## 2. Controlled real repair checks / 受控真实修复检查

`python -m evals.repair_protocol` explicitly constructs a small counter fixture for evaluation only. It is not an autonomous game-generation run, a game template, or a generator dependency. Ground-truth labels and separate independent checks are not model prompts.

计数器仅由显式评估入口构建，不进入正常生成器，也不是预写游戏模板。故障标签及独立验收不提供给模型；结果必须与正常游戏生成分开统计。

- **Code defect:** the fixture incorrectly adds zero per click, while the original specification and frozen checks require one. The expected behavior is a real code repair followed by frozen and independent checks.
- **Test conflict:** the fixture correctly adds one, but a frozen self-check expects two after one click. The expected behavior is a cited blocked response, no edits and preserved correct behavior.

代码缺陷样本要求真正修代码；测试冲突样本要求报告待复核、保留正确实现，而不是修改游戏迎合错误预期。两种场景均使用真实浏览器结果作为修复输入。

| Batch / 批次 | Code defect / 代码缺陷 | Test conflict / 测试冲突 | Actual API attempts / 调用 |
|---|---|---|---|
| Initial strict envelope / 首轮严格格式，两次重复 | 2/2 repaired and checked / 修复并验证通过 | 1/2 accepted; one short-summary envelope rejected / 一次通过，一次因摘要格式拒绝 | 4 |
| Final bounded-summary policy / 最终规则，一次重复 | 1/1 repaired and checked / 修复并验证通过 | 1/1 appropriately blocked / 正确停止 | 2 |

Final source was used for the last pair. Every selected final-probe artifact passed two independent browser repetitions. Initial failures and source fingerprints remain separately recorded. This small counter test does not establish reliable diagnosis of arbitrary game rules.

最后一对使用最终源码，所选产物均通过两次独立浏览器检查；首轮失败和源码指纹单独保留。这只验证小型计数器修复行为，不证明任意游戏规则都能正确诊断。

## 3. Full game trials / 完整游戏尝试

Unchanged English specifications and independent checks were reused through `examples/reliability_closure_suite.json`. Each game was attempted twice with at most five actual API attempts, three generation/repair rounds and a 360-second task budget per run. These limits provide more repair opportunity than the previous two-call energy trial, but are not a guarantee of completion.

复用原英文需求及固定独立检查，每个游戏尝试两次，每次最多五次实际调用、三轮生成／修复及 360 秒。比上轮资源样本的两次调用更充分，但不保证任务一定成功。

| Original run / 原运行 | Planning / 规划 | Original autonomous status / 原自主状态 | Independent selected checks / 独立检查 | Calls / 调用 |
|---|---|---|---|---|
| Platform 01 | Valid / 有效 | `run_error`: blocked envelope rejected / 待复核格式拒绝 | 6/6 | 5 |
| Energy duel 01 | Failed / 失败 | `partial_game_plan_failed` | 7/7 | 4 |
| Platform 02 | Recovered / 恢复有效 | `run_error`: blocked envelope rejected / 待复核格式拒绝 | 6/6 | 5 |
| Energy duel 02 | Valid / 有效 | `plan_review_required` | 7/7 | 4 |

All four artifacts passed selected independent checks; **0/4 completed autonomous acceptance**. The first energy plan repeatedly exceeded the unchanged 18-step limit. The second entered a genuine repair round, repeated the same assertion failures and stopped for review. Thus its unresolved outcome is not explained solely by the old two-call budget. Platform plans included an unreachable no-jump path across a gap; the model reported conflicts rather than intentionally removing the physical rule.

四份产物通过独立所选检查，但自主验收 0/4。资源首份计划反复超出 18 步，第二份实际进入修复后仍重复失败、停止待复核，因此不能再仅归因于上轮预算太少。平台自编测试包含不跳跃跨越缺口的不可达路径，模型报告了冲突，没有故意取消物理规则。

The full game batch used the initial strict envelope. Under final offline revalidation, Platform 02's bounded summary is accepted as a blocked diagnosis; Platform 01's over-limit summary remains rejected. **Neither original run is retroactively relabelled.** Full fresh game generation was not repeated after the metadata-only parser change. Independent passage remains selected evidence, not full gameplay acceptance or proof that the model's diagnosis is always correct.

完整游戏批次使用首版严格格式。最终规则离线复核可接受平台 02 的有界摘要；平台 01 仍超限拒绝。两个原成绩都不重写，最终兼容修改后未重新完整生成游戏。独立检查通过不等于完整玩法验收，也不证明每条模型诊断都正确。

## 4. Budget and verification / 预算与验证

- **24 actual API attempts total:** initial controlled probes 4 + full game trials 18 + final controlled probes 2. Formatting/transport retries count toward the same total. No further paid calls were made.
- **302/302 regression tests passed**, including **46 real-browser tests**, no skips. All previous 281 tests remain; 21 new tests cover bounded cross-test diagnostics, protocol metadata and evaluation integrity.
- All four game artifacts passed two final-source, read-only independent repetitions; game/plan and original fixture hashes remained unchanged. These rechecks make zero API calls and do not alter autonomous statuses.

合计 24 次真实调用，包含重试；回归 302/302 全通过，含 46 项真实浏览器测试。四份游戏最终源码下各复放两次均通过，文件及固定需求完整性正常；复放不调用 API、不覆盖自主成绩。

Detailed usage, source/harness fingerprints, original failures, offline compatibility and recheck results are retained in `RELIABILITY_1_2_1_RESULTS.json`. Long free-form model summaries are represented by type/length/hash rather than copied reasoning text. Temporary games, raw API logs, screenshots, test dependencies and helpers are removed; previous user runs and local credentials remain untouched.

JSON 保留用量、源码指纹、原失败、格式复核及复放结果；长摘要只保留类型、长度和哈希，不复制冗长推演。清理本轮临时产物与依赖，不改旧 runs 或本机密钥。

## 5. Remaining priorities / 仍需改进

The patch improves actionable diagnostics and real-model repair protocol evidence, not general autonomous completion. Remaining problems include long scenario construction, unreachable test strategies, incorrect expected-state reasoning and verbose model envelopes. Further work should target shorter original-rule transitions and genuinely valid win paths, retain independent checks, and preserve all failures. Do not add more game categories, weaken acceptance or claim reliability from a counter fixture alone.

本版改进的是错误反馈和真实修复协议证据，不是已解决通用自主完成。长情景、不可达策略、预期推演和输出冗长仍存在。后续应针对短规则转换与真实可达路径改进，保持独立检查和失败记录；不靠扩充游戏名称、放宽验收或计数器样本宣称可靠。
