# PE6203 Game Agent — MVP Version 0.2

用于 PE6203 小组项目的游戏开发 Agent：读取需求 → 生成二维网页游戏 → 浏览器自动测试 → 根据反馈有限次修复。当前使用 DeepSeek API，可继续扩展模型适配。

## 当前功能

- 从零生成原生 HTML/CSS/JavaScript 离线单人小游戏。
- 根据真实状态执行按键、目标跟随和功能检查，保存截图与日志。
- 记录失败分类、需求通过比例、耗时和 token 用量。
- 支持独立复测已有游戏，不调用 API、不修改游戏。

## 快速运行

需要 Python 3.10+。在项目目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m agent configure
.\.venv\Scripts\python.exe -m agent game_design_prompt.md --max-rounds 2 --max-calls 5
```

配置时输入自己的 DeepSeek API key；已有配置可在本地修改 `.env` 中的 `LLM_MODEL` 等参数。生成与修复会消费 API 额度。

结果保存在 `runs/<run_id>/`，包含 `game/`、`traces/`、`summary.json` 和 `REPORT.md`。打开游戏（替换实际目录名）：

```powershell
.\.venv\Scripts\python.exe -m agent serve "runs/<run_id>/game"
```

然后访问 http://127.0.0.1:8000。更多需求示例见 `examples/`。

## 小组协作须知

- 不上传或分享 `.env`、API key、本地运行日志；只共享 `.env.example`。
- 当前仅支持离线二维网页游戏，不含复杂引擎、联网或任意命令执行。
- 自动检查通过不等于完整游戏验收，仍需人工试玩；生成代码应在受控环境运行。
- 本版框架测试 54/54 通过，不代表对未知游戏需求的成功率。

升级详情与独立复测方法见 [UPGRADE.md](UPGRADE.md)。
