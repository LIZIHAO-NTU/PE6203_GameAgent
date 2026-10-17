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

### Local provenance supplement (added after A's PR #1 review)

The table below was transcribed from the four **existing** local `traces/report.json` and `traces/api/001_request.json` files, not from new API calls. SHA-256 values are for the exact local UTF-8 specification/system-prompt text (`spec`/`system`) or exact saved file bytes (`request`/`plan`). The saved request contains `system` and `user` messages, not an Authorization header; nevertheless, the full request and model response are not published here. All four requests used `deepseek-flash`, `max_tokens=6000`, JSON-object response format, thinking disabled, streaming disabled, and one allowed/actual API attempt. Within each specification, the baseline and candidate user messages were byte-for-byte equal; their system prompts differed as shown below. The current probe can replay the baseline request but does not select the historical candidate arm.

| Local arm | Spec SHA-256 | System SHA-256 | Saved request SHA-256 | Saved plan SHA-256 |
|---|---|---|---|---|
| Energy / baseline | `a74071d849ab09463e6c9feff4d020fcdc3c47f1be84f00e3fee08e08488a1cf` | `bfc471d10eac106fe77306ee831c341846d7711043dfce7eb9f77180dfde04b5` | `f3108182549e7d219818d7701762c03471daa5db3f8dbef2f4feef54123a128e` | `dcbd79ce68ab21f61d10b312c5e3ea8fe1382d1842b85f273a3b44d3834dfa2d` |
| Energy / candidate | `a74071d849ab09463e6c9feff4d020fcdc3c47f1be84f00e3fee08e08488a1cf` | `576b545aa0ef85044be422f21467bc6f8549bdeae169761d91954de333ea12ed` | `39489fbaf848ab60211be2dc641eaf75c0423dd8d071faf53220bca2fb5bd85a` | `95213ae94043309094efd01f3dcf3f12924c9400106903aa6ecbc1f6169b95f7` |
| Shop / baseline | `277c61a592a1d4182fe9f950678a28ceeb48ed81486d8ba8a2b55263eac7114f` | `bfc471d10eac106fe77306ee831c341846d7711043dfce7eb9f77180dfde04b5` | `719929164c83c5632caa099289d2de524dc5befa0eb5c2c8d3b9192b324deeda` | `50d7169fd071c1ebe82f5543f9736d6cb2fb397a45ee7536115cd5268cbd3862` |
| Shop / candidate | `277c61a592a1d4182fe9f950678a28ceeb48ed81486d8ba8a2b55263eac7114f` | `576b545aa0ef85044be422f21467bc6f8549bdeae169761d91954de333ea12ed` | `0362cc99d2048f8c5069e0f45a437aab28826556a25b50f8bc279cb0f3590ba4` | `ce555b24ef5c424b0ed9abff421f72e03e3590fb7d4799ba813d20d0e3e3678c` |

The **exact candidate-only insertion** below was recovered by diffing the saved Energy baseline/candidate `messages[0].content`; the Shop pair has the same respective system-prompt hashes. This is the complete added text, inserted after the baseline line beginning `Prefer 2..3 focused rule assertions` and before `For counter/resource tests`. No existing prompt line was removed or changed in the captured requests.

```text
Allocate the 18-step budget BEFORE writing a test: choose the shortest legal action path
from a fresh page, reserve steps for the assertions that prove its rule, and remove
redundant intermediate observations. A terminal path must fit with its prerequisites
and assertions in ONE test; otherwise leave that path as an honest manual check.
For every proposed input, privately update a small ledger of the CURRENT actor,
resources, target values and phase. Mark whether the input is accepted, ignored or
terminal; only accepted inputs spend resources and advance turns as the spec states.
To test an invalid input, first reach a state where that actor's input is truly invalid.
To test a win, enumerate every prerequisite input and its resulting state until the
winning input is legal. Check the final literals against this ledger before output.
```

Sanitized excerpts from **Energy baseline's model draft**, with the original `examples/reliability_1_2/energy_duel.md` as the rule source (these IDs are *not* held-out acceptance tests):

- `T3` draft evidence says `After A's first attack, B has 0 energy`; its actions are `#act` (A attack), capture, then `#act` (B attack). It asserts `hpA` unchanged from the capture, `energyB=0`, `turn=B`. Actual rule trace from the initial state: A spends 2 energy and reduces B from 4 to 2 HP; B **still has its initial 2 energy**, so B's attack is legal and reduces A from 4 to 2 HP, spends B's 2 energy, and returns the turn to A. Expected actual state: `hpA=2, hpB=2, energyA=0, energyB=0, turn=A, phase=Playing`.
- `T5` draft evidence claims the second A attack spends 2 from `energyA=3` and wins; its final checks require `hpB=0` and `phase=WonA`. Actual action ledger: initial `(A energy 2, B energy 2, B HP 4)` → A attack `(0,2,2; turn B)` → B charge `(0,3,2; turn A)` → A charge `(1,3,2; turn B)` → B charge at cap `(1,3,2; turn A)` → A attempts attack with only 1 energy, a complete no-op. Thus `hpB=2, phase=Playing, turn=A`; the draft's terminal assertions are wrong.

These excerpts support rule-level audit of two draft tests and bind the four local artifacts by hash. They do **not** independently authenticate provider billing, prove every raw response correct, establish a statistically general prompt comparison, or constitute a new autonomous game run. The negative decision remains: keep the production planner unchanged. Keep the local raw files for a reviewer who needs to recompute hashes; do not commit or forward them without a separate privacy check.

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
