"""Usage: python -m agent game_design_prompt.md; see README.md for setup."""
import argparse
from datetime import datetime, timezone
import getpass
import importlib.util
import json
from pathlib import Path
import sys
import uuid

from .config import Config, load_dotenv


def configure():
    target = Path.cwd() / ".env"
    if target.exists():
        raise ValueError(".env already exists; edit it locally rather than overwrite it")
    print("Your API key is stored only in local .env (plaintext, git-ignored). Never share it.")
    key = getpass.getpass("DeepSeek API key (input hidden): ").strip()
    if not key or any(char in key for char in "\r\n\"'"):
        raise ValueError("Empty/invalid key")
    example = Path(__file__).resolve().parent.parent / ".env.example"
    content = example.read_text(encoding="utf-8").replace("DEEPSEEK_API_KEY=", "DEEPSEEK_API_KEY=" + key, 1)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(content)
    print("Saved .env. No API request was made.")
    return 0


def doctor(config, args):
    from .verification import preflight
    parser = argparse.ArgumentParser(prog="python -m agent doctor")
    parser.add_argument("--skip-browser", action="store_true")
    options = parser.parse_args(args)
    package = importlib.util.find_spec("playwright") is not None
    result = {"python": sys.version.split()[0], "api_key_configured": bool(config.api_key),
              "model": config.model, "base_url": config.base_url, "playwright_installed": package,
              "network_api_tested": False}
    if package and not options.skip_browser:
        result["browser"] = preflight()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not package:
        print("Install: python -m pip install -r requirements.txt")
    if not result.get("browser", {}).get("ok") and not options.skip_browser:
        print("Install browser: python -m playwright install chromium")
        print("Or use installed Edge: set PLAYWRIGHT_CHANNEL=msedge in .env")
    if not config.api_key:
        print("Configure key: python -m agent configure")
    return 0 if config.api_key and package and (options.skip_browser or result["browser"]["ok"]) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    load_dotenv(Path.cwd() / ".env")
    try:
        if argv and argv[0] == "configure":
            if len(argv) != 1:
                raise ValueError("configure takes no arguments")
            return configure()
        if argv and argv[0] == "serve":
            from .server import make_server
            parser = argparse.ArgumentParser(prog="python -m agent serve")
            parser.add_argument("game", type=Path)
            parser.add_argument("--port", type=int, default=8000)
            options = parser.parse_args(argv[1:])
            if not (options.game / "index.html").is_file():
                raise ValueError("Game directory must contain index.html")
            server = make_server(options.game, options.port)
            print(f"Game: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
            try:
                server.serve_forever()
            finally:
                server.server_close()
            return 0
        if argv and argv[0] == "summarize":
            from .evaluation import export
            parser = argparse.ArgumentParser(prog="python -m agent summarize")
            parser.add_argument("runs", type=Path)
            parser.add_argument("--output", type=Path, default=Path("reports") /
                                ("evaluation_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"))
            options = parser.parse_args(argv[1:])
            if not options.runs.is_dir():
                raise ValueError("Runs directory does not exist")
            report = export(options.runs, options.output)
            print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
            print(f"Saved JSON and CSV: {options.output.resolve()}")
            return 0
        if argv and argv[0] == "recheck":
            from .recheck import recheck
            parser = argparse.ArgumentParser(prog="python -m agent recheck")
            parser.add_argument("game", type=Path)
            parser.add_argument("--plan", type=Path, required=True)
            parser.add_argument("--output", type=Path, default=Path("rechecks") /
                                (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]))
            parser.add_argument("--timeout", type=int, default=60)
            parser.add_argument("--headful", action="store_true")
            options = parser.parse_args(argv[1:])
            code = recheck(options.game, options.plan, options.output, options.timeout, options.headful)
            print(f"Offline recheck (0 API calls): {options.output.resolve()}")
            return code
        config = Config.from_env()
        if argv and argv[0] == "benchmark":
            from .benchmark import benchmark
            parser = argparse.ArgumentParser(prog="python -m agent benchmark",
                description="Paid multi-game evaluation; all retries count towards the shared cap.")
            parser.add_argument("suite", type=Path)
            parser.add_argument("--output", type=Path, default=Path("runs") /
                                ("benchmark_" + datetime.now().strftime("%Y%m%d_%H%M%S")))
            parser.add_argument("--max-total-calls", type=int, default=20)
            parser.add_argument("--max-calls-per-case", type=int, default=5)
            parser.add_argument("--max-rounds", type=int, default=3)
            parser.add_argument("--max-seconds", type=int, default=420)
            parser.add_argument("--repeats", type=int, default=1)
            options = parser.parse_args(argv[1:])
            report = benchmark(config, options.suite, options.output, options.max_total_calls,
                               options.max_calls_per_case, options.max_rounds, options.max_seconds,
                               options.repeats)
            print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
            print(f"Benchmark: {options.output.resolve()}")
            return 0 if all(r.get("independent_passed") for r in report["cases"]) else 2
        if argv and argv[0] == "doctor":
            return doctor(config, argv[1:])
        parser = argparse.ArgumentParser(description="MVP: spec -> game -> browser tests -> bounded repair. "
                                         "Other commands: configure, doctor, serve, summarize, recheck.")
        parser.add_argument("spec", type=Path)
        parser.add_argument("--output", type=Path)
        parser.add_argument("--max-rounds", type=int, default=3, help="Includes first generation (default: 3)")
        parser.add_argument("--max-calls", type=int, default=8, help="Includes retries and planning")
        parser.add_argument("--max-seconds", type=int, default=600)
        parser.add_argument("--test-timeout", type=int, default=60)
        parser.add_argument("--headful", action="store_true", help="Show automated browser windows")
        parser.add_argument("--strict-plan", action="store_true", help="Stop if functional planning fails; do not generate a partial game")
        options = parser.parse_args(argv)
        if not options.spec.is_file():
            raise ValueError("Specification file does not exist")
        if not (1 <= options.max_rounds <= 10 and 1 <= options.max_calls <= 30
                and 30 <= options.max_seconds <= 3600 and 10 <= options.test_timeout <= 180):
            raise ValueError("Limits: rounds 1..10, calls 1..30, seconds 30..3600, test timeout 10..180")
        output = options.output or Path("runs") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                                                  + "_" + uuid.uuid4().hex[:6])
        from .runner import run
        return run(config, options.spec, output, options.max_rounds, options.max_calls,
                   options.max_seconds, options.test_timeout, options.headful, strict_plan=options.strict_plan)
    except KeyboardInterrupt:
        print("Stopped by user; interrupted runs are not valid autonomous demonstrations.", file=sys.stderr)
        return 130
    except Exception as error:
        # Only controller diagnostics are printed; API bodies are never printed here.
        print(f"Error: {error}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
