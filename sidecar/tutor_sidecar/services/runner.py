from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT_S = 5.0
OUTPUT_LIMIT = 64 * 1024

# Harness dopisywany pod kodem ucznia (osadzanym przez json.dumps — zero problemów
# z cudzysłowami). Wyniki idą do PLIKU (argv[1]), nie na stdout — printy ucznia
# nie mogą zepsuć protokołu. Porównanie: najpierw wartościami (ast.literal_eval
# oczekiwanego repr), w odwodzie tekstowo po repr.
_STATIC_HARNESS = """
import ast, json, sys, traceback

if sys.platform == "linux":
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))

results = {"setup_error": None, "tests": []}
namespace = {}
try:
    exec(compile(USER_CODE, "<twoj_kod>", "exec"), namespace)
except BaseException:
    results["setup_error"] = traceback.format_exc(limit=5)
else:
    for test in TESTS:
        entry = {
            "call": test["call"],
            "expected": test["expected"],
            "got": None,
            "passed": False,
            "error": None,
        }
        try:
            got = eval(test["call"], namespace)
            entry["got"] = repr(got)
            try:
                entry["passed"] = got == ast.literal_eval(test["expected"])
            except Exception:
                entry["passed"] = repr(got) == test["expected"].strip()
        except BaseException:
            entry["error"] = traceback.format_exc(limit=3)
        results["tests"].append(entry)

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(results, handle)
"""


@dataclass
class RunOutcome:
    passed: bool
    timed_out: bool
    setup_error: str | None
    tests: list[dict[str, Any]] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0


def find_python() -> str | None:
    """W dev sys.executable jest prawdziwym CPythonem. W binarce PyInstallera
    to bootloader — kod ucznia musi wykonać interpreter z systemu."""
    if not getattr(sys, "frozen", False):
        return sys.executable
    candidates = [
        shutil.which("python3"),
        str(Path.home() / ".local/bin/python3"),
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/usr/bin/python3",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


_version_cache: dict[str, str] = {}


def python_label(python: str) -> str:
    if python not in _version_cache:
        try:
            probe = subprocess.run(
                [python, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
                capture_output=True,
                timeout=10,
                text=True,
            )
            _version_cache[python] = (
                f"Python {probe.stdout.strip()}" if probe.returncode == 0 else python
            )
        except OSError:
            _version_cache[python] = python
        except subprocess.TimeoutExpired:
            _version_cache[python] = python
    return _version_cache[python]


def _truncate(raw: bytes, limit: int) -> str:
    text = raw.decode("utf-8", "replace")
    if len(text) > limit:
        return text[:limit] + "\n… (wyjście obcięte)"
    return text


def _child_env() -> dict[str, str]:
    if sys.platform == "win32":
        keep = ("SYSTEMROOT", "TEMP", "TMP")
        return {key: os.environ[key] for key in keep if key in os.environ}
    return {}


def run_tests(
    python: str,
    code: str,
    tests: list[dict[str, str]],
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    output_limit: int = OUTPUT_LIMIT,
) -> RunOutcome:
    with tempfile.TemporaryDirectory(prefix="pylearn-run-") as tmp:
        harness_path = Path(tmp) / "harness.py"
        results_path = Path(tmp) / "results.json"
        harness_path.write_text(
            f"USER_CODE = {json.dumps(code)}\nTESTS = {json.dumps(tests)}\n{_STATIC_HARNESS}",
            encoding="utf-8",
        )

        started = time.monotonic()
        timed_out = False
        stdout_raw = b""
        stderr_raw = b""
        try:
            # -I: tryb izolowany (bez site-packages i env użytkownika); -X utf8:
            # przewidywalne kodowanie niezależnie od locale.
            proc = subprocess.run(
                [python, "-I", "-X", "utf8", str(harness_path), str(results_path)],
                capture_output=True,
                timeout=timeout_s,
                stdin=subprocess.DEVNULL,
                env=_child_env(),
                cwd=tmp,
            )
            stdout_raw, stderr_raw = proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout_raw = exc.stdout or b""
            stderr_raw = exc.stderr or b""
        duration_ms = int((time.monotonic() - started) * 1000)

        results: dict[str, Any] | None = None
        if results_path.exists():
            try:
                results = json.loads(results_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                results = None

    stdout = _truncate(stdout_raw, output_limit)
    stderr = _truncate(stderr_raw, output_limit)

    setup_error = results.get("setup_error") if results else None
    test_results = list(results.get("tests") or []) if results else []
    if results is None and not timed_out:
        # Proces zszedł zanim zapisał wyniki (segfault, sys.exit, zabójczy rlimit).
        setup_error = stderr.strip() or "Proces zakończył się bez zapisania wyników."

    passed = (
        not timed_out
        and setup_error is None
        and len(test_results) == len(tests)
        and all(bool(entry.get("passed")) for entry in test_results)
    )
    return RunOutcome(
        passed=passed,
        timed_out=timed_out,
        setup_error=setup_error,
        tests=test_results,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
    )
