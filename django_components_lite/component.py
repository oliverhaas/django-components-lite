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

# NOTE: `ReferenceType` is NOT a generic pre-3.9
AllComponents = list[ReferenceType[type["Component"]]]
CompHashMapping = WeakValueDictionary[str, type["Component"]]
ComponentRef = ReferenceType["Component"]


# Keep track of all the Component classes created, so we can clean up after tests
ALL_COMPONENTS: AllComponents = []


def all_components() -> list[type["Component"]]:
    """Get a list of all created [`Component`](../api#django_components_lite.Component) classes."""
    components: list[type[Component]] = []
    for comp_ref in ALL_COMPONENTS:
        comp = comp_ref()
        if comp is not None:
            components.append(comp)
    return components


# NOTE: Initially, we fetched components by their registered name, but that didn't work
# for multiple registries and unregistered components.
#
# To have unique identifiers that works across registries, we rely
# on component class' module import path (e.g. `path.to.my.MyComponent`).
#
# But we also don't want to expose the module import paths to the outside world, as
# that information could be potentially exploited. So, instead, each component is
# associated with a hash that's derived from its module import path, ensuring uniqueness,
# consistency and privacy.
#
# E.g. `path.to.my.secret.MyComponent` -> `ab01f32`
#
# For easier debugging, we then prepend the hash with the component class name, so that
# we can easily identify the component class by its hash.
#
# E.g. `path.to.my.secret.MyComponent` -> `MyComponent_ab01f32`
#
# The associations are defined as WeakValue map, so deleted components can be garbage
# collected and automatically deleted from the dict.
comp_cls_id_mapping: CompHashMapping = WeakValueDictionary()


def get_component_by_class_id(comp_cls_id: str) -> type["Component"]:
    """
    Get a component class by its unique ID.

    Each component class is associated with a unique hash that's derived from its module import path.

    E.g. `path.to.my.secret.MyComponent` -> `MyComponent_ab01f32`

    This hash is available under [`class_id`](../api#django_components_lite.Component.class_id)
    on the component class.

    Raises `KeyError` if the component class is not found.

    NOTE: This is mainly intended for extensions.
    """
    return comp_cls_id_mapping[comp_cls_id]


def _get_component_name(cls: type["Component"], registered_name: str | None = None) -> str:
    return default(registered_name, cls.__name__)


# CO_VARARGS flag on the function's code object - set when the function
# declares ``*args``. Documented at
# https://docs.python.org/3/library/inspect.html#inspect.CO_VARARGS (0x04).
_CO_VARARGS = 0x04


def _positional_param_info(func: Any) -> tuple[tuple[str, ...], bool]:
    """
    Return ``(positional_or_keyword_param_names, has_var_positional)`` for ``func``.

    Reads the names straight off ``func.__code__`` instead of going through
    ``inspect.signature``. On Python 3.14+ ``inspect.signature`` eagerly
    resolves annotations (PEP 649), which fails with ``NameError`` for
    ``TYPE_CHECKING``-guarded forward references in user code. We only need
    parameter names and the ``*args`` flag, so the code-object read is both
    immune to that and faster.
    """
    code = func.__code__
    # [posonly : argcount] is the positional-or-keyword slice.
    # Drop `self` if the method hasn't been decorated to make it positional-only.
    names = code.co_varnames[code.co_posonlyargcount : code.co_argcount]
    if names and names[0] == "self":
        names = names[1:]
    has_var_positional = bool(code.co_flags & _CO_VARARGS)
    return tuple(names), has_var_positional


def _call_get_context_data(component: "Component", args: list[Any], kwargs: dict[str, Any]) -> Any:
    """
    Call ``component.get_context_data(...)`` routing template-tag positional
    args into the corresponding named parameters on the override's signature.

    Uses metadata cached at ``__init_subclass__`` time. Fast-paths the common
    case where no positional routing is needed.
    """
    cls = component.__class__
    if cls._gctx_has_var_positional:
        # Override declares `*args` - pass positional args through natively.
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
    # ``strict=False`` because len(args) < len(pos_names) is valid:
    # the remaining params either have defaults or are supplied via kwargs.
    for name, value in zip(pos_names, args, strict=False):
        if name in call_kwargs:
            raise TypeError(
                f"{cls.__name__}.get_context_data() got multiple values for argument {name!r}",
            )
        call_kwargs[name] = value
    return component.get_context_data(**call_kwargs)


