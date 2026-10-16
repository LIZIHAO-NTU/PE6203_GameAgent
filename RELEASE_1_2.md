# PlayForge 1.2.0 — Planning and Repair Evidence / 规划与修复证据

Release / 发布: 2026-10-17. Evaluation began / 评估开始: 2026-10-16, Asia/Shanghai.

Full title / 完整题目: **PlayForge: Build a Coding Agent That Can Build a Game**.

## 1. What changed / 本轮实现

This release prioritizes the first parts of the agreed roadmap: establish the actual 1.1.0 default-mode baseline, improve planning/repair feedback, and test two mixed mechanics. It preserves the single-agent loop, provider settings, immutable acceptance, native input tools, bounded retries, best-version retention and read-only dashboard. It does not introduce a new model provider, game engine, prewritten game template, arbitrary execution tool or multi-agent runtime.

本版优先实施既定路线的前几步：补测真实默认基线、改进规划及修复反馈、测试两种组合规则。保留单 Agent、模型配置、冻结验收、原生输入、有限重试、较好版本及只读状态页；不新增模型适配、游戏引擎、游戏模板、任意执行工具或多 Agent 框架。

### Located planning errors / 精确规划错误位置

`PlanValidationError` remains a `ValueError` but exposes `location` and `detail`. Validation identifies the test ID, setup/check array index and combined action number. The next planning attempt receives these details alongside the original error and execution contract. Context-local state is reset on both success and failure, including concurrent validation. Accepted semantics, expected values and frozen tests are unchanged.

规划错误仍兼容原异常类型，但会指出测试 ID、准备／检查下标和合并步骤，下一次模型规划收到对应详情。成功、失败和并发情况下均清理定位上下文；不自动猜规则、不修改断言、不放宽冻结验收。

For example / 示例:

~~~text
tests[6] (T7).steps[0] (combined step 1): Invalid state path
~~~

This improves diagnosis, not guaranteed model compliance. Real follow-ups still contained invalid JSON, a test without an assertion and an over-limit goal timeout. The controller rejected them and preserved partial artifacts rather than calling them functional success.

定位更具体不等于模型一定会改对。复测仍出现 JSON 错误、无断言测试及超限等待；控制器拒绝这些计划、保留部分产物，不算功能成功。

### Evidence-linked repair / 按证据组织修复

`agent/feedback.py` links failed tests to their frozen scenario, related requirements, setup length, failed action and ordinary-input reproduction. Existing compact feedback retains actual/expected observations and recent action logs. Up to three scenarios are included, with a 16,000-character scenario-list bound and explicit omitted counts; full evidence remains in traces. Passed test IDs remain visible as regression constraints.

新增反馈模块把失败测试关联到冻结情景、相关需求、准备长度、失败动作和普通输入复现过程；原反馈仍保留实际／预期值及近期动作。最多提供三个情景，对情景列表限制大小并明确标记省略数量；完整记录保留，已通过测试仍作为回归约束。

The original specification and frozen plan remain available. Scenario requirements and model explanations are claims, not independent truth. This is not a whole-prompt token cap or an LLM memory condenser, and no measured cost/latency reduction is claimed.

原始需求和冻结计划仍提供给模型；模型拆出的需求和解释不是独立真值。这不是整个提示词的 token 上限，也没有增加摘要模型；本轮不声称成本或时延下降。

### Explicit blocked repair / 明确的修复待复核响应

After recorded failed verification, the coder may return only:

~~~json
{"blocked":{"category":"test_issue","reason":"Original-rule and observation evidence","evidence_test_ids":["T1"]}}
~~~

Allowed categories are `test_issue`, `tool_limit`, and `uncertain`. Cited IDs must be actual failed tests. Initial-generation blocks, mixed file edits, nonexistent evidence and a `code_error` block are rejected. A valid block writes no candidate files, preserves the best artifact and frozen plan, and ends with `plan_review_required`, never successful acceptance. It consumes no extra diagnostic call: this is an alternative response to the existing repair call.

只能引用真实失败测试；初次生成、混入文件修改、虚构测试及用可修复代码错误申请停止都会拒绝。有效响应不写新候选文件、保留较好产物和冻结计划，状态为待复核而非成功。它复用原修复调用，不额外增加诊断调用。

This relies on the model recognizing and reporting a conflict. It cannot prevent every incorrect repair or prove the test is wrong. **No paid run in this batch returned `blocked`.** The controller behavior was verified with simulated model responses and an actual browser mismatch/recheck. Real-model adoption remains to be evaluated further.

该机制仍依赖模型识别并报告冲突，不能保证拦截所有错误修复，也不能证明测试必然错误。**本轮付费运行没有返回 blocked**；控制行为通过模拟模型和真实浏览器冲突／复放验证，真实模型是否稳定采用仍需更多证据。

