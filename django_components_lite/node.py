import functools
import inspect
import keyword
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, ClassVar, cast

from django.template import Context, Library
from django.template.base import FilterExpression, Node, NodeList, Parser, Token
from django.template.exceptions import TemplateSyntaxError

from django_components_lite.util.misc import gen_id
from django_components_lite.util.template_tag import (
    TagParam,
    validate_params,
)

if TYPE_CHECKING:
    from django_components_lite.component import Component


# Normally, when `Node.render()` is called, it receives only a single argument `context`.
#
# ```python
# def render(self, context: Context) -> str:
#     return self.nodelist.render(context)
# ```
#
# In django-components, the input to template tags is treated as function inputs, e.g.
#
# `{% component name="John" age=20 %}`
#
# And, for convenience, we want to allow the `render()` method to accept these extra parameters.
# That way, user can define just the `render()` method and have access to all the information:
#
# ```python
# def render(self, context: Context, name: str, **kwargs: Any) -> str:
#     return f"Hello, {name}!"
# ```
#
# So we need to wrap the `render()` method, and for that we need the metaclass.
#
# The outer `render()` (our wrapper) will match the `Node.render()` signature (accepting only `context`),
# while the inner `render()` (the actual implementation) will match the user-defined `render()` method's signature
# (accepting all the parameters).
class NodeMeta(type):
    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
    ) -> type["BaseNode"]:
        cls = cast("type[BaseNode]", super().__new__(mcs, name, bases, attrs))

        # Ignore the `BaseNode` class itself
        if attrs.get("__module__") == "django_components_lite.node":
            return cls

        if not hasattr(cls, "tag"):
            raise ValueError(f"Node {name} must have a 'tag' attribute")

        # Skip if already wrapped
        orig_render = cls.render
        if getattr(orig_render, "_djc_wrapped", False):
            return cls

        signature = inspect.signature(orig_render)

        # A full signature of `BaseNode.render()` may look like this:
        #
        # `def render(self, context: Context, name: str, **kwargs) -> str:`
        #
        # We need to remove the first two parameters from the signature.
        # So we end up only with
        #
        # `def render(name: str, **kwargs) -> str:`
        #
        # And this becomes the signature that defines what params the template tag accepts, e.g.
        #
        # `{% component name="John" age=20 %}`
        if len(signature.parameters) < 2:
            raise TypeError(f"`render()` method of {name} must have at least two parameters")

        validation_params = list(signature.parameters.values())
        validation_params = validation_params[2:]
        validation_signature = signature.replace(parameters=validation_params)

        # NOTE: This is used for creating docs by `_format_tag_signature()` in `docs/scripts/reference.py`
        cls._signature = validation_signature

        @functools.wraps(orig_render)
        def wrapper_render(self: "BaseNode", context: Context) -> str:
            # Resolve FilterExpressions to actual values
            raw_args, raw_kwargs = self.params
            resolved_args = [arg.resolve(context) for arg in raw_args]
            resolved_kwargs = {k: v.resolve(context) for k, v in raw_kwargs.items()}

            # {% component %} accepts arbitrary args and kwargs (incl. non-identifier keys
            # like `data-id` or `@click`), so we skip the signature validation walk for it.
            if cls._skip_param_validation:
                return orig_render(self, context, *resolved_args, **resolved_kwargs)

            # Build TagParam list for validation
            # Template tags may accept kwargs that are not valid Python identifiers, e.g.
            # `{% component data-id="John" class="pt-4" :href="myVar" %}`
            #
            # Passing them in is still useful, as user may want to pass in arbitrary data
            # to their `{% component %}` tags as HTML attributes.
            resolved_params_without_invalid_kwargs: list[TagParam] = []
            invalid_kwargs: dict[str, Any] = {}
            did_see_special_kwarg = False

            # First add positional args
            for value in resolved_args:
                if did_see_special_kwarg:
                    raise SyntaxError("positional argument follows keyword argument")
                resolved_params_without_invalid_kwargs.append(TagParam(key=None, value=value))

            # Then add keyword args, separating valid from invalid Python identifiers
            for key, value in resolved_kwargs.items():
                if not key.isidentifier() or keyword.iskeyword(key):
                    # Special kwargs (e.g. data-id, class, @click)
                    invalid_kwargs[key] = value
                    did_see_special_kwarg = True
                else:
                    resolved_params_without_invalid_kwargs.append(TagParam(key=key, value=value))

            # Validate the params against the signature
            args, kwargs = validate_params(
                orig_render,
                validation_signature,
                self.tag,
                resolved_params_without_invalid_kwargs,
                invalid_kwargs,
            )

            return orig_render(self, context, *args, **kwargs)

        # Wrap cls.render() so we resolve the args and kwargs and pass them to the
        # actual render method.
        cls.render = wrapper_render  # type: ignore[method-assign]
        cls.render._djc_wrapped = True  # type: ignore[attr-defined]

        return cls


