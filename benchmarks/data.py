"""Shared sample data used by every backend.

Renders three sections (cards, buttons, alerts), each with ``N`` items, so a
single page render produces ``3 * N`` component invocations.
"""

from __future__ import annotations

N = 1000

VARIANTS = ["primary", "secondary", "success", "danger", "info"]
SIZES = ["sm", "md", "lg"]
LEVELS = ["info", "warning", "error", "success"]

cards = [
    {
        "title": f"Card {i}",
        "body": f"Body text for card {i}.",
        "variant": VARIANTS[i % len(VARIANTS)],
        "footer": f"Footer {i}",
    }
    for i in range(N)
]

buttons = [
    {
        "label": f"Button {i}",
        "variant": VARIANTS[i % len(VARIANTS)],
        "size": SIZES[i % len(SIZES)],
        "disabled": i % 7 == 0,
    }
    for i in range(N)
]

alerts = [
    {
        "level": LEVELS[i % len(LEVELS)],
        "message": f"Alert {i} says something.",
        "dismissible": i % 3 == 0,
    }
    for i in range(N)
]

context = {"cards": cards, "buttons": buttons, "alerts": alerts}
