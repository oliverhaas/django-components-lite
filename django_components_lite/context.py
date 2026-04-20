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
    context_copy = context.new()
    _copy_forloop_context(context, context_copy)

    # Required for compatibility with Django's {% extends %} tag
    # See https://github.com/django-components/django-components/pull/859
    context_copy.render_context = context.render_context

    # Pass through our internal keys
    if _COMPONENT_CONTEXT_KEY in context:
        context_copy[_COMPONENT_CONTEXT_KEY] = context[_COMPONENT_CONTEXT_KEY]

    return context_copy


def make_flat_render_context(outer_context: Context, data: dict) -> Context:
    """
    Build the isolated Context used to render a component's template.

    Unlike ``make_isolated_context_copy`` + ``context.update(...)``, this creates
    a Context with everything already merged into the base layer - no stack
    pushes, no layer walking during variable resolution.

    ``outer_context`` is flattened and used as the base; the caller's ``data``
    (template data, context processors, internal keys) is layered on top so it
    wins on key conflicts. When called from ``{% component %}`` the outer
    context is already isolated (an empty shell), so the flatten is cheap.
    When called directly via ``Component.render(context=...)`` the caller's
    Context data flows through as expected.
    """
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