### Joint selected-check metrics / 联合所选检查指标

The benchmark adds `joint_selected_checks_passed` and `joint_selected_checks_rate_over_attempted`. Both self-plan and independent selected checks must pass; absent independent evidence does not count as confirmed success. Full-game/manual acceptance remains separate. Historical reports are not rewritten.

联合指标要求自测与独立所选检查同时通过，缺失证据不计确认通过；不等于完整玩法／人工验收，历史报告保持原样。

## 2. Real-model results / 真实模型结果

Model configuration / 模型配置: DeepSeek `deepseek-flash`; same endpoint/settings throughout. Structured expectation requests and plan audit remained off by default. Windows, Edge, Playwright 1.63.0. **30 actual API attempts** in total, including format/transport retries; token usage is retained in `RELIABILITY_1_2_RESULTS.json`, not converted into an invented bill.

固定 DeepSeek 配置，未改模型适配，结构化摘要请求及额外计划审查保持关闭。共 30 次真实调用尝试，包含格式重试；JSON 保留 token 记录，不编造费用账单。

| Version/batch / 版本与批次 | Case / 样本 | Original autonomous result / 原自主结果 | Independent selected checks / 独立检查 | Calls / 调用 |
|---|---|---|---|---|
| 1.1.0 baseline | Word lock | Self-pass, but independent failure / 自测通过但独立失败 | Failed / 未通过 | 3 |
| 1.1.0 baseline | Number dial | Selected checks passed, manual pending / 自测通过，人工待验收 | Passed / 通过 | 3 |
| 1.1.0 baseline | Platform hop | Budget exhausted / 调用预算用尽 | Passed / 通过 | 4 |
| 1.1.0 baseline | Aim range | Selected checks passed, manual pending / 自测通过，人工待验收 | Passed / 通过 | 3 |
| 1.1.0 baseline | Tactical duel | Partial game, plan failed / 有产物，计划失败 | Passed / 通过 | 3 |
| 1.1.0 supplement | Market budget | Selected checks passed, manual pending / 自测通过，人工待验收 | Passed / 通过 | 3 |
| 1.2.0 follow-up | Word lock | Selected checks passed, manual pending / 自测通过，人工待验收 | Passed / 通过 | 2 |
| 1.2.0 follow-up | Platform hop | Partial game, plan failed / 有产物，计划失败 | Passed / 通过 | 4 |
| 1.2.0 mixed rules | Signal vault | Selected checks passed, manual pending / 自测通过，人工待验收 | Passed / 通过 | 3 |
| 1.2.0 mixed rules | Energy duel | Budget exhausted / 调用预算用尽 | Passed / 通过 | 2 |

The initial baseline batch used its 16-call cap before the market case could run. That original skipped row is retained. Market was subsequently run as a separate three-call supplement using an archived 1.1.0 implementation. Tracked source content matches the base commit after newline normalization; raw fingerprints differ due to newlines and an unreferenced copied helper. The supplement is explicitly recorded and excluded from the matched word/platform comparison.

首批 16 次上限导致资源样本跳过，原跳过记录保留。之后用归档 1.1.0 单独补测三次，未冒充原批次成功。归档受跟踪源码与基础提交在统一换行后完全一致；换行及一个未引用的辅助文件造成原始指纹差异，JSON 明确记录，补测不参与文字／平台的配对对照。

Across six distinct baseline cases: self checks passed 4/6, independent selected checks 5/6, joint checks 3/6. Across four candidate cases: self checks passed 2/4, independent selected checks 4/4, joint checks 2/4. **These are different case sets and cannot be used as an improvement percentage.** Each matched pair also has only one stochastic run per version.

六份基线：自测 4/6、独立 5/6、联合 3/6。四份新版样本：自测 2/4、独立 4/4、联合 2/4。集合不同，不能算提升百分比；同需求配对也只有每版一次，不能证明因果效果或稳定泛化。

The word follow-up no longer showed the observed counter error. Platform planning remains unresolved; the energy duel's first game passed independent checks but failed a self check, and its remaining repair call could not run under the two-call allocation. Both remain unverified autonomous outcomes. Frozen independent checks never entered generation or repair prompts.

文字复测未再出现该计数错误。平台规划仍未解决；资源战术首份产物通过独立检查，但自测失败，因分配的两次调用已用完，不能继续修复。这两项不算自主成功，独立验收从未提供给生成或修复模型。

## 3. Preserved counterexample / 保留的错误修复反例

