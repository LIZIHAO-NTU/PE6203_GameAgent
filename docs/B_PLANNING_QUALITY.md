# B — Planning-quality development experiment (2026-10-17)

## Decision

**Do not merge the candidate planner-prompt change.** A more explicit action/resource/turn ledger was tested, but the two-case, one-draft-per-arm sample did not improve reliable plan delivery. The final branch intentionally leaves `agent/prompts.py` unchanged. This is a development experiment, not a new held-out evaluation or a claim about general model accuracy.

Baseline: `81727441b83eda88528c5d27b77343658be11ad6` (`main`, PlayForge 1.2.1). Local Python 3.12.14, Playwright 1.63.0, configured `deepseek-flash`. No game generation, repair, browser verification or independent acceptance occurred in these four paid calls.

## Historical planning-error classification

| Class | Existing evidence | Why it matters |
|---|---|---|
| Structural length | [1.2.1 full-game trials](../RELEASE_1_2_1.md), Energy duel 01: planning/recovery repeatedly exceeded 18 combined steps | No functional plan froze; the resulting game only had startup self-evidence. |
| Unreachable path | Same trials, Platform 01/02: no-jump path crossed a gap | Frozen checks can require an impossible route even when selected independent checks pass. |
| Wrong post-action state | [Plan-audit comparison](../AUDIT_COMPARISON.md), energy bridge: entering a closed bridge was wrongly treated as movement with energy cost | Subsequent position/resource assertions are invalid. |
| Wrong turn/winner | Same comparison, last-stone-loses `T4/T5`: actor after two previous moves was misidentified | A rule-correct implementation may fail its own frozen checks. |
| Bad length repair | Same comparison, stamp-exchange audit added setup assertions and changed an 18-step test into 20 steps | A review response can spot a real issue yet still be unusable. |

These are distinct from implementation defects. In the 1.2.1 batch, all four generated artifacts passed the *selected* independent checks, but 0/4 completed autonomous acceptance. This does not prove full gameplay correctness.

### Questions for A to verify against the existing base

1. Is `inspect_plan` intentionally limited to cross-test initial assertions and stale real-time captures? The Energy duel baseline is schema-valid with no warnings yet has demonstrably wrong `T3`/`T5` expectations. This is a **planning-quality coverage gap**, not proof of a controller code bug; should the team require a human pre-freeze rule trace for turn/resource games until a narrower checker is validated?
2. Can A provide the original Platform 01/02 and Energy duel 01/02 plan/traces for independent review? The repository contains their summaries, not all raw run artifacts, so the historical classification relies on the published 1.2.1 report rather than re-executing those exact drafts.
3. When B later reviews S1, please supply its frozen original specification and independent checks before execution. B should not infer or silently repair a missing movement path after a failing run.

## Controlled development comparison

The probe entry point is `python -m evals.planning_probe SPEC --output NEW_DIRECTORY`. It recreates the runner's **first** planning request, allows **one** actual API attempt, limits planner output to at most 6,000 tokens, validates the returned plan and records the raw response in a Git-ignored `runs/` directory. It does not retry structural failures, generate a game, or claim semantic validation. The candidate added a pre-output fresh-page step allocation and per-action actor/resource/phase ledger to the planning prompt. Both arms used identical specs, model, JSON setting, first-request schema and token cap; only the system prompt differed. No seed is available, so stochastic variation remains a limitation.

| Spec / arm | Structure | Tests | Max combined steps | Input / output tokens | Key observation |
|---|---:|---:|---:|---:|---|
| Energy duel / baseline | Valid | 6 | 18 | 4,156 / 2,742 | `T3` and `T5` have wrong action-state expectations (below). |
| Energy duel / candidate | **Invalid** | 1 | — | 4,324 / 1,040 | Declared `R2`–`R6` automated but produced no covering tests. |
| Resource shop / baseline | Valid | 7 | 13 | 4,085 / 2,470 | No contradiction found in the reviewed action/state literals; this is not proof of complete quality. |
| Resource shop / candidate | Valid | 6 | 16 | 4,253 / 2,418 | `T1` added an unsupported exact-text assertion on the whole `[data-game-surface]`: value `"6"`; the spec only requires the price to be displayed, not that the entire surface text equals `6`. |