# Descriptor to pass getting/setting of `template_name` onto `template_file`
class ComponentTemplateNameDescriptor:
    def __get__(self, instance: Optional["Component"], cls: type["Component"]) -> Any:
        obj = default(instance, cls)
        return obj.template_file

    def __set__(self, instance_or_cls: Union["Component", type["Component"]], value: Any) -> None:
        cls = instance_or_cls if isinstance(instance_or_cls, type) else instance_or_cls.__class__
        cls.template_file = value


class ComponentMeta(type):
    def __setattr__(cls, name: str, value: Any) -> None:
        # Support descriptor protocol for class-level attribute assignment
        desc = cls.__dict__.get(name, None)
        if hasattr(desc, "__set__"):
            desc.__set__(cls, value)
        else:
            super().__setattr__(name, value)

    def __new__(mcs, name: str, bases: tuple[type, ...], attrs: dict) -> type:
        # If user set `template_name` on the class, we instead set it to `template_file`,
        # because we want `template_name` to be the descriptor that proxies to `template_file`.
        if "template_name" in attrs:
            attrs["template_file"] = attrs.pop("template_name")
        attrs["template_name"] = ComponentTemplateNameDescriptor()

        cls = cast("type[Component]", super().__new__(mcs, name, bases, attrs))

        # Resolve relative file paths (template_file, js_file, css_file) into
        # paths relative to COMPONENTS.dirs root.
        # May fail during Django startup when settings aren't ready yet.
        # Files will be resolved on first access instead.
        with contextlib.suppress(Exception):
            resolve_component_files(cls)

        return cls


# Internal data that are made available within the component's template
@dataclass
class ComponentContext:
    component: ComponentRef
    component_path: list[str]
    template_name: str | None
    default_slot: str | None
    outer_context: Context | None


