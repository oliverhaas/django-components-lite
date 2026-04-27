"""
Tests focusing on the Component class.
For tests focusing on the `component` tag, see `test_templatetags_component.py`
"""

from typing import Any

import pytest
from django.http import HttpRequest, HttpResponse
from django.template import Context, RequestContext, Template, TemplateSyntaxError
from django.test import override_settings
from pytest_django.asserts import assertHTMLEqual

from django_components_lite import (
    Component,
    ComponentRegistry,
    all_components,
    get_component_by_class_id,
    register,
)


class TestComponent:
    def test_empty_component(self):
        class EmptyComponent(Component):
            pass

        EmptyComponent.render(args=["123"])

    def test_template_string_static_inlined(self):
        class SimpleComponent(Component):
            template: str = """
                Variable: <strong>{{ variable }}</strong>
            """

            def get_context_data(self, **kwargs):
                return {
                    "variable": kwargs.get("variable"),
                }

        rendered = SimpleComponent.render(kwargs={"variable": "test"})
        assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong>
            """,
        )

    def test_template_file_static(self):
        class SimpleComponent(Component):
            template_file = "simple_template.html"

            def get_context_data(self, **kwargs):
                return {
                    "variable": kwargs.get("variable"),
                }

        rendered = SimpleComponent.render(kwargs={"variable": "test"})
        assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong>
            """,
        )

    # Test that even with cached template loaders, each Component has its own `Template`
    # even when multiple components point to the same template file.
    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [
                    "tests/templates/",
                    "tests/components/",
                ],
                "OPTIONS": {
                    "builtins": [
                        "django_components_lite.templatetags.component_tags",
                    ],
                    "loaders": [
                        (
                            "django.template.loaders.cached.Loader",
                            [
                                # Default Django loader
                                "django.template.loaders.filesystem.Loader",
                                # Including this is the same as APP_DIRS=True
                                "django.template.loaders.app_directories.Loader",
                                # Components loader
                                "django_components_lite.template_loader.Loader",
                            ],
                        ),
                    ],
                },
            },
        ],
    )
    def test_template_file_static__cached(self):
        class SimpleComponent1(Component):
            template_file = "simple_template.html"

            def get_context_data(self, **kwargs):
                return {
                    "variable": kwargs.get("variable"),
                }

        class SimpleComponent2(Component):
            template_file = "simple_template.html"

            def get_context_data(self, **kwargs):
                return {
                    "variable": kwargs.get("variable"),
                }

        # Render to trigger template caching
        SimpleComponent1.render(kwargs={"variable": "test"})
        SimpleComponent2.render(kwargs={"variable": "test"})

        # Both components have their own cached Template instance
        assert isinstance(SimpleComponent1._cached_template, Template)
        assert isinstance(SimpleComponent2._cached_template, Template)
        assert SimpleComponent1._cached_template.source == SimpleComponent2._cached_template.source

        rendered = SimpleComponent1.render(kwargs={"variable": "test"})
        assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong>
            """,
        )

        rendered = SimpleComponent2.render(kwargs={"variable": "test"})
        assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong>
            """,
        )

    def test_template_file_static__compat(self):
        class SimpleComponent(Component):
            template_name = "simple_template.html"

            def get_context_data(self, **kwargs):
                return {
                    "variable": kwargs.get("variable"),
                }

        # Access fields on Component class
        assert SimpleComponent.template_name == "simple_template.html"
        assert SimpleComponent.template_file == "simple_template.html"

        SimpleComponent.template_name = "other_template.html"
        assert SimpleComponent.template_name == "other_template.html"
        assert SimpleComponent.template_file == "other_template.html"

        SimpleComponent.template_name = "simple_template.html"
        rendered = SimpleComponent.render(kwargs={"variable": "test"})
        assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong>
            """,
        )

        # Access fields on Component instance
        comp = SimpleComponent()
        assert comp.template_name == "simple_template.html"
        assert comp.template_file == "simple_template.html"

        # NOTE: Setting `template_file` on INSTANCE is not supported, as users should work
        #       with classes and not instances. This is tested for completeness.
        comp.template_name = "other_template_2.html"  # type: ignore[misc]
        assert comp.template_name == "other_template_2.html"
        assert comp.template_file == "other_template_2.html"
        assert SimpleComponent.template_name == "other_template_2.html"
        assert SimpleComponent.template_file == "other_template_2.html"

        SimpleComponent.template_name = "simple_template.html"
        rendered = comp.render(kwargs={"variable": "test"})
        assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong>
            """,
        )

    def test_get_component_by_id(self):
        class SimpleComponent(Component):
            pass

        assert get_component_by_class_id(SimpleComponent.class_id) == SimpleComponent

    def test_get_component_by_id_raises_on_missing_component(self):
        with pytest.raises(KeyError):
            get_component_by_class_id("nonexistent")

    def test_get_context_data_returns_none(self):
        class SimpleComponent(Component):
            template_file = "test_component/get-context-data-returns-none.html"

            def get_context_data(self, **kwargs):
                return None

        assert SimpleComponent.render() == "Hello"


