import functools
import inspect
import keyword
from collections.abc import Iterable
from typing import Any, ClassVar, cast

from django.template import Context, Library
from django.template.base import FilterExpression, Node, NodeList, Parser, Token
from django.template.exceptions import TemplateSyntaxError

from django_components_lite.util.template_tag import (
    TagParam,
    validate_params,
)


# We wrap `render()` so the user-defined inner method can declare the tag's
# parameters in its signature (e.g. `render(self, context, name, **kwargs)`),
# while the outer wrapper still matches Django's `Node.render(context)`.
class NodeMeta(type):
    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
    ) -> type["BaseNode"]:
        cls = cast("type[BaseNode]", super().__new__(mcs, name, bases, attrs))

        # Skip BaseNode itself
        if attrs.get("__module__") == "django_components_lite.node":
            return cls

        if not hasattr(cls, "tag"):
            raise ValueError(f"Node {name} must have a 'tag' attribute")

        orig_render = cls.render
        if getattr(orig_render, "_djc_wrapped", False):
            return cls

        signature = inspect.signature(orig_render)

        # Drop `self` and `context` so the remaining signature describes the tag's params.
        if len(signature.parameters) < 2:
            raise TypeError(f"`render()` method of {name} must have at least two parameters")

        validation_params = list(signature.parameters.values())
        validation_params = validation_params[2:]
        validation_signature = signature.replace(parameters=validation_params)

        @functools.wraps(orig_render)
        def wrapper_render(self: "BaseNode", context: Context) -> str:
            raw_args, raw_kwargs = self.params
            resolved_args = [arg.resolve(context) for arg in raw_args]
            resolved_kwargs = {k: v.resolve(context) for k, v in raw_kwargs.items()}

            # `{% comp %}` accepts arbitrary args and non-identifier kwargs
            # (e.g. `data-id`, `@click`), so signature validation is skipped.
            if cls._skip_param_validation:
                return orig_render(self, context, *resolved_args, **resolved_kwargs)

            resolved_params_without_invalid_kwargs: list[TagParam] = []
            invalid_kwargs: dict[str, Any] = {}
            did_see_special_kwarg = False

            for value in resolved_args:
                if did_see_special_kwarg:
                    raise SyntaxError("positional argument follows keyword argument")
                resolved_params_without_invalid_kwargs.append(TagParam(key=None, value=value))

            for key, value in resolved_kwargs.items():
                if not key.isidentifier() or keyword.iskeyword(key):
                    invalid_kwargs[key] = value
                    did_see_special_kwarg = True
                else:
                    resolved_params_without_invalid_kwargs.append(TagParam(key=key, value=value))

            args, kwargs = validate_params(
                orig_render,
                validation_signature,
                self.tag,
                resolved_params_without_invalid_kwargs,
                invalid_kwargs,
            )

            return orig_render(self, context, *args, **kwargs)

        cls.render = wrapper_render  # type: ignore[method-assign]
        cls.render._djc_wrapped = True  # type: ignore[attr-defined]

        return cls


# Like `parser.parse(parse_until=[end_tag])`, but does not consume tokens and
# returns the body as a raw string instead of a NodeList.
# See https://github.com/django/django/blob/1fb3f57e81239a75eb8f873b392e11534c041fdc/django/template/base.py#L471
def _extract_contents_until(parser: Parser, until_blocks: list[str]) -> str:
    contents: list[str] = []
    for token in reversed(parser.tokens):
        # Use raw TokenType.* values for a tiny perf boost.
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
    """Base class for django-components-lite custom template tags."""

    # #####################################
    # PUBLIC API (Configurable by users)
    # #####################################

    tag: ClassVar[str]
    """The tag name, e.g. ``"slot"`` matches ``{% slot %}``."""

    end_tag: ClassVar[str | None] = None
    """The end tag name, e.g. ``"endslot"``. If ``None``, the tag has no body."""

    _skip_param_validation: ClassVar[bool] = False
    """If True, skip signature-based param validation and forward resolved args/kwargs as-is."""

    allowed_flags: ClassVar[Iterable[str] | None] = None
    """List of allowed positional flags, e.g. ``["required"]`` for ``{% slot required %}``."""

    def render(self, context: Context, *_args: Any, **_kwargs: Any) -> str:
        """Render the node. Override in subclasses; the signature defines the tag's params."""
        return self.nodelist.render(context)

    # #####################################
    # Attributes
    # #####################################

    params: tuple[list[FilterExpression], dict[str, FilterExpression]]
    """Tuple of (args, kwargs) FilterExpressions parsed from the tag."""

    flags: dict[str, bool]
    """Dictionary of all ``allowed_flags`` mapped to whether each was set on this tag."""

    nodelist: NodeList
    """The parsed nodelist between the opening and closing tags."""

    contents: str | None
    """The raw text contents between the opening and closing tags."""

    template_name: str | None
    """The name of the template that contains this node."""

    # #####################################
    # MISC
    # #####################################

    def __init__(
        self,
        params: tuple[list[FilterExpression], dict[str, FilterExpression]] | None = None,
        flags: dict[str, bool] | None = None,
        nodelist: NodeList | None = None,
        contents: str | None = None,
        template_name: str | None = None,
    ) -> None:
        self.params = params if params is not None else ([], {})
        self.flags = flags or dict.fromkeys(self.allowed_flags or [], False)
        self.nodelist = nodelist or NodeList()
        self.contents = contents
        self.template_name = template_name

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: contents={self.contents!r}. flags={self.active_flags}>"

    @property
    def active_flags(self) -> list[str]:
        """Names of flags that were set on this tag instance."""
        flags = []
        for flag, value in self.flags.items():
            if value:
                flags.append(flag)
        return flags

    @classmethod
    def parse(cls, parser: Parser, token: Token, **kwargs: Any) -> "BaseNode":
        """Parse a tag occurrence; passed to Django's ``Library.tag()``."""
        bits = token.split_contents()
        tag_name = bits[0]

        if tag_name != cls.tag:
            raise TemplateSyntaxError(f"Start tag parser received tag '{tag_name}', expected '{cls.tag}'")

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

        all_flags = {f: flags.get(f, False) for f in (cls.allowed_flags or ())}

        args: list[FilterExpression] = []
        tag_kwargs: dict[str, FilterExpression] = {}
        for bit in remaining_bits:
            if "=" in bit:
                key, val = bit.split("=", 1)
                tag_kwargs[key] = FilterExpression(val, parser)
            else:
                args.append(FilterExpression(bit, parser))

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
            contents=contents,
            template_name=parser.origin.name if parser.origin else None,
            **kwargs,
        )

    @classmethod
    def register(cls, library: Library) -> None:
        """Register this node's tag with the given library."""
        library.tag(cls.tag, cls.parse)

    @classmethod
    def unregister(cls, library: Library) -> None:
        """Unregister the node from the given library."""
        library.tags.pop(cls.tag, None)
