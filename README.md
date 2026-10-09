# PE6203 Game Agent — MVP Version 0.3

用于 PE6203 小组项目的游戏开发 Agent：读取 Markdown 需求，从空目录生成原生 HTML/CSS/JavaScript 游戏，自动打开浏览器检查，再根据真实反馈有限次修复。

目标是**先实现可启动、规则清楚的核心游戏，再考虑美化**。没有预写游戏代码、游戏模板或内置通关器。四类测试游戏只是评估样本，不是生成器只能选择的四个类型。

当前为可行性原型，不保证任意未知游戏稳定完成。范围是离线二维网页游戏；已测包含单人玩法和本机双人井字棋，不含联网多人、3D、后端或复杂引擎。

## 1. 系统如何工作

~~~text
读取需求 → 规划需求与固定测试 → 生成文件 → 浏览器运行与检查
                                  ↑              ↓
                                  └── 失败反馈与有限修复
                                                 ↓
                                     保存较好版本和执行记录
~~~

- **模型**理解需求、规划、生成及修改代码；当前沿用 DeepSeek 兼容接口。
- **工具**执行文件写入、浏览器加载、键盘／鼠标操作及状态、DOM 检查。
- **Loop / Harness**控制参数校验、预算、日志、版本选择和停止条件。
- **修复记忆**保留近期失败和已通过检查，从较好版本继续，不是跨任务长期学习。
- **规划降级**在功能计划校验失败时仍可尝试生成原始需求对应的游戏，但只检查启动，明确标记功能未验收。`--strict-plan` 可关闭降级。

## 2. 安装与配置

需要 Python 3.10+、模型 API 账户及 Playwright 浏览器。以下为 Windows PowerShell 示例，所有命令在仓库根目录执行：

~~~powershell
git clone https://github.com/LIZIHAO-NTU/PE6203_GameAgent.git
cd PE6203_GameAgent
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m playwright install chromium
./.venv/Scripts/python.exe -m agent configure
~~~

配置时按提示输入自己的 API key，输入不显示，配置写入本机 `.env`，不调用模型。已有 `.env` 时直接在本机编辑；`configure` 不会覆盖现有配置。不要分享 key 或账户密码。

使用完整虚拟环境解释器路径，无需激活环境，避免依赖装到另一个 Python。macOS/Linux 可替换为 `./.venv/bin/python`；本次浏览器实测环境为 Windows + Edge。

| 配置项 | 含义 |
|---|---|
| `DEEPSEEK_API_KEY` | 自己的 API key；也支持 `LLM_API_KEY`，后者优先 |
| `LLM_BASE_URL` / `LLM_MODEL` | 服务地址与实际账户可用的模型 ID |
| `LLM_THINKING` | 当前适配的 DeepSeek 选项；其他兼容服务通常需留空 |
| `LLM_JSON_MODE` | 是否请求 JSON 输出，需与接口能力匹配 |
| `LLM_MAX_TOKENS` / `LLM_TIMEOUT_SECONDS` | 单次输出上限和请求超时，不是整个任务预算 |
| `PLAYWRIGHT_CHANNEL` | 留空使用 Playwright Chromium；`msedge` 使用已安装的 Edge |
| `PRICE_*` / `PRICE_CURRENCY` | 可选计价；不填则只记录 token，不编造费用 |

详细配置格式见 [.env.example](.env.example)。本次实测使用 `deepseek-flash`，这只是当时配置，不承诺所有账户可用。更换兼容服务可能需要调整专用选项；老师最终指定模型后的兼容性仍需测试。

环境检查（不调用付费 API）：

~~~powershell
./.venv/Scripts/python.exe -m agent doctor
~~~

`doctor` 检查配置是否存在、依赖及浏览器能否使用，**不验证 key 有效性、余额或模型服务可达性**。

## 3. 生成与试玩

~~~powershell
./.venv/Scripts/python.exe -m agent game_design_prompt.md
~~~

