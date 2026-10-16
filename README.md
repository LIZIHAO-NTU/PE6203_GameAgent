# PlayForge: Build a Coding Agent That Can Build a Game

Current version: `1.0.0-beta.3` — a research beta, not a stable production release. This version adds explicit per-test setup, pre-freeze planning review and conservative failure routing. See [PLANNING.md](PLANNING.md) for behavior, defaults and limits; [CAPABILITY.md](CAPABILITY.md) preserves the earlier real-model screening.

The subsequent four-case real DeepSeek audit on/off comparison is in [AUDIT_COMPARISON.md](AUDIT_COMPARISON.md): 24 API attempts; keep audit opt-in/off by default. The agent implementation was unchanged for that evaluation.

当前版本：`1.0.0-beta.3`，定位为研究测试版，不代表生产级稳定正式版。本次增加独立准备步骤、冻结前计划审查与保守失败分流，默认值和边界见 [PLANNING.md](PLANNING.md)。[CAPABILITY.md](CAPABILITY.md) 保留此前真实模型筛查；历史记录不改写。

后续四类新需求的真实 DeepSeek 审查开关对照见 [AUDIT_COMPARISON.md](AUDIT_COMPARISON.md)：共 24 次 API 尝试，结论为暂时保持审查默认关闭；评估期间未改 Agent 实现。

PlayForge is a lightweight game-coding agent for the PE6203 group project: read a Markdown specification, generate vanilla HTML/CSS/JavaScript from scratch, run browser checks, and make bounded repairs from execution feedback.

PlayForge 是用于 PE6203 小组项目的游戏开发 Agent：读取 Markdown 需求，从空目录生成原生 HTML/CSS/JavaScript 游戏，自动打开浏览器检查，再根据真实反馈有限次修复。

**Core gameplay before visual polish.** No prewritten game implementations, game templates or built-in solvers. The four benchmark families are evaluation samples, not the only games the agent can generate.

目标是**先实现可启动、规则清楚的核心游戏，再考虑美化**。没有预写游戏代码、游戏模板或内置通关器。四类测试游戏只是评估样本，不是生成器只能选择的四个类型。

This is a research beta, not a guarantee of success on arbitrary unseen games. Scope: offline 2D browser games; historical tests include single-player games and local two-player tic-tac-toe, not networked multiplayer, 3D, backends or complex engines.

当前为研究测试版，不保证任意未知游戏稳定完成。范围是离线二维网页游戏；已测包含单人玩法和本机双人井字棋，不含联网多人、3D、后端或复杂引擎。

### Game UI language / 游戏界面语言

Player-facing text defaults to **English**, even when the specification is written in another language. An explicit UI language requirement takes precedence, including bilingual or per-element instructions. Exact required display strings are preserved unless translation is explicitly requested. Technical identifiers, selectors, state keys and contract values are not translated. Planning, optional pre-freeze review and code generation/repair share this policy; frozen tests remain unchanged. No language switcher is added unless requested. This is a prompt policy, not a guarantee of model compliance; verify the generated UI. Existing saved games are unaffected.

游戏标题、规则、按钮、提示及可访问性标签默认使用**英文**，不根据需求正文的语言自动切换。需求明确指定界面语言时优先遵从，包括双语或特定元素的语言要求；要求原样显示的文字保留原文，除非明确要求翻译。技术标识、选择器、状态字段及接口约定值不翻译。规划、可选冻结前审查、代码生成及修复共用此规则，不改动已冻结测试；未要求时不增加语言切换器。这是提示词规则，不保证模型每次都遵从，仍需检查生成界面；不影响已保存游戏。

Language smoke checks (2026-10-14): a Chinese specification without a UI-language instruction produced English text; an English specification requesting Simplified Chinese produced Chinese text while preserving the exact button label `Again`. Both generated artifacts passed independent language and basic-play checks. Six real DeepSeek API attempts were used in total, including an initial default-language run blocked by a plan-schema error followed by a transport timeout; that blocked run is not counted as a success. These are small smoke checks, not a general compliance rate. Temporary test games were removed. Four prompt-wiring tests were added: the final full regression passed 199/199 tests, including 33 real-browser tests. The first full run had two browser errors (including a screenshot timeout); the affected 29-test group and subsequent full rerun passed without code or test-standard changes.