# Similar to `parser.parse(parse_until=[end_tag])`, except:
# 1. Does not remove the token it goes over (unlike `parser.parse()`, which mutates the parser state)
# 2. Returns a string, instead of a NodeList
#
# This is used so we can access the contents of the tag body as strings.
#
# See https://github.com/django/django/blob/1fb3f57e81239a75eb8f873b392e11534c041fdc/django/template/base.py#L471
def _extract_contents_until(parser: Parser, until_blocks: list[str]) -> str:
    contents: list[str] = []
    for token in reversed(parser.tokens):
        # Use the raw values here for TokenType.* for a tiny performance boost.
        token_type = token.token_type.value
        if token_type == 0:  # TokenType.TEXT
            contents.append(token.contents)
        elif token_type == 1:  # TokenType.VAR
            contents.append("{{ " + token.contents + " }}")
        elif token_type == 2:  # TokenType.BLOCK
            try:
                command = token.contents.split()[0]
            except IndexError:
                contents.append("{% " + token.contents + " %}")
                continue
            if command in until_blocks:
                return "".join(contents)
            contents.append("{% " + token.contents + " %}")
        elif token_type == 3:  # TokenType.COMMENT
            contents.append("{# " + token.contents + " #}")
        else:
            raise ValueError(f"Unknown token type {token_type}")

    return "".join(contents)


