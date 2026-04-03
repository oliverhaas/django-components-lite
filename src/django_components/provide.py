from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, NamedTuple, cast

from django.template import Context, TemplateSyntaxError
from django.utils.safestring import SafeString

from django_components.context import _INJECT_CONTEXT_KEY_PREFIX
from django_components.node import BaseNode
from django_components.util.misc import gen_id

if TYPE_CHECKING:
    from django_components.component import Component


# Similarly to ComponentContext instances, we store the actual Provided data
# outside of the Context object, to make it easier to debug the data flow.
provide_cache: dict[str, NamedTuple] = {}

# Given a `{% provide %}` instance, keep track of which components are referencing it.
# ProvideID -> Component[]
# NOTE: We manually clean up the entries when either:
#       - `{% provide %}` ends and there are no more references to it
#       - The last component that referenced it is garbage collected
provide_references: dict[str, set[str]] = defaultdict(set)

# The opposite - Given a component, keep track of which `{% provide %}` instances it is referencing.
# Component -> ProvideID[]
# NOTE: We manually clean up the entries when components are garbage collected.
component_provides: dict[str, dict[str, str]] = defaultdict(dict)

# Track which {% provide %} blocks are currently active (rendering).
# This prevents premature cache cleanup when components are garbage collected.
active_provides: set[str] = set()


@contextmanager
def managed_provide_cache(provide_id: str) -> Generator[None, None, None]:
    # Mark this provide block as active
    active_provides.add(provide_id)
    try:
        yield
    except Exception as e:
        # Mark this provide block as no longer active
        active_provides.discard(provide_id)
        # NOTE: In case of an error in within the `{% provide %}` block (e.g. when rendering a component),
        # we rely on the component finalizer to remove the references.
        # But we still want to call cleanup in case `{% provide %}` contained no components.
        _cache_cleanup(provide_id)
        # Forward the error
        raise e from None

    # Mark this provide block as no longer active
    active_provides.discard(provide_id)
    # Cleanup on success
    _cache_cleanup(provide_id)


def _cache_cleanup(provide_id: str) -> None:
    # Don't cleanup if the provide block is still active.
    if provide_id in active_provides:
        return

    # Remove provided data from the cache, IF there are no more references to it.
    # A `{% provide %}` will have no reference if:
    # - It contains no components in its body
    # - It contained components, but those components were already garbage collected
    if provide_id in provide_references and not provide_references[provide_id]:
        provide_references.pop(provide_id)
        provide_cache.pop(provide_id, None)

    # Case: `{% provide %}` contained no components in its body.
    # The provided data was not referenced by any components, but it's still in the cache.
    elif provide_id not in provide_references and provide_id in provide_cache:
        provide_cache.pop(provide_id)


def register_provide_reference(context: Context, component: "Component") -> None:
    # No `{% provide %}` among the ancestors, nothing to register to
    if not provide_cache:
        return

    # For all instances of `{% provide %}` that the current component is within,
    # make note that this component has access to them.
    for key, value in context.flatten().items():
        # NOTE: Provided data is stored on the Context object as e.g.
        # `{"_DJC_INJECT__my_provide": "a1b3c3"}`
        # Where "a1b3c3" is the ID of the provided data.
        if not key.startswith(_INJECT_CONTEXT_KEY_PREFIX):
            continue

        provide_id = cast("str", value)
        provide_key = key.split(_INJECT_CONTEXT_KEY_PREFIX, 1)[1]

        # Update the Provide -> Component[] mapping.
        provide_references[provide_id].add(component.id)

        # Update the Component -> Provide[] mapping.
        component_provides[component.id][provide_key] = provide_id


def unregister_provide_reference(component_id: str) -> None:
    # List of `{% provide %}` IDs that the component had access to.
    component_provides_ids = component_provides.get(component_id)
    if not component_provides_ids:
        return

    # Remove this component from all provide references it was subscribed to
    for provide_id in component_provides_ids.values():
        references_to_this_provide = provide_references.get(provide_id)
        if references_to_this_provide:
            references_to_this_provide.discard(component_id)


def unlink_component_from_provide_on_gc(component_id: str) -> None:
    """
    Finalizer function to be called when a Component object is garbage collected.

    Unlinking the component at this point ensures that one can call `Component.inject()`
    even after the component was rendered, as long as one keeps the reference to the component object.
    """
    unregister_provide_reference(component_id)
    provide_ids = component_provides.pop(component_id, None)
    if provide_ids:
        for provide_id in provide_ids.values():
            _cache_cleanup(provide_id)


