"""Version-bound, file-level edits; always materialize into a new candidate."""
from copy import deepcopy

from .contracts import require, safe_relative_path, validate_bundle
from .state import bundle_digest


def resolve_edit(response, base=None, allow_partial=True):
    require(isinstance(response, dict), "Code response must be an object")
    require("delete_files" not in response, "File deletion is not supported")
    if "changes" not in response:
        require(response.get("edit_mode", "full") == "full", "Unknown edit mode")
        validate_bundle(response)
        bundle = deepcopy(response)
        return bundle, {"mode": "full", "changed_files": [f["path"] for f in bundle["files"]]}
    require(allow_partial and base is not None, "Partial edits need an existing base and auto repair mode")
    require("files" not in response, "Cannot mix files and changes")
    require(response.get("edit_mode") == "replace_files", "Unknown partial edit mode")
    validate_bundle(base)
    require(response.get("base_sha256") == bundle_digest(base), "Stale or incorrect repair base hash")
    changes = response["changes"]
    require(isinstance(changes, list) and 1 <= len(changes) <= 20, "Need 1..20 changed files")
    merged = {f["path"]: deepcopy(f) for f in base["files"]}
    casing = {p.lower(): p for p in merged}
    seen = set()
    for item in changes:
        require(isinstance(item, dict), "Invalid changed file")
        path = str(safe_relative_path(item.get("path")))
        require(isinstance(item.get("content"), str), "Changed content must be text")
        require(path.lower() not in seen, "Duplicate changed path")
        require(path.lower() not in casing or casing[path.lower()] == path, "Changed path casing differs from base")
        seen.add(path.lower())
        merged[path] = {"path": path, "content": item["content"]}
    bundle = {"summary": str(response.get("summary", ""))[:2000], "files": list(merged.values())}
    validate_bundle(bundle)
    return bundle, {"mode": "replace_files", "base_sha256": bundle_digest(base),
                    "changed_files": [f["path"] for f in changes]}
