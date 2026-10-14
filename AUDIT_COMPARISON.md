# Plan-Audit On/Off Comparison / 计划审查开关对照

Date / 日期：2026-10-14. Fixed agent / 固定版本：`1.0.0-beta.3`, commit `1f8c548a279718ebea6221da4bbe30d0752463ae`.

## 1. Decision / 结论

**Keep `--plan-audit` opt-in/off by default.** In this small DeepSeek sample, the current review path did not improve independently confirmed delivery. It sometimes found real mistakes, but two invalid review responses blocked game generation and an approved review missed turn/winner errors. Improve review response reliability and failure handling before enabling it by default or expanding the game platform.

**暂时保持 `--plan-audit` 默认关闭、按需开启。**这批 DeepSeek 小样本没有显示独立验收交付改善：审查能发现部分真实错误，但两次无效审查响应阻断了游戏生成，一次批准又漏过轮次／胜负错误。应先提高审查响应可靠性与失败处理，再考虑默认开启或扩大游戏平台。

Agent source and prompts were NOT changed during or after the comparison. The existing default was already off, so no implementation change was needed to apply this decision. No GitHub push was performed for this evaluation-only task.

对照过程中及完成后均未改 Agent 源码或提示词；原默认值已经关闭，因此本次决策无需改实现。本轮仅做评估，未推送 GitHub。

## 2. Frozen protocol / 固定方案

- Four new requirements: one-way grid gate, stamp exchange arithmetic, last-stone-loses terminal rules, and energy/bridge combination. Each has six independent selected checks, authored before either condition ran.
- Eight end-to-end task attempts: each requirement once with audit off and once on. These are independent stochastic drafts, not the same draft reused. No seed control or repeated generation per condition.
- Order: gate off/on, exchange on/off, stones off/on, energy on/off. Two pairs per order reduce but do not remove time/cache effects.
- Per task: six API attempts, three generation/repair rounds, 420 seconds; verifier timeout 60 seconds. The audit consumes part of the same six-attempt cap, not extra calls.
- Same model/configuration, agent-source fingerprint, specifications and acceptance hashes, repair mode `auto`, one verification repetition, diagnosis/syntax checks/lessons disabled. Only the assigned audit switch differs.
- Configured model `deepseek-flash`; Python 3.11.9, Playwright 1.63.0, Edge 155.0.4283.45, Windows. No game templates, solvers or manually edited generated games.

中文摘要：四类新需求各开关一次，交替安排执行顺序；每次最多 6 次 API 尝试、3 轮生成／修复及 420 秒，审查占用原预算。固定模型、代码指纹、需求、独立验收及其他开关；只有审查开关不同。每次独立生成草稿，没有种子控制，不能把单次结果当统计结论。独立测试不提供给生成／审查模型，也不用于本轮修复。

All eight assigned tasks ran. Actual use: **24/48 API attempts**, 119,910 input tokens and 67,408 output tokens; no unknown-usage calls. The unused budget was not spent on retries or new conditions. Price fields were not configured, so actual monetary cost is unknown; consult provider billing.

八次任务全部执行，实际 **24/48 次 API 尝试**，输入 119,910 token、输出 67,408 token，用量未知调用为零。没有为了用满预算追加重跑或新条件。未配置价格字段，实际金额未知，以服务商账单为准。

## 3. Results / 结果

“Independent delivery” means an artifact exists and all selected independent checks passed. It is not complete human gameplay acceptance. Missing artifacts remain missing evidence, not proof of an incorrect implementation.

“独立确认交付”表示有游戏产物且所选独立检查全部通过，不是完整人工游戏验收。没有产物属于缺少证据，不等于游戏实现有错误。

| Measure / 指标 | Audit off / 关闭 | Audit on / 开启 |
|---|---:|---:|
| Assigned / 实际任务 | 4 | 4 |
| Artifacts produced / 产生游戏 | 4 | 2 |
| Independent evaluated / 有独立验收结果 | 4 | 2 |
| Independently confirmed delivery / 独立确认交付 | 4/4 | 2/4 |
| Independent pass among evaluated / 有结果者通过 | 4/4 | 2/2 |
| Self-plan passed / 自测计划通过 | 2/4 | 0/4 |
| API attempts / API 尝试 | 12 | 12 |
| Actual audit attempts / 实际审查调用 | 0 | 3 |
| Repeated identical assertion events after repair / 修复后相同断言再次失败 | 2 | 1 |
| Invalid code-bundle rounds / 代码包格式无效轮次 | 1 | 0 |
| Sum elapsed including stops/acceptance / 含停止及验收的累计秒数 | 216.874 | 165.061 |

The lower audit-on time includes two early stops before code generation; it is NOT a speed improvement. Fewer repairs also coincide with fewer generated artifacts, not proof of better diagnosis. Both arms used 12 attempts, but produced different numbers of independently checked artifacts; token/cache differences do not establish a money-saving claim.