class TestComponentRenderAPI:
    def test_raw_input(self):
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                Variable: <strong>{{ variable }}</strong>
                {% slot 'my_slot' %}{% endslot %}
            """

            def get_context_data(self, **kwargs):
                assert self.args == [123, "str"]
                assert self.kwargs == {"variable": "test", "another": 1}
                assert isinstance(self.context, Context)
                assert list(self.slots.keys()) == ["my_slot"]
                my_slot = self.slots["my_slot"]
                assert my_slot() == "MY_SLOT"

                return {
                    "variable": kwargs["variable"],
                }

        rendered = TestComponent.render(
            kwargs={"variable": "test", "another": 1},
            args=(123, "str"),
            slots={"my_slot": "MY_SLOT"},
        )

        assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong> MY_SLOT
            """,
        )

    def test_args_kwargs_slots__simple(self):
        called = False

        class TestComponent(Component):
            template_file = "test_component/args-kwargs-slots--simple.html"

            def get_context_data(self, **kwargs):
                nonlocal called
                called = True

                assert self.args == [123, "str"]
                assert self.kwargs == {"variable": "test", "another": 1}
                assert list(self.slots.keys()) == ["my_slot"]
                my_slot = self.slots["my_slot"]
                assert my_slot() == "MY_SLOT"

        TestComponent.render(
            kwargs={"variable": "test", "another": 1},
            args=(123, "str"),
            slots={"my_slot": "MY_SLOT"},
        )

        assert called

    def test_args_kwargs_slots__available_outside_render(self):
        comp: Any = None

        class TestComponent(Component):
            template_file = "test_component/args-kwargs-slots--available-outside-render.html"

            def get_context_data(self, **kwargs):
                nonlocal comp
                comp = self

        assert comp is None

        TestComponent.render()

        assert comp.args == []  # type: ignore[attr-defined]
        assert comp.kwargs == {}  # type: ignore[attr-defined]
        assert comp.slots == {}  # type: ignore[attr-defined]
        assert comp.context == Context()  # type: ignore[attr-defined]

    def test_metadata__template(self):
        comp: Any = None

        @register("test")
        class TestComponent(Component):
            template_file = "test_component/metadata--template.html"

            def get_context_data(self, **kwargs):
                nonlocal comp
                comp = self

        template_str: str = """
            {% load component_tags %}
            <div class="test-component">
                {% compc "test" %}
            </div>
        """
        template = Template(template_str)
        rendered = template.render(Context())

        assertHTMLEqual(rendered, '<div class="test-component">hello</div>')

        assert isinstance(comp, TestComponent)

        assert isinstance(comp.outer_context, Context)
        assert comp.outer_context == Context()

        assert isinstance(comp.registry, ComponentRegistry)
        assert comp.registered_name == "test"

        assert comp.node is not None
        assert comp.node.template_name == "<unknown source>"

    def test_metadata__component(self):
        comp: Any = None

        @register("test")
        class TestComponent(Component):
            template_file = "test_component/metadata--component.html"

            def get_context_data(self, **kwargs):
                nonlocal comp
                comp = self

        class Outer(Component):
            template_file = "test_component/outer.html"

        rendered = Outer.render()

        assert rendered.strip() == "hello"

        assert isinstance(comp, TestComponent)

        assert isinstance(comp.outer_context, Context)
        assert comp.outer_context is not comp.context

        assert isinstance(comp.registry, ComponentRegistry)
        assert comp.registered_name == "test"

        assert comp.node is not None

        # Now uses template_file, so template_name is the file path
        assert comp.node.template_name.endswith("test_component/outer.html")  # type: ignore[union-attr]

    def test_metadata__python(self):
        comp: Any = None

        @register("test")
        class TestComponent(Component):
            template_file = "test_component/metadata--python.html"

            def get_context_data(self, **kwargs):
                nonlocal comp
                comp = self

        rendered = TestComponent.render(
            context=Context(),
            args=(),
            kwargs={},
            slots={},
            request=None,
            outer_context=Context(),
            registry=ComponentRegistry(),
            registered_name="test",
        )

        assert rendered == "hello"

        assert isinstance(comp, TestComponent)

        assert isinstance(comp.outer_context, Context)
        assert comp.outer_context == Context()

        assert isinstance(comp.registry, ComponentRegistry)
        assert comp.registered_name == "test"

        assert comp.node is None