class Component(metaclass=ComponentMeta):
    # #####################################
    # PUBLIC API (Configurable by users)
    # #####################################

    template_file: ClassVar[str | None] = None
    """Path to the component's Django template. Resolved relative to the component's
    Python file, then `COMPONENTS.dirs` / `COMPONENTS.app_dirs`, then Django template dirs."""

    # NOTE: Managed by `ComponentTemplateNameDescriptor` set in the metaclass; declared
    # here for type hinting.
    template_name: ClassVar[str | None]
    """Legacy alias for `template_file`."""

    template: str | None = None
    """Inline Django template string. Mutually exclusive with `template_file`."""

    js: str | None = None
    """Inline JS string. Mutually exclusive with `js_file`."""

    js_file: ClassVar[str | None] = None
    """Path to a JS file. Resolved like `template_file`; rendered as a `<script>` tag prepended to the output."""

    response_class: ClassVar[type[HttpResponse]] = HttpResponse
    """Response class used by `render_to_response()`. Defaults to `django.http.HttpResponse`."""

    # #####################################
    # MISC
    # #####################################

    class_id: ClassVar[str]
    """Unique ID of the component class, e.g. `MyComponent_ab01f2`,
    derived from its module import path."""

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
        # `name` can be supplied by the render pipeline to avoid recomputing.
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

        # If the subclass overrides get_context_data, cache its positional-
        # parameter metadata so _render can route tag positional args into
        # the right parameter slots without re-inspecting the signature on
        # every render.
        gctx = cls.__dict__.get("get_context_data")
        if gctx is not None:
            cls._gctx_positional_names, cls._gctx_has_var_positional = _positional_param_info(gctx)

    # Defaults used when the base ``get_context_data(**kwargs)`` is not
    # overridden: no positional routing, no ``*args``.
    _gctx_positional_names: ClassVar[tuple[str, ...]] = ()
    _gctx_has_var_positional: ClassVar[bool] = False

    ########################################
    # INSTANCE PROPERTIES
    ########################################

    name: str
    """Component name. The registered name if registered, else the class name."""

    registered_name: str | None
    """The name under which the component was registered, or `None` if rendered directly via `Component.render()`."""

    args: Any
    """Positional arguments passed to the component (plain list)."""

    kwargs: Any
    """Keyword arguments passed to the component (plain dict)."""

    slots: Any
    """Slots passed to the component, mapping slot name to `Slot` instance."""

    context: Context
    """The Django `Context` the template renders against. Components use isolated context,
    so the template only sees what `get_context_data()` returns; pass data via args/kwargs."""

    outer_context: Context | None
    """The `Context` outside the `{% comp %}` tag at the call site, or `None` when rendered via `Component.render()`."""

    registry: ComponentRegistry
    """The `ComponentRegistry` that resolved this component."""

    node: Optional["ComponentNode"]
    """The `ComponentNode` that triggered this render, or `None` when rendered via `Component.render()`."""

    request: HttpRequest | None
    """The `HttpRequest`, propagated from `RequestContext` or the `request` kwarg of `render()`."""

    @property
    def context_processors_data(self) -> dict:
        """Data from Django context processors. Available when rendered with
        `RequestContext` or with the `request` kwarg of `render()` set."""
        request = self.request

        if request is None:
            return {}
        return gen_context_processors_data(self.context, request)

    # #####################################
    # MISC
    # #####################################

    # #####################################
    # RENDERING
    # #####################################

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
        """
        Render the component and wrap the content in an HTTP response class.

        `render_to_response()` takes the same inputs as
        [`Component.render()`](../api/#django_components_lite.Component.render).
        See that method for more information.

        After the component is rendered, the HTTP response class is instantiated with the rendered content.

        Any additional kwargs are passed to the response class.

        **Example:**

        ```python
        Button.render_to_response(
            args=["John"],
            kwargs={
                "surname": "Doe",
                "age": 30,
            },
            slots={
                "footer": "i AM A SLOT",
            },
            # HttpResponse kwargs
            status=201,
            headers={...},
        )
        # HttpResponse(content=..., status=201, headers=...)
        ```

        **Custom response class:**

        You can set a custom response class on the component via
        [`Component.response_class`](../api/#django_components_lite.Component.response_class).
        Defaults to
        [`django.http.HttpResponse`](https://docs.djangoproject.com/en/5.2/ref/request-response/#httpresponse-objects).

        ```python
        from django.http import HttpResponse
        from django_components_lite import Component

        class MyHttpResponse(HttpResponse):
            ...

        class MyComponent(Component):
            response_class = MyHttpResponse

        response = MyComponent.render_to_response()
        assert isinstance(response, MyHttpResponse)
        ```
        """
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
        """
        Render the component into a string. This is the equivalent of calling
        the [`{% component %}`](../template_tags#component) tag.

        ```python
        Button.render(
            args=["John"],
            kwargs={
                "surname": "Doe",
                "age": 30,
            },
            slots={
                "footer": "i AM A SLOT",
            },
        )
        ```

        **Inputs:**

        - `args` - Optional. A list of positional args for the component. This is the same as calling the component
          as:

            ```django
            {% component "button" arg1 arg2 ... %}
            ```

        - `kwargs` - Optional. A dictionary of keyword arguments for the component. This is the same as calling
          the component as:

            ```django
            {% component "button" key1=val1 key2=val2 ... %}
            ```

        - `slots` - Optional. A dictionary of slot fills. This is the same as passing [`{% fill %}`](../template_tags#fill)
            tags to the component.

            ```django
            {% component "button" %}
                {% fill "content" %}
                    Click me!
                {% endfill %}
            {% endcomponent %}
            ```

            Dictionary keys are the slot names. Dictionary values are the slot fills.

            Slot fills can be strings, render functions, or [`Slot`](../api/#django_components_lite.Slot) instances:

            ```python
            Button.render(
                slots={
                    "content": "Click me!"
                    "content2": lambda ctx: "Click me!",
                    "content3": Slot(lambda ctx: "Click me!"),
                },
            )
            ```

        - `context` - Optional. Plain dictionary or Django's
            [Context](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Context).
            The context within which the component is rendered.

            When a component is rendered within a template with the [`{% component %}`](../template_tags#component)
            tag, this will be set to the
            [Context](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Context)
            instance that is used for rendering the template.

            When you call `Component.render()` directly from Python, you can ignore this input most of the time.
            Instead use `args`, `kwargs`, and `slots` to pass data to the component.

            You can pass
            [`RequestContext`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.RequestContext)
            to the `context` argument, so that the component will gain access to the request object and will use
            [context processors](https://docs.djangoproject.com/en/5.2/ref/templates/api/#using-requestcontext).
            Read more on [Working with HTTP requests](../../concepts/fundamentals/http_request).

            ```py
            Button.render(
                context=RequestContext(request),
            )
            ```

            Components use isolated context, so the template will NOT have access to this context directly.
            Data MUST be passed via component's args and kwargs.

        - `request` - Optional. HTTPRequest object. Pass a request object directly to the component to apply
            [context processors](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Context.update).

            Read more about [Working with HTTP requests](../../concepts/fundamentals/http_request).

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

    # Internal entrypoint for rendering - used by the public render() above
    # and by ComponentNode.render() for the {% component %} tag path.
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
        ######################################
        # 1. Handle inputs
        ######################################

        # Allow to pass down Request object via context.
        # `context` may be passed explicitly via `Component.render()` and `Component.render_to_response()`,
        # or implicitly via `{% component %}` tag.
        parent_comp_ctx = _get_parent_component_context(context) if context else None
        if request is None and context:
            # If the context is `RequestContext`, it has `request` attribute
            request = getattr(context, "request", None)
            # Check if this is a nested component and whether parent has request
            if request is None and parent_comp_ctx:
                parent_comp = parent_comp_ctx.component()
                request = parent_comp and parent_comp.request

        component_name = _get_component_name(comp_cls, registered_name)

        # Allow to provide no args/kwargs/slots/context.
        args_list: list[Any] = [] if args is None else list(args)
        kwargs_dict: dict[str, Any] = {} if kwargs is None else kwargs
        slots_dict = normalize_slot_fills(slots, component_name=component_name) if slots else {}
        # Use RequestContext if request is provided, so that child non-component template tags
        # can access the request object too.
        context = context if context is not None else (RequestContext(request) if request else Context())

        # Allow to provide a dict instead of Context
        # NOTE: This if/else is important to avoid nested Contexts,
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

        ######################################
        # 2. Prepare component state
        ######################################

        # `parent_comp_ctx` was resolved above when checking for a parent's request.
        if parent_comp_ctx is not None:
            component_path = [*parent_comp_ctx.component_path, component_name]
        else:
            component_path = [component_name]

        # This is data that will be accessible (internally) from within the component's template.
        # NOTE: Be careful with the context - Do not store a strong reference to the component,
        #       because that would prevent the component from being garbage collected.
        # Only snapshot outer_context when slots were passed: filled slots are
        # the only code path that consults ComponentContext.outer_context.
        ctx_outer = snapshot_context(outer_context) if slots_dict and outer_context is not None else None
        component_ctx = ComponentContext(
            component=ref(component),
            component_path=component_path,
            # Template name is set only once we've resolved the component's Template instance.
            template_name=None,
            # This field will be modified from within `SlotNodes.render()`:
            # - The `default_slot` will be set to the first slot that has the `default` attribute set.
            # - If multiple slots have the `default` attribute set, yet have different name, then
            #   we will raise an error.
            default_slot=None,
            outer_context=ctx_outer,
        )

        ######################################
        # 3. Call data methods & render
        ######################################

        # Wrap the user-code + template render in a try/except so nested
        # component failures surface with the full component path prepended
        # to the exception message.
        try:
            # Fast path: common case has no positional routing to do, so avoid
            # the extra function call and attribute lookups.
            if args_list and (comp_cls._gctx_positional_names or comp_cls._gctx_has_var_positional):
                template_data = _call_get_context_data(component, args_list, kwargs_dict) or {}
            else:
                template_data = component.get_context_data(**kwargs_dict) or {}

            template = get_component_template(component)
            component_ctx.template_name = template.name if template else None

            if template is None:
                html = None
            else:
                # Flat isolated context: template_data + context_processors +
                # internal component key, merged into the base layer so the
                # template engine doesn't walk a push/pop stack per lookup.
                # Skip the context_processors_data property when there's no
                # request - it always returns {} in that case.
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

        # Prepend <link>/<script> tags for this component's JS/CSS files
        if html is not None:
            dep_tags = build_dependency_tags(comp_cls)
            if dep_tags:
                html = dep_tags + "\n" + html

        return mark_safe(html) if html is not None else ""  # noqa: S308

    # User-override hook. Typed as Any so subclasses can narrow the signature
    # (e.g. `def get_context_data(self, *, user): ...`) without triggering
    # mypy's [override] check for Liskov violations.
    get_context_data: Any

    def get_context_data(self, **kwargs: Any) -> dict:  # type: ignore[no-redef]
        """
        Override this to provide template context variables.

        Receives the kwargs that were passed to the component. For access to
        positional args, slots, or the outer context, use ``self.args``,
        ``self.slots``, ``self.context``.

        By default, returns an empty dict.
        """
        return {}


# Perf
# Each component may use different start and end tags. We represent this
# as individual subclasses of `ComponentNode`. However, multiple components
# may use the same start & end tag combination, e.g. `{% component %}` and `{% endcomponent %}`.
# So we cache the already-created subclasses to be reused.
component_node_subclasses_by_name: dict[str, tuple[type["ComponentNode"], ComponentRegistry]] = {}


class ComponentNode(BaseNode):
    """
    Renders one of the components that was previously registered with
    [`@register()`](./api.md#django_components_lite.register)
    decorator.

    The [`{% component %}`](../template_tags#component) tag takes:

    - Component's registered name as the first positional argument,
    - Followed by any number of positional and keyword arguments.

    ```django
    {% load component_tags %}
    <div>
        {% component "button" name="John" job="Developer" / %}
    </div>
    ```

    The component name must be a string literal.

    ### Inserting slot fills

    If the component defined any [slots](../concepts/fundamentals/slots.md), you can
    "fill" these slots by placing the [`{% fill %}`](../template_tags#fill) tags
    within the [`{% component %}`](../template_tags#component) tag:

    ```django
    {% component "my_table" rows=rows headers=headers %}
      {% fill "pagination" %}
        < 1 | 2 | 3 >
      {% endfill %}
    {% endcomponent %}
    ```

    You can even nest [`{% fill %}`](../template_tags#fill) tags within
    [`{% if %}`](https://docs.djangoproject.com/en/5.2/ref/templates/builtins/#if),
    [`{% for %}`](https://docs.djangoproject.com/en/5.2/ref/templates/builtins/#for)
    and other tags:

    ```django
    {% component "my_table" rows=rows headers=headers %}
        {% if rows %}
            {% fill "pagination" %}
                < 1 | 2 | 3 >
            {% endfill %}
        {% endif %}
    {% endcomponent %}
    ```

    ### Isolated context

    Components always use isolated context - the template inside the component does NOT have
    access to variables defined in the outer template. Data must be passed explicitly via
    args and kwargs.
    """

    tag = "comp"
    end_tag = "endcomp"
    allowed_flags = ()
    _skip_param_validation = True

    def __init__(
        self,
        # ComponentNode inputs
        name: str,
        registry: ComponentRegistry,
        # BaseNode inputs
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
        # Set the component-specific start and end tags by subclassing the BaseNode
        subcls_name = cls.__name__ + "_" + name

        # We try to reuse the same subclass for the same start tag, so we can
        # avoid creating a new subclass for each time `{% component %}` is called.
        if start_tag not in component_node_subclasses_by_name:
            subcls: type[ComponentNode] = type(subcls_name, (cls,), {"tag": start_tag, "end_tag": end_tag})
            component_node_subclasses_by_name[start_tag] = (subcls, registry)

            # Remove the cache entry when either the registry or the component are deleted
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

        # Call `BaseNode.parse()` as if with the context of subcls.
        node: ComponentNode = super(cls, cached_subcls).parse(
            parser,
            token,
            registry=cached_registry,
            name=name,
        )
        return node

    def render(self, context: Context, *args: Any, **kwargs: Any) -> str:
        # Do not render nested `{% component %}` tags in other `{% component %}` tags
        # at the stage when we are determining if the latter has named fills or not.
        if _is_extracting_fill(context):
            return ""

        component_cls: type[Component] = self.registry.get(self.name)

        # Skip the fill-resolution walk when the tag has no body (common case
        # for props-only components like `{% component "card" ... / %}`).
        slot_fills = resolve_fills(context, self, self.name) if self.nodelist else {}

        # Components use isolated context: the template only sees what get_context_data() returns,
        # like Django's inclusion_tag behavior.
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
