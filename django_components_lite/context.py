"""
This file centralizes various ways we use Django's Context class
pass data across components, nodes, slots, and contexts.

Compared to `django_components_lite/util/context.py`, this file contains the "business" logic
and the list of all internal keys that we define on the `Context` object.
"""

from django.template import Context

from django_components_lite.util.misc import get_last_index

_COMPONENT_CONTEXT_KEY = "_DJC_COMPONENT_CTX"
_STRATEGY_CONTEXT_KEY = "DJC_DEPS_STRATEGY"


def make_isolated_context_copy(context: Context) -> Context:
    """Fresh Context preserving only flags, render_context, forloop, and internal key."""
    # Preserve the concrete class (e.g. RequestContext) and its __dict__
    # (e.g. `_processors`) without paying for copy.copy's render_context
    # and dicts copies that context.new() would do.
    ctx = object.__new__(context.__class__)
    ctx.__dict__ = context.__dict__.copy()

    base: dict[str, object] = {}
    for layer in context.dicts:
        if "forloop" in layer:
            base.update(layer)
        if _COMPONENT_CONTEXT_KEY in layer:
            base[_COMPONENT_CONTEXT_KEY] = layer[_COMPONENT_CONTEXT_KEY]

    builtins = {"True": True, "False": False, "None": None}
    ctx.dicts = [builtins, base] if base else [builtins]
    ctx.render_context = context.render_context
    return ctx


def make_flat_render_context(outer_context: Context, data: dict) -> Context:
    """Flat render Context with `data` layered on top of `outer_context.flatten()`."""
    merged = {**outer_context.flatten(), **data}
    ctx = Context(
        merged,
        autoescape=outer_context.autoescape,
        use_l10n=outer_context.use_l10n,
        use_tz=outer_context.use_tz,
    )
    # Share render_context so Django's {% extends %} tag keeps working.
    ctx.render_context = outer_context.render_context
    return ctx


def _copy_forloop_context(from_context: Context, to_context: Context) -> None:
    """Forward the info about the current loop"""
    # Note that the ForNode (which implements `{% for %}`) does not
    # only add the `forloop` key, but also keys corresponding to the loop elements
    # So if the loop syntax is `{% for my_val in my_lists %}`, then ForNode also
    # sets a `my_val` key.
    # For this reason, instead of copying individual keys, we copy the whole stack layer
    # set by ForNode.
    if "forloop" in from_context:
        forloop_dict_index = get_last_index(from_context.dicts, lambda d: "forloop" in d) or -1
        to_context.update(from_context.dicts[forloop_dict_index])