class TestGetContextDataOverrides:
    """Override hook accepts any subclass signature."""

    def test_override_with_named_kwargs(self):
        class MyComponent(Component):
            template: str = "user: {{ user }}"

            def get_context_data(self, user=None):
                return {"user": user}

        assert MyComponent.render(kwargs={"user": "alice"}) == "user: alice"

    def test_override_with_positional_and_kwargs(self):
        class MyComponent(Component):
            template: str = "a: {{ a }}, b: {{ b }}"

            def get_context_data(self, a, b=None):
                return {"a": a, "b": b}

        assert MyComponent.render(kwargs={"a": 1, "b": 2}) == "a: 1, b: 2"


class TestPositionalArgRouting:
    """Template-tag positional args route to named `get_context_data` params."""

    def test_positional_args_routed_to_named_params(self):
        class MyComponent(Component):
            template: str = "label: {{ label }}, for: {{ for_ }}"

            def get_context_data(self, label, for_):
                return {"label": label, "for_": for_}

        assert MyComponent.render(args=["Email", "email"]) == "label: Email, for: email"

    def test_positional_via_tag(self):
        @register("form_input_label")
        class FormInputLabel(Component):
            template: str = '<label for="{{ for_ }}">{{ text }}</label>'

            def get_context_data(self, text, for_):
                return {"text": text, "for_": for_}

        tpl = Template(
            '{% load component_tags %}{% comp "form_input_label" "Email" "email" %}{% endcomp %}',
        )
        assert tpl.render(Context()) == '<label for="email">Email</label>'

    def test_positional_mixed_with_kwargs(self):
        class MyComponent(Component):
            template: str = "a: {{ a }}, b: {{ b }}, c: {{ c }}"

            def get_context_data(self, a, b=None, **kwargs):
                return {"a": a, "b": b, "c": kwargs.get("c")}

        out = MyComponent.render(args=["x"], kwargs={"b": "y", "c": "z"})
        assert out == "a: x, b: y, c: z"

    def test_kwarg_can_be_passed_as_positional(self):
        class MyComponent(Component):
            template: str = "label: {{ label }}"

            def get_context_data(self, label, **kwargs):
                return {"label": label}

        assert MyComponent.render(args=["Email"]) == "label: Email"

    def test_positional_and_same_kwarg_raises(self):
        class MyComponent(Component):
            template: str = ""

            def get_context_data(self, label, **kwargs):
                return {}

        with pytest.raises(TypeError, match="multiple values for argument 'label'"):
            MyComponent.render(args=["Email"], kwargs={"label": "other"})

    def test_too_many_positional_args_raises(self):
        class MyComponent(Component):
            template: str = ""

            def get_context_data(self, label):
                return {}

        with pytest.raises(TypeError, match="takes 1 positional arguments but 2 were given"):
            MyComponent.render(args=["Email", "extra"])

    def test_var_positional_receives_all_args(self):
        class MyComponent(Component):
            template: str = "args: {{ joined }}"

            def get_context_data(self, *args, **kwargs):
                return {"joined": "|".join(str(a) for a in args)}

        assert MyComponent.render(args=["a", "b", "c"]) == "args: a|b|c"

    def test_no_positional_params_leaves_self_args(self):
        captured: list = []

        class MyComponent(Component):
            template: str = ""

            def get_context_data(self, **kwargs):
                captured.extend(self.args)
                return {}

        MyComponent.render(args=["a", "b"])
        assert captured == ["a", "b"]

    def test_forward_ref_annotation_under_type_checking(self):
        # Repros the 3.14 PEP 649 eager-annotation bug: on Python 3.14+
        # inspect.signature() evaluates __annotate__ eagerly, which raises
        # NameError for names that only exist under `if TYPE_CHECKING:`.
        # We read __code__ directly, so the annotation is never touched.
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            # A name that exists ONLY for type-checking. At runtime this
            # branch doesn't execute, so the name is undefined.
            class UndefinedAtRuntime: ...

        class MyComponent(Component):
            template: str = "x: {{ x }}"

            def get_context_data(self, x: "list[UndefinedAtRuntime]", **kwargs):
                return {"x": x}

        # Class creation must not crash (was NameError on Python 3.14).
        # The positional arg must still bind to `x` by name.
        assert MyComponent.render(args=[[42]]) == "x: [42]"


