# PlayForge — Beta 3: Setup, Plan Review and Failure Routing / 初始化、计划审查与失败分流

Release / 版本：`1.0.0-beta.3`.

Follow-up: a later real DeepSeek on/off comparison is recorded in [AUDIT_COMPARISON.md](AUDIT_COMPARISON.md). This document's zero-API statements describe the initial implementation/verification session, not that later evaluation.

后续说明：之后进行的真实 DeepSeek 开关对照见 [AUDIT_COMPARISON.md](AUDIT_COMPARISON.md)。本文零 API 记录指初次实施／验证任务，不包括该后续评估。

This update targets the planning weaknesses observed in [CAPABILITY.md](CAPABILITY.md). It does not expand the game platform, embed game templates, or claim that model-authored tests are now always correct. No paid API calls were made for this update.

本次针对上一轮评估发现的规划短板，不扩大游戏技术平台，不加入游戏模板，也不声称自编测试已经可靠正确。本轮未调用付费 API。

## 1. One flow / 统一流程

~~~text
Original spec + execution contract
    → Draft plan and structural validation
    → Deterministic initial-state conflict review (always on, zero API)
    → Optional one-attempt model audit (original spec + draft ONLY)
    → Freeze plan
    → Generate game
    → Fresh page for EACH test → setup_steps → check steps
    → Pass / repair actual errors / stop for review without weakening tests
~~~

中文流程：原始需求及执行约定 → 草稿与结构校验 → 默认启用的初始状态冲突检查 → 可选模型审查 → 冻结计划 → 生成游戏 → 每项测试独立新页面、准备及检查 → 根据证据完成、修复或停止复核。

## 2. Independent setup / 每项测试独立准备

The browser still opens a fresh context/page for every test. Optional `setup_steps` run on that page immediately before `steps`, using the exact same trusted DSL. They are ordinary clicks, keys and observations, not a scenario loader or hidden state mutation. Existing plans without the field still work.

每项测试仍打开独立浏览器上下文／页面。可选 `setup_steps` 在该页面的 `steps` 前执行，使用同一套可信 DSL，只能做普通输入与观察，不是关卡加载器或隐藏状态修改。旧计划无需新增字段。

Example / 示例（已有普通计数按钮；并非游戏实现模板）：

~~~json
{
  "id": "T2",
  "description": "A second increment reaches two",
  "requirement_ids": ["R1"],
  "setup_steps": [{"action": "click", "selector": "#increment"}],
  "steps": [
    {"action": "assert", "source": "state", "path": "score", "op": "eq", "value": 1},
    {"action": "click", "selector": "#increment"},
    {"action": "assert", "source": "state", "path": "score", "op": "eq", "value": 2}
  ]
}
~~~

Setup and check together must stay within 18 steps; all waits count toward the existing 45-second plan-wide budget. Check steps must contain an assertion, not only setup. Captures are shared between setup/check within one test and never between tests. Evidence actions record `stage: setup|check`.

准备及检查合计不超过 18 步，全部等待计入原有全计划 45 秒预算；检查部分必须有断言，不能只在准备部分断言。捕获值只在同一项测试内共享，不能跨测试继承；动作证据标记 `setup`／`check` 阶段。

## 3. Review before freezing / 冻结前审查

### Deterministic review / 默认确定性检查

The reviewer compares consecutive literal equality assertions before any input or time advance, preferring tests labelled `initial` as anchors. If one test expects coins=10 on a new page and another expects coins=4 before doing anything, it emits a review warning. It does not edit the plan, invent setup, solve a map, or automatically declare either expected value correct.

检查器比较输入或时间推进前的连续字面相等断言，优先使用标记为 `initial` 的测试作参照。新页面上一项要求金币 10、另一项无操作先要求 4，就给出复核提醒；不会改计划、编造准备操作、求解地图或自动判定哪一个数正确。

Read-only CLI / 只读命令，不调用 API：

~~~powershell
python -m agent inspect-plan path/to/plan.json
~~~

Exit code zero means inspection completed, not that the plan is semantically correct. / 退出码 0 只表示检查执行完成，不代表计划语义正确。

On the previous Beta 2 resource-shop plan, this detects `T5` (expected coins 4 rather than initial 10) and `T7` (expected Won rather than initial Playing). It does not detect every problem, including Sokoban/maze legality after inputs and a missing prerequisite hidden behind a capture/wait. Random or auto-changing states can also create false alarms.

对历史 Beta 2 购买升级计划，能够指出 `T5`（初始金币预期 4 而不是 10）及 `T7`（初始状态预期 Won 而不是 Playing）。它不能发现所有错误，例如输入之后的地图合法性、藏在捕获／等待后的遗漏准备；随机或自动变化的状态也可能误报。

### Optional model audit / 可选模型审查

Enable with `--plan-audit` on ordinary generation or `benchmark`. Default: off. There is at most one actual API attempt, including malformed/transport failure; no automatic audit retry. It shares the existing call/time cap and reserves a call for generation. If insufficient budget remains, record `skipped_budget` rather than pretending review happened.

普通生成或 `benchmark` 可加 `--plan-audit`，默认关闭。最多一次实际 API 尝试，格式／传输失败也计入且不自动重试；共享原调用及时间预算，预留一次生成调用。预算不足记录 `skipped_budget`，不能声称已审查。

~~~powershell
python -m agent game_design_prompt.md --plan-audit --max-calls 8
~~~

This command WOULD spend credits if run; it was not run against a paid model during this task. The auditor receives only original specification, valid draft, execution contract and deterministic warnings—never generated game code, execution feedback or held-out acceptance plans. It returns `approved`, `revised` or `unverified`.

