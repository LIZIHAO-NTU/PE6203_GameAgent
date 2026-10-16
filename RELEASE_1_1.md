# PlayForge 1.1.0 — Bounded Expansion / 有限范围扩展

Release date / 日期: 2026-10-16. Full title / 完整题目: **PlayForge: Build a Coding Agent That Can Build a Game**.

## 1. Scope and version / 范围与版本

This release follows the proposed sequence: expected-outcome agreement, form tools, selected new mechanics, then an optional status viewer. It keeps the single-agent controller, existing budgets, immutable frozen assertions and offline vanilla HTML/CSS/JavaScript scope. No prewritten game templates, solver, engine, network service or 3D support was added.

本版按既定顺序实施：预期核对、表单工具、小范围新玩法及可选状态页。保留单 Agent 闭环、预算、不可放宽的冻结断言及原生离线网页边界；没有加入预写游戏模板、通关器、游戏引擎、联网服务或 3D。

Version `1.1.0` denotes a backward-compatible feature expansion, not an instructor-grade or production reliability claim. Future fixes can use `1.1.1`, additive features `1.2.0`, and incompatible architectural changes `2.0.0`. Historical Beta results keep their original labels.

`1.1.0` 表示兼容现有流程的功能扩展，不代表达到老师评测或生产可靠性保证。之后修复用 `1.1.1`、新增兼容功能用 `1.2.0`，不兼容架构调整再考虑 `2.0.0`；历史 Beta 记录不重编号。

## 2. Expected outcomes / 预期与断言核对

Optional `test.evidence.expected_observations` is an ordered list of `{"value":...}` records, one per literal `assert` in combined setup/check order. Legacy `{"step":...,"value":...}` records remain supported. Provided lists must cover all literal assertions, preserve value types, agree with their thresholds and fit existing bounds. An empty list is valid only when there are no literal assertions. This runs before freezing; recovery cannot change an existing assertion to make a game pass.

可选结构化摘要按准备和检查步骤的顺序排列，每个字面量断言对应一个值，兼容旧的步骤编号格式。已提供摘要必须完整覆盖、保留类型、与断言数值或阈值一致；没有字面量断言时才允许空列表。核对发生在冻结前，恢复不得改写已承诺的断言来制造通过。

This checks internal agreement, **not** free-prose understanding or game-rule truth. Unit tests demonstrate that two equally wrong numbers still agree. In the resource sample the model omitted the requested evidence/summary, so agreement validation did not apply. Its assertion expected credits `4`, but `buy → earn → buy` gives `5−4+3−4=0`, enters Won, and later actions must do nothing. The original run remains `plan_review_required`, despite passing independently specified checks. The counterexample and per-draft metadata coverage are retained in `EXPANSION_RESULTS.json`.

这不是自然语言理解或规则真值判定。单元测试证明两个同样错误的数字仍能通过一致性检查。真实资源样本中，模型遗漏了请求的证据和摘要，因此本项核对没有适用；其断言写 `4`，真实操作后应为 `0`。原运行仍记为待复核，不用独立检查通过覆盖原成绩；JSON 另保留各初稿的摘要覆盖数量。

### Evidence-driven default / 根据实测调整默认行为

Both paid candidate batches requested duplicate summary lists. The initial indexed form caused coverage/index errors; ordered values reduced bookkeeping but did not resolve omissions and contradictions. Therefore requesting this metadata is **off by default** in the final release, enabled explicitly with `--structured-expectations`. Supplied metadata is always validated, even when the flag is off; it is never silently removed. Ordinary plans retain `spec_quote` and `expected_basis`.

两批付费候选版都请求重复摘要。首批编号摘要出现覆盖和下标问题；有序摘要仍有遗漏和数值矛盾。最终版因此默认不请求重复摘要，可用 `--structured-expectations` 显式试验。关闭开关不意味着忽略已提供的矛盾摘要；已提供字段始终校验。普通计划仍保留原需求引文和简短预期依据。

The final opt-in wiring/default was regression-tested with simulated model responses and real browsers, **not paid-generated again** after exhausting the 30-attempt cap. Paid candidate outcomes must not be presented as final default-mode performance or as a controlled improvement estimate.

最终开关和默认行为经过模拟模型及真实浏览器回归；30 次预算用完后，没有再付费生成最终默认模式。不能把候选版数据当成最终默认模式效果，也不能据此声称成功率提升。

## 3. Trusted form tools / 受控表单工具

| Tool / 工具 | Behavior / 行为 |
|---|---|
| `fill` | Native input/textarea fill, 0–500 characters; empty clears; real input events / 原生输入与事件，空字符串清空 |
| `select_option` | Select one native option by value, max 200 characters; real change events / 按值选择原生选项并触发事件 |
| Observation `source: "value"` | Read the current input/select value; no state mutation / 观察当前控件值，不写入状态 |

Password/file/hidden inputs, arbitrary contenteditable controls and custom-widget scripting are not supported. Disabled/read-only controls are not forced. Puzzle answers must be public non-secret task data, never account credentials. No answer is injected into hidden game state. Form-value echo alone is excluded from functional-evidence detection; plans still need an observable rule outcome. Other structural evidence gates remain heuristic, not semantic proof.

不支持密码、文件、隐藏控件、任意可编辑元素及自定义控件脚本，不强行操作禁用或只读控件。谜题答案必须来自公开的非敏感任务信息，不是账号凭据，也不注入隐藏游戏状态。只验证输入回显不算功能证据，仍需规则结果；其他结构门槛也不是语义正确性证明。

## 4. Small real-model evaluation / 小规模真实评估