class TestComponentRender:
    def test_render_minimal(self):
        class SimpleComponent(Component):
            template: str = """
                {% load component_tags %}
                the_arg2: {{ the_arg2 }}
                args: {{ args|safe }}
                the_kwarg: {{ the_kwarg }}
                kwargs: {{ kwargs|safe }}
                ---
                from_context: {{ from_context }}
                ---
                slot_second: {% slot "second" default %}
                    SLOT_SECOND_DEFAULT
                {% endslot %}
            """

            def get_context_data(self, **kwargs):
                return {
                    "the_arg2": self.args[0] if self.args else None,
                    "the_kwarg": kwargs.pop("the_kwarg", None),
                    "args": self.args[1:],
                    "kwargs": kwargs,
                }

        rendered = SimpleComponent.render()
        assertHTMLEqual(
            rendered,
            """
            the_arg2: None
            args: []
            the_kwarg: None
            kwargs: {}
            ---
            from_context:
            ---
            slot_second: SLOT_SECOND_DEFAULT
            """,
        )

    def test_render_full(self):
        class SimpleComponent(Component):
            template: str = """
                {% load component_tags %}
                the_arg: {{ the_arg }}
                the_arg2: {{ the_arg2 }}
                args: {{ args|safe }}
                the_kwarg: {{ the_kwarg }}
                kwargs: {{ kwargs|safe }}
                ---
                from_context: {{ from_context }}
                ---
                slot_first: {% slot "first" required %}
                {% endslot %}
                ---
                slot_second: {% slot "second" default %}
                    SLOT_SECOND_DEFAULT
                {% endslot %}
            """

            def get_context_data(self, **kwargs):
                return {
                    "the_arg": self.args[0],
                    "the_arg2": self.args[1],
                    "the_kwarg": kwargs.pop("the_kwarg", None),
                    "args": self.args[2:],
                    "kwargs": kwargs,
                }

        rendered = SimpleComponent.render(
            context={"from_context": 98},
            args=["one", "two", "three"],
            kwargs={"the_kwarg": "test", "kw2": "ooo"},
            slots={"first": "FIRST_SLOT"},
        )
        assertHTMLEqual(
            rendered,
            """
            the_arg: one
            the_arg2: two
            args: ['three']
            the_kwarg: test
            kwargs: {'kw2': 'ooo'}
            ---
            from_context: 98
            ---
            slot_first: FIRST_SLOT
            ---
            slot_second: SLOT_SECOND_DEFAULT
            """,
        )

    def test_render_to_response_full(self):
        class SimpleComponent(Component):
            template: str = """
                {% load component_tags %}
                the_arg: {{ the_arg }}
                the_arg2: {{ the_arg2 }}
                args: {{ args|safe }}
                the_kwarg: {{ the_kwarg }}
                kwargs: {{ kwargs|safe }}
                ---
                from_context: {{ from_context }}
                ---
                slot_first: {% slot "first" required %}
                {% endslot %}
                ---
                slot_second: {% slot "second" default %}
                    SLOT_SECOND_DEFAULT
                {% endslot %}
            """

            def get_context_data(self, **kwargs):
                return {
                    "the_arg": self.args[0],
                    "the_arg2": self.args[1],
                    "the_kwarg": kwargs.pop("the_kwarg"),
                    "args": self.args[2:],
                    "kwargs": kwargs,
                }

        rendered = SimpleComponent.render_to_response(
            context={"from_context": 98},
            args=["one", "two", "three"],
            kwargs={"the_kwarg": "test", "kw2": "ooo"},
            slots={"first": "FIRST_SLOT"},
        )
        assert isinstance(rendered, HttpResponse)

        assertHTMLEqual(
            rendered.content.decode(),
            """
            the_arg: one
            the_arg2: two
            args: ['three']
            the_kwarg: test
            kwargs: {'kw2': 'ooo'}
            ---
            from_context: 98
            ---
            slot_first: FIRST_SLOT
            ---
            slot_second: SLOT_SECOND_DEFAULT
            """,
        )

    def test_render_to_response_change_response_class(self):
        class MyResponse:
            def __init__(self, content: str) -> None:
                self.content = bytes(content, "utf-8")

        class SimpleComponent(Component):
            response_class = MyResponse
            template: str = "HELLO"

        rendered = SimpleComponent.render_to_response()
        assert isinstance(rendered, MyResponse)

        assertHTMLEqual(
            rendered.content.decode(),
            "HELLO",
        )

    def test_render_with_include(self):
        class SimpleComponent(Component):
            template: str = """
                {% load component_tags %}
                {% include 'slotted_template.html' %}
            """

        rendered = SimpleComponent.render()
        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Default header</header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    # See https://github.com/django-components/django-components/issues/580
    # And https://github.com/django-components/django-components/commit/fee26ec1d8b46b5ee065ca1ce6143889b0f96764
    def test_render_with_include_and_context(self):
        class SimpleComponent(Component):
            template: str = """
                {% load component_tags %}
                {% include 'slotted_template.html' %}
            """

        rendered = SimpleComponent.render(context=Context())
        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Default header</header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    # See https://github.com/django-components/django-components/issues/580
    # And https://github.com/django-components/django-components/issues/634
    # And https://github.com/django-components/django-components/commit/fee26ec1d8b46b5ee065ca1ce6143889b0f96764
    def test_render_with_include_and_request_context(self):
        class SimpleComponent(Component):
            template: str = """
                {% load component_tags %}
                {% include 'slotted_template.html' %}
            """

        rendered = SimpleComponent.render(context=RequestContext(HttpRequest()))
        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Default header</header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    def test_render_with_extends(self):
        class SimpleComponent(Component):
            template: str = """
                {% extends 'block.html' %}
                {% block body %}
                    OVERRIDEN
                {% endblock %}
            """

        rendered = SimpleComponent.render()
        assertHTMLEqual(
            rendered,
            """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <main role="main">
                <div class='container main-container'>
                    OVERRIDEN
                </div>
                </main>
            </body>
            </html>
            """,
        )

    def test_render_can_access_instance(self):
        class TestComponent(Component):
            template_file = "test_component/render-can-access-instance.html"

            def get_context_data(self, **kwargs):
                return {
                    "id": self.name,
                }

        rendered = TestComponent.render()
        assertHTMLEqual(
            rendered,
            "Variable: <strong>TestComponent</strong>",
        )

    def test_render_to_response_can_access_instance(self):
        class TestComponent(Component):
            template_file = "test_component/render-to-response-can-access-instance.html"

            def get_context_data(self, **kwargs):
                return {
                    "id": self.name,
                }

        rendered_resp = TestComponent.render_to_response()
        assertHTMLEqual(
            rendered_resp.content.decode("utf-8"),
            "Variable: <strong>TestComponent</strong>",
        )

    def test_prepends_exceptions_on_template_compile_error(self):
        @register("simple_component")
        class SimpleComponent(Component):
            template_file = "test_component/prepends-exceptions-on-template-compile-error.html"

        class Other(Component):
            template_file = "test_component/other.html"

        with pytest.raises(
            TemplateSyntaxError,
            match=r"An error occurred while rendering components Other:[\s\S]*"
            r"Invalid block tag on line 4: 'endif', expected 'endcomp'",
        ):
            Other.render()

    def test_prepends_exceptions_on_template_compile_error2(self):
        @register("simple_component")
        class SimpleComponent(Component):
            template_file = "test_component/prepends-exceptions-on-template-compile-error2.html"

        class Other(Component):
            template_file = "test_component/other-1.html"

        with pytest.raises(
            TemplateSyntaxError,
            match=r"An error occurred while rendering components Other:[\s\S]*Unclosed tag on line 3: 'comp'",
        ):
            Other.render()


class TestComponentHelpers:
    def test_all_components(self):
        # NOTE: When running all tests, this list may already have some components
        # as some components in test files are defined on module level.
        all_comps_before = len(all_components())

        # Components don't have to be registered to be included in the list
        class TestComponent(Component):
            template: str = """
                Hello from test
            """

        assert len(all_components()) == all_comps_before + 1

        @register("test2")
        class Test2Component(Component):
            template: str = """
                Hello from test2
            """

        assert len(all_components()) == all_comps_before + 2