上述命令真正运行会消费额度，本次未对付费模型执行。审查器只收到原始需求、格式有效的草稿、执行约定和确定性提醒，不会收到游戏源码、运行反馈或独立验收计划；输出 `approved`／`revised`／`unverified`。

Revisions are allowed only BEFORE generation/freezing, with a cited issue and original-spec evidence for each changed test. Requirement IDs/text/priority/verification, test IDs/coverage, state contract and manual checks are preserved. Existing assertion observations/operators cannot be removed or changed; expected values/references and ordinary setup/input sequences may be corrected. Evidence explanations are model claims, not automatically verified truth. Invalid/unverified audits stop before generation as `plan_review_required`.

只有在生成／冻结前才能修改草稿，且每个改动测试必须有具体问题和原需求依据。需求编号／文字／优先级／验收方式、测试编号／覆盖、状态接口及人工检查均保留；既有断言观察对象和比较操作不能删除或改变，可按原需求修正预期值／引用及准备／输入序列。依据说明仍是模型声明，不是自动证明。无效或未确认的审查会在生成前停止，标记 `plan_review_required`。

The draft and audit response are saved separately; only the accepted plan becomes `traces/plan.json`. Once frozen, no new mechanism changes it. Late planning recovery retains the existing stricter assertion-preservation rules and never runs this pre-generation audit against game code. Structurally invalid drafts still use the existing validation/retry/fallback path, not the semantic audit.

草稿及审查响应单独保存，仅接受后的计划成为 `traces/plan.json`。冻结后本功能不再改动它；晚期规划恢复仍遵守原有更严格的断言保留规则，不会拿游戏代码运行本次冻结前审查。格式无效的草稿仍走原有校验／重试／降级流程，不由语义审查代修。

## 4. Failure routing / 失败分流

| Evidence / 证据 | Action / 行为 |
|---|---|
| Browser/infrastructure failure / 浏览器环境失败 | Stop infrastructure handling; do not rewrite gameplay / 停止，不重写游戏规则 |
| Missing resources/runtime errors / 缺资源或运行报错 | Prioritize implementation repair / 优先修实现 |
| Failed test also has an initial-state conflict warning / 失败测试同时有初始化矛盾 | Preserve game and frozen plan; request review / 保留游戏及冻结计划，要求复核 |
| Same test/step/actual/expected/op repeats after one repair / 修复后同一断言证据完全重复 | Stop further blind repair; cause remains unverified / 停止继续盲修，原因仍未确认 |
| Optional diagnosis says test_issue/tool_limit/uncertain / 可选诊断仍有问题或不确定 | Preserve artifact; no success claim / 保留产物，不宣称成功 |
| Selected checks genuinely pass / 所选检查确实通过 | Existing completion gate; full acceptance still pending / 原完成门禁，仍非完整验收 |

Repeated-assertion stopping requires actual observed values; absent/malformed evidence is not a fingerprint. Runtime/resource/infrastructure errors take precedence. This policy is conservative: an implementation that needed more repairs might be stopped early. `plan_review_required` means unresolved, NOT that the tests are definitely wrong or the game definitely correct. If an artifact exists, it remains playable for review; if pre-generation audit stopped, no game is fabricated.

重复断言停止必须有实际观察值，缺少证据不能算指纹；资源／运行／环境错误优先处理。策略较保守，可能提前停止本来需要更多修复的实现。`plan_review_required` 表示未解决，不表示测试一定错或游戏一定对。有产物就保留供复核，生成前停止则不伪造游戏。

## 5. Validation / 验证记录

**195/195 framework tests passed, including 33 real-browser tests**, retaining all previous 160 tests. Final full run: 162.169 seconds. Coverage includes setup isolation/capture/budgets, real-browser pre-freeze revision → generation → checks, conflicting initial assumptions, conservative stop behavior, uncertain diagnosis, rejected assertion removal/operator changes, and a one-attempt audit transport policy.

**195/195 项框架测试通过，含 33 项真实浏览器测试**，保留原有 160 项；最终全量用时 162.169 秒。覆盖准备步骤隔离／捕获／预算、冻结前修订到真实浏览器验收闭环、初始状态矛盾、保守停止、不确定诊断、拒绝删断言／改操作及单次审查请求策略。模型响应全部模拟；本版本未测量付费模型审查的真实效果。

All seven prior Beta 2 artifacts passed their independent acceptance plans twice using the final Beta 3 verifier (shared 60-second budget per artifact), with all source/plan integrity checks passing and zero API calls. Artifacts: tic-tac-toe, Sokoban, memory pairs, brick breaker, resource shop, key maze and inventory delivery. Reports remain local under `runs/planning_beta3_rechecks_20261014/<case_id>_01/`. This verifies backward acceptance behavior, not new model-generated-game reliability.

用最终 Beta 3 验证器对七个历史 Beta 2 产物的独立验收各重复两次（单产物共用 60 秒），全部通过，源码／计划完整性校验全部通过，API 调用为零。包含井字棋、推箱子、记忆配对、打砖块、购买升级、钥匙迷宫及库存配送；报告本地保留于上述目录。这验证旧验收路径兼容，不是新版模型生成能力的成绩。

The prior [CAPABILITY_RESULTS.json](CAPABILITY_RESULTS.json) is left unchanged. These changes do not retroactively convert failed Beta 2 autonomous runs into successes or provide a new unseen-game success rate. Next meaningful experiment is a separately budgeted, same-model comparison with fresh requirements and `--plan-audit` on/off.

此前逐次能力评估 JSON 保持不变；本次不把 Beta 2 失败运行追认成成功，也不给出新的未知游戏成功率。下一步有意义的实验，是另定预算，用新需求、同模型比较开启／关闭 `--plan-audit` 的效果。