class BaseNode(Node, metaclass=NodeMeta):
    """
    Node class for all django-components custom template tags.

    This class has a dual role:

    1. It declares how a particular template tag should be parsed - By setting the
       [`tag`](../api#django_components_lite.BaseNode.tag),
       [`end_tag`](../api#django_components_lite.BaseNode.end_tag),
       and [`allowed_flags`](../api#django_components_lite.BaseNode.allowed_flags) attributes:

        ```python
        class SlotNode(BaseNode):
            tag = "slot"
            end_tag = "endslot"
            allowed_flags = ["required"]
        ```

        This will allow the template tag `{% slot %}` to be used like this:

        ```django
        {% slot required %} ... {% endslot %}
        ```

    2. The [`render`](../api#django_components_lite.BaseNode.render) method is
        the actual implementation of the template tag.

        This is where the tag's logic is implemented:

        ```python
        class MyNode(BaseNode):
            tag = "mynode"

            def render(self, context: Context, name: str, **kwargs: Any) -> str:
                return f"Hello, {name}!"
        ```

        This will allow the template tag `{% mynode %}` to be used like this:

        ```django
        {% mynode name="John" %}
        ```

    The template tag accepts parameters as defined on the
    [`render`](../api#django_components_lite.BaseNode.render) method's signature.

    For more info, see [`BaseNode.render()`](../api#django_components_lite.BaseNode.render).
    """

    # #####################################
    # PUBLIC API (Configurable by users)
    # #####################################

    tag: ClassVar[str]
    """
    The tag name.

    E.g. `"component"` or `"slot"` will make this class match
    template tags `{% component %}` or `{% slot %}`.

    ```python
    class SlotNode(BaseNode):
        tag = "slot"
        end_tag = "endslot"
    ```

    This will allow the template tag `{% slot %}` to be used like this:

    ```django
    {% slot %} ... {% endslot %}
    ```
    """

    end_tag: ClassVar[str | None] = None
    """
    The end tag name.

    E.g. `"endcomponent"` or `"endslot"` will make this class match
    template tags `{% endcomponent %}` or `{% endslot %}`.

    ```python
    class SlotNode(BaseNode):
        tag = "slot"
        end_tag = "endslot"
    ```

    This will allow the template tag `{% slot %}` to be used like this:

    ```django
    {% slot %} ... {% endslot %}
    ```

    If not set, then this template tag has no end tag.

    So instead of `{% component %} ... {% endcomponent %}`, you'd use only
    `{% component %}`.

    ```python
    class MyNode(BaseNode):
        tag = "mytag"
        end_tag = None
    ```
    """

    _skip_param_validation: ClassVar[bool] = False
    """
    If set on a subclass, the wrapped ``render()`` will skip the ``inspect``-based
    parameter validation and forward resolved args/kwargs directly. Intended for
    tags that accept arbitrary args and non-identifier kwargs (currently only
    ``ComponentNode``).
    """

    allowed_flags: ClassVar[Iterable[str] | None] = None
    """
    The list of all *possible* flags for this tag.

    E.g. `["required"]` will allow this tag to be used like `{% slot required %}`.

    ```python
    class SlotNode(BaseNode):
        tag = "slot"
        end_tag = "endslot"
        allowed_flags = ["required", "default"]
    ```

    This will allow the template tag `{% slot %}` to be used like this:

    ```django
    {% slot required %} ... {% endslot %}
    {% slot default %} ... {% endslot %}
    {% slot required default %} ... {% endslot %}
    ```
    """

    def render(self, context: Context, *_args: Any, **_kwargs: Any) -> str:
        """
        Render the node. This method is meant to be overridden by subclasses.

        The signature of this function decides what input the template tag accepts.

        The `render()` method MUST accept a `context` argument. Any arguments after that
        will be part of the tag's input parameters.

        So if you define a `render` method like this:

        ```python
        def render(self, context: Context, name: str, **kwargs: Any) -> str:
        ```

        Then the tag will require the `name` parameter, and accept any extra keyword arguments:

        ```django
        {% component name="John" age=20 %}
        ```
        """
        return self.nodelist.render(context)

    # #####################################
    # Attributes
    # #####################################

    params: tuple[list[FilterExpression], dict[str, FilterExpression]]
    """
    The parameters to the tag in the template.

    A tuple of (args, kwargs) where args is a list of FilterExpression objects
    and kwargs is a dict mapping string keys to FilterExpression objects.

    E.g. the following tag:

    ```django
    {% component "my_comp" key=val key2='val2 two' %}
    ```

    Has params:
    - args: [FilterExpression("my_comp")]
    - kwargs: {"key": FilterExpression("val"), "key2": FilterExpression("'val2 two'")}
    """

    flags: dict[str, bool]
    """
    Dictionary of all [`allowed_flags`](../api#django_components_lite.BaseNode.allowed_flags)
    that were set on the tag.

    Flags that were set are `True`, and the rest are `False`.

    E.g. the following tag:

    ```python
    class SlotNode(BaseNode):
        tag = "slot"
        end_tag = "endslot"
        allowed_flags = ["default", "required"]
    ```

    ```django
    {% slot "content" default %}
    ```

    Has 2 flags, `default` and `required`, but only `default` was set.

    The `flags` dictionary will be:

    ```python
    {
        "default": True,
        "required": False,
    }
    ```

    You can check if a flag is set by doing:

    ```python
    if node.flags["default"]:
        ...
    ```
    """

    nodelist: NodeList
    """
    The nodelist of the tag.

    This is the text between the opening and closing tags, e.g.

    ```django
    {% slot "content" default required %}
      <div>
        ...
      </div>
    {% endslot %}
    ```

    The `nodelist` will contain the `<div> ... </div>` part.
    """

    contents: str | None
    """
    The raw text contents between the opening and closing tags, e.g.

    ```django
    {% slot "content" default required %}
      <div>
        ...
      </div>
    {% endslot %}
    ```

    The `contents` will be `"<div> ... </div>"`.
    """

    node_id: str
    """
    The unique ID of the node.

    Extensions can use this ID to store additional information.
    """

    template_name: str | None
    """
    The name of the [`Template`](https://docs.djangoproject.com/en/5.2/ref/templates/api/#django.template.Template)
    that contains this node.

    The template name is set by Django's
    [template loaders](https://docs.djangoproject.com/en/5.2/topics/templates/#loaders).

    For example, the filesystem template loader will set this to the absolute path of the template file.

    ```
    "/home/user/project/templates/my_template.html"
    ```
    """

    template_component: type["Component"] | None
    """
    If the template that contains this node belongs to a [`Component`](../api#django_components_lite.Component),
    then this will be the [`Component`](../api#django_components_lite.Component) class.
    """

    # #####################################
    # MISC
    # #####################################

    def __init__(
        self,
        params: tuple[list[FilterExpression], dict[str, FilterExpression]] | None = None,
        flags: dict[str, bool] | None = None,
        nodelist: NodeList | None = None,
        node_id: str | None = None,
        contents: str | None = None,
        template_name: str | None = None,
        template_component: type["Component"] | None = None,
    ) -> None:
        self.params = params if params is not None else ([], {})
        self.flags = flags or dict.fromkeys(self.allowed_flags or [], False)
        self.nodelist = nodelist or NodeList()
        self.node_id = node_id or gen_id()
        self.contents = contents
        self.template_name = template_name
        self.template_component = template_component

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.node_id}. Contents: {self.contents}. Flags: {self.active_flags}>"

    @property
    def active_flags(self) -> list[str]:
        """
        Flags that were set for this specific instance as a list of strings.

        E.g. the following tag:

        ```django
        {% slot "content" default required %}
        ```

        Will have the following flags:

        ```python
        ["default", "required"]
        ```
        """
        flags = []
        for flag, value in self.flags.items():
            if value:
                flags.append(flag)
        return flags

    @classmethod
    def parse(cls, parser: Parser, token: Token, **kwargs: Any) -> "BaseNode":
        """
        This function is what is passed to Django's `Library.tag()` when
        [registering the tag](https://docs.djangoproject.com/en/5.2/howto/custom-template-tags/#registering-the-tag).

        In other words, this method is called by Django's template parser when we encounter
        a tag that matches this node's tag, e.g. `{% component %}` or `{% slot %}`.

        To register the tag, you can use [`BaseNode.register()`](../api#django_components_lite.BaseNode.register).
        """
        # NOTE: Avoids circular import
        from django_components_lite.template import get_component_from_origin

        tag_id = gen_id()
        bits = token.split_contents()
        tag_name = bits[0]

        # Sanity check
        if tag_name != cls.tag:
            raise TemplateSyntaxError(f"Start tag parser received tag '{tag_name}', expected '{cls.tag}'")

        # Extract flags (positional keywords like "default", "required")
        flags: dict[str, bool] = {}
        remaining_bits: list[str] = []
        allowed_flags_set = set(cls.allowed_flags) if cls.allowed_flags else set()
        for bit in bits[1:]:
            if allowed_flags_set and bit in allowed_flags_set:
                if bit in flags:
                    raise TemplateSyntaxError(f"'{tag_name}' received flag '{bit}' multiple times")
                flags[bit] = True
            else:
                remaining_bits.append(bit)

        # Set all allowed flags, defaulting to False
        all_flags = {f: flags.get(f, False) for f in (cls.allowed_flags or ())}

        # Parse args and kwargs using Django's FilterExpression
        args: list[FilterExpression] = []
        tag_kwargs: dict[str, FilterExpression] = {}
        for bit in remaining_bits:
            if "=" in bit:
                key, val = bit.split("=", 1)
                tag_kwargs[key] = FilterExpression(val, parser)
            else:
                args.append(FilterExpression(bit, parser))

        # Parse body (between start and end tag)
        if cls.end_tag:
            contents = _extract_contents_until(parser, [cls.end_tag])
            nodelist = parser.parse(parse_until=[cls.end_tag])
            parser.delete_first_token()
        else:
            nodelist = NodeList()
            contents = None

        return cls(
            params=(args, tag_kwargs),
            flags=all_flags,
            nodelist=nodelist,
            node_id=tag_id,
            contents=contents,
            template_name=parser.origin.name if parser.origin else None,
            template_component=get_component_from_origin(parser.origin) if parser.origin else None,
            **kwargs,
        )

    @classmethod
    def register(cls, library: Library) -> None:
        """
        A convenience method for registering the tag with the given library.

        ```python
        class MyNode(BaseNode):
            tag = "mynode"

        MyNode.register(library)
        ```

        Allows you to then use the node in templates like so:

        ```django
        {% load mylibrary %}
        {% mynode %}
        ```
        """
        library.tag(cls.tag, cls.parse)

    @classmethod
    def unregister(cls, library: Library) -> None:
        """Unregisters the node from the given library."""
        library.tags.pop(cls.tag, None)