开启组较短的时间包含两次生成前提前停止，**不是速度提升**；较少修复也伴随较少产物，不能说明诊断更好。两组各用 12 次调用，却交付了不同数量的可验收产物；token／缓存差异不证明费用改善。

| Requirement / 需求 | Off: calls; self; independent / 关闭 | On: calls; audit; self; independent / 开启 |
|---|---|---|
| One-way gate / 单向门 | 2; pass; 6/6 | 2; invalid review; fail; no artifact / 审查无效、无产物 |
| Stamp exchange / 邮票兑换 | 3; fail; 6/6 | 2; invalid revision; fail; no artifact / 修订无效、无产物 |
| Last stone loses / 最后一颗者输 | 3; pass after repair; 6/6 | 4; approved; fail; 6/6 |
| Energy bridge / 能量桥 | 4; fail; 6/6 | 4; not applicable; startup-only; 6/6 / 未进入审查，仅启动自测 |

Audit actually ran in **three of four on assignments**: two responses were rejected; one was approved. Energy planning was structurally invalid before review, so its audit status is `not_applicable`; its result must not be attributed to an executed semantic audit.

开启组只有 **3/4 次实际调用审查**：两次响应被拒绝，一次获批。能量桥在审查前就没有有效结构计划，状态为 `not_applicable`，不能把其结果归因于已经执行的语义审查。

## 4. What failed / 具体短板

### Gate: response contract failure / 单向门：响应结构失败

The reviewer returned `status=revised` and issues but omitted the mandatory complete `plan`. The controller rejected it as `Missing supported boolean` and stopped before generating code. Manual tracing found no executable expected-value contradiction in the seven draft tests; some descriptions were awkward, but their actual input/expected sequences were consistent with the specification.

审查返回 `revised` 及问题列表，却遗漏必需的完整 `plan`，控制器以 `Missing supported boolean` 拒绝，在生成前停止。按需求人工推演，七项草稿的可执行输入／预期未发现矛盾；描述有犹豫措辞，但不等于执行逻辑错误。

### Exchange: useful detection, unusable revision / 兑换：发现真问题，但修订无法执行

The off plan's `T3` clicks Buy at initial coins=7, then wrongly expects coins=7/stamps=0. The correct result is coins=4/stamps=1. A code repair did not change this contradictory assertion, and the conservative routing stopped rather than manufacturing a pass.

关闭组 `T3` 在初始金币 7 时购买，错误地预期仍为金币 7、邮票 0；正确结果为金币 4、邮票 1。修代码无法满足这个错误断言，随后按保守策略停止，没有伪造通过。

In the on draft, `T3` compares numeric stamp state with a string, and `T4` assumes three purchases are affordable from seven coins at cost three. The reviewer corrected those errors but added redundant setup assertions to `T5`, increasing its combined steps from 18 to 20. The revision violated the existing cap and was rejected. We did not remove assertions or raise limits after seeing this failure.

开启组草稿 `T3` 将数值状态与字符串比较，`T4` 误认为 7 金币能连续购买三次、每次花 3。审查纠正了这些错误，却给 `T5` 增加冗余准备断言，使合计步骤由 18 变 20，被现有上限拒绝。本次没有事后删断言或放宽上限。

### Stones: incorrect approval / 石子：错误批准

After A takes two then B takes two, one stone remains and it is A's turn. Audited tests `T4`/`T5` expect B; `T5` also consequently expects the wrong loser/winner. The reviewer approved this draft. The resulting game followed the original rules and passed independent checks, but failed its self-plan twice. In the off condition, a genuine restart implementation bug was repaired and both check sets passed.

A 取两颗、B 再取两颗后，剩一颗，应轮到 A。获批计划的 `T4`／`T5` 却预期 B，`T5` 还据此写错输赢。生成游戏符合原始规则、独立检查通过，却两次被错误自测卡住。关闭组则遇到真实的重置代码问题，修复后自测及独立检查都通过。

### Energy: map assumptions and schema limits / 能量：地图假设及结构上限

The off plan's `T2`, `T3`, `T5`, `T6` assume the initial right move enters a closed bridge and spends energy. It should be blocked for zero cost, so later positions, switching and exhaustion expectations are wrong. `T2` additionally compares the combined position text to scalar x. One repair response was an invalid bundle; a later valid repair left the same assertions failing, and the independent artifact remained correct on selected checks.

关闭组 `T2`、`T3`、`T5`、`T6` 假设起点向右能进入关闭的桥并扣能量；实际应原地且不扣能量，后续位置、开关及耗尽预期也就错了。`T2` 还把坐标字符串与单个 x 比较。一轮修复代码包无效，后续有效修复仍遇到相同断言失败；独立检查中的游戏行为保持正确。

