import difflib
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from dataclasses import replace as dataclass_replace
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    NamedTuple,
    Protocol,
    TypeVar,
    Union,
    cast,
    runtime_checkable,
)

from django.template import Context, Template
from django.template.base import NodeList, TextNode
from django.template.exceptions import TemplateSyntaxError
from django.utils.html import conditional_escape
from django.utils.safestring import SafeString, mark_safe

from django_components_lite.context import _COMPONENT_CONTEXT_KEY
from django_components_lite.node import BaseNode
from django_components_lite.util.exception import add_slot_to_error_message
from django_components_lite.util.misc import default, get_last_index, is_identifier

if TYPE_CHECKING:
    from django_components_lite.component import ComponentNode

TSlotData = TypeVar("TSlotData", bound=Mapping)

DEFAULT_SLOT_KEY = "default"
FILL_GEN_CONTEXT_KEY = "_DJANGO_COMPONENTS_GEN_FILL"
SLOT_NAME_KWARG = "name"
SLOT_REQUIRED_FLAG = "required"
SLOT_DEFAULT_FLAG = "default"
FILL_DATA_KWARG = "data"
FILL_FALLBACK_KWARG = "fallback"
FILL_BODY_KWARG = "body"


# Public types
type SlotResult = str | SafeString
"""Result of a slot render function."""


@dataclass(frozen=True)
class SlotContext[TSlotData: Mapping]:
    """Metadata available inside slot functions."""

    data: TSlotData
    """Data passed to the slot."""
    fallback: Union[str, "SlotFallback"] | None = None
    """Slot's fallback content. Lazily-rendered - coerce to string to force render."""
    context: Context | None = None
    """Django template `Context` available inside the `{% fill %}` tag."""


@runtime_checkable
class SlotFunc[TSlotData: Mapping](Protocol):
    """Callable signature for a slot function."""

    def __call__(self, ctx: SlotContext[TSlotData]) -> SlotResult: ...


@dataclass
class Slot[TSlotData: Mapping]:
    """Holds a slot content function and its metadata."""

    contents: Any
    """Original value passed to the `Slot` constructor (string, function, or fill body)."""
    content_func: SlotFunc[TSlotData] = cast("SlotFunc[TSlotData]", None)  # noqa: RUF009
    """The actual slot function. Do NOT call directly; call the `Slot` instance instead."""

    # Following fields are only for debugging
    component_name: str | None = None
    """Name of the component that originally received this slot fill."""
    slot_name: str | None = None
    """Slot name to which this Slot was initially assigned."""
    nodelist: NodeList | None = None
    """For `{% fill %}`-derived slots, the `NodeList` of the fill's body."""
    fill_node: Union["FillNode", "ComponentNode"] | None = None
    """Originating `FillNode` or `ComponentNode`, or `None` for slots constructed in Python."""
    extra: dict[str, Any] = field(default_factory=dict)
    """Dictionary for arbitrary user metadata about the slot."""

    def __post_init__(self) -> None:
        # Disallow Slot-as-contents because it makes metadata handling ambiguous.
        if isinstance(self.contents, Slot):
            raise TypeError("Slot received another Slot instance as `contents`")

        if self.content_func is None:
            self.contents, new_nodelist, self.content_func = self._resolve_contents(self.contents)
            if self.nodelist is None:
                self.nodelist = new_nodelist

        if not callable(self.content_func):
            raise TypeError(f"Slot 'content_func' must be a callable, got: {self.content_func}")

    def __call__(
        self,
        data: TSlotData | None = None,
        fallback: Union[str, "SlotFallback"] | None = None,
        context: Context | None = None,
    ) -> SlotResult:
        slot_ctx: SlotContext = SlotContext(context=context, data=data or {}, fallback=fallback)
        result = self.content_func(slot_ctx)
        return conditional_escape(result)

    @property
    def do_not_call_in_templates(self) -> bool:
        """Django flag preventing the instance from being called inside templates."""
        return True

    def __repr__(self) -> str:
        comp_name = f"'{self.component_name}'" if self.component_name else None
        slot_name = f"'{self.slot_name}'" if self.slot_name else None
        return f"<{self.__class__.__name__} component_name={comp_name} slot_name={slot_name}>"

    def _resolve_contents(self, contents: Any) -> tuple[Any, NodeList, SlotFunc[TSlotData]]:
        # String / scalar contents are wrapped in a TextNode.
        if not callable(contents):
            contents = str(contents) if not isinstance(contents, (str, SafeString)) else contents
            contents = conditional_escape(contents)
            slot = _nodelist_to_slot(
                component_name=self.component_name or "<Slot._resolve_contents>",
                slot_name=self.slot_name,
                nodelist=NodeList([TextNode(contents)]),
                contents=contents,
                data_var=None,
                fallback_var=None,
            )
            return slot.contents, slot.nodelist, slot.content_func

        return contents, None, contents


