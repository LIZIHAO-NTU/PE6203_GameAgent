"""Export immutable run artifacts, without configuration secrets or cached dependencies."""
import json
import os
from pathlib import Path
import shutil

from . import __version__
from .evidence import file_hashes


def export_run(source, output, report=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    package = Path(__file__).resolve().parent
    if output.exists() or output == source or source in output.parents:
        raise ValueError("Export needs a new directory outside the source run")
    def linked(path):
        if path.is_symlink():
            return True
        return os.name == "nt" and bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)
    for name in ("game", "traces"):
        root = source / name
        if not root.is_dir() or linked(root) or any(linked(p) for p in root.rglob("*")):
            raise ValueError("Run needs non-symlink game/ and traces/ directories")
    if not (source / "game/index.html").is_file():
        raise ValueError("Run has no game/index.html")
    if report:
        report = Path(report).resolve()
        with report.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError("Report must be an existing PDF; none will be fabricated")
    original = source / "summary.json"
    original_version = json.loads(original.read_text(encoding="utf-8")).get("agent_version") if original.is_file() else None
    hashes = {name: file_hashes(source / name) for name in ("game", "traces")}
    output.mkdir(parents=True, exist_ok=False)
    for name in ("game", "traces"):
        shutil.copytree(source / name, output / name)
    (output / "agent").mkdir()
    for file in package.glob("*.py"):
        shutil.copy2(file, output / "agent" / file.name)
    for name in ("requirements.txt", ".env.example"):
        shutil.copy2(package.parent / name, output / name)
    if report:
        shutil.copy2(report, output / "report.pdf")
    notes = ("# Exported agent and run / Agent 与运行结果导出\n\n"
             "Run commands from the export root / 在导出根目录运行：\n\n"
             "```powershell\npython -m pip install -r requirements.txt\n"
             "python -m playwright install chromium\npython -m agent configure\n"
             "python -m agent game_design_prompt.md\n```\n\n"
             "The Markdown specification must be supplied separately. New development runs use runs/.\n"
             "需求 Markdown 需另行提供，新开发结果写入 runs/。\n\n"
             "Play the preserved result / 试玩保留结果：`python -m agent serve game`\n\n"
             "Do not edit game/ or traces/. Local .env configuration is not copied; review traces for private content.\n"
             "不要修改 game/、traces/；不复制本地 .env 配置。分享 traces 前检查私人内容。\n\n"
             "A report.pdf is required separately unless supplied to export-run.\n"
             "未向 export-run 提供报告时，仍需另行添加 report.pdf。\n")
    (output / "README.md").write_text(notes, encoding="utf-8")
    (output / "agent/README.md").write_text(notes, encoding="utf-8")
    integrity = all(file_hashes(output / name) == hashes[name] and file_hashes(source / name) == hashes[name]
                    for name in hashes)
    manifest = {"agent_version": __version__, "original_run_agent_version": original_version, "artifacts_match": integrity,
                "artifact_sha256": hashes, "has_report": report is not None,
                "course_acceptance": None, "note": "Packaging is not evidence of autonomous success or full course compliance. Review traces for private prompt content before sharing."}
    (output / "DELIVERY.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if not integrity:
        raise RuntimeError("Source/export changed during packaging; inspect DELIVERY.json")
    return manifest