The baseline word game initially counted every non-empty answer, including the correct one, as required. Its frozen self-test incorrectly expected zero attempts after a first correct answer. The agent changed the implementation to satisfy that test and then reported self-pass. Independent checks caught the rule violation. Two read-only repetitions confirm: the initial artifact passes selected independent checks; the repaired artifact fails them. Original statuses remain unchanged.

旧版文字游戏初稿按要求计入正确答案的尝试次数，自编冻结测试却期待 0。Agent 修改游戏迎合错误测试后报告自测通过，独立检查检出了违规。两次只读复放确认初稿通过、修后失败；原成绩不改写。

This is why the release adds a truthful stop path and joint evidence reporting instead of allowing post-hoc test edits. The new path is an engineering safeguard, not a solved general rule oracle.

因此本版提供诚实停止路径和联合证据指标，而不是事后修改测试。它是工程保护，不代表通用规则推演问题已解决。

## 4. Mixed-rule scope / 组合规则范围

- **Signal Vault:** public text/code clues, native selection, answer costs, attempt counting, capped recharge, terminal locks and reset. Seven independent selected tests, with visible counters and state consistency observations.
- **Energy Duel:** local alternating turns, attack costs, capped charging, insufficient-resource no-ops, both reachable winners, terminal lock and reset. Seven selected tests, mostly observing public DOM counters.

两份英文需求及独立计划均在生成前固定，存放于 `examples/reliability_1_2/`。没有预写实现、通关脚本或隐藏答案注入；验证通过仅支持这些小规模规则组合的可行性，不代表所有文字、战术或资源游戏可靠。

## 5. Verification / 验证

**281/281 framework tests passed, including 45 real-browser tests, no skips and no paid API calls.** All previous 254 tests remain; 27 new tests cover located errors, context isolation, feedback integrity, blocked repairs, evidence validation, joint metrics and mixed fixtures. A browser test confirms a deliberately wrong frozen expectation remains failed while the preserved game passes a separately correct plan.

框架回归 281/281 全部通过，含 45 项真实浏览器测试，无跳过、不调用付费 API。保留原 254 项，新增 27 项覆盖定位、上下文隔离、反馈完整性、待复核响应、证据校验、指标及组合样本；真实浏览器验证了错误冻结预期保持失败、正确游戏仍被保留。

All ten final artifacts were replayed twice through the unchanged independent plans under final 1.2.0 code. Nine passed; the known bad baseline word repair remained failed. Its initial artifact also passed twice. All game/plan and fixture integrity checks passed. Replays make zero API calls and do not replace original autonomous results. Raw intermediate games, screenshots, API logs and dependencies are task-temporary; sanitized evidence and fixtures are retained.

十份最终产物各重复两次，九份通过，已知错误的旧版文字修复保持失败；其初稿另重复两次通过。全部游戏／计划和固定需求完整性检查正常。复放不调用 API、不覆盖原自主成绩；清理临时游戏、图片、日志及依赖，保留脱敏证据与测试需求。

## 6. External ideas and boundaries / 外部借鉴及边界

- **SWE-agent:** explicit command documentation and format-error guidance informed actionable validation locations. Reference: [historical command documentation](https://swe-agent.com/0.7/config/commands/). PlayForge still uses its own validated browser-action DSL; no SWE-agent runtime or commands were copied.
- **Aider:** automatic lint/test-after-edit reinforces the existing verify-after-change loop. Reference: [linting and testing](https://aider.chat/docs/usage/lint-test.html). That loop already existed here; this release does not claim to invent it or enable arbitrary model-chosen host commands.
- **OpenHands:** preserving important goals, technical constraints and failure context informed selective scenario feedback alongside raw traces. Reference: [Context Condenser](https://docs.openhands.dev/sdk/guides/context-condenser). No OpenHands SDK, extra summarizing model or reported external performance gains are imported.

借鉴的是适合本项目的接口反馈、修改后验证及关键信息组织思想，代码自行实现，不引入整套外部系统。其他项目的收益不能直接算成 PlayForge 的收益。

## 7. Deferred work / 暂缓内容

Still deferred: interactive generation/cancellation UI, broader visual/black-box validation, more repeated mixed variants, multiple-error draft feedback, instructor-specific model adaptation, networking, 3D and engines. The existing dashboard remains read-only; CLI startup and model settings are unchanged. Next prioritize the remaining schema/oracle weaknesses and real-model repair-protocol behavior before claiming broader support.

本轮没有扩建生成／取消 UI，也未实现广泛视觉验收、更多重复变体、同时列出全部草稿错误或新模型适配。现有状态页仍只读，CLI 和模型配置不变。下一轮继续针对格式、预期推演和真实修复行为取证，再决定扩大范围；联网、3D、复杂引擎暂缓。