Environment: DeepSeek `deepseek-flash`, Windows, Edge and Playwright. Six English specifications and six independent plans were fixed before the first API call. Each independent plan has six selected tests and is withheld from generation. Samples cover only small explicit rules; generated state snapshots still need manual authenticity checks.

六份英文需求及独立验收计划在调用前固定，每份六项检查，不传给生成模型。环境为 DeepSeek、Windows、Edge 和 Playwright。样本规则明确且规模很小；生成状态接口是否真实仍需人工核对。

| Initial sample / 首批样本 | Autonomous result / 原自主结果 | Independent checks / 独立检查 | API attempts / 调用 |
|---|---|---|---|
| Word lock / 文字谜题 | Selected checks passed, manual pending / 自测通过，人工待验收 | 6/6 | 2 |
| Number dial / 算术谜题 | Selected checks passed, manual pending / 自测通过，人工待验收 | 6/6 | 2 |
| Platform hop / 平台跳跃 | Partial game, plan failed / 有产物，功能计划失败 | 6/6 | 4 |
| Aim range / 弹丸瞄准 | Partial game, plan failed / 有产物，功能计划失败 | 6/6 | 4 |
| Tactical duel / 本机战术 | Partial game, plan failed / 有产物，功能计划失败 | 6/6 | 4 |
| Market budget / 资源管理 | Plan review required / 计划待复核 | 6/6 | 3 |

Initial batch: 19 attempts, 6/6 artifacts pass selected independent checks, **2/6 autonomous self-plans pass**. A separately labelled follow-up used the remaining 11 attempts: platform (4), aiming (4), tactics (3). All three artifacts again passed 6/6 independent checks; **0/3 autonomous self-plans passed**, due to metadata coverage/contradiction failures. No original outcome was replaced and no frozen assertion was weakened.

首批 19 次调用，六份产物通过所选独立检查，但仅两份完成自主自测。定向复测另用 11 次，三份产物再次通过独立检查，但自主计划仍全部失败。两批分开记录，不替换首轮、不放宽冻结规则。合计 **30 次 API 尝试**，不是 30 个游戏，也不是已证明的通用成功率。

The useful result is feasibility of these input/control/rule combinations, not reliable autonomous completion of broad genres. Planning semantics and metadata overhead remain explicit weaknesses. No instructor-model compatibility, latency/cost improvement or arbitrary unseen-game reliability is claimed.

实测证明的是这些小规模交互和规则组合具有生成可行性，不是大类游戏都能稳定自主完成。计划语义及填写负担仍是短板；不声称老师模型兼容、成本下降或未知游戏可靠性。

## 5. Read-only dashboard / 只读状态页

~~~powershell
python -m agent dashboard runs/YOUR_RUN --port 8005
~~~

Open `http://127.0.0.1:8005/`; stop with Ctrl+C. It displays recorded status, API attempts, elapsed time, selected round, requirements and recent event labels, plus game/report links. Missing/corrupt evidence is unverified, not successful. The run's original version is distinct from the viewer version. Raw API traces, `.env` and summary-file routes are not served; the viewer does not initiate model calls or accept generation requests.

显示已有状态、调用次数、耗时、选中轮次、需求和近期事件，提供游戏及报告入口。缺失或损坏证据不显示成功；原运行版本与查看器版本分开。不会提供原始 API 记录、密钥文件或生成接口，不产生模型费用。仅供本机展示，不是公网部署、多用户权限系统或安全隔离替代品。

Desktop screenshot was visually inspected; the real-browser mobile check at width 390 passed without horizontal overflow. The owned temporary preview was stopped at task teardown. Use the command above to view your retained runs; temporary evaluation games/previews were not kept as deliverables.

已目视检查桌面截图，并以真实浏览器验证 390px 手机宽度无横向溢出。任务结束停止临时预览；临时评估游戏和图片不作为交付保留，可用上述命令查看已有 runs。

## 6. Verification and next boundary / 验证与后续边界

Final regression: **254/254 passed, including 44 real-browser tests**, with no skips and no paid API calls. All previous 220 tests were retained; 34 new tests cover agreement/legacy rules, form behavior, echo-only evidence exclusion, experiment mode and read-only UI. All nine artifacts passed two fresh-browser repetitions of their six independent selected tests, with unchanged game/plan hashes and frozen fixtures.

最终 **254/254 项回归全部通过，含 44 项真实浏览器测试**，无跳过，不调用付费 API。保留原有 220 项，新增 34 项覆盖摘要、兼容性、表单、回显证据排除、实验开关及状态页。九份产物各重复两遍六项独立检查，全部通过，游戏、计划及固定需求哈希未变。

Exact final regression counts, source fingerprints, preserved initial failures, fixture integrity and final repeated-check results are recorded in `EXPANSION_RESULTS.json`. Replays are read-only, make zero API calls and do not promote original failed runs to autonomous success. Two fresh-browser repetitions per artifact check repeatability of the selected tests, not full gameplay acceptance.

最终回归数量、源代码指纹、首轮失败、需求完整性和重复复放结果见 JSON。复放不改游戏、不调用 API，也不改变原始自主成绩。每份产物在新浏览器中重复两次，只验证所选检查的重复性。

Next priority: improve small rule-transition test design and evaluate new variants with frozen independent checks. Do not add more genre labels, a multi-agent framework or a large UI until autonomous planning is more dependable. Networking, 3D, engines and persistence remain deferred.

后续先改进小型规则转换测试，再用新变体检查；自主计划可靠性提高前，不急于堆游戏名称、多 Agent 或大型 UI。联网、3D、引擎及持久化继续暂缓。
