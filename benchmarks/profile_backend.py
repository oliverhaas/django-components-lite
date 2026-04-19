"""Profile one page render of a backend with cProfile.

Usage::

    python -m benchmarks.profile_backend djc_lite
    python -m benchmarks.profile_backend djc
    python -m benchmarks.profile_backend inclusion
    python -m benchmarks.profile_backend include
"""

from __future__ import annotations

import cProfile
import importlib
import pstats
import sys

ROWS = 40


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    module = importlib.import_module(f"benchmarks.{sys.argv[1]}.bench")
    run = module.run

    run()  # warm-up

    profiler = cProfile.Profile()
    profiler.enable()
    run()
    profiler.disable()

    print("=== By cumulative time ===\n")
    pstats.Stats(profiler).strip_dirs().sort_stats("cumulative").print_stats(ROWS)
    print("\n=== By total time ===\n")
    pstats.Stats(profiler).strip_dirs().sort_stats("tottime").print_stats(ROWS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
