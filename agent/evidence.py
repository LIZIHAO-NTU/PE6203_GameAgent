"""Small reproducibility metadata; never reads credentials or runs generated code."""
import hashlib
from importlib.metadata import PackageNotFoundError, version
import platform
import os
import sys


def file_hashes(root):
    result = {}
    for p in root.rglob("*"):
        if p.is_symlink() or (os.name == "nt" and getattr(p.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Linked artifacts are not allowed in evidence")
        if p.is_file():
            result[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return dict(sorted(result.items()))


def runtime_metadata():
    try:
        playwright_version = version("playwright")
    except PackageNotFoundError:
        playwright_version = None
    from pathlib import Path
    source = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))}
    return {"python": sys.version.split()[0], "system": platform.system(),
            "release": platform.release(), "machine": platform.machine(),
            "playwright": playwright_version,
            "agent_source_sha256": hashlib.sha256(str(sorted(source.items())).encode()).hexdigest()}
