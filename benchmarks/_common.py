"""Shared timeit harness used inside each backend subprocess."""

from __future__ import annotations

import json
import sys
import timeit
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def bench(run: Callable[[], object], name: str) -> None:
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run()  # warm-up
    times = timeit.repeat(run, number=1, repeat=repeats)
    print(
        json.dumps(
            {
                "backend": name,
                "times": times,
                "min": min(times),
                "mean": sum(times) / len(times),
                "max": max(times),
            },
        ),
    )
