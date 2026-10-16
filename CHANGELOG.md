# PlayForge Changelog / 版本记录

## 1.0.0-beta.4 — 2026-10-16

- Add trusted `assert_stable` with bounded live samples, wait-budget accounting and immutable assertion protection during plan audit/recovery. It checks sampled equality, not continuous stability or full gameplay correctness.
- 新增受控 `assert_stable`：操作后有界采样、计入等待预算，审查及恢复不得放宽冻结检查；只证明采样时刻一致，不代表完整规则正确。
- Request a short original-spec quote and expected-outcome basis per test; validate supplied metadata and warn about unmatched quotes. Legacy plans remain compatible; model explanations are not ground truth.
- 每项测试请求简短原需求引文和预期依据；校验已提供字段，对不匹配引文提醒，兼容旧计划；模型解释不作为真值。
- Flag potentially stale real-time equality captures across input events; only a corresponding actual failure triggers conservative review, and runtime/infrastructure errors retain priority.
- 对跨输入的实时旧快照相等比较给出启发式提醒，相关测试实际失败才停止盲修，运行及环境错误仍优先处理。
- Add new English requirements, independent checks, a bounded comparison and a single-command rehearsal. Preserve failures and scope limits; see [TEST_RELIABILITY.md](TEST_RELIABILITY.md). [EXTENSION_PLAN.md](EXTENSION_PLAN.md) is proposal only.
- 新增英文需求、独立检查、有上限对照及单命令演练；保留失败与边界，后续扩展只写方案、不实施。

## 1.0.0-beta.3 — 2026-10-14

- Add optional per-test `setup_steps` using the trusted input/observation DSL on each fresh page. Setup and check share one 18-step cap and existing wait budgets; checks still require assertions. Preserve legacy plans, record action stages, and protect setup assertions during late recovery.
- 新增每项测试的独立准备步骤，与检查共用原有步骤／等待预算，仅用普通输入和观察；兼容旧计划，记录动作阶段，晚期恢复不得修改冻结的准备断言。
- Add zero-API initial-state contradiction inspection and opt-in, one-attempt `--plan-audit` before game generation/freezing. Review sees only specification/draft, preserves requirement/test coverage and assertion observation/operator shapes, records original/revised plans, and cannot edit frozen acceptance. `inspect-plan` exposes read-only inspection.
- 新增零 API 初始状态冲突检查及可选单次冻结前模型审查；只看需求／草稿，保留需求责任、测试覆盖及断言观察／操作，保存草稿／修订，不能改冻结验收。
- Route failed initialization conflicts, repeated identical assertion evidence and uncertain diagnosis to `plan_review_required`, retaining artifacts without manufacturing success. Runtime/infrastructure failures remain distinct; conservative stopping can also stop a real implementation bug early.
- 对初始化矛盾、修复后相同断言及不确定诊断停止盲修，保留产物但不算成功；区分运行／环境错误，明确保守停止可能提前终止真实代码缺陷的修复。
- 195/195 tests passed, including 33 real-browser tests; all previous 160 retained. No paid API calls or new real-model effectiveness claims. See [PLANNING.md](PLANNING.md).
- 195/195 项测试通过，含 33 项真实浏览器测试，保留原有 160 项；未调用付费 API，不声称真实模型效果已提升，详见上述双语说明。

## 1.0.0-beta.2 — 2026-10-14

- Conduct a bounded real-model capability screening with DeepSeek: six baseline cases, six optimized cases and one new inventory/capacity variant; 47 API attempts in total. Preserve failures and distinguish self-authored tests from held-out checks. See [CAPABILITY.md](CAPABILITY.md).
- 使用 DeepSeek 完成有上限的真实能力筛查：六次基线、六次优化复测及一次库存／容量新变体，共 47 次 API 尝试。保留失败，区分自测与独立验收。
- Fix observation interoperability for literal dotted snapshot keys; retain nested paths and fail closed on conflicting representations. Clarify nested snapshots, bounded waits and spec-derived test expectations in prompts. Add missing requirement IDs to planning-validation feedback; never weaken frozen assertions.
- 修复扁平点路径状态快照兼容，保留嵌套路径，对冲突值拒绝验收；澄清快照、等待上限和按需求推演测试的提示，校验反馈指出遗漏需求编号，不放宽冻结断言。
- Extend benchmark reporting with evaluation denominators, disagreement counts, run fingerprints and frozen-source integrity checks. Record errors during independent evaluation without losing API accounting. Add evaluation-only fixtures, no prewritten game implementation.
- 增加独立验收分母、分歧计数、运行指纹及冻结文件完整性检查；独立评估阶段的错误保留调用计数。新增评估需求与计划，不预写游戏实现。
- 160/160 framework tests pass, including 27 real-browser tests; all 143 previous tests remain. Small-sample results do not prove generalization or cost improvement. Planning semantics and fresh-page setup remain important limitations.
- 160/160 项框架测试通过，含 27 项真实浏览器测试，保留原有 143 项。小样本不证明泛化或成本提升；测试语义及每项测试独立初始状态仍是重要短板。