语言冒烟检查（2026-10-14）：中文需求未指定界面语言时生成英文；英文需求指定简体中文时生成中文，并保留指定按钮文字 `Again`。两份产物均通过独立语言及基本玩法检查。总计 6 次真实 DeepSeek API 尝试，包含第一次默认语言测试中计划格式错误后的请求超时；该次阻断不计为成功。这是小样例检查，不是普遍遵从率；临时测试游戏已清理。新增 4 项提示词接入测试，最终全量回归 199/199 通过，含 33 项真实浏览器测试。首轮出现两项浏览器异常（含截图超时），随后对应 29 项测试组及完整套件复跑均通过，期间未修改代码或放宽验收。

## 1. How it works / 系统如何工作

Version 1.0 Beta 3 keeps one controller loop, with draft review before freezing and explicit setup on each fresh test page. See [INTEGRATION.md](INTEGRATION.md) for the integration baseline and [PLANNING.md](PLANNING.md) for the latest changes.

1.0 Beta 3 保持同一条 Agent Loop，加入冻结前草稿审查及每项测试的显式初始化。整合基线与最新改进分别见上述双语文档。

~~~text
Spec → Plan → Generate → Browser verification → Bounded repair
                         Save the better version and traces

读取需求 → 规划需求与固定测试 → 生成文件 → 浏览器运行与检查
                                  ↑              ↓
                                  └── 失败反馈与有限修复
                                                 ↓
                                     保存较好版本和执行记录
~~~

- **Model / 模型**: understands requirements, plans, generates and edits code via a DeepSeek-compatible API. 理解需求、规划、生成及修改代码，当前沿用 DeepSeek 兼容接口。
- **Tools / 工具**: validated file writes, page loading, keyboard/mouse input and DOM/state observations. 执行文件写入、浏览器加载、键盘／鼠标操作及状态、DOM 检查。
- **Loop / Harness**: validation, budgets, logs, version selection and stopping conditions. 控制参数校验、预算、日志、版本选择和停止条件。
- **Repair memory / 修复记忆**: recent failures and passed checks, continuing from a better version; not cross-task learning. 保留近期失败和通过项，从较好版本继续，不是跨任务长期学习。
- **Planning fallback / 规划降级**: may generate the original-spec game after invalid planning, but only claims startup evidence; disabled by `--strict-plan`. 功能计划校验失败时仍可按原需求生成，但只检查启动，明确标记功能未验收。
- **Planning recovery / 规划恢复**: one budget-bounded recovery request after startup, then freeze, retest and repair; startup evidence is not reused as functional success. 启动后在预算内尝试一次恢复，成功后冻结新计划并复测、修复，不能沿用启动成绩。
- **Completion gate / 质量门禁**: complete test evidence and input-followed-by-rule assertions, plus DOM/state consistency checks. 检查证据完整性及操作后的核心规则断言，支持画面／状态一致性检查。See / 详见 [QUALITY.md](QUALITY.md) (Chinese / 中文)。

## 2. Installation and configuration / 安装与配置

Requires Python 3.10+, a model API account and a Playwright browser. Run these Windows PowerShell commands from the repository root.

需要 Python 3.10+、模型 API 账户及 Playwright 浏览器。以下为 Windows PowerShell 示例，所有命令在仓库根目录执行：

~~~powershell
git clone https://github.com/LIZIHAO-NTU/PE6203_GameAgent.git PlayForge
cd PlayForge
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m playwright install chromium
./.venv/Scripts/python.exe -m agent configure
~~~

Enter your own API key; input is hidden. The command writes a local plaintext `.env`, which is Git-ignored, without calling the model. It refuses to overwrite an existing `.env`; edit that file locally. Never share keys or account passwords.

配置时按提示输入自己的 API key，输入不显示，配置写入本机明文 `.env`（Git 已忽略），不调用模型。已有 `.env` 时直接在本机编辑；`configure` 不会覆盖现有配置。不要分享 key 或账户密码。

Explicit virtual-environment interpreter paths avoid installing dependencies into another Python; activation is unnecessary. On macOS/Linux, use `./.venv/bin/python`. Browser regression testing was performed on Windows with Edge.

使用完整虚拟环境解释器路径，无需激活环境，避免依赖装到另一个 Python。macOS/Linux 可替换为 `./.venv/bin/python`；本次浏览器实测环境为 Windows + Edge。

