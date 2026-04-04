from typing import Any

from django import VERSION as DJANGO_VERSION
from django.template import Context, NodeList, Template
from django.template.base import Node, Origin, Parser
from django.template.library import InclusionNode

from django_components_lite.util.template_parser import parse_template


# In some cases we can't work around Django's design, and need to patch the template class.
def monkeypatch_template_cls(template_cls: type[Template]) -> None:
    if is_cls_patched(template_cls):
        return

    monkeypatch_template_init(template_cls)
    monkeypatch_template_compile_nodelist(template_cls)
    template_cls._djc_patched = True


# Patch `Template.__init__` to apply `on_template_loaded()` and `on_template_compiled()`
# extension hooks if the template belongs to a Component.
def monkeypatch_template_init(template_cls: type[Template]) -> None:
    original_init = template_cls.__init__

    # NOTE: Function signature of Template.__init__ hasn't changed in 11 years, so we can safely patch it.
    #       See https://github.com/django/django/blame/main/django/template/base.py#L139
    def __init__(  # noqa: N807
        self: Template,
        template_string: Any,
        origin: Origin | None = None,
        name: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # NOTE: Avoids circular import
        from django_components_lite.template import (
            get_component_by_template_file,
            get_component_from_origin,
            set_component_to_origin,
        )

        # If this Template instance was created by us when loading a template file for a component
        # with `load_component_template()`, then we do 2 things:
        #
        # Associate the Component class with the template by setting it on the `Origin` instance
        # (`template.origin.component_cls`). This way the `{% component%}` and `{% slot %}` tags
        # will know inside which Component class they were defined.
        if get_component_from_origin(origin) is not None:
            pass  # already set
        elif origin is not None and origin.template_name is not None:
            component_cls = get_component_by_template_file(origin.template_name)
            if component_cls is not None:
                set_component_to_origin(origin, component_cls)

        # Calling original `Template.__init__` should also compile the template into a Nodelist
        # via `Template.compile_nodelist()`.
        original_init(self, template_string, origin, name, *args, **kwargs)

    template_cls.__init__ = __init__


# Patch `Template.compile_nodelist` to use our custom parser. Our parser makes it possible
# to use template tags as inputs to the component tag:
#
# {% component "my-component" description="{% lorem 3 w %}" / %}
def monkeypatch_template_compile_nodelist(template_cls: type[Template]) -> None:
    def _compile_nodelist(self: Template) -> NodeList:
        """
        Parse and compile the template source into a nodelist. If debug
        is True and an exception occurs during parsing, the exception is
        annotated with contextual line information where it occurred in the
        template source.
        """
        #  ---------------- ORIGINAL (Django v5.1.3) ----------------
        # if self.engine.debug:
        #     lexer = DebugLexer(self.source)
        # else:
        #     lexer = Lexer(self.source)

        # tokens = lexer.tokenize()
        #  ---------------- OUR CHANGES START ----------------
        tokens = parse_template(self.source)
        #  ---------------- OUR CHANGES END ----------------
        parser = Parser(
            tokens,
            self.engine.template_libraries,
            self.engine.template_builtins,
            self.origin,
        )

        try:
            nodelist = parser.parse()
            if DJANGO_VERSION >= (5, 1):
                #  ---------------- ADDED IN Django v5.1 - See https://github.com/django/django/commit/35bbb2c9c01882b1d77b0b8c737ac646144833d4
                self.extra_data = getattr(parser, "extra_data", {})
                #  ---------------- END OF ADDED IN Django v5.1 ----------------
            return nodelist
        except Exception as e:
            if self.engine.debug:
                e.template_debug = self.get_exception_info(e, e.token)  # type: ignore[attr-defined]
            raise

    template_cls.compile_nodelist = _compile_nodelist


def monkeypatch_inclusion_node(inclusion_node_cls: type[Node]) -> None:
    if is_cls_patched(inclusion_node_cls):
        return

    monkeypatch_inclusion_init(inclusion_node_cls)
    monkeypatch_inclusion_render(inclusion_node_cls)
    inclusion_node_cls._djc_patched = True


# Patch `InclusionNode.__init__` so that `InclusionNode.func` returns also `{"_DJC_INSIDE_INCLUSION_TAG": True}`.
# This is then used in `Template.render()` so that we can detect if template was rendered inside an inclusion tag.
# See https://github.com/django-components/django-components/issues/1390
def monkeypatch_inclusion_init(inclusion_node_cls: type[Node]) -> None:
    original_init = inclusion_node_cls.__init__

    # NOTE: Function signature of InclusionNode.__init__ hasn't changed in 9 years, so we can safely patch it.
    #       See https://github.com/django/django/blame/main/django/template/library.py#L348
    def __init__(  # noqa: N807
        self: InclusionNode,
        func: Any,
        takes_context: bool,
        args: Any,
        kwargs: Any,
        filename: Any,
        *future_args: Any,
        **future_kwargs: Any,
    ) -> None:
        original_init(self, func, takes_context, args, kwargs, filename, *future_args, **future_kwargs)

        orig_func = self.func

        def new_func(*args: Any, **kwargs: Any) -> Any:
            result = orig_func(*args, **kwargs)
            result["_DJC_INSIDE_INCLUSION_TAG"] = True
            return result

        self.func = new_func

    inclusion_node_cls.__init__ = __init__


def monkeypatch_inclusion_render(inclusion_node_cls: type[Node]) -> None:
    # Modify `InclusionNode.render()`  so that the included
    # template does NOT render the JS/CSS by itself.
    #
    # Instead, we want the parent template to decide whether to render the JS/CSS.
    #
    # We achieve this by setting `_DJC_INSIDE_INCLUSION_TAG`.
    #
    # Fix for https://github.com/django-components/django-components/issues/1390
    if is_cls_patched(inclusion_node_cls):
        # Do not patch if done so already. This helps us avoid RecursionError
        return

    orig_inclusion_render = inclusion_node_cls.render

    # NOTE: This implementation is based on Django v5.2.5)
    def _inclusion_render(self: InclusionNode, context: Context, *args: Any, **kwargs: Any) -> str:
        with context.update({"_DJC_INSIDE_INCLUSION_TAG": True}):
            return orig_inclusion_render(self, context, *args, **kwargs)

    inclusion_node_cls.render = _inclusion_render


def is_cls_patched(cls: type[Any]) -> bool:
    return getattr(cls, "_djc_patched", False)
