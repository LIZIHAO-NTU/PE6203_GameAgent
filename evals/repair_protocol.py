"""Controlled counter fault injection, NOT fresh autonomous game development.

Only this explicit evaluation module builds the synthetic counter fixtures. The game
generator never imports them. Ground-truth labels and held-out plans are not prompts.
"""
import argparse
import json
from pathlib import Path
import time

from agent import __version__
from agent.config import Config, load_dotenv
from agent.contracts import validate_plan, write_bundle
from agent.diagnostics import validate_blocked_repair
from agent.editing import resolve_edit
from agent.evidence import file_hashes, runtime_metadata
from agent.feedback import repair_feedback
from agent.prompts import CODER_SYSTEM
from agent.provider import ChatClient
from agent.runner import apply_gate
from agent.state import bundle_digest
from agent.trace import Trace
from agent.verification import preflight, verify, verify_repeated


SPEC = ("Synthetic counter protocol fixture, not a game. Offline vanilla HTML/CSS/JS. "
        "Score starts at 0. Each click on #increment adds exactly 1, including repeated clicks. "
        "#restart resets score to 0. #score displays the bare integer. Use a visible "
        "[data-game-surface] and window.__gameTest.getState() returning actual {score:number}. "
        "No timers, networking, hidden flags or tester-specific behavior.")


def counter_bundle(broken=False):
    increment = "0" if broken else "1"
    return {"summary":"Synthetic evaluation fixture, not a generated game", "files":[{
        "path":"index.html", "content":'<!doctype html><html lang="en"><meta charset="utf-8">'
        '<title>Counter fixture</title><main data-game-surface style="width:320px;min-height:160px">'
        '<h1>Counter</h1><span id="score">0</span><button id="increment">Increment</button>'
        '<button id="restart">Restart</button></main><script>let score=0;'
        'function render(){document.querySelector("#score").textContent=String(score)}'
        'document.querySelector("#increment").onclick=()=>{score+='+increment+';render()};'
        'document.querySelector("#restart").onclick=()=>{score=0;render()};'
        'window.__gameTest={getState:()=>({score})};</script></html>'}]}


def counter_plan(conflict=False):
    def click(selector): return {"action":"click","selector":selector}
    def check(source,value):
        return {"action":"assert","source":source,"op":"eq","value":value,
                **({"path":"score"} if source=="state" else {"selector":"#score"})}
    return validate_plan({"supported":True,"title":"Frozen counter checks",
        "development_plan":["Check required counter transitions"],"state_contract":{"score":"number"},
        "requirements":[{"id":"R1","text":"Each click adds exactly one","verification":"automated","priority":"core"},
                        {"id":"R2","text":"Restart resets score","verification":"automated","priority":"core"}],
        "tests":[{"id":"T1","description":"One increment","requirement_ids":["R1"],
                  "steps":[click("#increment"),check("state",2 if conflict else 1),check("text","1")]},
                 {"id":"T2","description":"Repeated increment and restart","requirement_ids":["R1","R2"],
                  "steps":[click("#increment"),click("#increment"),check("state",2),check("text","2"),
                           click("#restart"),check("state",0),check("text","0")]}],"manual_checks":[]})


