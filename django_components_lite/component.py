# ruff: noqa: N804
import contextlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import (
    Any,
    ClassVar,
    Optional,
    Union,
    cast,
)
from weakref import ReferenceType, WeakValueDictionary, finalize, ref

from django.http import HttpRequest, HttpResponse
from django.template.base import FilterExpression, NodeList, Parser, Token
from django.template.context import Context, RequestContext
from django.utils.safestring import mark_safe

from django_components_lite.component_media import resolve_component_files
from django_components_lite.component_registry import ComponentRegistry
from django_components_lite.component_registry import registry as registry_
from django_components_lite.context import (
    _COMPONENT_CONTEXT_KEY,
    make_flat_render_context,
    make_isolated_context_copy,
)
from django_components_lite.dependencies import build_dependency_tags
from django_components_lite.node import BaseNode
from django_components_lite.slots import (
    _is_extracting_fill,
    normalize_slot_fills,
    resolve_fills,
)
from django_components_lite.template import get_component_template
from django_components_lite.util.context import gen_context_processors_data, snapshot_context
from django_components_lite.util.exception import set_component_error_message
from django_components_lite.util.misc import (
    default,
    hash_comp_cls,
)
from django_components_lite.util.weakref import cached_ref

AllComponents = list[ReferenceType[type["Component"]]]
CompHashMapping = WeakValueDictionary[str, type["Component"]]
ComponentRef = ReferenceType["Component"]


# All Component subclasses ever created, weakly. Used by tests to clean up.
ALL_COMPONENTS: AllComponents = []


def all_components() -> list[type["Component"]]:
    """List all live Component subclasses."""
    return [c for c in (ref() for ref in ALL_COMPONENTS) if c is not None]


# Maps `Component.class_id` -> the class. Hashes the module import path so we get
# a stable, unique, registry-independent ID without leaking the path itself.
comp_cls_id_mapping: CompHashMapping = WeakValueDictionary()


def get_component_by_class_id(comp_cls_id: str) -> type["Component"]:
    """Look up a Component by its `class_id`. Raises `KeyError` if unknown."""
    return comp_cls_id_mapping[comp_cls_id]


def _get_component_name(cls: type["Component"], registered_name: str | None = None) -> str:
    return default(registered_name, cls.__name__)


# CO_VARARGS bit on a function's code object - set when it declares `*args`.
# https://docs.python.org/3/library/inspect.html#inspect.CO_VARARGS
_CO_VARARGS = 0x04


def _positional_param_info(func: Any) -> tuple[tuple[str, ...], bool]:
    """Return `(positional_or_keyword_param_names, has_var_positional)` for `func`.

    Reads from `func.__code__` instead of `inspect.signature`. On Python 3.14+
    `inspect.signature` eagerly resolves annotations (PEP 649), failing with
    `NameError` for `TYPE_CHECKING`-guarded forward refs in user code.
    """
    code = func.__code__
    names = code.co_varnames[code.co_posonlyargcount : code.co_argcount]
    if names and names[0] == "self":
        names = names[1:]
    return tuple(names), bool(code.co_flags & _CO_VARARGS)


def _call_get_context_data(component: "Component", args: list[Any], kwargs: dict[str, Any]) -> Any:
    """Call `get_context_data()` routing tag positional args to the override's named params."""
    cls = component.__class__
    if cls._gctx_has_var_positional:
        return component.get_context_data(*args, **kwargs)

    pos_names = cls._gctx_positional_names
    if not args or not pos_names:
        return component.get_context_data(**kwargs)

    if len(args) > len(pos_names):
        raise TypeError(
            f"{cls.__name__}.get_context_data() takes {len(pos_names)} positional "
            f"arguments but {len(args)} were given",
        )
    call_kwargs = dict(kwargs)
    # strict=False: len(args) < len(pos_names) is valid; missing params use defaults or kwargs.
    for name, value in zip(pos_names, args, strict=False):
        if name in call_kwargs:
            raise TypeError(f"{cls.__name__}.get_context_data() got multiple values for argument {name!r}")
        call_kwargs[name] = value
    return component.get_context_data(**call_kwargs)


# Proxies `template_name` reads/writes onto `template_file`.
class ComponentTemplateNameDescriptor:
    def __get__(self, instance: Optional["Component"], cls: type["Component"]) -> Any:
        return default(instance, cls).template_file

    def __set__(self, instance_or_cls: Union["Component", type["Component"]], value: Any) -> None:
        cls = instance_or_cls if isinstance(instance_or_cls, type) else instance_or_cls.__class__
        cls.template_file = value


