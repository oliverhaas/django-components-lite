"""Shared state for component rendering."""

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from django_components.component import ComponentContext

# Maps render_id -> ComponentContext.
# Used by slots to find their parent component during rendering.
component_context_cache: Dict[str, "ComponentContext"] = {}