| Setting / 配置项 | English | 中文 |
|---|---|---|
| `DEEPSEEK_API_KEY` | Your key; `LLM_API_KEY` is also supported and takes precedence. | 自己的密钥；也支持 `LLM_API_KEY`，后者优先。 |
| `LLM_BASE_URL` / `LLM_MODEL` | Endpoint and a model ID available to your account. | 服务地址与自己账户实际可用的模型 ID。 |
| `LLM_THINKING` | DeepSeek-specific; usually leave blank for other providers. | DeepSeek 专用选项；其他兼容服务通常需留空。 |
| `LLM_JSON_MODE` | Request JSON output only if the endpoint supports it. | 是否请求 JSON 输出，需与接口能力匹配。 |
| `LLM_MAX_TOKENS` / `LLM_TIMEOUT_SECONDS` | Per-request output and timeout limits, not whole-task budgets. | 单次输出和超时上限，不是整个任务预算。 |
| `PLAYWRIGHT_CHANNEL` | Blank: Playwright Chromium; `msedge`: installed Edge. | 留空使用 Playwright Chromium；`msedge` 使用已安装的 Edge。 |
| `PRICE_*` / `PRICE_CURRENCY` | Optional prices; without them, report tokens, not invented costs. | 可选计价；不填则记录 token，不编造费用。 |

See [.env.example](.env.example). Historical tests used `deepseek-flash`; this is a recorded configuration, not a promise that every account supports it. Other providers may need option adjustments. Compatibility with the instructor's final model remains to be tested.

详细配置格式见 [.env.example](.env.example)。本次实测使用 `deepseek-flash`，这只是当时配置，不承诺所有账户可用。更换兼容服务可能需要调整专用选项；老师最终指定模型后的兼容性仍需测试。

Environment check — no paid API call / 环境检查——不调用付费 API：

~~~powershell
./.venv/Scripts/python.exe -m agent doctor
~~~

`doctor` checks local configuration, dependencies and browser availability. **It does not verify key validity, balance or model-provider connectivity.**

`doctor` 检查配置是否存在、依赖及浏览器能否使用，**不验证 key 有效性、余额或模型服务可达性**。

## 3. Generate and play / 生成与试玩

~~~powershell
./.venv/Scripts/python.exe -m agent game_design_prompt.md
~~~

**Planning, generation and repair consume API credits.** Defaults: 3 generation/repair rounds including the first version, 8 API attempts, and a 600-second task budget; each browser verification defaults to 60 seconds. Planning, recovery, formatting retries and transport retries all share the API-attempt cap.

**规划、生成和修复会消费 API 额度。**默认最多 3 轮生成／修复（含首次生成）、8 次 API 尝试、600 秒任务预算；单轮浏览器验证默认最多 60 秒。规划、恢复、格式重试和网络重试共用调用上限，可能提前耗尽预算。

Example with an explicit specification and budget / 指定需求与预算的示例：

~~~powershell
./.venv/Scripts/python.exe -m agent examples/benchmark/sokoban.md --max-rounds 3 --max-calls 5 --max-seconds 360
~~~

Describe controls, initial state, legal/illegal actions, scoring or win/loss, restart behavior and technical constraints. Do not include keys or private data; you do not need to write a JSON plan.

需求应说明操作、初始状态、合法／非法动作、计分或胜负、重开行为和技术约束。不要写入 key 或隐私数据；不需要自己编写 JSON 计划。

`--output` selects a new output directory and never overwrites existing results; `--headful` shows the test browser; `--strict-plan` stops after functional planning fails instead of generating a partial result.

`--output` 可指定新输出目录，已有目录不会覆盖；`--headful` 显示自动测试浏览器；`--strict-plan` 在功能规划失败后停止，不生成部分结果。

### Reliability options / 稳定性选项

