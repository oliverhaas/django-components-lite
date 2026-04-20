"""
This file centralizes various ways we use Django's Context class
pass data across components, nodes, slots, and contexts.

Compared to `django_components_lite/util/context.py`, this file contains the "business" logic
and the list of all internal keys that we define on the `Context` object.
"""

from django.template import Context

_COMPONENT_CONTEXT_KEY = "_DJC_COMPONENT_CTX"
_STRATEGY_CONTEXT_KEY = "DJC_DEPS_STRATEGY"

# Django's Context._reset_dicts builds this dict fresh every __init__.
# We hand it in pre-built so every context we create shares the same object.
_CONTEXT_BUILTINS = {"True": True, "False": False, "None": None}


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

    ctx.dicts = [_CONTEXT_BUILTINS, base] if base else [_CONTEXT_BUILTINS]
    ctx.render_context = context.render_context
    return ctx


def make_flat_render_context(outer_context: Context, data: dict) -> Context:
    """Flat render Context with `data` layered on top of `outer_context.flatten()`."""
    merged = {**outer_context.flatten(), **data}
    # Construct Context by hand to skip Context.__init__'s RenderContext() -
    # we overwrite render_context immediately with outer's anyway.
    ctx = object.__new__(Context)
    ctx.autoescape = outer_context.autoescape
    ctx.use_l10n = outer_context.use_l10n
    ctx.use_tz = outer_context.use_tz
    ctx.template_name = "unknown"
    ctx.template = None
    ctx.dicts = [_CONTEXT_BUILTINS, merged]
    ctx.render_context = outer_context.render_context
    return ctx