**规划、生成和修复会消费 API 额度。**默认最多 3 轮生成／修复（含首次生成）、8 次 API 尝试、600 秒任务预算；单轮浏览器验证默认最多 60 秒。规划、格式重试和网络重试均占调用次数，可能提前耗尽预算。

也可以输入自己的需求并显式设置上限：

~~~powershell
./.venv/Scripts/python.exe -m agent examples/benchmark/sokoban.md --max-rounds 3 --max-calls 5 --max-seconds 360
~~~

需求应说明操作、初始状态、合法／非法动作、计分或胜负、重开行为和技术约束。不要写入 key 或隐私数据；不需要自己编写 JSON 计划。

`--output` 可指定新输出目录，已有目录不会覆盖；`--headful` 显示自动测试浏览器；`--strict-plan` 在功能规划失败后停止，不生成部分结果。

每次结果位于新的 `runs/<run_id>/`：

~~~text
game/          自动生成的游戏源代码
traces/        需求、固定计划、API 记录、状态、各轮代码与测试证据
summary.json   机器可读结果与用量
REPORT.md      人类可读报告、未完成项和试玩待办
~~~

用终端输出的实际目录替换下面的占位符：

~~~powershell
./.venv/Scripts/python.exe -m agent serve "runs/<run_id>/game"
~~~

