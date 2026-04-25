"""Catch-all for tests that use template tags and don't fit other files"""

from django.template import Context, Template
from pytest_django.asserts import assertHTMLEqual

from django_components_lite import Component, registry

#######################
# TESTS
#######################


class TestNestedTags:
    class SimpleComponent(Component):
        template: str = """
            Variable: <strong>{{ var }}</strong>
        """

        def get_context_data(self, **kwargs):
            return {
                "var": kwargs["var"],
            }

    def test_nested_quote_single(self):
        registry.register("test", self.SimpleComponent)

        template: str = """
            {% load component_tags %}
            {% comp "test" var=_("organisation's") %} {% endcomp %}
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
            {% compc "test" var=_("organisation's") %}
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
            {% comp "test" var=_('organisation"s') %} {% endcomp %}
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
            {% compc "test" var=_('organisation"s') %}
        """
        rendered = Template(template).render(Context())
        expected = """
            Variable: <strong>organisation"s</strong>
        """
        assertHTMLEqual(rendered, expected)
