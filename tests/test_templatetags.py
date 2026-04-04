"""Catch-all for tests that use template tags and don't fit other files"""

from django.template import Context, Template
from pytest_django.asserts import assertHTMLEqual

from django_components_lite import Component, register, registry

#######################
# TESTS
#######################


class TestMultilineTags:
    def test_multiline_tags(self):
        @register("test_component")
        class SimpleComponent(Component):
            template: str = """
                Variable: <strong>{{ variable }}</strong>
            """

            def get_template_data(self, args, kwargs, slots, context):
                return {
                    "variable": kwargs["variable"],
                    "variable2": kwargs.get("variable2", "default"),
                }

        template: str = """
            {% load component_tags %}
            {% component
                "test_component"
                variable=123
                variable2="abc"
            %}
            {% endcomponent %}
        """
        rendered = Template(template).render(Context())
        expected = """
            Variable: <strong>123</strong>
        """
        assertHTMLEqual(rendered, expected)


class TestNestedTags:
    class SimpleComponent(Component):
        template: str = """
            Variable: <strong>{{ var }}</strong>
        """

        def get_template_data(self, args, kwargs, slots, context):
            return {
                "var": kwargs["var"],
            }

    def test_nested_quote_single(self):
        registry.register("test", self.SimpleComponent)

        template: str = """
            {% load component_tags %}
            {% component "test" var=_("organisation's") %} {% endcomponent %}
        """
        rendered = Template(template).render(Context())
        expected = """
            Variable: <strong>organisation&#x27;s</strong>
        """
        assertHTMLEqual(rendered, expected)

    def test_nested_quote_single_self_closing(self):
        registry.register("test", self.SimpleComponent)

        template: str = """
            {% load component_tags %}
            {% component "test" var=_("organisation's") / %}
        """
        rendered = Template(template).render(Context())
        expected = """
            Variable: <strong>organisation&#x27;s</strong>
        """
        assertHTMLEqual(rendered, expected)

    def test_nested_quote_double(self):
        registry.register("test", self.SimpleComponent)

        template: str = """
            {% load component_tags %}
            {% component "test" var=_('organisation"s') %} {% endcomponent %}
        """
        rendered = Template(template).render(Context())
        expected = """
            Variable: <strong>organisation"s</strong>
        """
        assertHTMLEqual(rendered, expected)

    def test_nested_quote_double_self_closing(self):
        registry.register("test", self.SimpleComponent)

        template: str = """
            {% load component_tags %}
            {% component "test" var=_('organisation"s') / %}
        """
        rendered = Template(template).render(Context())
        expected = """
            Variable: <strong>organisation"s</strong>
        """
        assertHTMLEqual(rendered, expected)
