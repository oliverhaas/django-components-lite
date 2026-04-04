# ruff: noqa: N804
import contextlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import (
    Any,
    ClassVar,
    NamedTuple,
    Optional,
    Union,
    cast,
)
from weakref import ReferenceType, WeakValueDictionary, finalize, ref

from django.http import HttpRequest, HttpResponse
from django.template.base import FilterExpression, NodeList, Parser, Template, Token
from django.template.context import Context, RequestContext
from django.template.loader_tags import BLOCK_CONTEXT_KEY, BlockContext
from django.test.signals import template_rendered
from django.utils.safestring import mark_safe

from django_components_lite.component_media import resolve_component_files
from django_components_lite.component_registry import ComponentRegistry
from django_components_lite.component_registry import registry as registry_
from django_components_lite.constants import COMP_ID_PREFIX
from django_components_lite.context import _COMPONENT_CONTEXT_KEY, COMPONENT_IS_NESTED_KEY, make_isolated_context_copy
from django_components_lite.dependencies import build_dependency_tags
from django_components_lite.node import BaseNode

# Maps render_id -> ComponentContext. Used by slots to find their parent component during rendering.
component_context_cache: dict[str, "ComponentContext"] = {}

from django_components_lite.slots import (
    Slot,
    SlotResult,
    _is_extracting_fill,
    normalize_slot_fills,
    resolve_fills,
)
from django_components_lite.template import cache_component_template_file, prepare_component_template
from django_components_lite.util.context import gen_context_processors_data, snapshot_context
from django_components_lite.util.exception import component_error_message
from django_components_lite.util.logger import trace_component_msg
from django_components_lite.util.misc import (
    default,
    gen_id,
    hash_comp_cls,
    to_dict,
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


class ComponentVars(NamedTuple):
    """
    Type for the variables available inside the component templates.

    All variables here are scoped under `component_vars.`, so e.g. attribute
    `kwargs` on this class is accessible inside the template as:

    ```django
    {{ component_vars.kwargs }}
    ```
    """

    args: Any
    """
    The `args` argument as passed to
    [`Component.get_template_data()`](../api/#django_components_lite.Component.get_template_data).

    This is the same [`Component.args`](../api/#django_components_lite.Component.args)
    that's available on the component instance.

    If you defined the [`Component.Args`](../api/#django_components_lite.Component.Args) class,
    then the `args` property will return an instance of that class.

    Otherwise, `args` will be a plain list.

    **Example:**

    With `Args` class:

    ```djc_py
    from django_components_lite import Component, register

    @register("table")
    class Table(Component):
        class Args:
            page: int
            per_page: int

        template = '''
            <div>
                <h1>Table</h1>
                <p>Page: {{ component_vars.args.page }}</p>
                <p>Per page: {{ component_vars.args.per_page }}</p>
            </div>
        '''
    ```

    Without `Args` class:

    ```djc_py
    from django_components_lite import Component, register

    @register("table")
    class Table(Component):
        template = '''
            <div>
                <h1>Table</h1>
                <p>Page: {{ component_vars.args.0 }}</p>
                <p>Per page: {{ component_vars.args.1 }}</p>
            </div>
        '''
    ```
    """

    kwargs: Any
    """
    The `kwargs` argument as passed to
    [`Component.get_template_data()`](../api/#django_components_lite.Component.get_template_data).

    This is the same [`Component.kwargs`](../api/#django_components_lite.Component.kwargs)
    that's available on the component instance.

    If you defined the [`Component.Kwargs`](../api/#django_components_lite.Component.Kwargs) class,
    then the `kwargs` property will return an instance of that class.

    Otherwise, `kwargs` will be a plain dict.

    **Example:**

    With `Kwargs` class:

    ```djc_py
    from django_components_lite import Component, register

    @register("table")
    class Table(Component):
        class Kwargs:
            page: int
            per_page: int

        template = '''
            <div>
                <h1>Table</h1>
                <p>Page: {{ component_vars.kwargs.page }}</p>
                <p>Per page: {{ component_vars.kwargs.per_page }}</p>
            </div>
        '''
    ```

    Without `Kwargs` class:

    ```djc_py
    from django_components_lite import Component, register

    @register("table")
    class Table(Component):
        template = '''
            <div>
                <h1>Table</h1>
                <p>Page: {{ component_vars.kwargs.page }}</p>
                <p>Per page: {{ component_vars.kwargs.per_page }}</p>
            </div>
        '''
    ```
    """

    slots: Any
    """
    The `slots` argument as passed to
    [`Component.get_template_data()`](../api/#django_components_lite.Component.get_template_data).

    This is the same [`Component.slots`](../api/#django_components_lite.Component.slots)
    that's available on the component instance.

    If you defined the [`Component.Slots`](../api/#django_components_lite.Component.Slots) class,
    then the `slots` property will return an instance of that class.

    Otherwise, `slots` will be a plain dict.

    **Example:**

    With `Slots` class:

    ```djc_py
    from django_components_lite import Component, SlotInput, register

    @register("table")
    class Table(Component):
        class Slots:
            footer: SlotInput

        template = '''
            <div>
                {% component "pagination" %}
                    {% fill "footer" body=component_vars.slots.footer / %}
                {% endcomponent %}
            </div>
        '''
    ```

    Without `Slots` class:

    ```djc_py
    from django_components_lite import Component, SlotInput, register

    @register("table")
    class Table(Component):
        template = '''
            <div>
                {% component "pagination" %}
                    {% fill "footer" body=component_vars.slots.footer / %}
                {% endcomponent %}
            </div>
        '''
    ```
    """


def _gen_component_id() -> str:
    return COMP_ID_PREFIX + gen_id()


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


def on_component_garbage_collected(component_id: str) -> None:
    """Finalizer function to be called when a Component object is garbage collected."""
    component_context_cache.pop(component_id, None)


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

    def get_template_data(self, args: Any, kwargs: Any, slots: Any, context: Context) -> Mapping | None:
        """
        Use this method to define variables that will be available in the template.

        This method has access to the [Render API](../../concepts/fundamentals/render_api).

        Read more about [Template variables](../../concepts/fundamentals/html_js_css_variables).

        **Example:**

        ```py
        class MyComponent(Component):
            def get_template_data(self, args, kwargs, slots, context):
                return {
                    "name": kwargs["name"],
                    "id": self.id,
                }

            template = "Hello, {{ name }}!"

        MyComponent.render(name="World")
        ```

        **Args:**

        - `args`: Positional arguments passed to the component.
        - `kwargs`: Keyword arguments passed to the component.
        - `slots`: Slots passed to the component.
        - `context`: [`Context`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Context)
           used for rendering the component template.

        **Pass-through kwargs:**

        It's best practice to explicitly define what args and kwargs a component accepts.

        However, if you want a looser setup, you can easily write components that accept any number
        of kwargs, and pass them all to the template
        (similar to [django-cotton](https://github.com/wrabit/django-cotton)).

        To do that, simply return the `kwargs` dictionary itself from `get_template_data()`:

        ```py
        class MyComponent(Component):
            def get_template_data(self, args, kwargs, slots, context):
                return kwargs
        ```

        **Type hints:**

        To get type hints for the `args`, `kwargs`, and `slots` parameters,
        you can define the [`Args`](../api#django_components_lite.Component.Args),
        [`Kwargs`](../api#django_components_lite.Component.Kwargs), and
        [`Slots`](../api#django_components_lite.Component.Slots) classes on the component class,
        and then directly reference them in the function signature of `get_template_data()`.

        When you set these classes, the `args`, `kwargs`, and `slots` parameters will be
        given as instances of these (`args` instance of `Args`, etc).

        When you omit these classes, or set them to `None`, then the `args`, `kwargs`, and `slots`
        parameters will be given as plain lists / dictionaries, unmodified.

        Read more on [Typing and validation](../../concepts/fundamentals/typing_and_validation).

        **Example:**

        ```py
        from django.template import Context
        from django_components_lite import Component, SlotInput

        class MyComponent(Component):
            class Args:
                color: str

            class Kwargs:
                size: int

            class Slots:
                footer: SlotInput

            def get_template_data(self, args: Args, kwargs: Kwargs, slots: Slots, context: Context):
                assert isinstance(args, MyComponent.Args)
                assert isinstance(kwargs, MyComponent.Kwargs)
                assert isinstance(slots, MyComponent.Slots)

                return {
                    "color": args.color,
                    "size": kwargs.size,
                    "id": self.id,
                }
        ```

        You can also add typing to the data returned from
        [`get_template_data()`](../api#django_components_lite.Component.get_template_data)
        by defining the [`TemplateData`](../api#django_components_lite.Component.TemplateData)
        class on the component class.

        When you set this class, you can return either the data as a plain dictionary,
        or an instance of [`TemplateData`](../api#django_components_lite.Component.TemplateData).

        If you return plain dictionary, the data will be validated against the
        [`TemplateData`](../api#django_components_lite.Component.TemplateData) class
        by instantiating it with the dictionary.

        **Example:**

        ```py
        class MyComponent(Component):
            class TemplateData:
                color: str
                size: int

            def get_template_data(self, args, kwargs, slots, context):
                return {
                    "color": kwargs["color"],
                    "size": kwargs["size"],
                }
                # or
                return MyComponent.TemplateData(
                    color=kwargs["color"],
                    size=kwargs["size"],
                )
        ```

        """
        return None

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
    # PUBLIC API - HOOKS (Configurable by users)
    # #####################################

    def on_render_before(self, context: Context, template: Template | None) -> None:
        """
        Runs just before the component's template is rendered.

        It is called for every component, including nested ones, as part of
        the component render lifecycle.

        Args:
            context (Context): The Django
                [Context](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Context)
                that will be used to render the component's template.
            template (Optional[Template]): The Django
                [Template](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Template)
                instance that will be rendered, or `None` if no template.

        Returns:
            None. This hook is for side effects only.

        **Example:**

        You can use this hook to access the context or the template:

        ```py
        from django.template import Context, Template
        from django_components_lite import Component

        class MyTable(Component):
            def on_render_before(self, context: Context, template: Optional[Template]) -> None:
                # Insert value into the Context
                context["from_on_before"] = ":)"

                assert isinstance(template, Template)
        ```

        !!! warning

            If you want to pass data to the template, prefer using
            [`get_template_data()`](../api#django_components_lite.Component.get_template_data)
            instead of this hook.

        !!! warning

            Do NOT modify the template in this hook. The template is reused across renders.

            Since this hook is called for every component, this means that the template would be modified
            every time a component is rendered.

        """

    def on_render(self, context: Context, template: Template | None) -> str | None:
        """
        Render the component. Override to customize rendering.
        """
        if template is None:
            return None
        return template.render(context)

    def on_render_after(
        self,
        context: Context,
        template: Template | None,
        result: str | None,
        error: Exception | None,
    ) -> SlotResult | None:
        """
        Hook that runs when the component was fully rendered,
        including all its children.

        It receives the same arguments as [`on_render_before()`](../api#django_components_lite.Component.on_render_before),
        plus the outcome of the rendering:

        - `result`: The rendered output of the component. `None` if the rendering failed.
        - `error`: The error that occurred during the rendering, or `None` if the rendering succeeded.

        [`on_render_after()`](../api#django_components_lite.Component.on_render_after) behaves the same way
        as the second part of [`on_render()`](../api#django_components_lite.Component.on_render) (after the `yield`).

        ```py
        class MyTable(Component):
            def on_render_after(self, context, template, result, error):
                if error is None:
                    # The rendering succeeded
                    return result
                else:
                    # The rendering failed
                    print(f"Error: {error}")
        ```

        Same as [`on_render()`](../api#django_components_lite.Component.on_render),
        you can return a new HTML, raise a new exception, or return nothing:

        1. Return a new HTML

            The new HTML will be used as the final output.

            If the original template raised an error, it will be ignored.

            ```py
            class MyTable(Component):
                def on_render_after(self, context, template, result, error):
                    return "NEW HTML"
            ```

        2. Raise a new exception

            The new exception is what will bubble up from the component.

            The original HTML and original error will be ignored.

            ```py
            class MyTable(Component):
                def on_render_after(self, context, template, result, error):
                    raise Exception("Error message")
            ```

        3. Return nothing (or `None`) to handle the result as usual

            If you don't raise an exception, and neither return a new HTML,
            then original HTML / error will be used:

            - If rendering succeeded, the original HTML will be used as the final output.
            - If rendering failed, the original error will be propagated.

            ```py
            class MyTable(Component):
                def on_render_after(self, context, template, result, error):
                    if error is not None:
                        # The rendering failed
                        print(f"Error: {error}")
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
        id: str | None = None,  # noqa: A002
    ) -> None:
        self.id = default(id, _gen_component_id, factory=True)  # type: ignore[arg-type]
        self.name = _get_component_name(self.__class__, registered_name)
        self.registered_name: str | None = registered_name
        self.args = default(args, [])
        self.kwargs = default(kwargs, {})
        self.slots = default(slots, {})
        self.raw_args: list[Any] = self.args if isinstance(self.args, list) else list(self.args)
        self.raw_kwargs: dict[str, Any] = self.kwargs if isinstance(self.kwargs, dict) else to_dict(self.kwargs)
        self.raw_slots: dict[str, Slot] = self.slots if isinstance(self.slots, dict) else to_dict(self.slots)
        self.context = default(context, Context())
        self.request = request
        self.outer_context: Context | None = outer_context
        self.registry = default(registry, registry_)
        self.node = node

        # Run finalizer when component is garbage collected
        finalize(self, on_component_garbage_collected, self.id)

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

    id: str
    """
    This ID is unique for every time a [`Component.render()`](../api#django_components_lite.Component.render)
    (or equivalent) is called (AKA "render ID").

    This is useful for logging or debugging.

    The ID is a 7-letter alphanumeric string in the format `cXXXXXX`,
    where `XXXXXX` is a random string of 6 alphanumeric characters (case-sensitive).

    E.g. `c1A2b3c`.

    A single render ID has a chance of collision 1 in 57 billion. However, due to birthday paradox,
    the chance of collision increases to 1% when approaching ~33K render IDs.

    Thus, there is currently a soft-cap of ~30K components rendered on a single page.

    If you need to expand this limit, please open an issue on GitHub.

    **Example:**

    ```py
    class MyComponent(Component):
        def get_template_data(self, args, kwargs, slots, context):
            print(f"Rendering '{self.id}'")

    MyComponent.render()
    # Rendering 'ab3c4d'
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

    raw_args: list[Any]
    """
    Positional arguments passed to the component.

    This is part of the [Render API](../../concepts/fundamentals/render_api).

    Unlike [`Component.args`](../api/#django_components_lite.Component.args), this attribute
    is not typed and will remain as plain list even if you define the
    [`Component.Args`](../api/#django_components_lite.Component.Args) class.

    **Example:**

    ```python
    from django_components_lite import Component

    class Table(Component):
        def on_render_before(self, context: Context, template: Optional[Template]) -> None:
            assert self.raw_args[0] == 123
            assert self.raw_args[1] == 10
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

    raw_kwargs: dict[str, Any]
    """
    Keyword arguments passed to the component.

    This is part of the [Render API](../../concepts/fundamentals/render_api).

    Unlike [`Component.kwargs`](../api/#django_components_lite.Component.kwargs), this attribute
    is not typed and will remain as plain dict even if you define the
    [`Component.Kwargs`](../api/#django_components_lite.Component.Kwargs) class.

    `raw_kwargs` have the defaults applied to them.
    Read more about [Component defaults](../../concepts/fundamentals/component_defaults).

    **Example:**

    ```python
    from django_components_lite import Component

    class Table(Component):
        def on_render_before(self, context: Context, template: Optional[Template]) -> None:
            assert self.raw_kwargs["page"] == 123
            assert self.raw_kwargs["per_page"] == 10
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

    raw_slots: dict[str, Slot]
    """
    Slots passed to the component.

    This is part of the [Render API](../../concepts/fundamentals/render_api).

    Unlike [`Component.slots`](../api/#django_components_lite.Component.slots), this attribute
    is not typed and will remain as plain dict even if you define the
    [`Component.Slots`](../api/#django_components_lite.Component.Slots) class.

    **Example:**

    ```python
    from django_components_lite import Component

    class Table(Component):
        def on_render_before(self, context: Context, template: Optional[Template]) -> None:
            assert self.raw_slots["header"] == "MY_HEADER"
            assert self.raw_slots["footer"] == "FOOTER: " + ctx.data["user_id"]
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

    Whether the context variables defined in `context` are available to the template depends on the
    [context behavior mode](../settings#django_components_lite.app_settings.ComponentsSettings.context_behavior):

    - In `"django"` context behavior mode, the template will have access to the keys of this context.

    - In `"isolated"` context behavior mode, the template will NOT have access to this context,
        and data MUST be passed via component's args and kwargs.
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

    This is relevant when your components are isolated, for example when using
    the ["isolated"](../settings#django_components_lite.app_settings.ComponentsSettings.context_behavior)
    context behavior mode or when using the `only` flag.

    When components are isolated, each component has its own instance of Context,
    so `outer_context` is different from the `context` argument.
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

            Whether the variables defined in `context` are available to the template depends on the
            [context behavior mode](../settings#django_components_lite.app_settings.ComponentsSettings.context_behavior):

            - In `"django"` context behavior mode, the template will have access to the keys of this context.

            - In `"isolated"` context behavior mode, the template will NOT have access to this context,
                and data MUST be passed via component's args and kwargs.

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
        return cls._render_with_error_trace(
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

    # This is the internal entrypoint for the render function
    @classmethod
    def _render_with_error_trace(
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
        component_name = _get_component_name(cls, registered_name)
        render_id = _gen_component_id()

        # Modify the error to display full component path (incl. slots)
        with component_error_message([component_name]):
            try:
                return cls._render_impl(
                    render_id=render_id,
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
            except Exception as e:
                raise e from None

    @classmethod
    def _render_impl(
        comp_cls,
        render_id: str,
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
        if request is None and context:
            # If the context is `RequestContext`, it has `request` attribute
            request = getattr(context, "request", None)
            # Check if this is a nested component and whether parent has request
            if request is None:
                _, parent_comp_ctx = _get_parent_component_context(context)
                if parent_comp_ctx:
                    parent_comp = parent_comp_ctx.component()
                    request = parent_comp and parent_comp.request

        component_name = _get_component_name(comp_cls, registered_name)

        # Allow to provide no args/kwargs/slots/context
        # NOTE: We make copies of args / kwargs / slots, so that plugins can modify them
        # without affecting the original values.
        args_list: list[Any] = list(default(args, []))
        kwargs_dict = to_dict(default(kwargs, {}))
        slots_dict = normalize_slot_fills(
            to_dict(default(slots, {})),
            component_name=component_name,
        )
        # Use RequestContext if request is provided, so that child non-component template tags
        # can access the request object too.
        context = context if context is not None else (RequestContext(request) if request else Context())

        # Allow to provide a dict instead of Context
        # NOTE: This if/else is important to avoid nested Contexts,
        # See https://github.com/django-components/django-components/issues/414
        if not isinstance(context, (Context, RequestContext)):
            context = RequestContext(request, context) if request else Context(context)

        component = comp_cls(
            id=render_id,
            args=args_list,
            kwargs=kwargs_dict,
            slots=slots_dict,
            context=context,
            request=request,
            outer_context=outer_context,
            registry=registry,
            registered_name=registered_name,
            node=node,
        )

        # If user doesn't specify `Args`, `Kwargs`, `Slots` types, then we pass them in as plain
        # dicts / lists.
        component.args = args_list
        component.kwargs = kwargs_dict
        component.slots = slots_dict

        ######################################
        # 2. Prepare component state
        ######################################

        # Required for compatibility with Django's {% extends %} tag
        # See https://github.com/django-components/django-components/pull/859
        context.render_context.push(  # type: ignore[union-attr]
            {BLOCK_CONTEXT_KEY: context.render_context.get(BLOCK_CONTEXT_KEY, BlockContext())},  # type: ignore[union-attr]
        )

        # We pass down the components the info about the component's parent.
        # This is used for correctly resolving slot fills, correct rendering order,
        # or CSS scoping.
        _parent_id, parent_comp_ctx = _get_parent_component_context(context)
        if parent_comp_ctx is not None:
            component_path = [*parent_comp_ctx.component_path, component_name]
        else:
            component_path = [component_name]

        trace_component_msg(
            "COMP_PREP_START",
            component_name=component_name,
            component_id=render_id,
            slot_name=None,
            component_path=component_path,
            extra=(
                f"Received {len(args_list)} args, {len(kwargs_dict)} kwargs, {len(slots_dict)} slots,"
                f" Available slots: {slots_dict}"
            ),
        )

        # This is data that will be accessible (internally) from within the component's template.
        # NOTE: Be careful with the context - Do not store a strong reference to the component,
        #       because that would prevent the component from being garbage collected.
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
            # NOTE: This is only a SNAPSHOT of the outer context.
            outer_context=snapshot_context(outer_context) if outer_context is not None else None,
        )

        # Instead of passing the ComponentContext directly through the Context, the entry on the Context
        # contains only a key to retrieve the ComponentContext from `component_context_cache`.
        #
        # This way, the flow is easier to debug. Because otherwise, if you tried to print out
        # or inspect the Context object, your screen would be filled with the deeply nested ComponentContext objects.
        # But now, the printed Context may simply look like this:
        # `[{ "True": True, "False": False, "None": None }, {"_DJC_COMPONENT_CTX": "c1A2b3c"}]`
        component_context_cache[render_id] = component_ctx

        ######################################
        # 3. Call data methods
        ######################################

        template_data = component._call_data_methods()

        #############################################################################
        # 4. Make Context copy
        #
        # NOTE: To support infinite recursion, we make a copy of the context.
        #       This way we don't have to call the whole component tree in one go recursively,
        #       but instead can render one component at a time.
        #############################################################################

        with prepare_component_template(component, template_data) as template:
            # Set `_DJC_COMPONENT_IS_NESTED` based on whether we're currently INSIDE
            # the `{% extends %}` tag.
            # Part of fix for https://github.com/django-components/django-components/issues/508
            # See django_monkeypatch.py
            comp_is_nested = (
                bool(context.render_context.get(BLOCK_CONTEXT_KEY))  # type: ignore[union-attr]
                if template is not None
                else False
            )

            # Capture the template name so we can print better error messages (currently used in slots)
            component_ctx.template_name = template.name if template else None

            with context.update(  # type: ignore[union-attr]
                {
                    # Make data from context processors available inside templates
                    **component.context_processors_data,
                    # Private context fields
                    _COMPONENT_CONTEXT_KEY: render_id,
                    COMPONENT_IS_NESTED_KEY: comp_is_nested,
                    # NOTE: Public API for variables accessible from within a component's template
                    # See https://github.com/django-components/django-components/issues/280#issuecomment-2081180940
                    "component_vars": ComponentVars(
                        args=component.args,
                        kwargs=component.kwargs,
                        slots=component.slots,
                    ),
                },
            ):
                # Make a "snapshot" of the context as it was at the time of the render call.
                #
                # Previously, we recursively called `Template.render()` as this point, but due to recursion
                # this was limiting the number of nested components to only about 60 levels deep.
                #
                # Now, we make a flat copy, so that the context copy is static and doesn't change even if
                # we leave the `with context.update` blocks.
                #
                # This makes it possible to render nested components with a queue, avoiding recursion limits.
                context_snapshot = snapshot_context(context)

        # Cleanup
        context.render_context.pop()  # type: ignore[union-attr]

        trace_component_msg(
            "COMP_PREP_END",
            component_name=component_name,
            component_id=render_id,
            slot_name=None,
            component_path=component_path,
        )

        ######################################
        # 5. Render component
        ######################################

        component.on_render_before(context_snapshot, template)

        # Emit signal that the template is about to be rendered
        if template is not None:
            template_rendered.send(sender=template, template=template, context=context_snapshot)

        # Render the component synchronously
        html: str | None = None
        error: Exception | None = None
        try:
            html = component.on_render(context_snapshot, template)
        except Exception as e:  # noqa: BLE001
            error = e

        # Post-render hook
        try:
            maybe_output = component.on_render_after(context_snapshot, template, html, error)
            if maybe_output is not None:
                html = maybe_output
                error = None
        except Exception as new_error:  # noqa: BLE001
            error = new_error
            html = None

        if error is not None:
            raise error

        # Prepend <link>/<script> tags for this component's JS/CSS files
        if html is not None:
            dep_tags = build_dependency_tags(comp_cls)
            if dep_tags:
                html = dep_tags + "\n" + html

        return mark_safe(html) if html is not None else ""  # noqa: S308

    def get_context_data(self, **kwargs: Any) -> dict:
        """
        Override this to provide template context variables.

        This is the simple, Django-style API. For access to args, slots, and
        the rendering context, override `get_template_data()` instead.

        By default, returns an empty dict.
        """
        return {}

    def _call_data_methods(self) -> dict:
        # If the subclass overrides get_template_data, use that (advanced API).
        # Otherwise fall back to get_context_data (simple Django-style API).
        if type(self).get_template_data is not Component.get_template_data:
            maybe_template_data = self.get_template_data(self.args, self.kwargs, self.slots, self.context)
        else:
            maybe_template_data = self.get_context_data(**self.kwargs)
        return to_dict(default(maybe_template_data, {}))


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

    ### Isolating components

    By default, components behave similarly to Django's
    [`{% include %}`](https://docs.djangoproject.com/en/5.2/ref/templates/builtins/#include),
    and the template inside the component has access to the variables defined in the outer template.

    You can selectively isolate a component, using the `only` flag, so that the inner template
    can access only the data that was explicitly passed to it:

    ```django
    {% component "name" positional_arg keyword_arg=value ... only %}
    ```

    Alternatively, you can set all components to be isolated by default, by setting
    [`context_behavior`](../settings#django_components_lite.app_settings.ComponentsSettings.context_behavior)
    to `"isolated"` in your settings:

    ```python
    # settings.py
    COMPONENTS = {
        "context_behavior": "isolated",
    }
    ```

    ### Omitting the component keyword

    If you would like to omit the `component` keyword, and simply refer to your
    components by their registered names:

    ```django
    {% button name="John" job="Developer" / %}
    ```

    You can do so by setting the "shorthand" tag formatter in the settings:

    ```python
    # settings.py
    COMPONENTS = {
        "tag_formatter": "django_components_lite.component_shorthand_formatter",
    }
    ```
    """

    tag = "component"
    end_tag = "endcomponent"
    allowed_flags = ()

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
        end_tag: str,
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

        slot_fills = resolve_fills(context, self, self.name)

        # Components use isolated context  -  template only sees get_template_data() output,
        # like Django's inclusion_tag behavior.
        inner_context = make_isolated_context_copy(context)

        return component_cls._render_with_error_trace(
            context=inner_context,
            args=args,
            kwargs=kwargs,
            slots=slot_fills,
            registered_name=self.name,
            outer_context=context,
            registry=self.registry,
            node=self,
        )


def _get_parent_component_context(
    context: Context | Mapping,
) -> tuple[None, None] | tuple[str, ComponentContext]:
    parent_id = context.get(_COMPONENT_CONTEXT_KEY, None)
    if parent_id is None:
        return None, None

    # NOTE: This may happen when slots are rendered outside of the component's render context.
    # See https://github.com/django-components/django-components/issues/1189
    if parent_id not in component_context_cache:
        return None, None

    parent_comp_ctx = component_context_cache[parent_id]
    return parent_id, parent_comp_ctx