# NOTE: This must be defined here, so we don't have any forward references
# otherwise Pydantic has problem resolving the types.
type SlotInput[TSlotData: Mapping] = SlotResult | SlotFunc[TSlotData] | Slot[TSlotData]
"""Union of all forms in which slot content can be passed to a component."""

# Internal type aliases
SlotName = str


class SlotFallback:
    """Lazy wrapper around a slot's fallback content; coerce to string to render."""

    def __init__(self, slot: "SlotNode", context: Context) -> None:
        self._slot = slot
        self._context = context

    def __str__(self) -> str:
        return mark_safe(self._slot.nodelist.render(self._context))  # noqa: S308


class SlotNode(BaseNode):
    """`{% slot %}` tag: marks a place inside a component where outer content can be inserted."""

    tag = "slot"
    end_tag = "endslot"
    allowed_flags = (SLOT_DEFAULT_FLAG, SLOT_REQUIRED_FLAG)

    # NOTE:
    # Slots are resolved at render time, so we only know about a slot when we render it.
    # That means we can use variables and place slots in loops, but we cannot know all
    # slot names ahead of time, so we cannot raise for unfilled slots or extra fills.
    def render(self, context: Context, name: str, **kwargs: Any) -> SafeString:
        # Skip rendering during the fill-discovery pass.
        if _is_extracting_fill(context):
            return ""

        if _COMPONENT_CONTEXT_KEY not in context or not context[_COMPONENT_CONTEXT_KEY]:
            raise TemplateSyntaxError(
                "Encountered a SlotNode outside of a Component context. "
                "Make sure that all {% slot %} tags are nested within {% comp %} tags.\n"
                f"SlotNode: {self.__repr__()}",
            )

        component_ctx = context[_COMPONENT_CONTEXT_KEY]
        component = component_ctx.component()
        if component is None:
            raise RuntimeError(
                "Component was garbage collected before its slots could be rendered.",
            )
        component_name = component.name
        # NOTE: Use `ComponentContext.outer_context`, and NOT `Component.outer_context`.
        #       The first is a SNAPSHOT of the outer context.
        outer_context = component_ctx.outer_context

        slot_fills = component.slots
        slot_name = name
        is_default = self.flags[SLOT_DEFAULT_FLAG]
        is_required = self.flags[SLOT_REQUIRED_FLAG]

        if is_default:
            # Allow multiple slots marked 'default' only if they share a name.
            default_slot_name = component_ctx.default_slot
            if default_slot_name is not None and slot_name != default_slot_name:
                raise TemplateSyntaxError(
                    "Only one component slot may be marked as 'default', "
                    f"found '{default_slot_name}' and '{slot_name}'. "
                    f"To fix, check template '{component_ctx.template_name}' "
                    f"of component '{component_name}'.",
                )

            if default_slot_name is None:
                component_ctx.default_slot = slot_name

            # Reject double-fill: same slot filled both explicitly and implicitly as 'default'.
            if (
                slot_name != DEFAULT_SLOT_KEY
                and slot_fills.get(slot_name, False)
                and slot_fills.get(DEFAULT_SLOT_KEY, False)
            ):
                raise TemplateSyntaxError(
                    f"Slot '{slot_name}' of component '{component_name}' was filled twice: "
                    "once explicitly and once implicitly as 'default'.",
                )

        # If marked 'default' and a 'default' fill exists, use it; otherwise use the slot's name.
        fill_name = DEFAULT_SLOT_KEY if is_default and DEFAULT_SLOT_KEY in slot_fills else slot_name

        # Filled slots render against the outer context (where the slot was filled),
        # so e.g. `{{ item.name }}` inside `{% fill %}` resolves against the loop's context,
        # not the component's.
        if fill_name in slot_fills:
            slot_is_filled = True
            slot = slot_fills[fill_name]
        else:
            slot_is_filled = False
            slot = _nodelist_to_slot(
                component_name=component_name,
                slot_name=slot_name,
                nodelist=self.nodelist,
                contents=self.contents,
                data_var=None,
                fallback_var=None,
            )

        # Required-but-not-filled: fuzzy-match the slot name against provided fills to
        # surface likely typos in the error message.
        if is_required and not slot_is_filled:
            msg = (
                f"Slot '{slot_name}' is marked as 'required' (i.e. non-optional), "
                f"yet no fill is provided. Check template."
            )
            fill_names = list(slot_fills.keys())
            if fill_names:
                fuzzy_fill_name_matches = difflib.get_close_matches(fill_name, fill_names, n=1, cutoff=0.7)
                if fuzzy_fill_name_matches:
                    msg += f"\nDid you mean '{fuzzy_fill_name_matches[0]}'?"
            raise TemplateSyntaxError(msg)

        fallback = SlotFallback(self, context)

        used_ctx = self._resolve_slot_context(context, slot_is_filled, outer_context)

        # Push an empty data layer so the slot body sees a fresh stack frame for any
        # `{% with %}` it does, without polluting the caller's context.
        with used_ctx.update({}):
            # Required for compatibility with Django's {% extends %} tag: the render context
            # used outside of a component must match the one used inside the slot.
            # See https://github.com/django-components/django-components/pull/859
            if len(used_ctx.render_context.dicts) > 1 and "block_context" in used_ctx.render_context.dicts[-2]:
                render_ctx_layer = used_ctx.render_context.dicts[-2]
            else:
                render_ctx_layer = used_ctx.render_context.dicts[-1]

            with used_ctx.render_context.push(render_ctx_layer), add_slot_to_error_message(component_name, slot_name):
                return slot(data=kwargs, fallback=fallback, context=used_ctx)

    def _resolve_slot_context(
        self,
        context: Context,
        slot_is_filled: bool,
        outer_context: Context | None,
    ) -> Context:
        """Pick context for slot rendering: outer for filled slots, current for fallbacks."""
        if not slot_is_filled:
            return context
        return outer_context if outer_context is not None else Context()