The baseline Energy duel `T3` does `A attack`, then `B attack`. B still has its initial 2 energy, so B's attack is **legal**: `hpA=2`, `hpB=2`, `energyB=0`, turn returns to A. The plan instead treats HP and turn as unchanged. In `T5`, after A attacks, B charges, A charges and B charges, A has only 1 energy. Its attempted second attack is ignored; `hpB` remains 2 and phase remains Playing, not WonA. The draft is structurally valid but semantically inconsistent with the original rules. The candidate Energy duel draft had no corresponding transitions to assess because it failed coverage validation.

All four raw plans and redacted provider traces remain local under `runs/b_plan_{baseline,candidate}_{energy,shop}/traces/`; `runs/` is Git-ignored. Do not publish those raw model responses without privacy review. Total actual usage was **4 API attempts**, 16,818 input tokens (7,296 cached) and 8,670 output tokens; no unknown-usage calls. The repo has no configured price, so its cost estimate is null, **not free**. At the [DeepSeek published Flash peak rates](https://api-docs.deepseek.com/quick_start/pricing/), those known tokens imply approximately US$0.0134 before any provider-specific billing adjustments; this is not a verified CNY charge. Consult the provider usage page for the actual debit. The pre-agreed ceiling was ¥3; no further paid calls are planned for this B experiment.

## Reproduction and regression

```powershell
# From the repository root. Configure your own local .env first; never share its key.
$env:LLM_MAX_TOKENS = "6000"
.\.venv\Scripts\python.exe -B -m evals.planning_probe examples/reliability_1_2/energy_duel.md --output runs/my_new_probe
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_planning_probe.py -v
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -q
```

The first command is **paid** and stochastic; the two test commands are zero-API. Before this branch's two probe tests, the baseline suite passed 302/302 in an environment allowing local loopback sockets (46 browser tests skipped by default). The initial sandbox-only run had 3 local-port permission errors, then the same baseline suite passed after that restriction was lifted. On this branch, **304/304 passed** with 46 browser checks skipped, and **304/304 passed** when all real-browser checks were enabled. The first browser run failed because Playwright searched the default user cache rather than this machine's `.venv/ms-playwright` installation; setting `$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path $PWD '.venv\ms-playwright')` resolved it without reinstalling or altering code. These are local-environment outcomes, not changes to the historical game trials.

## B handoff and personal-report evidence

- Deliverable now: reproducible one-call probe, two zero-API tests, historical error taxonomy, four-arm raw development evidence and a documented negative decision. A reviews this branch; B reviews C's primary work separately.
- **S2 remains pending candidate freeze.** B then authors a *new* turn-order / legal-versus-illegal-action specification and independent acceptance draft with an original-rule basis for each expected value. C independently reviews and executes it. Neither the acceptance plan nor its answers may be sent to the generation Agent. Do not label today's development specs as unseen S2.
- **S1 remains pending A's draft.** B reviews A's movement/boundary specification, checks reachable operations and expected states, executes the frozen candidate run, and archives original failures. B does not review/execute S3 under the handbook's assignment.
- Personal report contribution: identified that valid schema and a clean deterministic review did not catch wrong turn/resource expectations; designed a controlled development probe; tested a ledger prompt; retained the old prompt after counterevidence. Technical lesson: action-state correctness must be checked against original rules independently of structural validity. Future work: test a narrower pre-freeze semantic check on more development rules before proposing any default change.
- Two-minute demo segment: show Energy duel `T3`'s two clicks and actual state ledger, contrast the draft's wrong frozen expectation, then show why the candidate prompt was not adopted. Label this as a planning-quality failure analysis, not a successful game-generation improvement.