class ComponentMeta(type):
    def __setattr__(cls, name: str, value: Any) -> None:
        desc = cls.__dict__.get(name, None)
        if hasattr(desc, "__set__"):
            desc.__set__(cls, value)
        else:
            super().__setattr__(name, value)

    def __new__(mcs, name: str, bases: tuple[type, ...], attrs: dict) -> type:
        # Route `template_name = "..."` to `template_file`; the public `template_name`
        # attr is the descriptor.
        if "template_name" in attrs:
            attrs["template_file"] = attrs.pop("template_name")
        attrs["template_name"] = ComponentTemplateNameDescriptor()

        cls = cast("type[Component]", super().__new__(mcs, name, bases, attrs))

        # Resolve relative file paths now if Django settings are ready, else lazily.
        with contextlib.suppress(Exception):
            resolve_component_files(cls)

        return cls


# Internal per-render state, made available to slots/fills via the context.
@dataclass
class ComponentContext:
    component: ComponentRef
    component_path: list[str]
    template_name: str | None
    default_slot: str | None
    outer_context: Context | None


class Component(metaclass=ComponentMeta):
    # User-configurable class attributes.

    template_file: ClassVar[str | None] = None
    """Path to the component's Django template. Resolved relative to the component's
    Python file, then `COMPONENTS.dirs` / `COMPONENTS.app_dirs`, then Django template dirs."""

    # Descriptor proxying to `template_file`; declared here only for type hints.
    template_name: ClassVar[str | None]
    """Legacy alias for `template_file`."""

    template: str | None = None
    """Inline Django template string. Mutually exclusive with `template_file`."""

    js: str | None = None
    """Inline JS string. Mutually exclusive with `js_file`."""

    js_file: ClassVar[str | None] = None
    """Path to a JS file rendered as a `<script>` tag prepended to the output. Resolved like `template_file`."""

    response_class: ClassVar[type[HttpResponse]] = HttpResponse
    """Response class used by `render_to_response()`."""

    class_id: ClassVar[str]
    """Stable unique ID derived from the component's module import path, e.g. `MyComponent_ab01f2`."""

    do_not_call_in_templates: ClassVar[bool] = True
    """Django marker preventing the instance from being called as a function in templates."""

    def __init__(
        self,
        registered_name: str | None = None,
        outer_context: Context | None = None,
        registry: ComponentRegistry | None = None,
        context: Context | None = None,
        args: Any | None = None,
        kwargs: Any | None = None,
        slots: Any | None = None,
        request: HttpRequest | None = None,
        node: Optional["ComponentNode"] = None,
        name: str | None = None,
    ) -> None:
        self.name = name if name is not None else _get_component_name(self.__class__, registered_name)
        self.registered_name: str | None = registered_name
        self.args = [] if args is None else args
        self.kwargs = {} if kwargs is None else kwargs
        self.slots = {} if slots is None else slots
        self.context = Context() if context is None else context
        self.request = request
        self.outer_context: Context | None = outer_context
        self.registry = registry_ if registry is None else registry
        self.node = node

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.class_id = hash_comp_cls(cls)
        comp_cls_id_mapping[cls.class_id] = cls

        ALL_COMPONENTS.append(cached_ref(cls))

        # Cache positional-param metadata for the override so _render can route
        # tag positional args without re-inspecting the signature each render.
        gctx = cls.__dict__.get("get_context_data")
        if gctx is not None:
            cls._gctx_positional_names, cls._gctx_has_var_positional = _positional_param_info(gctx)

    # Defaults for the un-overridden base `get_context_data(**kwargs)`.
    _gctx_positional_names: ClassVar[tuple[str, ...]] = ()
    _gctx_has_var_positional: ClassVar[bool] = False

    # Instance attribute type hints (set in __init__).

    name: str
    """Component name: the registered name if registered, else the class name."""

    registered_name: str | None
    """Name under which the component was registered, or `None` if rendered directly via `render()`."""

    args: Any
    """Positional arguments passed to the component (plain list)."""

    kwargs: Any
    """Keyword arguments passed to the component (plain dict)."""

    slots: Any
    """Slots passed to the component, mapping slot name to `Slot` instance."""

    context: Context
    """The Django `Context` the template renders against. Templates only see what `get_context_data()`
    returns; pass data via args/kwargs."""

    outer_context: Context | None
    """The `Context` outside the `{% comp %}` tag at the call site, or `None` when rendered via `render()`."""

    registry: ComponentRegistry
    """The `ComponentRegistry` that resolved this component."""

    node: Optional["ComponentNode"]
    """The `ComponentNode` that triggered this render, or `None` when rendered via `render()`."""

    request: HttpRequest | None
    """The `HttpRequest`, propagated from `RequestContext` or the `request` kwarg of `render()`."""

    @property
    def context_processors_data(self) -> dict:
        """Django context-processor output. Empty unless `request` is set (via `RequestContext` or `render(request=...)`)."""
        if self.request is None:
            return {}
        return gen_context_processors_data(self.context, self.request)

    @classmethod
    def render_to_response(
        cls,
        context: dict[str, Any] | Context | None = None,
        args: Any | None = None,
        kwargs: Any | None = None,
        slots: Any | None = None,
        request: HttpRequest | None = None,
        outer_context: Context | None = None,
        registry: ComponentRegistry | None = None,
        registered_name: str | None = None,
        node: Optional["ComponentNode"] = None,
        **response_kwargs: Any,
    ) -> HttpResponse:
        """Render to a string and wrap in `response_class`. Extra kwargs go to the response class."""
        content = cls.render(
            args=args,
            kwargs=kwargs,
            context=context,
            slots=slots,
            request=request,
            outer_context=outer_context,
            registry=registry,
            registered_name=registered_name,
            node=node,
        )
        return cls.response_class(content, **response_kwargs)

    @classmethod
    def render(
        cls,
        context: dict[str, Any] | Context | None = None,
        args: Any | None = None,
        kwargs: Any | None = None,
        slots: Any | None = None,
        request: HttpRequest | None = None,
        outer_context: Context | None = None,
        registry: ComponentRegistry | None = None,
        registered_name: str | None = None,
        node: Optional["ComponentNode"] = None,
    ) -> str:
        """Render the component to a string. Python equivalent of `{% comp "name" args... kwargs %}`.

        `slots` accepts strings, render functions, or `Slot` instances. Pass a `RequestContext`
        (or the `request` kwarg) to enable Django context processors.
        """
        return cls._render(
            context=context,
            args=args,
            kwargs=kwargs,
            slots=slots,
            request=request,
            outer_context=outer_context,
            registry=registry,
            registered_name=registered_name,
            node=node,
        )

    # Entrypoint for both `Component.render()` and `ComponentNode.render()`.
    @classmethod
    def _render(
        comp_cls,
        context: dict[str, Any] | Context | None = None,
        args: Any | None = None,
        kwargs: Any | None = None,
        slots: Any | None = None,
        request: HttpRequest | None = None,
        outer_context: Context | None = None,
        registry: ComponentRegistry | None = None,
        registered_name: str | None = None,
        node: Optional["ComponentNode"] = None,
    ) -> str:
        # Resolve request: explicit kwarg, RequestContext.request, then parent component's request.
        parent_comp_ctx = _get_parent_component_context(context) if context else None
        if request is None and context:
            request = getattr(context, "request", None)
            if request is None and parent_comp_ctx:
                parent_comp = parent_comp_ctx.component()
                request = parent_comp and parent_comp.request

        component_name = _get_component_name(comp_cls, registered_name)
        args_list: list[Any] = [] if args is None else list(args)
        kwargs_dict: dict[str, Any] = {} if kwargs is None else kwargs
        slots_dict = normalize_slot_fills(slots, component_name=component_name) if slots else {}
        context = context if context is not None else (RequestContext(request) if request else Context())

        # Wrap a plain dict, but never wrap a Context in another Context.
        # See https://github.com/django-components/django-components/issues/414
        if not isinstance(context, (Context, RequestContext)):
            context = RequestContext(request, context) if request else Context(context)

        component = comp_cls(
            args=args_list,
            kwargs=kwargs_dict,
            slots=slots_dict,
            context=context,
            request=request,
            outer_context=outer_context,
            registry=registry,
            registered_name=registered_name,
            node=node,
            name=component_name,
        )

        component_path = (
            [*parent_comp_ctx.component_path, component_name] if parent_comp_ctx is not None else [component_name]
        )

        # Snapshot outer_context only when slots were passed (the only consumer).
        # Use a weak ref to the component so the template can't keep it alive.
        ctx_outer = snapshot_context(outer_context) if slots_dict and outer_context is not None else None
        component_ctx = ComponentContext(
            component=ref(component),
            component_path=component_path,
            template_name=None,  # Set once we resolve the Template below.
            default_slot=None,  # Set by SlotNode.render() if a slot is marked default.
            outer_context=ctx_outer,
        )

        # Prepend the component name to the exception path for nested-render errors.
        try:
            # Fast path: skip positional routing when the override doesn't need it.
            if args_list and (comp_cls._gctx_positional_names or comp_cls._gctx_has_var_positional):
                template_data = _call_get_context_data(component, args_list, kwargs_dict) or {}
            else:
                template_data = component.get_context_data(**kwargs_dict) or {}

            template = get_component_template(component)
            component_ctx.template_name = template.name if template else None

            if template is None:
                html = None
            else:
                # Flat isolated context: merge template_data + context_processors + internal
                # key into one base layer so the engine doesn't walk a push/pop stack per lookup.
                # Skip context_processors_data when no request (it returns {} anyway).
                if request is None:
                    render_data = {**template_data, _COMPONENT_CONTEXT_KEY: component_ctx}
                else:
                    render_data = {
                        **component.context_processors_data,
                        **template_data,
                        _COMPONENT_CONTEXT_KEY: component_ctx,
                    }
                render_ctx = make_flat_render_context(context, render_data)
                render_ctx.template = template
                html = template.render(render_ctx)
        except Exception as err:
            set_component_error_message(err, [component_name])
            raise err from None

        if html is not None:
            dep_tags = build_dependency_tags(comp_cls)
            if dep_tags:
                html = dep_tags + "\n" + html

        return mark_safe(html) if html is not None else ""  # noqa: S308

    # `Any` lets subclasses narrow the signature (e.g. `def get_context_data(self, *, user)`)
    # without tripping mypy's Liskov [override] check.
    get_context_data: Any

    def get_context_data(self, **kwargs: Any) -> dict:  # type: ignore[no-redef]
        """Return template context variables. Override with any signature; default returns `{}`.

        Positional tag args are routed to the override's named parameters; access positional
        args, slots, and the outer context via `self.args`, `self.slots`, `self.context`.
        """
        return {}


