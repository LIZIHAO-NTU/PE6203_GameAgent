# PlayForge — Expansion Plan / 后续扩展方案

Status: proposal only; the features below are NOT implemented by this update.

状态：仅方案。本轮只实施测试可靠性、英文需求评估和运行演练，不实施下列扩展。

## 1. Goal / 扩展目标

Expand rule and interaction coverage within offline vanilla 2D browser games. Do not equate more game names with better generalization, or add prewritten games, level solvers or game templates. Keep the existing single controller loop and independent acceptance evidence.

优先扩大二维离线网页游戏中的规则组合和交互覆盖，不用游戏名称数量代表泛化能力，不加入预写游戏、通关器或游戏模板，也不重搭多 Agent 架构。

## 2. Suggested sequence / 推荐顺序

| Stage / 阶段 | Candidate work / 候选改进 | Expected benefit / 价值 | Cost and risk / 成本与风险 | Go/no-go evidence / 验收依据 |
|---|---|---|---|---|
| 0 | Structured expected-outcome summaries and assertion agreement checks / 结构化预期摘要与断言一致性检查 | Catch contradictions between a correct short explanation and a wrong numeric assertion / 发现解释正确但数字断言写错的情况 | Medium; agreement is not proof of the game rules / 中，内部一致不等于规则正确 | New held-out arithmetic/terminal variants, no weakening of frozen tests / 新算术及终局变体，不放宽冻结验收 |
| A | Add trusted text-entry and selection actions, with validation, event logs and normal user events / 增加文本输入、选项选择动作 | Enable testing word/code puzzles and configurable rules / 验证文字、密码类谜题及可配置规则 | Low–medium; avoid arbitrary JS, secret entry or hidden answer injection / 低至中，不允许任意脚本、秘密或答案注入 | Correct/incorrect answers, empty input, reset and terminal behavior / 正误输入、空输入、重开、终局 |
| B | Improve continuous-control testing using existing keys/keys/drag plus bounded observations / 加强连续操作测试，不重复实现已有按键组合与拖动 | Explore simple platformers, aiming and trajectory games / 探索简单平台跳跃、瞄准及轨迹游戏 | Medium–high; timing and reachability are difficult / 中至高，时序和可达性难 | Normal movement, collision, failure/restart, one reachable goal; no claim from a screenshot alone / 移动、碰撞、失败重开和真实可达目标 |
| C | Evaluate richer discrete state transitions and local two-player rules / 测试复杂离散规则和本机双人玩法 | Explore small tactics, tile rotation and resource-management games / 探索小型战术、旋转拼块、资源管理 | Medium; test-oracle arithmetic and turn ordering remain weaknesses / 中，规则推演和轮次仍是短板 | Invalid-action no-op, turn ordering, resource conservation, both terminal outcomes / 非法动作、轮次、资源守恒、两类终局 |
| D | Optional development-status UI over the existing CLI / 在现有命令行之上增加可选状态界面 | Easier teammate use and presentation / 方便组员使用和展示 | Low–medium; must not obscure failures or change course-required startup / 低至中，不掩盖失败或替代老师要求的启动方式 | Clear running/completed/unverified states; links to game and traces / 状态清楚，游戏和记录易找 |
| E | Engines, networking, 3D or persistence only after scope confirmation / 确认范围后再考虑引擎、联网、三维或存储 | Potentially broader platform support / 扩大技术平台 | High; dependencies, security, deployment and course boundaries change / 高，依赖、安全、部署及课程边界均变化 | Written scope confirmation and a separate bounded proof of feasibility / 先确认范围，再单独验证可行性 |

These are planning estimates, not delivery guarantees. A game may already be generated successfully without being reliably testable by current tools.

上述成本是相对规划估计，不是工期承诺。“有时生成得出来”与“当前工具能稳定验证”必须区分。

## 3. Evaluation before expanding / 每次扩展前的验证

1. Select one new interaction or rule dimension, not several new frameworks at once.
2. Freeze 3–4 English requirements and independent checks before paying for generation.
3. Include one straightforward example, one rule variant and one mixed-mechanic example.
4. Keep the same model, caps and time budgets for comparisons; preserve first failures and absent artifacts.
5. Run the existing regression suite and previously accepted examples; check for regressions.
6. Report startup, self-plan results, independent selected checks, unresolved manual items, recovery, time and actual API attempts separately.
7. Accept a feature only when its trusted tool behavior is tested and independent outcomes show no clear regression. Small samples still do not establish a universal success rate.

每轮只扩一个交互或规则维度；事前固定英文需求和独立验收；保留首轮失败；用相同预算比较，并回归旧样例。功能可运行、Agent 自测、独立检查和人工未验收项分开统计，不能把启动或截图当作规则验收。

## 4. Model and course compatibility / 模型与课程适配

Do not select a final architecture around an unconfirmed instructor model. Once its endpoint, model ID and supported options are known, verify JSON behavior, request options, timeouts and one full fresh-directory run. Do not claim compatibility from a configured API key or doctor alone.

老师模型确定后，再验证端点、模型 ID、专用参数、JSON 输出、超时及从新目录开始的完整运行。`doctor` 只检查本地配置和浏览器，不证明模型服务可用。

## 5. Scope for the next implementation / 下一轮建议范围

The current comparison still found incorrect arithmetic assertions, including a correct textual ledger paired with a wrong expected number. Prioritize Stage 0, then A if reliability evidence permits, followed by a narrow part of B or C. Keep D optional and E deferred. Adding game categories must not bypass schema and oracle failures.

本轮仍发现数字断言错误，甚至出现文字推演正确、断言数字写错的情况。因此建议优先做 0，证据允许后再做 A，并从 B/C 中选一个小范围。D 可选、E 暂缓，不靠增加游戏类型绕过计划格式和验收预期问题。