class FillNode(BaseNode):
    """`{% fill %}` tag: insert content into a component's slot. Must sit inside `{% comp %}`."""

    tag = "fill"
    end_tag = "endfill"
    allowed_flags = ()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Disallow {% block %} tags inside {% fill %}; the two systems don't compose.
        # Use {% slot %}/{% fill %} for component composition.
        from django.template.loader_tags import BlockNode

        for node in self.nodelist.get_nodes_by_type(BlockNode):
            raise TemplateSyntaxError(
                f"Template block '{node.name}' is not allowed inside {{% fill %}}. "
                "Use {% slot %}/{% fill %} for component composition instead of {% block %}.",
            )

    def render(
        self,
        context: Context,
        name: str,
        *,
        data: str | None = None,
        fallback: str | None = None,
        body: SlotInput | None = None,
    ) -> str:
        if not _is_extracting_fill(context):
            raise TemplateSyntaxError(
                "FillNode.render() (AKA {% fill ... %} block) cannot be rendered outside of a Component context. "
                "Make sure that the {% fill %} tags are nested within {% comp %} tags.",
            )

        if not isinstance(name, str):
            raise TemplateSyntaxError(f"Fill tag '{SLOT_NAME_KWARG}' kwarg must resolve to a string, got {name}")

        if data is not None:
            if not isinstance(data, str):
                raise TemplateSyntaxError(f"Fill tag '{FILL_DATA_KWARG}' kwarg must resolve to a string, got {data}")
            if not is_identifier(data):
                raise TemplateSyntaxError(
                    f"Fill tag kwarg '{FILL_DATA_KWARG}' does not resolve to a valid Python identifier, got '{data}'",
                )

        if fallback is not None:
            if not isinstance(fallback, str):
                raise TemplateSyntaxError(
                    f"Fill tag '{FILL_FALLBACK_KWARG}' kwarg must resolve to a string, got {fallback}",
                )
            if not is_identifier(fallback):
                raise TemplateSyntaxError(
                    f"Fill tag kwarg '{FILL_FALLBACK_KWARG}' does not resolve to a valid Python identifier,"
                    f" got '{fallback}'",
                )

        if data and fallback and data == fallback:
            raise TemplateSyntaxError(
                f"Fill '{name}' received the same string for slot fallback ({FILL_FALLBACK_KWARG}=...)"
                f" and slot data ({FILL_DATA_KWARG}=...)",
            )

        if body is not None and self.contents:
            raise TemplateSyntaxError(
                f"Fill '{name}' received content both through '{FILL_BODY_KWARG}' kwarg and '{{% fill %}}' body. "
                f"Use only one method.",
            )

        fill_data = FillWithData(
            fill=self,
            name=name,
            fallback_var=fallback,
            data_var=data,
            extra_context={},
            body=body,
        )

        self._extract_fill(context, fill_data)

        return ""

    def _extract_fill(self, context: Context, data: "FillWithData") -> None:
        # `FILL_GEN_CONTEXT_KEY` is set only while rendering between `{% comp %}...{% endcomp %}`
        # to collect fill tags (including dynamically-generated ones via {% for %}/{% if %}).
        captured_fills: list[FillWithData] | None = context.get(FILL_GEN_CONTEXT_KEY, None)

        if captured_fills is None:
            raise RuntimeError(
                "FillNode.render() (AKA {% fill ... %} block) cannot be rendered outside of a Component context. "
                "Make sure that the {% fill %} tags are nested within {% comp %} tags.",
            )

        # Capture variables defined WITHIN this `{% comp %} ... {% endcomp %}` (e.g. via `{% with %}`)
        # so they're visible inside the fill body. We start from the last layer that has
        # `FILL_GEN_CONTEXT_KEY` to avoid pulling in variables from outside the comp tag.
        index_of_new_layers = get_last_index(context.dicts, lambda d: FILL_GEN_CONTEXT_KEY in d)
        context_dicts: list[dict[str, Any]] = context.dicts
        for dict_layer in context_dicts[index_of_new_layers:]:
            for key, value in dict_layer.items():
                if not key.startswith("_"):
                    data.extra_context[key] = value

        # Forloop layers can sit anywhere in the stack (one per nested {% for %}).
        # Copy each one so the fill body can reference `forloop` and the loop variable.
        for layer in context.dicts:
            if "forloop" in layer:
                layer_copy = layer.copy()
                layer_copy["forloop"] = layer_copy["forloop"].copy()
                data.extra_context.update(layer_copy)

        captured_fills.append(data)