| Option / 参数 | Default / 默认 | Behavior / 行为 |
|---|---|---|
| `--repair-mode auto` | `auto` | Version-bound changed-file repair; full responses still accepted / 按版本哈希局部改文件，仍接受完整输出。 |
| `--repair-mode full` | Optional / 可选 | Preserve whole-project repair responses / 保留完整项目修复路径。 |
| `--verify-repeats 2` | `1` | All repeats must pass within one shared test-timeout / 重复必须全通过，共用单次验证预算。 |
| `--diagnose` | Off / 关闭 | At most one diagnosis API attempt for ambiguous failure, within the shared cap / 模糊失败时最多一次诊断调用，占原预算。 |
| `--syntax-check` | Off / 关闭 | Trusted Node checks for external JS; missing/incomplete checks are labelled / 可选 Node 外部 JS 语法检查，未运行或不完整会注明。 |
| `--lessons runs/lessons.json` | Off / 关闭 | Opt-in generic recovery observations, not game source or test answers / 可选通用修复经验，不保存游戏源码或测试答案。 |

Example for stronger repeatability (generation is still paid; no hidden API allowance):
较强复测示例（生成仍付费，不增加隐藏调用额度）：

~~~powershell
./.venv/Scripts/python.exe -m agent examples/benchmark/sokoban.md --max-calls 8 --repair-mode auto --verify-repeats 2 --lessons runs/lessons.json
~~~

Repetitions use fresh browser contexts and may take longer or expose intermittent failures; real-time scheduling is not guaranteed identical. Keep optional diagnosis off for the cheapest baseline. Compare features under the same model/spec/budget before claiming reliability improvements.

重复使用新的浏览器上下文，可能耗时更长或暴露偶发失败，不保证实时调度完全一致。低成本基线可保持诊断关闭；需在相同模型、需求和预算下比较配置，才能判断是否真的改进。

Each run creates a new `runs/<run_id>/` / 每次结果位于新目录：

~~~text
game/          Generated game source / 自动生成的游戏源码
traces/        Plans, API records, versions and evidence / 计划、API 记录、版本与证据
summary.json   Results and usage / 结果与用量
REPORT.md      Findings and manual checks / 报告与人工复核待办
~~~

Replace the placeholder with the printed run directory / 用终端输出的实际目录替换占位符：

~~~powershell
./.venv/Scripts/python.exe -m agent serve "runs/<run_id>/game"
~~~

