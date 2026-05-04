import re

import pytest
from django.template import Context, Template
from django.template.exceptions import TemplateSyntaxError

from django_components_lite.node import BaseNode
from django_components_lite.templatetags import component_tags


class TestNode:
    def test_node_class_requires_tag(self):
        with pytest.raises(ValueError):  # noqa: PT011

            class CaptureNode(BaseNode):
                pass

    # Test that the template tag can be used within the template under the registered tag
    def test_node_class_tags(self):
        class TestNode(BaseNode):
            tag = "mytag"
            end_tag = "endmytag"

            def render(self, context: Context, name: str, **kwargs) -> str:
                return f"Hello, {name}!"

        TestNode.register(component_tags.register)

        # Works with end tag
        template_str: str = """
            {% load component_tags %}
            {% mytag 'John' %}
            {% endmytag %}
            Second: {% mytag 'Mary' %}{% endmytag %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        assert rendered.strip() == "Hello, John!\n            Second: Hello, Mary!"

        # But raises if missing end tag
        template_str2: str = """
            {% load component_tags %}
            {% mytag 'John' %}
        """
        with pytest.raises(TemplateSyntaxError, match=re.escape("Unclosed tag on line 3: 'mytag'")):
            Template(template_str2)

        TestNode.unregister(component_tags.register)

    def test_node_class_no_end_tag(self):
        class TestNode(BaseNode):
            tag = "mytag"

            def render(self, context: Context, name: str, **kwargs) -> str:
                return f"Hello, {name}!"

        TestNode.register(component_tags.register)

        # Raises with end tag
        template_str: str = """
            {% load component_tags %}
            {% mytag 'John' %}
            {% endmytag %}
        """
        with pytest.raises(TemplateSyntaxError, match=re.escape("Invalid block tag on line 4: 'endmytag'")):
            Template(template_str)

        # Works when missing end tag
        template_str2: str = """
            {% load component_tags %}
            {% mytag 'John' %}
        """
        template2 = Template(template_str2)
        rendered2 = template2.render(Context({}))
        assert rendered2.strip() == "Hello, John!"

        TestNode.unregister(component_tags.register)

    def test_node_class_flags(self):
        captured = None

        class TestNode(BaseNode):
            tag = "mytag"
            end_tag = "endmytag"
            allowed_flags = ["required", "default"]

            def render(self, context: Context, name: str, **kwargs) -> str:
                nonlocal captured
                captured = self.allowed_flags, self.flags, self.active_flags

                return f"Hello, {name}!"

        TestNode.register(component_tags.register)

        template_str = """
            {% load component_tags %}
            {% mytag 'John' required %}
            {% endmytag %}
        """
        template = Template(template_str)
        template.render(Context({}))

        allowed_flags, flags, active_flags = captured  # type: ignore[misc]
        assert allowed_flags == ["required", "default"]
        assert flags == {"required": True, "default": False}
        assert active_flags == ["required"]

        TestNode.unregister(component_tags.register)

    def test_node_render(self):
        # Check that the render function is called with the context
        captured = None

        class TestNode(BaseNode):
            tag = "mytag"

            def render(self, context: Context) -> str:
                nonlocal captured
                captured = context.flatten()

                return f"Hello, {context['name']}!"

        TestNode.register(component_tags.register)

        template_str = """
            {% load component_tags %}
            {% mytag %}
        """
        template = Template(template_str)
        rendered = template.render(Context({"name": "John"}))

        assert captured == {"False": False, "None": None, "True": True, "name": "John"}
        assert rendered.strip() == "Hello, John!"

        TestNode.unregister(component_tags.register)

    def test_node_render_accepted_params_set_by_render_signature(self):
        captured = None

        class TestNode1(BaseNode):
            tag = "mytag"
            allowed_flags = ["required", "default"]

            def render(self, context: Context, name: str, count: int = 1, *, msg: str, mode: str = "default") -> str:
                nonlocal captured
                captured = name, count, msg, mode
                return ""

        TestNode1.register(component_tags.register)

        # Set only required params
        template1 = Template(
            """
            {% load component_tags %}
            {% mytag 'John' msg='Hello' required %}
        """,
        )
        template1.render(Context({}))
        assert captured == ("John", 1, "Hello", "default")

        # Set all params
        template2 = Template(
            """
            {% load component_tags %}
            {% mytag 'John2' count=2 msg='Hello' mode='custom' required %}
        """,
        )
        template2.render(Context({}))
        assert captured == ("John2", 2, "Hello", "custom")

        # Set no params
        template3 = Template(
            """
            {% load component_tags %}
            {% mytag %}
        """,
        )
        with pytest.raises(TypeError):
            template3.render(Context({}))

        # Omit required arg
        template4 = Template(
            """
            {% load component_tags %}
            {% mytag msg='Hello' %}
        """,
        )
        with pytest.raises(TypeError):
            template4.render(Context({}))

        # Omit required kwarg
        template5 = Template(
            """
            {% load component_tags %}
            {% mytag name='John' %}
        """,
        )
        with pytest.raises(TypeError):
            template5.render(Context({}))

        # Extra args
        template6 = Template(
            """
            {% load component_tags %}
            {% mytag 123 count=1 name='John' %}
        """,
        )
        with pytest.raises(TypeError):
            template6.render(Context({}))

        # Extra args after kwargs (new parser collects args/kwargs separately,
        # so '123' maps to position 0 = 'name', but name='John' is also a kwarg)
        template6 = Template(
            """
            {% load component_tags %}
            {% mytag count=1 name='John' 123 %}
        """,
        )
        with pytest.raises(TypeError):
            template6.render(Context({}))

        # Extra kwargs
        template7 = Template(
            """
            {% load component_tags %}
            {% mytag 'John' msg='Hello' mode='custom' var=123 %}
        """,
        )
        with pytest.raises(TypeError):
            template7.render(Context({}))

        # Extra kwargs - non-identifier or kwargs (render has no **kwargs, so rejected)
        template8 = Template(
            """
            {% load component_tags %}
            {% mytag 'John' msg='Hello' mode='custom' data-id=123 class="pa-4" @click.once="myVar" %}
        """,
        )
        with pytest.raises(TypeError):
            template8.render(Context({}))

        # Special kwargs alongside positional args (data-id is an invalid identifier)
        template9 = Template(
            """
            {% load component_tags %}
            {% mytag data-id=123 'John' msg='Hello' %}
        """,
        )
        with pytest.raises(TypeError):
            template9.render(Context({}))

        TestNode1.unregister(component_tags.register)

    def test_node_render_extra_args_and_kwargs(self):
        captured = None

        class TestNode1(BaseNode):
            tag = "mytag"
            allowed_flags = ["required", "default"]

            def render(self, context: Context, name: str, *args, msg: str, **kwargs) -> str:
                nonlocal captured
                captured = name, args, msg, kwargs
                return ""

        TestNode1.register(component_tags.register)

        template1 = Template(
            "{% load component_tags %}"
            "{% mytag 'John' 123 456 789 msg='Hello' a=1 b=2 c=3 required"
            ' data-id=123 class="pa-4" @click.once="myVar" %}',
        )
        template1.render(Context({}))
        assert captured == (
            "John",
            (123, 456, 789),
            "Hello",
            {"a": 1, "b": 2, "c": 3, "data-id": 123, "class": "pa-4", "@click.once": "myVar"},
        )

        TestNode1.unregister(component_tags.register)

    def test_node_render_kwargs_only(self):
        captured = None

        class TestNode(BaseNode):
            tag = "mytag"

            def render(self, context: Context, **kwargs) -> str:
                nonlocal captured
                captured = kwargs
                return ""

        TestNode.register(component_tags.register)

        # Test with various kwargs including non-identifier keys
        template = Template(
            "{% load component_tags %}"
            "{% mytag name='John' age=25 data-id=123 class=\"header\""
            ' @click="handleClick" v-if="isVisible" %}',
        )
        template.render(Context({}))

        # All kwargs should be accepted since the function accepts **kwargs
        assert captured == {
            "name": "John",
            "age": 25,
            "data-id": 123,
            "class": "header",
            "@click": "handleClick",
            "v-if": "isVisible",
        }

        # Test with positional args (should fail since function only accepts kwargs)
        template2 = Template(
            """
            {% load component_tags %}
            {% mytag "John" name="Mary" %}
            """,
        )
        with pytest.raises(TypeError):
            template2.render(Context({}))

        TestNode.unregister(component_tags.register)