def run_probes(config, output, max_calls=8, repeats=2, max_seconds=600,
               client_factory=ChatClient, verifier=verify, preflight_fn=preflight):
    if not 1<=max_calls<=24 or not 1<=repeats<=3 or not 60<=max_seconds<=1800:
        raise ValueError("Invalid probe budget/repetitions")
    output=Path(output).resolve()
    if output.exists(): raise ValueError("Probe output exists; refusing overwrite")
    if not config.api_key: raise ValueError("API key is not configured")
    if not preflight_fn(timeout=25).get("ok"): raise ValueError("Browser unavailable")
    output.mkdir(parents=True)
    trace=Trace(output/"traces",(config.api_key,))
    deadline=time.monotonic()+max_seconds
    client=client_factory(config,trace,max_calls,deadline)
    report={"kind":"controlled_repair_probe","agent_version":__version__,"model":config.model,
            "runtime":runtime_metadata(),"max_api_attempts":max_calls,"rows":[],
            "generation_calls":0,"full_game_acceptance":None,
            "note":"Fixtures and deliberate faults are evaluation setup, not autonomous generation. Never mix these results into game success rates."}
    try:
        for repeat in range(repeats):
            for kind in ("code_error","test_conflict"):
                row={"id":f"{kind}_{repeat+1:02d}","ground_truth":kind,"status":"pending"}
                report["rows"].append(row)
                if client.calls>=max_calls or time.monotonic()>=deadline:
                    row["status"]="skipped_budget"
                    continue
                base=output/row["id"]
                base.mkdir()
                bundle=counter_bundle(broken=kind=="code_error")
                plan=counter_plan(conflict=kind=="test_conflict")
                held_out=counter_plan()
                trace.save(row["id"]+"/frozen_plan.json",plan)
                trace.save(row["id"]+"/independent_plan.json",held_out)
                plan_path=trace.root/row["id"]/"frozen_plan.json"
                independent_path=trace.root/row["id"]/"independent_plan.json"
                write_bundle(bundle,base/"initial")
                before_hash=file_hashes(base/"initial")
                frozen_bytes=plan_path.read_bytes()
                failure=apply_gate(plan,verifier(base/"initial",plan_path,base/"before",timeout=60),"valid")
                row["initial_failure"]=failure
                if failure.get("ok") or not any(t.get("passed") is not True for t in failure.get("tests",[])):
                    row["status"]="invalid_injection_or_infrastructure"
                    continue
                before_calls=client.calls
                try:
                    response=client.ask_json("repair_probe",CODER_SYSTEM,json.dumps({
                        "original_spec":SPEC,"frozen_plan":plan,"previous_version":bundle,
                        "verification_feedback":repair_feedback(failure,plan),"planning_status":"valid",
                        "requested_output_mode":"replace_files","repair_base_sha256":bundle_digest(bundle),
                        "remaining_seconds":max(0,int(deadline-time.monotonic()))},ensure_ascii=False))
                    if isinstance(response,dict) and "blocked" in response:
                        row["blocked"]=validate_blocked_repair(response,failure,True)
                        row["response_kind"]="blocked"
                        row["status"]="appropriate_block" if kind=="test_conflict" else "unnecessary_block"
                        row["selected_directory"]="initial"
                    else:
                        fixed,edit=resolve_edit(response,bundle,allow_partial=True)
                        write_bundle(fixed,base/"candidate")
                        row["response_kind"]="files"
                        row["edit"]=edit
                        frozen=apply_gate(plan,verifier(base/"candidate",plan_path,base/"after",timeout=60),"valid")
                        row["frozen_after"]=frozen
                        row["selected_directory"]="candidate"
                        row["status"]="repair_unverified" if kind=="code_error" else "conflict_not_blocked"
                    selected=base/row["selected_directory"]
                    independent=apply_gate(held_out,verify_repeated(selected,independent_path,base/"independent",
                        timeout=60,repeats=2,verifier=verifier),"valid")
                    row["independent"]=independent
                    if kind=="code_error" and row["response_kind"]=="files":
                        if row["frozen_after"].get("ok") and independent.get("ok"):
                            row["status"]="repaired_and_checked"
                    row["source_integrity"]=file_hashes(base/"initial")==before_hash
                    row["frozen_integrity"]=plan_path.read_bytes()==frozen_bytes
                    row["selected_sha256"]=file_hashes(selected)
                    if not row["source_integrity"] or not row["frozen_integrity"]:
                        row["status"]="integrity_failed"
                except Exception as error:
                    row.update(status="probe_error",error=trace.redact(str(error))[:1500])
                finally:
                    row["api_attempts"]=client.calls-before_calls
                print(row["id"],row["status"],"API",row["api_attempts"],flush=True)
    finally:
        report["usage"]=client.usage_summary()
        report["completed_expected_behavior"]=sum(r["status"] in {"appropriate_block","repaired_and_checked"} for r in report["rows"])
        report["scheduled"]=2*repeats
        trace.save("probe_report.json",report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--max-calls",type=int,default=8)
    parser.add_argument("--repeats",type=int,default=2)
    args=parser.parse_args()
    load_dotenv(Path.cwd()/".env")
    report=run_probes(Config.from_env(),args.output,args.max_calls,args.repeats)
    print("Actual API attempts:",report["usage"]["api_attempts"],flush=True)
    return 0 if report["completed_expected_behavior"]==report["scheduled"] else 2


if __name__=="__main__": raise SystemExit(main())
