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
from django.template.base import FilterExpression, NodeList, Parser, Template, Token
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
from django_components_lite.template import cache_component_template_file, get_component_template
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

        # If the component defined `template_file`, then associate this Component class
        # with that template file path.
        if attrs.get("template_file"):
            cache_component_template_file(cls)

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
    """
    Filepath to the Django template associated with this component.

    The filepath must be either:

    - Relative to the directory where the Component's Python file is defined.
    - Relative to one of the component directories, as set by
      [`COMPONENTS.dirs`](../settings#django_components_lite.app_settings.ComponentsSettings.dirs)
      or
      [`COMPONENTS.app_dirs`](../settings#django_components_lite.app_settings.ComponentsSettings.app_dirs)
      (e.g. `<root>/components/`).
    - Relative to the template directories, as set by Django's `TEMPLATES` setting (e.g. `<root>/templates/`).

    !!! warning

        Only one of [`template_file`](../api#django_components_lite.Component.template_file)
        or [`template`](../api#django_components_lite.Component.template) must be defined.

    **Example:**

    Assuming this project layout:

    ```txt
    |- components/
      |- table/
        |- table.html
        |- table.css
        |- table.js
    ```

    Template name can be either relative to the python file (`components/table/table.py`):

    ```python
    class Table(Component):
        template_file = "table.html"
    ```

    Or relative to one of the directories in
    [`COMPONENTS.dirs`](../settings#django_components_lite.app_settings.ComponentsSettings.dirs)
    or
    [`COMPONENTS.app_dirs`](../settings#django_components_lite.app_settings.ComponentsSettings.app_dirs)
    (`components/`):

    ```python
    class Table(Component):
        template_file = "table/table.html"
    ```
    """

    # NOTE: This attribute is managed by `ComponentTemplateNameDescriptor` that's set in the metaclass.
    #       But we still define it here for documenting and type hinting.
    template_name: ClassVar[str | None]
    """
    Alias for [`template_file`](../api#django_components_lite.Component.template_file).

    For historical reasons, django-components used `template_name` to align with Django's
    [TemplateView](https://docs.djangoproject.com/en/5.2/ref/class-based-views/base/#django.views.generic.base.TemplateView).

    `template_file` was introduced to align with
    [`js`](../api#django_components_lite.Component.js)/[`js_file`](../api#django_components_lite.Component.js_file)
    and [`css`](../api#django_components_lite.Component.css)/[`css_file`](../api#django_components_lite.Component.css_file).

    Setting and accessing this attribute is proxied to
    [`template_file`](../api#django_components_lite.Component.template_file).
    """

    template: str | None = None
    """
    Inlined Django template (as a plain string) associated with this component.

    !!! warning

        Only one of
        [`template_file`](../api#django_components_lite.Component.template_file)
        or [`template`](../api#django_components_lite.Component.template)
        must be defined.

    **Example:**

    ```python
    class Table(Component):
        template = '''
          <div>
            {{ my_var }}
          </div>
        '''
    ```

    **Syntax highlighting**

    When using the inlined template, you can enable syntax highlighting
    with `str`.

    Learn more about [syntax highlighting](../../concepts/fundamentals/single_file_components/#syntax-highlighting).

    ```djc_py
    from django_components_lite import Component, types

    class MyComponent(Component):
        template: str = '''
          <div>
            {{ my_var }}
          </div>
        '''
    ```
    """

    js: str | None = None
    """
    Main JS associated with this component inlined as string.

    !!! warning

        Only one of [`js`](../api#django_components_lite.Component.js) or
        [`js_file`](../api#django_components_lite.Component.js_file) must be defined.

    **Example:**

    ```py
    class MyComponent(Component):
        js = "console.log('Hello, World!');"
    ```

    **Syntax highlighting**

    When using the inlined template, you can enable syntax highlighting
    with `str`.

    Learn more about [syntax highlighting](../../concepts/fundamentals/single_file_components/#syntax-highlighting).

    ```djc_py
    from django_components_lite import Component, types

    class MyComponent(Component):
        js: str = '''
          console.log('Hello, World!');
        '''
    ```
    """

    js_file: ClassVar[str | None] = None
    """
    Main JS associated with this component as file path.

    The filepath must be either:

    - Relative to the directory where the Component's Python file is defined.
    - Relative to one of the component directories, as set by
      [`COMPONENTS.dirs`](../settings#django_components_lite.app_settings.ComponentsSettings.dirs)
      or
      [`COMPONENTS.app_dirs`](../settings#django_components_lite.app_settings.ComponentsSettings.app_dirs)
      (e.g. `<root>/components/`).
    - Relative to the staticfiles directories, as set by Django's `STATICFILES_DIRS` setting (e.g. `<root>/static/`).

    When you create a Component class with `js_file`, these will happen:

    1. If the file path is relative to the directory where the component's Python file is,
       the path is resolved.
    2. The file is read and its contents is set to [`Component.js`](../api#django_components_lite.Component.js).

    !!! warning

        Only one of [`js`](../api#django_components_lite.Component.js) or
        [`js_file`](../api#django_components_lite.Component.js_file) must be defined.

    **Example:**

    ```js title="path/to/script.js"
    console.log('Hello, World!');
    ```

    ```py title="path/to/component.py"
    class MyComponent(Component):
        js_file = "path/to/script.js"

    print(MyComponent.js)
    # Output: console.log('Hello, World!');
    ```
    """

    response_class: ClassVar[type[HttpResponse]] = HttpResponse
    """
    This attribute configures what class is used to generate response from
    [`Component.render_to_response()`](../api/#django_components_lite.Component.render_to_response).

    The response class should accept a string as the first argument.

    Defaults to
    [`django.http.HttpResponse`](https://docs.djangoproject.com/en/5.2/ref/request-response/#httpresponse-objects).

    **Example:**

    ```py
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

    # #####################################
    # MISC
    # #####################################

    class_id: ClassVar[str]
    """
    Unique ID of the component class, e.g. `MyComponent_ab01f2`.

    This is derived from the component class' module import path, e.g. `path.to.my.MyComponent`.
    """

    _template: Template | None = None
    """
    Cached [`Template`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Template)
    instance for the [`Component`](../api#django_components_lite.Component),
    created from
    [`Component.template`](#django_components_lite.Component.template) or
    [`Component.template_file`](#django_components_lite.Component.template_file).
    """

    do_not_call_in_templates: ClassVar[bool] = True
    """
    Django special property to prevent calling the instance as a function
    inside Django templates.

    Read more about Django's
    [`do_not_call_in_templates`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#variables-and-lookups).
    """

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

    ########################################
    # INSTANCE PROPERTIES
    ########################################

    name: str
    """
    The name of the component.

    If the component was registered, this will be the name under which the component was registered in
    the [`ComponentRegistry`](../api#django_components_lite.ComponentRegistry).

    Otherwise, this will be the name of the class.

    **Example:**

    ```py
    @register("my_component")
    class RegisteredComponent(Component):
        def get_template_data(self, args, kwargs, slots, context):
            return {
                "name": self.name,  # "my_component"
            }

    class UnregisteredComponent(Component):
        def get_template_data(self, args, kwargs, slots, context):
            return {
                "name": self.name,  # "UnregisteredComponent"
            }
    ```
    """

    registered_name: str | None
    """
    If the component was rendered with the [`{% component %}`](../template_tags#component) template tag,
    this will be the name under which the component was registered in
    the [`ComponentRegistry`](../api#django_components_lite.ComponentRegistry).

    Otherwise, this will be `None`.

    **Example:**

    ```py
    @register("my_component")
    class MyComponent(Component):
        template = "{{ name }}"

        def get_template_data(self, args, kwargs, slots, context):
            return {
                "name": self.registered_name,
            }
    ```

    Will print `my_component` in the template:

    ```django
    {% component "my_component" / %}
    ```

    And `None` when rendered in Python:

    ```python
    MyComponent.render()
    # None
    ```
    """

    args: Any
    """
    Positional arguments passed to the component.

    This is part of the [Render API](../../concepts/fundamentals/render_api).

    `args` has the same behavior as the `args` argument of
    [`Component.get_template_data()`](../api/#django_components_lite.Component.get_template_data):

    - If you defined the [`Component.Args`](../api/#django_components_lite.Component.Args) class,
        then the `args` property will return an instance of that `Args` class.
    - Otherwise, `args` will be a plain list.

    **Example:**

    With `Args` class:

    ```python
    from django_components_lite import Component

    class Table(Component):
        class Args:
            page: int
            per_page: int

        def on_render_before(self, context: Context, template: Optional[Template]) -> None:
            assert self.args.page == 123
            assert self.args.per_page == 10

    rendered = Table.render(
        args=[123, 10],
    )
    ```

    Without `Args` class:

    ```python
    from django_components_lite import Component

    class Table(Component):
        def on_render_before(self, context: Context, template: Optional[Template]) -> None:
            assert self.args[0] == 123
            assert self.args[1] == 10
    ```
    """

    kwargs: Any
    """
    Keyword arguments passed to the component.

    This is part of the [Render API](../../concepts/fundamentals/render_api).

    `kwargs` has the same behavior as the `kwargs` argument of
    [`Component.get_template_data()`](../api/#django_components_lite.Component.get_template_data):

    - If you defined the [`Component.Kwargs`](../api/#django_components_lite.Component.Kwargs) class,
        then the `kwargs` property will return an instance of that `Kwargs` class.
    - Otherwise, `kwargs` will be a plain dict.

    Kwargs have the defaults applied to them.
    Read more about [Component defaults](../../concepts/fundamentals/component_defaults).

    **Example:**

    With `Kwargs` class:

    ```python
    from django_components_lite import Component

    class Table(Component):
        class Kwargs:
            page: int
            per_page: int

        def on_render_before(self, context: Context, template: Optional[Template]) -> None:
            assert self.kwargs.page == 123
            assert self.kwargs.per_page == 10

    rendered = Table.render(
        kwargs={
            "page": 123,
            "per_page": 10,
        },
    )
    ```

    Without `Kwargs` class:

    ```python
    from django_components_lite import Component

    class Table(Component):
        def on_render_before(self, context: Context, template: Optional[Template]) -> None:
            assert self.kwargs["page"] == 123
            assert self.kwargs["per_page"] == 10
    ```
    """

    slots: Any
    """
    Slots passed to the component.

    This is part of the [Render API](../../concepts/fundamentals/render_api).

    `slots` has the same behavior as the `slots` argument of
    [`Component.get_template_data()`](../api/#django_components_lite.Component.get_template_data):

    - If you defined the [`Component.Slots`](../api/#django_components_lite.Component.Slots) class,
        then the `slots` property will return an instance of that class.
    - Otherwise, `slots` will be a plain dict.

    **Example:**

    With `Slots` class:

    ```python
    from django_components_lite import Component, Slot, SlotInput

    class Table(Component):
        class Slots:
            header: SlotInput
            footer: SlotInput

        def on_render_before(self, context: Context, template: Optional[Template]) -> None:
            assert isinstance(self.slots.header, Slot)
            assert isinstance(self.slots.footer, Slot)

    rendered = Table.render(
        slots={
            "header": "MY_HEADER",
            "footer": lambda ctx: "FOOTER: " + ctx.data["user_id"],
        },
    )
    ```

    Without `Slots` class:

    ```python
    from django_components_lite import Component, Slot, SlotInput

    class Table(Component):
        def on_render_before(self, context: Context, template: Optional[Template]) -> None:
            assert isinstance(self.slots["header"], Slot)
            assert isinstance(self.slots["footer"], Slot)
    ```
    """

    context: Context
    """
    The `context` argument as passed to
    [`Component.get_template_data()`](../api/#django_components_lite.Component.get_template_data).

    This is Django's [Context](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Context)
    with which the component template is rendered.

    If the root component or template was rendered with
    [`RequestContext`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.RequestContext)
    then this will be an instance of `RequestContext`.

    Components use isolated context, so the template will NOT have access to this context directly.
    Data MUST be passed via component's args and kwargs.
    """

    outer_context: Context | None
    """
    When a component is rendered with the [`{% component %}`](../template_tags#component) tag,
    this is the Django's [`Context`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Context)
    object that was used just outside of the component.

    ```django
    {% with abc=123 %}
        {{ abc }} {# <--- This is in outer context #}
        {% component "my_component" / %}
    {% endwith %}
    ```

    Components use isolated context, so each component has its own instance of Context
    and `outer_context` is different from the `context` argument.
    """

    registry: ComponentRegistry
    """
    The [`ComponentRegistry`](../api/#django_components_lite.ComponentRegistry) instance
    that was used to render the component.
    """

    node: Optional["ComponentNode"]
    """
    The [`ComponentNode`](../api/#django_components_lite.ComponentNode) instance
    that was used to render the component.

    This will be set only if the component was rendered with the
    [`{% component %}`](../template_tags#component) tag.

    Accessing the [`ComponentNode`](../api/#django_components_lite.ComponentNode) is mostly useful for extensions,
    which can modify their behaviour based on the source of the Component.

    ```py
    class MyComponent(Component):
        def get_template_data(self, context, template):
            if self.node is not None:
                assert self.node.name == "my_component"
    ```

    For example, if `MyComponent` was used in another component - that is,
    with a `{% component "my_component" %}` tag
    in a template that belongs to another component - then you can use
    [`self.node.template_component`](../api/#django_components_lite.ComponentNode.template_component)
    to access the owner [`Component`](../api/#django_components_lite.Component) class.

    ```djc_py
    class Parent(Component):
        template: str = '''
            <div>
                {% component "my_component" / %}
            </div>
        '''

    @register("my_component")
    class MyComponent(Component):
        def get_template_data(self, context, template):
            if self.node is not None:
                assert self.node.template_component == Parent
    ```

    !!! info

        `Component.node` is `None` if the component is created by
        [`Component.render()`](../api/#django_components_lite.Component.render)
        (but you can pass in the `node` kwarg yourself).
    """
    request: HttpRequest | None
    """
    [HTTPRequest](https://docs.djangoproject.com/en/5.2/ref/request-response/#django.http.HttpRequest)
    object passed to this component.

    **Example:**

    ```py
    class MyComponent(Component):
        def get_template_data(self, args, kwargs, slots, context):
            user_id = self.request.GET['user_id']
            return {
                'user_id': user_id,
            }
    ```

    **Passing `request` to a component:**

    In regular Django templates, you have to use
    [`RequestContext`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.RequestContext)
    to pass the `HttpRequest` object to the template.

    With Components, you can either use `RequestContext`, or pass the `request` object
    explicitly via [`Component.render()`](../api#django_components_lite.Component.render) and
    [`Component.render_to_response()`](../api#django_components_lite.Component.render_to_response).

    When a component is nested in another, the child component uses parent's `request` object.
    """

    @property
    def context_processors_data(self) -> dict:
        """
        Retrieve data injected by
        [`context_processors`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#configuring-an-engine).

        This data is also available from within the component's template, without having to
        return this data from
        [`get_template_data()`](../api#django_components_lite.Component.get_template_data).

        In regular Django templates, you need to use
        [`RequestContext`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.RequestContext)
        to apply context processors.

        In Components, the context processors are applied to components either when:

        - The component is rendered with
            [`RequestContext`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.RequestContext)
            (Regular Django behavior)
        - The component is rendered with a regular
            [`Context`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Context) (or none),
            but the `request` kwarg of [`Component.render()`](../api#django_components_lite.Component.render) is set.
        - The component is nested in another component that matches any of these conditions.

        See
        [`Component.request`](../api#django_components_lite.Component.request)
        on how the `request`
        ([HTTPRequest](https://docs.djangoproject.com/en/5.2/ref/request-response/#django.http.HttpRequest))
        object is passed to and within the components.

        NOTE: This dictionary is generated dynamically, so any changes to it will not be persisted.

        **Example:**

        ```py
        class MyComponent(Component):
            def get_template_data(self, args, kwargs, slots, context):
                user = self.context_processors_data['user']
                return {
                    'is_logged_in': user.is_authenticated,
                }
        ```
        """
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

        **Type hints:**

        `Component.render()` is NOT typed. To add type hints, you can wrap the inputs
        in component's [`Args`](../api/#django_components_lite.Component.Args),
        [`Kwargs`](../api/#django_components_lite.Component.Kwargs),
        and [`Slots`](../api/#django_components_lite.Component.Slots) classes.

        Read more on [Typing and validation](../../concepts/fundamentals/typing_and_validation).

        ```python
        from typing import Optional
        from django_components_lite import Component, Slot, SlotInput

        # Define the component with the types
        class Button(Component):
            class Args:
                name: str

            class Kwargs:
                surname: str
                age: int

            class Slots:
                my_slot: Optional[SlotInput] = None
                footer: SlotInput

        # Add type hints to the render call
        Button.render(
            args=Button.Args(
                name="John",
            ),
            kwargs=Button.Kwargs(
                surname="Doe",
                age=30,
            ),
            slots=Button.Slots(
                footer=Slot(lambda ctx: "Click me!"),
            ),
        )
        ```
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

    # Defaults; may be overridden by `component_tags.py` at library-load time
    # based on `COMPONENTS.tag_name` / `COMPONENTS.tag_name_sc` settings.
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
        node_id: str | None = None,
        contents: str | None = None,
        template_name: str | None = None,
        template_component: type["Component"] | None = None,
    ) -> None:
        super().__init__(
            params=params,
            flags=flags,
            nodelist=nodelist,
            node_id=node_id,
            contents=contents,
            template_name=template_name,
            template_component=template_component,
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

        # Components use isolated context  -  template only sees get_template_data() output,
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