#######################################
# EXTRACTING {% fill %} FROM TEMPLATES
# (internal)
#######################################


class FillWithData(NamedTuple):
    fill: FillNode
    name: str
    """Name of the slot to be filled, as set on the `{% fill %}` tag."""
    body: SlotInput | None
    """Slot fill as set by the `body` kwarg on the `{% fill %}` tag."""
    fallback_var: str | None
    """Name of the FALLBACK variable, as set on the `{% fill %}` tag."""
    data_var: str | None
    """Name of the DATA variable, as set on the `{% fill %}` tag."""
    extra_context: dict[str, Any]
    """Extra context variables (from `{% with %}` / `{% for %}`) available inside the fill body."""


def resolve_fills(
    context: Context,
    component_node: "ComponentNode",
    component_name: str,
) -> dict[SlotName, Slot]:
    """Find all slot fills in a component body, whether explicit `{% fill %}` or implicit default."""
    slots: dict[SlotName, Slot] = {}

    nodelist = component_node.nodelist
    contents = component_node.contents

    if not nodelist:
        return slots

    maybe_fills = _extract_fill_content(nodelist, context, component_name)

    # No fills: treat the whole body as the default slot.
    if maybe_fills is False:
        # Ignore whitespace-only bodies.
        nodelist_is_empty = not len(nodelist) or all(
            isinstance(node, TextNode) and not node.s.strip() for node in nodelist
        )

        if not nodelist_is_empty:
            slots[DEFAULT_SLOT_KEY] = _nodelist_to_slot(
                component_name=component_name,
                slot_name=None,  # Will be populated later
                nodelist=nodelist,
                contents=contents,
                data_var=None,
                fallback_var=None,
                fill_node=component_node,
            )

    else:
        # NOTE: Explicitly-defined fills are kept even if empty (unlike default slot bodies).
        for fill in maybe_fills:
            if fill.body is not None:
                # Set `Slot.fill_node` so a `body=`-defined fill behaves like one from a `{% fill %}` tag.
                if isinstance(fill.body, Slot):
                    slot_fill = dataclass_replace(fill.body, fill_node=fill.fill)
                else:
                    slot_fill = Slot(fill.body, fill_node=fill.fill)
            else:
                slot_fill = _nodelist_to_slot(
                    component_name=component_name,
                    slot_name=fill.name,
                    nodelist=fill.fill.nodelist,
                    contents=fill.fill.contents,
                    data_var=fill.data_var,
                    fallback_var=fill.fallback_var,
                    extra_context=fill.extra_context,
                    fill_node=fill.fill,
                )
            slots[fill.name] = slot_fill

    return slots