Open the [local game page](http://127.0.0.1:8000/). Serving and playing do not call the model; input does not consume API credits per frame. If occupied, add `--port 8001` and use that port. Stop with Ctrl+C.

打开 [本地游戏页面](http://127.0.0.1:8000/)。`serve` 和玩家操作不调用模型；按键不会逐帧消费 API。端口被占用可追加 `--port 8001`，访问对应端口。服务用 Ctrl+C 停止。

Read `REPORT.md` and `summary.json`; opening a page or checking an exit code alone is not functional acceptance.

不要只看退出码或页面能否打开。先读 `REPORT.md` 和 `summary.json`：

| Status / 状态 | English | 中文 |
|---|---|---|
| `automated_passed_manual_pending` | Selected automated checks passed; full acceptance remains pending. | 所选自动检查通过，完整游戏仍待验收。 |
| `checks_failed` | Checks failed; a better launchable version may be preserved. | 检查失败，可能保留了可启动的较好版本。 |
| `plan_review_required` | Review is unverified, a failed test has an initialization conflict, or repair/diagnosis remains inconclusive. No success claim; an existing game is preserved. | 审查未确认、失败测试有初始化矛盾或修复／诊断仍不明确；不算成功，有游戏则保留。 |
| `partial_game_plan_failed` | Functional planning/recovery failed; startup-only evidence. | 功能规划／恢复失败，仅检查启动。 |
| `partial_game_evidence_missing` | Valid format, insufficient core-interaction evidence. | 计划格式有效，但核心交互证据不足。 |
| `unsupported_spec` | Outside the current scope; no silent substitution. | 超出当前范围，未擅自换技术实现。 |
| `budget_exhausted` / `run_error` / `generation_failed` | Budget, execution or generation failure; inspect the report. | 预算、运行或生成失败，查看报告。 |
| `interrupted` | Interrupted; not a completed autonomous run. | 运行中断，不算完整自主完成。 |

## 4. Multi-game benchmark — paid / 多类型游戏评估——付费

~~~powershell
./.venv/Scripts/python.exe -m agent benchmark examples/benchmark/suite.json --max-total-calls 20 --max-calls-per-case 5
~~~

One run per family by default; these families exercise different mechanics / 默认每类一次，测试不同底层机制：

| Game / 游戏 | Mechanics / 机制 |
|---|---|
| Tic-tac-toe / 井字棋 | Turns, legal moves, victory and terminal state / 回合、合法落子、胜负与终止状态 |
| Sokoban / 推箱子 | Grid movement, obstacles and pushing constraints / 网格移动、障碍与推动约束 |
| Memory pairs / 记忆配对 | Hidden information, matching, delays and input locks / 隐藏信息、匹配、延时与输入锁定 |
| Brick breaker / 打砖块 | Continuous motion, collision, pause and reset / 连续运动、碰撞、暂停与重置 |

`--max-total-calls` caps batch API attempts including retries, not money. `--max-calls-per-case` limits each run; `--repeats 2` repeats cases; benchmark `--max-seconds` is per case. Cases without enough budget remain recorded as skipped.

`--max-total-calls` 是整个批次的 API 尝试上限（包含重试），不是金额上限。`--max-calls-per-case` 限制单次用例；`--repeats 2` 可重复测试；此命令的 `--max-seconds` 表示每次用例的时间上限。预算不足的用例记录为 skipped。

Prewritten held-out checks are not given to the generation model or fed into that run's repairs. Reports separate startup, model-plan and independent-check results. These checks are not exhaustive; some observe game-supplied read-only state.

每个用例有预先编写的独立检查，不提供给生成模型，也不用于本轮修复。报告分别统计启动、模型计划和独立检查；独立检查仍非完备证明，部分观察依赖游戏提供的只读状态。

Reports: `runs/benchmark_*/BENCHMARK.md` and `benchmark.json`; games: `cases/<case_id>/game/`; independent evidence: `acceptance/<case_id>/`. Use the corresponding game directory with `serve`.

结果位于 `runs/benchmark_*/BENCHMARK.md` 和 `benchmark.json`，游戏在 `cases/<case_id>/game/`，独立证据在 `acceptance/<case_id>/`。试玩时把 `serve` 的目录换成对应 `game/`。

Add new specifications and acceptance plans under `examples/benchmark/` and register them in `suite.json`; do not inject ready-made game implementations.

新增需求、独立验收计划可放在 `examples/benchmark/` 并登记到 `suite.json`，不要注入现成游戏实现。

`examples/benchmark/capability_suite.json` contains six simple mechanic families; `transfer_suite.json` adds one inventory/capacity variant. They are evaluation fixtures, not game templates. Benchmark reports now expose scheduled/attempted/evaluated counts and self/independent disagreements; absent evaluation must not be presented as a gameplay failure or silently omitted. Frozen specification/acceptance hashes are checked before and after evaluation.

`capability_suite.json` 包含六类简单机制，`transfer_suite.json` 另测一个库存／容量变体，均为评估样例而非游戏模板。报告区分预定、已尝试、已独立验收及两种验收分歧；缺少验收不能被当成玩法失败或悄悄排除。运行前后校验冻结需求／独立计划的哈希。

## 5. Offline rechecks and metrics / 零 API 复测与统计

Replay an existing run using its recorded active plan, without model calls or changes to its score:
根据原运行记录的活动计划回放，不调用模型、不改写原成绩：

~~~powershell
./.venv/Scripts/python.exe -m agent replay "runs/<run_id>" --verify-repeats 2
~~~

Use `recheck` to select another explicit plan. Repetitions share `--timeout` (default 60 seconds). Evidence includes replay manifests, source hashes, actual actions and before/after screenshots. Screenshots are retained observations, not an automatic visual verdict.

需另选计划时使用 `recheck`。重复检查共用 `--timeout`（默认 60 秒）；证据包含回放清单、源码哈希、实际动作及前后截图。截图是保留的观察证据，不等于自动视觉验收。

Replay an existing game without editing it or overwriting its original score / 复测已有游戏，不修改游戏、不改写原始开发成绩：

~~~powershell
./.venv/Scripts/python.exe -m agent recheck "runs/<run_id>/game" --plan "runs/<run_id>/traces/plan.json"
~~~

Reusing the model's plan does **not** make this independent acceptance. Write independent checks separately. Results go to `rechecks/`; Playwright is required, but no model is called. If `summary.json` has `active_plan: functional_plan.json`, use `traces/functional_plan.json` instead; the original `plan.json` retains startup fallback checks.

以上复用原模型计划，**不因此成为独立验收**；独立检查需另行编写并适配该游戏。复测结果位于 `rechecks/`，不调用模型，但仍需 Playwright。若 `summary.json` 中 `active_plan` 为 `functional_plan.json`，应把 `--plan` 改为对应的 `traces/functional_plan.json`；原 `plan.json` 保留的是启动降级计划。

Aggregate ordinary runs into JSON/CSV / 汇总普通运行，生成 JSON/CSV：

~~~powershell
./.venv/Scripts/python.exe -m agent summarize runs
~~~

This command makes no model calls and reads only immediate child runs. For benchmarks, summarize `runs/<benchmark-directory>/cases` or read `benchmark.json`. Do not claim a controlled comparison across mixed models, prompts, specifications or budgets.

该命令不调用模型，只汇总指定目录的直接子运行。benchmark 应汇总 `runs/<benchmark目录>/cases`，或直接读该批次的 `benchmark.json`。不要混合模型、提示词、需求和预算来声称受控实验结果。

## 6. Tests and recorded results / 框架测试与实测记录

Initial Beta 3 implementation validation used simulated models, real browsers and read-only historical artifacts, with zero paid API calls; see [PLANNING.md](PLANNING.md). A subsequent fixed-version, four-case real-model comparison is recorded separately in [AUDIT_COMPARISON.md](AUDIT_COMPARISON.md). Do not reuse Beta 2 paid results or either small sample as a general Beta 3 success rate.

Beta 3 初次实施验证使用模拟模型、真实浏览器及历史产物只读复测，付费 API 为零，详见 [PLANNING.md](PLANNING.md)。之后固定版本的四类真实模型对照单独记录于 [AUDIT_COMPARISON.md](AUDIT_COMPARISON.md)。不能把 Beta 2 成绩或这些小样本当作 Beta 3 的普遍成功率。

Version 1.0 Beta 2 has a small real DeepSeek screening documented in [CAPABILITY.md](CAPABILITY.md): 13 generations across baseline, optimized and new-variant batches, using 47 API attempts. These small deterministic fixtures do not establish arbitrary unseen-game reliability. Earlier 0.5/0.4/0.3 records below retain their original scope.

1.0 Beta 2 的小型真实 DeepSeek 筛查详见 [CAPABILITY.md](CAPABILITY.md)：基线、优化及新变体三批共生成 13 次，消耗 47 次 API 尝试。这些简单确定性样例不能证明任意未知游戏可靠完成。下方 0.5／0.4／0.3 记录保留当时口径。

Framework tests use mock model responses and spend no API credits / 框架测试使用模拟模型，不消费 API 额度：

~~~powershell
./.venv/Scripts/python.exe -B -m unittest discover -s tests -v
~~~

Real-browser tests are skipped by default. Enable the full suite / 默认跳过真实浏览器测试，完整回归使用：

~~~powershell
$env:MVP_BROWSER_TESTS="1"
$env:PLAYWRIGHT_CHANNEL="msedge"
./.venv/Scripts/python.exe -B -m unittest discover -s tests -v
~~~

Leave `PLAYWRIGHT_CHANNEL` blank for Playwright Chromium. Temporary test artifacts belong in `.codex-tmp/`; remove only your task's temporary files, not someone else's work.

使用 Playwright Chromium 时将 `PLAYWRIGHT_CHANNEL` 留空。临时测试产物位于 `.codex-tmp/`；任务结束后清理本次临时文件，不误删其他人的材料。

### Version 1.0 Beta 3 — 2026-10-14 / 当前版本验证

**195/195 framework tests passed, including 33 real-browser tests.** All prior 160 tests remain. This initial framework validation used zero paid API calls; the later paid comparison did not change agent code or rerun this suite.

**195/195 项框架测试通过，含 33 项真实浏览器测试**，保留原有 160 项。该初次框架验证未调用付费 API；后续付费对照未改 Agent 代码，也未重跑该全量套件。

See [PLANNING.md](PLANNING.md) for regression and read-only replay results. The audit is opt-in (`--plan-audit`), consumes at most one actual API attempt from the existing cap, and runs only before game generation/freezing. `inspect-plan` is zero-API.

回归及只读复测记录见上述文档。`--plan-audit` 默认关闭，最多占用原预算内一次实际 API 尝试，仅在生成游戏和冻结计划前运行；`inspect-plan` 不调用模型。

### Version 1.0 Beta 2 — 2026-10-14 / 历史版本框架验证

**160/160 tests passed, including 27 real-browser tests.** All 143 previous tests are retained. These framework tests simulate model responses and are separate from the paid capability screening.

**160/160 项测试通过，含 27 项真实浏览器测试。**原有 143 项全部保留。框架测试使用模拟模型，与真实付费能力筛查分开统计。

### Version 0.5 baseline — 2026-10-14 / 历史整合基线验证

**143/143 regression tests passed, including 24 real-browser tests.** All 109 previous tests remain passing. Composed-feature and full/auto compatibility tests use simulated models and real browser interactions, not paid-model generation.

**143/143 项回归通过，含 24 项真实浏览器测试。**原有 109 项均保持通过。组合功能及完整／局部修复对照使用模拟模型与真实浏览器，不是付费模型生成成绩。

Validation and composed-feature checks are documented in [INTEGRATION.md](INTEGRATION.md). No paid DeepSeek experiment has been performed for 0.5; historical game results below are not its success rate.

验证记录与组合功能测试详见上述文档。0.5 未做付费 DeepSeek 实验，以下历史游戏成绩不代表当前版本成功率。

### Version 0.4 — 2026-10-14 / 历史版本验证

- **109/109 framework tests passed, including 21 real-browser tests.** This is not a model-generated-game success rate. **109/109 项框架测试通过，含 21 项真实浏览器测试**，不是模型生成游戏的成功率。
- Read-only historical Sokoban replay caught stale state and a missing win transition: original 1/3 checks, previously repaired version 3/3. Games and original scores were unchanged. 只读复放历史推箱子检出过期状态与通关判定问题：原始版 1/3，此前修复版 3/3；未改游戏与原始成绩。

Method and limitations / 方法与限制：[QUALITY.md](QUALITY.md)。

### Version 0.3 — 2026-10-10 / 历史版本实测

- **83/83 framework tests passed**, including real-browser tests, not paid-model generation success. **83/83 项框架测试通过**，含真实浏览器，不代表真实模型游戏成功率。
- **20 DeepSeek API attempts** across two iterative batches. In the refined batch, two tic-tac-toe runs, two Sokoban runs and one memory-pairs run launched, each passing 5/5 selected independent checks. 共 **20 次调用**；修正批次中井字棋、推箱子各两次，记忆配对一次可启动，各通过 5/5 所选独立检查。
- Brick breaker failed planning and was not generated; some model-authored expectations were incorrect. 打砖块规划失败，未生成，不能算通过；部分模型自编测试预期也有错误。
- The final 0.3 fallback and sequence-self-check changes were framework-tested but not paid-retested in these batches. 0.3 最终规划降级路径和测试序列自检提示在上述批次中仅完成框架验证，未付费重测。
- No controlled old-version baseline exists; do not claim improvement percentages or unseen-game reliability. 没有旧版本受控对照，不能声称提升百分比或保证未知玩法稳定成功。

See [GENERALIZATION.md](GENERALIZATION.md) for historical methodology. Raw `runs/` remain local and are not uploaded; a fresh clone has no historical generated games or logs.

完整方法、失败与统计口径见 [GENERALIZATION.md](GENERALIZATION.md)。原始 `runs/` 只保存在测试者本机，不随 GitHub 上传；新克隆仓库没有这些游戏和日志，需自行运行生成。

## 7. Structure and collaboration / 项目结构与协作

~~~text
agent/                 Controller, prompts and verification / 控制程序、提示词与验证
examples/              Specs and independent plans, not templates / 需求与独立计划
tests/                 Zero-paid-API regression tests / 零付费 API 回归
game_design_prompt.md  Default specification / 默认需求
.env.example           Shareable config without keys / 不含密钥的配置格式
GENERALIZATION.md      0.3 design and historical evidence / 0.3 设计与历史证据
UPGRADE.md             0.2 historical notes / 0.2 历史说明
CHANGELOG.md           Version history / 版本记录
QUALITY.md             0.4 gates, recovery and limitations / 0.4 门禁、恢复与限制
INTEGRATION.md         Integrated reliability baseline / 可靠性整合基线
CAPABILITY.md          Beta 2 capability screening and limits / Beta 2 能力筛查与短板
CAPABILITY_RESULTS.json Sanitized run-level evidence / 脱敏逐次评估证据
PLANNING.md            Beta 3 setup, review and routing / Beta 3 初始化、审查与分流
AUDIT_COMPARISON.md    Fixed-version real-model audit comparison / 固定版本真实审查对照
AUDIT_COMPARISON_RESULTS.json Sanitized comparison evidence / 脱敏对照证据
~~~

- Each teammate creates their own environment and `.env`; never copy another person's key. 每个成员创建自己的环境和 `.env`，不复制他人的 key。
- Share source, specs, tests and documentation, not secrets, raw logs, virtual environments or caches. Logs may contain full prompts and source; redact before sharing. 共享源码、需求、测试和文档，不共享密钥、原始日志、虚拟环境或缓存；分享日志前脱敏。
- Synchronize before editing. Prompts live in `agent/prompts.py`; rerun regression after changing prompts, tools or acceptance, recording version and budget. 修改前先同步；修改提示词、工具或验收后跑回归，记录版本和预算。
- Separate game defects, test defects and tool limitations; never fake state or lower original requirements to pass. 区分游戏错误、测试错误与工具限制，不伪造状态或降低原始要求。
- No manual code edits during autonomous development; playtesting follows the run. The instructor's final rules take precedence. 自动开发期间不人工修代码，试玩在结束后进行；正式展示以老师最终规则为准。

## 8. Troubleshooting and limits / 常见问题与限制

### Export a run / 导出运行结果

~~~powershell
./.venv/Scripts/python.exe -m agent export-run "runs/<run_id>" --output "submissions/<name>" --report "path/to/report.pdf"
~~~

This zero-API command copies the current agent, pinned requirements and exact `game/` / `traces/` into a new directory. It excludes local `.env`, dependencies and caches. `--report` must point to your existing PDF; omit it only for an incomplete draft package. The delivery manifest distinguishes current-agent and original-run versions. Inspect traces for private content before sharing.

此零 API 命令将当前 Agent、固定版本依赖及原样 `game/`、`traces/` 复制到新目录，不复制本地 `.env`、依赖环境和缓存。`--report` 指向自己已有的 PDF；省略则仅是缺报告的草稿包。清单区分当前 Agent 与原运行版本，分享前检查 traces 中的私人内容。

Exporting does not turn an old or assisted run into a valid autonomous course demonstration. Final live-run commands and course requirements still need confirmation.

导出不会把历史或经过额外协助的运行变成合格的自主现场展示；正式启动方式和课程规则仍需确认。

- **Playwright missing / 找不到依赖**: install and run with the same `.venv` interpreter. 用同一个 `.venv` 解释器安装并运行。
- **Browser unavailable / 浏览器不可用**: install Chromium, or set `PLAYWRIGHT_CHANNEL=msedge`, then run `doctor`. 安装 Chromium，或设置 Edge 通道后运行 `doctor`。
- **API 401/403, missing model or balance / API 或余额问题**: check your own provider account; `doctor` does not verify these. Never expose keys in screenshots. 检查账户配置；`doctor` 不验证这些，不要在截图中暴露密钥。
- **Output already exists / 目录已存在**: choose a new `--output`; old results are protected. 更换新的输出目录，不覆盖旧结果。
- **Page opens but checks fail / 能打开但检查失败**: inspect failed steps; rules, test expectations or interaction strategy may be wrong. Preserve failures. 阅读失败步骤，区分规则、测试或操作策略问题，保留失败记录。
- **Empty cost / 费用为空**: pricing was not configured, not free. Failed/time-out requests may be billed; provider billing is authoritative. 未配置价格，不是免费；失败或超时请求也可能计费，以服务商账单为准。

No networked games, 3D, complex prescribed engines, arbitrary package installation or unrestricted shell execution. Generated code is untrusted; browser/network restrictions are not an audited OS sandbox. Final course API compatibility, scope and required `game/` / `traces/` submission layout must still be aligned with the instructor's requirements; `runs/` is the current development/evaluation layout.

不支持联网、3D、复杂指定引擎、任意包安装或自由命令执行。生成代码不可信，现有浏览器和网络限制不是经过审计的 OS 沙箱。最终课程 API、未知需求范围和 `game/`、`traces/` 提交布局仍需按正式要求对齐；当前 `runs/` 用于开发评估。