# Cache of `ComponentNode` subclasses keyed by start tag, so we don't create a new
# subclass on every parse. Tied to a single registry per tag.
component_node_subclasses_by_name: dict[str, tuple[type["ComponentNode"], ComponentRegistry]] = {}


class ComponentNode(BaseNode):
    """The `{% comp %}` template tag. Renders a registered component."""

    tag = "comp"
    end_tag: ClassVar[str | None] = "endcomp"
    allowed_flags = ()
    _skip_param_validation = True

    def __init__(
        self,
        name: str,
        registry: ComponentRegistry,
        params: tuple[list[FilterExpression], dict[str, FilterExpression]] | None = None,
        flags: dict[str, bool] | None = None,
        nodelist: NodeList | None = None,
        contents: str | None = None,
        template_name: str | None = None,
    ) -> None:
        super().__init__(
            params=params,
            flags=flags,
            nodelist=nodelist,
            contents=contents,
            template_name=template_name,
        )
        self.name = name
        self.registry = registry

    @classmethod
    def parse(  # type: ignore[override]
        cls,
        parser: Parser,
        token: Token,
        registry: ComponentRegistry,
        name: str,
        start_tag: str,
        end_tag: str | None,
    ) -> "ComponentNode":
        # Component-specific start/end tags are encoded as a per-tag subclass, cached.
        subcls_name = cls.__name__ + "_" + name

        if start_tag not in component_node_subclasses_by_name:
            subcls: type[ComponentNode] = type(subcls_name, (cls,), {"tag": start_tag, "end_tag": end_tag})
            component_node_subclasses_by_name[start_tag] = (subcls, registry)
            # Drop the cache entry when either the subclass or the registry dies.
            finalize(subcls, lambda: component_node_subclasses_by_name.pop(start_tag, None))
            finalize(registry, lambda: component_node_subclasses_by_name.pop(start_tag, None))

        cached_subcls, cached_registry = component_node_subclasses_by_name[start_tag]

        if cached_registry is not registry:
            raise RuntimeError(
                f"Detected two Components from different registries using the same start tag '{start_tag}'",
            )
        if cached_subcls.end_tag != end_tag:
            raise RuntimeError(
                f"Detected two Components using the same start tag '{start_tag}' but with different end tags",
            )

        return super(cls, cached_subcls).parse(parser, token, registry=cached_registry, name=name)

    def render(self, context: Context, *args: Any, **kwargs: Any) -> str:
        # During fill extraction we walk the body without rendering nested components.
        if _is_extracting_fill(context):
            return ""

        component_cls: type[Component] = self.registry.get(self.name)
        # Skip the fill walk when there's no body (e.g. `{% compc "card" ... / %}`).
        slot_fills = resolve_fills(context, self, self.name) if self.nodelist else {}
        inner_context = make_isolated_context_copy(context)

        return component_cls._render(
            context=inner_context,
            args=args,
            kwargs=kwargs,
            slots=slot_fills,
            registered_name=self.name,
            outer_context=context,
            registry=self.registry,
            node=self,
        )


def _get_parent_component_context(context: Context | Mapping) -> ComponentContext | None:
    return context.get(_COMPONENT_CONTEXT_KEY, None)