def _extract_fill_content(
    nodes: NodeList,
    context: Context,
    component_name: str,
) -> list[FillWithData] | Literal[False]:
    # While `FILL_GEN_CONTEXT_KEY` is set, encountered {% fill %} nodes append themselves
    # to `captured_fills` instead of rendering content.
    captured_fills: list[FillWithData] = []

    with _extends_context_reset(context), context.update({FILL_GEN_CONTEXT_KEY: captured_fills}):
        content = mark_safe(nodes.render(context).strip())  # noqa: S308

    # No fills found: treat the body as default slot content.
    if not captured_fills:
        return False

    if content:
        raise TemplateSyntaxError(
            f"Illegal content passed to component '{component_name}'. "
            "Explicit 'fill' tags cannot occur alongside other text. "
            f"The component body rendered content: {content}",
        )

    seen_names: set[str] = set()
    for fill in captured_fills:
        if fill.name in seen_names:
            raise TemplateSyntaxError(
                f"Multiple fill tags cannot target the same slot name in component '{component_name}': "
                f"Detected duplicate fill tag name '{fill.name}'.",
            )
        seen_names.add(fill.name)

    return captured_fills


#######################################
# MISC
#######################################


def normalize_slot_fills(
    fills: Mapping[SlotName, SlotInput],
    component_name: str | None = None,
) -> dict[SlotName, Slot]:
    norm_fills = {}

    # NOTE: `copy_slot` is defined as a separate function, instead of being inlined within
    #       the forloop, because the value the forloop variable points to changes with each loop iteration.
    def copy_slot(content: SlotFunc | Slot, slot_name: str) -> Slot:
        if isinstance(content, Slot) and content.slot_name and content.component_name:
            return content

        # Always create a fresh Slot so we can attach metadata without mutating the caller's instance.
        content_func = content if not isinstance(content, Slot) else content.content_func

        if isinstance(content, Slot):
            used_component_name = content.component_name or component_name
            used_slot_name = content.slot_name or slot_name
            used_nodelist = content.nodelist
            used_contents = content.contents if content.contents is not None else content_func
            used_fill_node = content.fill_node
            used_extra = content.extra.copy()
        else:
            used_component_name = component_name
            used_slot_name = slot_name
            used_nodelist = None
            used_contents = content_func
            used_fill_node = None
            used_extra = {}

        return Slot(
            contents=used_contents,
            content_func=content_func,
            component_name=used_component_name,
            slot_name=used_slot_name,
            nodelist=used_nodelist,
            fill_node=used_fill_node,
            extra=used_extra,
        )

    for slot_name, content in fills.items():
        if content is None:
            continue
        if not callable(content):
            # `Slot.content_func` and `Slot.nodelist` will be set in `Slot.__init__()`.
            slot: Slot = Slot(contents=content, component_name=component_name, slot_name=slot_name)
        else:
            slot = copy_slot(content, slot_name)

        norm_fills[slot_name] = slot

    return norm_fills