The on condition exhausted its planning/late-recovery schema attempts on the 18-step limit, never ran the audit, and retained startup-only self-verification. Its game still passed the independent selected checks. It is not a successful autonomous self-verified run.

开启组初始规划及晚期恢复均未通过 18 步上限，没有运行审查，仅保留启动自测；游戏仍通过独立检查，但不能算自主自验收完成。

## 5. Wrong-test counts and limitations / 错误测试计数与边界

Manual review counted **distinct erroneous test IDs**, not failed attempts or individual assertions. Off had five confirmed erroneous tests across four available functional plans (23 tests reviewed). On had two confirmed erroneous tests in its only available frozen functional plan (six tests reviewed). Its rejected exchange draft also had two confirmed errors. Blocked or startup-only conditions are not assigned zero semantic errors.

人工按**不同错误测试编号**计数，而非失败次数或单条断言。关闭组四份可用功能计划共复核 23 项，确认 5 项错误；开启组只有一份可用冻结功能计划，复核 6 项，确认 2 项错误；被拒绝的兑换草稿另有 2 项确认错误。被阻断或只有启动计划的条件，不按“零错误”计算。

These denominators and available cases differ, so **5 versus 2 is not an error-reduction rate**. Review was performed after runs by the same assistant that authored the fixtures, not blinded external adjudication. Evidence and labels are recorded per run in [AUDIT_COMPARISON_RESULTS.json](AUDIT_COMPARISON_RESULTS.json).

分母和可用样例不同，因此 **5 对 2 不是错误减少率**。复核由编写样例的同一助手在运行后完成，不是盲评或外部裁决；逐次证据及标签见上述 JSON。

The drafts were independently sampled, not paired copies of one draft. One sample per requirement/condition cannot estimate a reliable success-rate difference or isolate audit effects from planner randomness. Independent acceptance covers selected rules, not every possible gameplay branch. No arbitrary-unseen-game guarantee follows.

两条件草稿独立采样，不是复制同一草稿后再切换审查。每条件每需求只有一次，无法可靠估计成功率差异，也不能把规划随机性与审查效应完全分开。独立验收是部分规则覆盖，不保证任意未知游戏。

## 6. Verification and retained evidence / 验证及保留证据

All four new acceptance plans were structurally validated before spending credits. Source/specification/acceptance hashes and paired budgets/settings were checked unchanged. All six generated artifacts passed their independent checks again in **two zero-API repetitions each**, with source/plan integrity checks passing. This is repeated testing of the same six artifacts, not twelve extra generation samples.

付费前四份新验收计划全部通过结构校验；对照前后源码／需求／验收哈希及两条件预算／设置保持一致。六个游戏各再次进行了**两次零 API 独立复测**，全部通过，源码／计划完整性检查通过。这是同一产物复测，不是额外生成十二次。

Screenshot spot checks confirmed energy-bridge rendering at a zero-energy win and stones showing the correct losing actor/winner. They are not full human interactive acceptance. Agent code was unchanged, so this task did not rerun or claim a new 195-test framework result; that earlier record remains in [PLANNING.md](PLANNING.md).

截图抽查了能量为零时胜利及石子终局的当前玩家／赢家显示，不冒充完整人工试玩。Agent 代码未改，本轮没有重跑或宣称新的 195 项框架回归成绩；此前记录仍见 [PLANNING.md](PLANNING.md)。

Final shared files: this report, sanitized JSON, and the four specification/acceptance pairs plus suite in `examples/audit_comparison/`. Raw logs, protocol, original plans, games and screenshots stay local in `runs/audit_comparison_20261014/`, including `repeat_acceptance/`. Temporary dependencies/scripts were removed; secrets are not included in shared results.

最终保留本报告、脱敏 JSON、四组需求／验收及套件文件。原始日志、协议、计划、游戏和截图仅保留于上述本地忽略目录；临时依赖／脚本已清理，共享结果不含密钥。

## 7. Next decision / 下一步

Do not enable review by default or add engines/networking/3D based on this batch. The most useful next implementation would be a smaller structured review response (specific test edits rather than regenerating a whole plan), local limit/commitment validation, and a clear unverified-artifact path when review fails. Any fallback must keep unresolved tests unresolved, never silently treat the original plan or game as passed. Compare such a change in a new, separately authorized experiment; do not patch and rerun only this batch's failures to improve the published score.

不要据本批默认开启审查，也不要扩大到引擎／联网／3D。下一轮最值得实现的是：缩小结构化审查输出，只修改具体测试而非重写整份计划；本地校验预算及验收责任；审查失败时保留明确“未验证”的产物路径。回退不能悄悄把未解决测试或游戏算通过。后续修改应另定实验及授权，不通过只重跑本批失败项美化公开成绩。