## 1.0.0-beta.1 — 2026-10-14

- Rename the 0.5 development snapshot to **1.0 Beta 1**, reflecting the integrated research-beta stage; no functional changes in this version-label update.
- 将 0.5 开发快照更名为 **1.0 Beta 1**，表示核心流程已成型、进入研究测试阶段；本次版本标记调整不新增功能。
- Synchronize runtime version and bilingual documentation. Preserve historical version labels and validation records; this is not a stable-release or unseen-game reliability claim.
- 统一运行版本标记及双语文档，保留历史版本和验证记录；不声称达到稳定正式版或保证未知游戏成功率。

## 0.5.0 — 2026-10-14

- 在原单 Agent Loop 中整合按哈希绑定的局部文件替换，兼容完整输出，校验失败可退回完整模式；拒绝删除、路径越界和错误基础版本。
- 增加本地资源结构检查、可选可信 Node 语法检查与保守的通过项防退化选优。
- 增加确定性失败分流、默认关闭且最多一次额外尝试的模型诊断；所有调用仍在原预算内。
- 增加共享超时的全通过重复验证、只读时间序列采样、前后截图、回放清单及源码／运行环境指纹。
- 增加零 API `replay`、原样 `export-run`，并保持 benchmark 的独立验收隔离。
- 增加默认关闭、仅记录同计划下已验证恢复的通用经验；拒绝任意指令注入、损坏文件和并发覆盖。
- 固定已测试依赖版本，更新中英双语说明。没有引入外部 Coding Agent 运行器或游戏模板。

阶段验证、组合回归与限制见 [INTEGRATION.md](INTEGRATION.md)。未做新的付费模型实验，不声称未知游戏成功率或成本提升。

## 0.4.0 — 2026-10-14

- 增加独立的确定性完成门禁：缺失、重复、未知或失败的测试证据不算通过；启动检查不能替代核心交互规则。
- 增加测试用途标签和非破坏性的质量提醒；旧计划保持可用，不根据标签或断言数量宣称语义正确。
- 增加只读 `assert_consistent`，比较实际 DOM 与实时状态快照，定位不同步；没有引入状态修改测试接口。
- 规划降级后，在原有调用及时间预算内尝试一次功能计划恢复；保留原计划、要求与断言，新计划冻结后复测、再修复。
- 生成、独立评估及零 API 复测使用相同完成门禁；保留原验证结果和控制层判定，扩充审计检查点。
- 强化单一有效状态、离散按键及测试预期的提示；不增加多 Agent、游戏模板或外部运行器。

验证结果与边界见 [QUALITY.md](QUALITY.md)。本版本未新增付费模型实测，不能声称已提高未知玩法成功率。

## 0.3.0 — 2026-10-10

目标：多种底层玩法的可运行性优先，不为某一种游戏预写实现模板。

- 增加实时／回合制交互与规则不变量分析，强调强制功能优先于美化。
- 增加坐标点击、Canvas 缩放、悬停、拖拽、组合按键与更多 DOM 观察。
- 增加近期修复工作记忆、较好版本作为修复起点、重复代码检测与更细的动作记录。
- 增强状态契约兼容性，允许自动检查项附带人工复核，保留原始响应及验收条件。
- 增加明确标记的规划失败降级；只检查启动时不声称功能通过，可使用 `--strict-plan` 关闭。
- 增加四类需求、预先编写的独立检查和带共享 API 上限的 `benchmark` 命令。
- 完善安装、配置、试玩、评估、协作、历史说明和安全边界。

验证：83 项框架测试通过；真实 DeepSeek 测试共 20 次调用。三个类型产生可启动且通过所选独立检查的结果，打砖块规划失败。最终降级补丁尚未付费重测，不能据此保证未知游戏成功率。详见 [GENERALIZATION.md](GENERALIZATION.md)。

## 0.2.0 — 2026-10-09

- 增加反馈驱动的 `wait_until`、`key_until`、`move_to` 与画布尺寸观察。
- 增加失败分类、计划风险提醒、需求比例与零 API 独立复测入口。
- 当时记录为 54 项框架测试通过，已有收集游戏的独立检查 7/7 通过；不是未知需求成功率。
- 保留原始说明于 [UPGRADE.md](UPGRADE.md)。