def _nodelist_to_slot(
    component_name: str,
    slot_name: str | None,
    nodelist: NodeList,
    contents: str | None = None,
    data_var: str | None = None,
    fallback_var: str | None = None,
    extra_context: dict[str, Any] | None = None,
    fill_node: Union[FillNode, "ComponentNode"] | None = None,
    extra: dict[str, Any] | None = None,
) -> Slot:
    if data_var and not is_identifier(data_var):
        raise TemplateSyntaxError(
            f"Slot data alias in fill '{slot_name}' must be a valid identifier. Got '{data_var}'",
        )

    if fallback_var and not is_identifier(fallback_var):
        raise TemplateSyntaxError(
            f"Slot fallback alias in fill '{slot_name}' must be a valid identifier. Got '{fallback_var}'",
        )

    # Use Template.render() so Django sets up and binds the context correctly.
    template = Template("")
    template.nodelist = nodelist

    def render_func(ctx: SlotContext) -> SlotResult:
        context = ctx.context or Context()

        # Expose `{% slot %}` kwargs under the alias declared by the `{% fill %}` `data=` kwarg.
        if data_var:
            context[data_var] = ctx.data

        # Expose the slot's fallback under the alias declared by `{% fill %}` `fallback=` kwarg.
        if fallback_var:
            context[fallback_var] = ctx.fallback

        # When a `{% fill %}` tag inside a `{% comp %}` tag sits inside a forloop, `extra_context`
        # carries the forloop variables. We must inject them into the same layer as
        # `_COMPONENT_CONTEXT_KEY` so they're visible to the fill body, but BEFORE the layer
        # holding user data from `get_context_data()` so user data wins on conflict.
        index_of_last_component_layer = get_last_index(context.dicts, lambda d: _COMPONENT_CONTEXT_KEY in d)
        if index_of_last_component_layer is None:
            index_of_last_component_layer = 0

        index_of_last_component_layer -= 1

        context.dicts.insert(index_of_last_component_layer, extra_context or {})

        rendered = template.render(context)

        context.dicts.pop(index_of_last_component_layer)

        return rendered

    return Slot(
        content_func=render_func,
        component_name=component_name,
        slot_name=slot_name,
        nodelist=nodelist,
        # The `contents` param may be `None` (e.g. self-closing `{% fill "footer" / %}`).
        # Passing `None` would make `Slot.contents` the render function, so we coerce to "".
        contents=default(contents, ""),
        fill_node=default(fill_node, None),
        extra=default(extra, {}),
    )


def _is_extracting_fill(context: Context) -> bool:
    return context.get(FILL_GEN_CONTEXT_KEY, None) is not None


# Fix for compatibility with Django's `{% include %}` and `{% extends %}` tags.
# See https://github.com/django-components/django-components/issues/1325
#
# When we search for `{% fill %}` tags, we also evaluate `{% include %}` and `{% extends %}`
# tags if they are within component body (between `{% comp %}` / `{% endcomp %}` tags).
# But by doing so, we trigger Django's block/extends logic to remember that this extended file
# was already walked.
# (See https://github.com/django/django/blob/0bff53b4138d8c6009e9040dbb8916a1271a68d7/django/template/loader_tags.py#L114)
#
# We need to clear that state, otherwise Django won't render the extended template the second time
# (when we actually render it).
@contextmanager
def _extends_context_reset(context: Context) -> Generator[None, None, None]:
    b4_ctx_extends = context.render_context.setdefault("extends_context", []).copy()
    try:
        yield
    finally:
        context.render_context["extends_context"] = b4_ctx_extends
