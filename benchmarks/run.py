"""Orchestrator: runs each backend as an isolated subprocess and prints a comparison table.

Each backend needs its own Django setup because ``django-components`` and
``django-components-lite`` both register a template library named
``component_tags`` and cannot coexist inside one ``INSTALLED_APPS``.
"""

from __future__ import annotations

import json
import subprocess
import sys

REPEAT = 5

BACKENDS = [
    ("plain {% include %}", "benchmarks.include.bench"),
    ("Django inclusion_tag", "benchmarks.inclusion.bench"),
    ("django-components-lite", "benchmarks.djc_lite.bench"),
    ("django-components (upstream)", "benchmarks.djc.bench"),
]


def run_one(module: str) -> dict | None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", module, str(REPEAT)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        tail = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "non-zero exit"
        print(f"[skipped] {module}: {tail}", file=sys.stderr)
        return None
    json_lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    if not json_lines:
        print(f"[skipped] {module}: no JSON output", file=sys.stderr)
        return None
    return json.loads(json_lines[-1])


def main() -> int:
    results: list[tuple[str, dict]] = []
    for name, module in BACKENDS:
        print(f"Running {name}...", file=sys.stderr)
        r = run_one(module)
        if r is not None:
            results.append((name, r))
    if not results:
        print("No backends ran successfully.", file=sys.stderr)
        return 1

    fastest = min(r["min"] for _, r in results)
    header = f"{'backend':30}  {'min (s)':>10}  {'mean (s)':>10}  {'max (s)':>10}  {'vs fastest':>12}"
    print()
    print(header)
    print("-" * len(header))
    for name, r in sorted(results, key=lambda item: item[1]["min"]):
        print(
            f"{name:30}  {r['min']:10.4f}  {r['mean']:10.4f}  {r['max']:10.4f}  {r['min'] / fastest:11.2f}x",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
