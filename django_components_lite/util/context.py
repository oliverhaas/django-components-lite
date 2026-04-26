import copy
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

from django.http import HttpRequest
from django.template import Engine
from django.template.context import BaseContext, Context
from django.template.loader_tags import BlockContext

if TYPE_CHECKING:
    from collections.abc import Callable

# Cache context processors data per request to avoid regenerating per component.
context_processors_data: WeakKeyDictionary[HttpRequest, dict[str, Any]] = WeakKeyDictionary()


class CopiedDict(dict):
    """Marker for dicts already copied by `snapshot_context`."""


def snapshot_context(context: Context) -> Context:
    """Copy a Context so it survives leaving its current scopes without being mutated."""
    # `copy()` preserves flags like `autoescape`, `use_l10n`, etc.
    context_copy = copy.copy(context)

    # Context is a stack of dict layers. We shallow-copy each layer, but deep-copy
    # forloop state so nested forloop metadata (index, first, last, parentloop) is preserved.
    dicts_with_copied_forloops: list[CopiedDict] = []

    # Iterate in reverse: once we hit an already-copied layer, all earlier layers
    # are also copies (older layers are not replaced), so we can stop.
    for ctx_dict_index in reversed(range(len(context.dicts))):
        ctx_dict = context.dicts[ctx_dict_index]

        if isinstance(ctx_dict, CopiedDict):
            # +1 to include the current layer
            dicts_with_copied_forloops = context.dicts[: ctx_dict_index + 1] + dicts_with_copied_forloops
            break

        ctx_dict_copy = CopiedDict(ctx_dict)
        if "forloop" in ctx_dict:
            ctx_dict_copy["forloop"] = ctx_dict["forloop"].copy()

            curr_forloop = ctx_dict_copy["forloop"]
            while curr_forloop is not None:
                curr_forloop["parentloop"] = curr_forloop["parentloop"].copy()
                if "parentloop" in curr_forloop["parentloop"]:
                    curr_forloop = curr_forloop["parentloop"]
                else:
                    break

        dicts_with_copied_forloops.insert(0, ctx_dict_copy)

    context_copy.dicts = dicts_with_copied_forloops

    render_ctx_copies: list[CopiedDict] = []
    for render_ctx_dict_index in reversed(range(len(context.render_context.dicts))):
        render_ctx_dict = context.render_context.dicts[render_ctx_dict_index]

        if isinstance(render_ctx_dict, CopiedDict):
            render_ctx_copies = context.render_context.dicts[: render_ctx_dict_index + 1] + render_ctx_copies
            break

        render_ctx_dict_copy = CopiedDict(render_ctx_dict)
        if "block_context" in render_ctx_dict:
            render_ctx_dict_copy["block_context"] = _copy_block_context(render_ctx_dict["block_context"])

        if "extends_context" in render_ctx_dict:
            render_ctx_dict_copy["extends_context"] = render_ctx_dict["extends_context"].copy()

        render_ctx_dict_copy["_djc_snapshot"] = True
        render_ctx_copies.insert(0, render_ctx_dict_copy)

    context_copy.render_context.dicts = render_ctx_copies
    return context_copy


def _copy_block_context(block_context: BlockContext) -> BlockContext:
    """Shallow copy of BlockContext, copying the per-key Node lists."""
    block_context_copy = block_context.__class__()
    for key, val in block_context.blocks.items():
        block_context_copy.blocks[key] = val.copy()
    return block_context_copy


# Mirrors `RequestContext.bind_template()` without depending on a Template object.
# See https://github.com/django/django/blame/2d34ebe49a25d0974392583d5bbd954baf742a32/django/template/context.py#L255
def gen_context_processors_data(context: BaseContext, request: HttpRequest) -> dict[str, Any]:
    if request in context_processors_data:
        return context_processors_data[request].copy()

    default_engine = Engine.get_default()

    # `RequestContext` accepts an optional `processors` argument.
    request_context_processors: tuple[Callable[..., Any], ...] = getattr(context, "_processors", ())

    processors = default_engine.template_context_processors + request_context_processors
    processors_data = {}
    for processor in processors:
        data = processor(request)
        try:
            processors_data.update(data)
        except TypeError as e:
            raise TypeError(f"Context processor {processor.__qualname__} didn't return a dictionary.") from e

    context_processors_data[request] = processors_data

    return processors_data