打开 [本地游戏页面](http://127.0.0.1:8000/)。`serve` 和玩家操作不调用模型；按键不会逐帧消费 API。端口被占用可追加 `--port 8001`，访问对应端口。服务用 Ctrl+C 停止。

不要只看退出码或页面能否打开。先读 `REPORT.md` 和 `summary.json`：

| 状态 | 解释 |
|---|---|
| `automated_passed_manual_pending` | 模型计划中的自动检查通过，完整游戏仍待验收 |
| `checks_failed` | 自动检查失败，可能已保存可启动的较好版本 |
| `partial_game_plan_failed` | 功能计划失败，只按启动范围检查 |
| `unsupported_spec` | 超出支持范围，没有擅自换技术实现 |
| `budget_exhausted` / `run_error` / `generation_failed` | 预算、运行或生成失败，查看原因与保留结果 |
| `interrupted` | 运行中断，不算完整自主完成 |

## 4. 多类型游戏评估（付费）

~~~powershell
./.venv/Scripts/python.exe -m agent benchmark examples/benchmark/suite.json --max-total-calls 20 --max-calls-per-case 5
~~~

默认每类一次。四类需求分别测试不同底层逻辑：

| 游戏 | 机制 |
|---|---|
| 井字棋 | 回合、合法落子、胜负和终止状态 |
| 推箱子 | 网格移动、障碍和推动约束 |
| 记忆配对 | 隐藏信息、匹配、延时和输入锁定 |
| 打砖块 | 连续运动、碰撞、暂停和重置 |

`--max-total-calls` 是整个批次的 API 尝试上限（包含重试），不是金额上限。`--max-calls-per-case` 限制单次用例；`--repeats 2` 可重复测试；此命令的 `--max-seconds` 表示每次用例的时间上限。预算不足的用例记录为 skipped。

每个用例有预先编写的独立检查，不提供给生成模型，也不用于本轮修复。报告分别统计启动、模型计划和独立检查；独立检查仍非完备证明，部分观察依赖游戏提供的只读状态。

结果位于 `runs/benchmark_*/BENCHMARK.md` 和 `benchmark.json`，游戏在 `cases/<case_id>/game/`，独立证据在 `acceptance/<case_id>/`。试玩时把 `serve` 的目录换成对应 `game/`。

新增需求、独立验收计划可放在 `examples/benchmark/` 并登记到 `suite.json`，不要注入现成游戏实现。

## 5. 零 API 复测与统计

复测已有游戏，不修改游戏、不改写原始开发成绩：

~~~powershell
./.venv/Scripts/python.exe -m agent recheck "runs/<run_id>/game" --plan "runs/<run_id>/traces/plan.json"
~~~

以上复用原模型计划，**不因此成为独立验收**；独立检查需另行编写并适配该游戏。复测结果位于 `rechecks/`，不调用模型，但仍需 Playwright。

汇总普通运行，生成 JSON/CSV：

~~~powershell
./.venv/Scripts/python.exe -m agent summarize runs
~~~

该命令不调用模型，只汇总指定目录的直接子运行。benchmark 应汇总 `runs/<benchmark目录>/cases`，或直接读该批次的 `benchmark.json`。不要混合模型、提示词、需求和预算来声称受控实验结果。

## 6. 框架测试与实测记录

框架测试使用模拟模型，不消费 API 额度：

~~~powershell
./.venv/Scripts/python.exe -B -m unittest discover -s tests -v
~~~

默认跳过真实浏览器测试。完整浏览器回归：

~~~powershell
$env:MVP_BROWSER_TESTS="1"
$env:PLAYWRIGHT_CHANNEL="msedge"
./.venv/Scripts/python.exe -B -m unittest discover -s tests -v
~~~

使用 Playwright Chromium 时将 `PLAYWRIGHT_CHANNEL` 留空。临时测试产物位于 `.codex-tmp/`；任务结束后清理本次临时文件，不误删其他人的材料。

2026-10-10 的验证记录：

- **83/83 项框架测试通过**，含真实浏览器，不代表真实模型游戏成功率。
- DeepSeek 实测共 **20 次调用**。修正批次中，井字棋、推箱子各两次可启动，记忆配对一次可启动；这五次各通过 5/5 项独立检查。
- 打砖块规划失败，未生成，不能算通过；部分模型自编测试预期也有错误。
- 最终规划降级路径和测试序列自检提示仅完成框架验证，尚未付费复测。
- 没有旧版本受控对照，不能声称提升百分比或保证未知玩法稳定成功。

完整方法、失败与统计口径见 [GENERALIZATION.md](GENERALIZATION.md)。原始 `runs/` 只保存在测试者本机，不随 GitHub 上传；新克隆仓库没有这些游戏和日志，需自行运行生成。

## 7. 项目结构与协作

~~~text
agent/                 控制程序、提示词、验证器和评估入口
examples/              需求与独立验收计划，不是游戏实现模板
tests/                 零付费 API 框架回归
game_design_prompt.md  默认需求
.env.example           可共享配置格式，不含密钥
GENERALIZATION.md      0.3 设计与实测边界
UPGRADE.md             0.2 历史说明
CHANGELOG.md           版本记录
~~~

- 每个成员创建自己的环境和 `.env`，不复制他人的 key。
- 共享源码、需求、测试和文档，不共享密钥、原始日志、虚拟环境或缓存。日志可能含完整需求和代码，分享前人工脱敏。
- 修改前先同步；提示词位于 `agent/prompts.py`。修改提示词、工具或验收后跑回归，记录版本和预算。
- 区分游戏错误、测试错误与操作工具限制，不为通过测试伪造状态或降低原始要求。
- 自动开发期间不人工修代码，试玩是结束后的验收。正式展示以老师最终规则为准。

## 8. 常见问题与限制

- **找不到 Playwright**：用同一个 `.venv` 解释器安装并运行。
- **浏览器不可用**：安装 Chromium，或在 `.env` 设置 `PLAYWRIGHT_CHANNEL=msedge` 后跑 `doctor`。
- **API 401/403、模型不存在或余额不足**：检查自己的账户配置；`doctor` 不验证这些，不要把密钥贴到截图中。
- **目录已存在**：换新 `--output`，系统不会覆盖旧结果。
- **检查失败但游戏能打开**：读失败步骤，可能是规则错误、错误测试或不适合的操作策略；保留失败记录。
- **费用为空**：未配置价格，不是免费；失败或超时请求也可能计费，以服务商账单为准。

不支持联网、3D、复杂指定引擎、任意包安装或自由命令执行。生成代码不可信，现有浏览器和网络限制不是经过审计的 OS 沙箱。最终课程 API、未知需求范围和 `game/`、`traces/` 提交布局仍需按正式要求对齐；当前 `runs/` 用于开发评估。
