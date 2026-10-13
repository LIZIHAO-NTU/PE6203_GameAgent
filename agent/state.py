"""Small run-local working memory. No game templates, hidden solvers or long-term claims."""
from dataclasses import dataclass, field
import hashlib
import json


def bundle_digest(bundle):
    # Ignore the model's summary and file ordering when detecting repeated code.
    files = sorted(bundle.get("files", []), key=lambda item: item.get("path", ""))
    return hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def compact_failure(result):
    failed = []
    for test in result.get("tests", []):
        if not test.get("passed"):
            failed.append({"id": test["id"], "kind": test.get("failure_kind"),
                           "failed_step": test.get("failed_step"), "error": test.get("error", "")[:1000],
                           "observations": test.get("observations", [])[-2:]})
    return {"smoke": result.get("smoke"), "runtime_errors": result.get("runtime_errors", [])[:5],
            "quality_gate": result.get("quality_gate"),
            "failed_tests": failed, "infrastructure_error": result.get("infrastructure_error")}


@dataclass
class AgentState:
    phase: str = "planning"
    repair_memory: list = field(default_factory=list)
    tested_hashes: dict = field(default_factory=dict)
    best_round: int | None = None
    stop_reason: str | None = None

    def observe(self, round_number, digest, result, explanation):
        self.tested_hashes[digest] = round_number
        self.repair_memory.append({"round": round_number, "code_sha256": digest,
                                   "change_summary": str(explanation)[:1200],
                                   "passed_test_ids": [t["id"] for t in result.get("tests", []) if t.get("passed")],
                                   "feedback": compact_failure(result)})
        self.repair_memory = self.repair_memory[-3:]
        self.phase = "verified" if result.get("ok") else "repairing"

    def context(self):
        return {"phase": self.phase, "repair_base_round": self.best_round,
                "previous_attempts": self.repair_memory,
                "policy": "Preserve passing rules; do not repeat ineffective edits or change acceptance criteria."}