class ProvideNode(BaseNode):
    """
    The [`{% provide %}`](#provide) tag is part of the "provider" part of
    the [provide / inject feature](../concepts/advanced/provide_inject.md).

    Pass kwargs to this tag to define the provider's data.

    Any components defined within the `{% provide %}..{% endprovide %}` tags will be able to access this data
    with [`Component.inject()`](api.md#django_components.Component.inject).

    This is similar to React's [`ContextProvider`](https://react.dev/learn/passing-data-deeply-with-context),
    or Vue's [`provide()`](https://vuejs.org/guide/components/provide-inject).

    **Args:**

    - `name` (str, required): Provider name. This is the name you will then use in
        [`Component.inject()`](api.md#django_components.Component.inject).
    - `**kwargs`: Any extra kwargs will be passed as the provided data.

    **Example:**

    Provide the "user_data" in parent component:

    ```djc_py
    @register("parent")
    class Parent(Component):
        template = \"\"\"
          <div>
            {% provide "user_data" user=user %}
              {% component "child" / %}
            {% endprovide %}
          </div>
        \"\"\"

        def get_template_data(self, args, kwargs, slots, context):
            return {
                "user": kwargs["user"],
            }
    ```

    Since the "child" component is used within the `{% provide %} / {% endprovide %}` tags,
    we can request the "user_data" using `Component.inject("user_data")`:

    ```djc_py
    @register("child")
    class Child(Component):
        template = \"\"\"
          <div>
            User is: {{ user }}
          </div>
        \"\"\"

        def get_template_data(self, args, kwargs, slots, context):
            user = self.inject("user_data").user
            return {
                "user": user,
            }
    ```

    Notice that the keys defined on the [`{% provide %}`](#provide) tag are then accessed as attributes
    when accessing them with [`Component.inject()`](api.md#django_components.Component.inject).

    ✅ Do this
    ```python
    user = self.inject("user_data").user
    ```

    ❌ Don't do this
    ```python
    user = self.inject("user_data")["user"]
    ```
    """

    tag = "provide"
    end_tag = "endprovide"
    allowed_flags = ()

    def render(self, context: Context, name: str, **kwargs: Any) -> SafeString:
        # NOTE: The "provided" kwargs are meant to be shared privately, meaning that components
        # have to explicitly opt in by using the `Component.inject()` method. That's why we don't
        # add the provided kwargs into the Context.
        with context.update({}):
            # "Provide" the data to child nodes
            provide_id = set_provided_context_var(context, name, kwargs)

            # `managed_provide_cache` will remove the cache entry at the end if no components reference it.
            with managed_provide_cache(provide_id):
                output = self.nodelist.render(context)

        return output


def get_injected_context_var(
    component_id: str,
    component_name: str,
    key: str,
    default: Any | None = None,
) -> Any:
    """
    Retrieve a 'provided' field. The field MUST have been previously 'provided'
    by the component's ancestors using the `{% provide %}` template tag.
    """
    # NOTE: `component_provides` is defaultdict. Use `.get()` to avoid making an empty dictionary.
    providers = component_provides.get(component_id)

    # Return provided value if found
    if providers and key in providers:
        provide_id = providers[key]
        return provide_cache[provide_id]

    # If a default was given, return that
    if default is not None:
        return default

    # Otherwise raise error
    raise KeyError(
        f"Component '{component_name}' tried to inject a variable '{key}' before it was provided."
        f" To fix this, make sure that at least one ancestor of component '{component_name}' has"
        f" the variable '{key}' in their 'provide' attribute.",
    )


# TODO_v2 - Once we wrap all executions of Django's Template as our Components,
#           we'll be able to store the provided data on ComponentContext instead of on Context.
def set_provided_context_var(
    context: Context,
    key: str,
    provided_kwargs: dict[str, Any],
) -> str:
    """
    'Provide' given data under given key. In other words, this data can be retrieved
    using `self.inject(key)` inside of `get_template_data()` method of components that
    are nested inside the `{% provide %}` tag.
    """
    # NOTE: We raise TemplateSyntaxError since this func should be called only from
    # within template.
    if not key:
        raise TemplateSyntaxError(
            "Provide tag received an empty string. Key must be non-empty and a valid identifier.",
        )
    if not key.isidentifier():
        raise TemplateSyntaxError(
            "Provide tag received a non-identifier string. Key must be non-empty and a valid identifier.",
        )

    # We turn the kwargs into a NamedTuple so that the object that's "provided"
    # is immutable. This ensures that the data returned from `inject` will always
    # have all the keys that were passed to the `provide` tag.
    fields = [(field, Any) for field in provided_kwargs]
    tuple_cls = NamedTuple("DepInject", fields)  # type: ignore[misc]
    payload = tuple_cls(**provided_kwargs)

    # To allow the components nested inside `{% provide %}` to access the provided data,
    # we pass the data through the Context.
    # But instead of storing the data directly on the Context object, we store it
    # in a separate dictionary, and we only set a key to the data on the Context.
    # This helps with debugging as the Context is easier to inspect. It also helps
    # with testing and garbage collection, as we can easily access/modify the provided data.
    context_key = _INJECT_CONTEXT_KEY_PREFIX + key
    provide_id = gen_id()
    context[context_key] = provide_id
    provide_cache[provide_id] = payload

    return provide_id
