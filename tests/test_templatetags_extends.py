"""Catch-all for tests that use template tags and don't fit other files"""

import pytest
from django.template import Context, Template, TemplateSyntaxError
from pytest_django.asserts import assertHTMLEqual

from django_components_lite import Component, register, registry


def gen_slotted_component():
    class SlottedComponent(Component):
        template_file = "slotted_template.html"

    return SlottedComponent


def gen_blocked_and_slotted_component():
    class BlockedAndSlottedComponent(Component):
        template_file = "blocked_and_slotted_template.html"

    return BlockedAndSlottedComponent


def gen_component_inside_include():
    class ComponentInsideInclude(Component):
        template: str = """<div>Hello</div>"""
        css_file = "style.css"
        js_file = "script.js"

    return ComponentInsideInclude


#######################
# TESTS
#######################


class TestBlockInsideFillDisallowed:
    def test_block_inside_fill_raises_error(self):
        @register("test_comp")
        class _TestComp(Component):
            template: str = "<div>{% slot 'main' %}{% endslot %}</div>"

        with pytest.raises(TemplateSyntaxError, match="not allowed inside"):
            Template(
                "{% load component_tags %}"
                '{% comp "test_comp" %}'
                '{% fill "main" %}'
                "{% block body %}{% endblock %}"
                "{% endfill %}"
                "{% endcomp %}",
            )


class TestExtendsCompat:
    def test_double_extends_on_main_template_and_component_one_component(self):
        registry.register("blocked_and_slotted_component", gen_blocked_and_slotted_component())

        @register("extended_component")
        class _ExtendedComponent(Component):
            template: str = """
                {% extends "blocked_and_slotted_template.html" %}
                {% block before_custom %}
                    <div>BLOCK OVERRIDEN</div>
                {% endblock %}
            """

        template: str = """
            {% extends 'block.html' %}
            {% load component_tags %}
            {% block body %}
                {% comp "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomp %}
            {% endblock %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))

        expected = """
            <!DOCTYPE html>
            <html lang="en">
                <body>
                    <main role="main">
                        <div class='container main-container'>
                            <div>BLOCK OVERRIDEN</div>
                            <custom-template>
                                <header>SLOT OVERRIDEN</header>
                                <main>Default main</main>
                                <footer>Default footer</footer>
                            </custom-template>
                        </div>
                    </main>
                </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_double_extends_on_main_template_and_component_two_identical_components(self):
        registry.register("blocked_and_slotted_component", gen_blocked_and_slotted_component())

        @register("extended_component")
        class _ExtendedComponent(Component):
            template: str = """
                {% extends "blocked_and_slotted_template.html" %}
                {% block before_custom %}
                    <div>BLOCK OVERRIDEN</div>
                {% endblock %}
            """

        template: str = """
            {% extends 'block.html' %}
            {% load component_tags %}
            {% block body %}
                {% comp "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomp %}
                {% comp "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN 2
                    {% endfill %}
                {% endcomp %}
            {% endblock %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))

        expected = """
            <!DOCTYPE html>
            <html lang="en">
                <body>
                    <main role="main">
                        <div class='container main-container'>
                            <div>BLOCK OVERRIDEN</div>
                            <custom-template>
                                <header>SLOT OVERRIDEN</header>
                                <main>Default main</main>
                                <footer>Default footer</footer>
                            </custom-template>
                            <div>BLOCK OVERRIDEN</div>
                            <custom-template>
                                <header>SLOT OVERRIDEN 2</header>
                                <main>Default main</main>
                                <footer>Default footer</footer>
                            </custom-template>
                        </div>
                    </main>
                </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_double_extends_on_main_template_and_component_two_different_components_same_parent(
        self,
    ):
        registry.register("blocked_and_slotted_component", gen_blocked_and_slotted_component())

        @register("extended_component")
        class _ExtendedComponent(Component):
            template: str = """
                {% extends "blocked_and_slotted_template.html" %}
                {% block before_custom %}
                    <div>BLOCK OVERRIDEN</div>
                {% endblock %}
            """

        @register("second_extended_component")
        class _SecondExtendedComponent(Component):
            template: str = """
                {% extends "blocked_and_slotted_template.html" %}
                {% block before_custom %}
                    <div>BLOCK OVERRIDEN</div>
                {% endblock %}
            """

        template_str: str = """
            {% extends 'block.html' %}
            {% load component_tags %}
            {% block body %}
                {% comp "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomp %}
                {% comp "second_extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN 2
                    {% endfill %}
                {% endcomp %}
            {% endblock %}
        """
        template = Template(template_str)
        rendered = template.render(Context({"DJC_DEPS_STRATEGY": "ignore"}))

        expected = """
            <!DOCTYPE html>
            <html lang="en">
                <body>
                    <main role="main">
                        <div class='container main-container'>
                            <div>BLOCK OVERRIDEN</div>
                            <custom-template>
                                <header>SLOT OVERRIDEN</header>
                                <main>Default main</main>
                                <footer>Default footer</footer>
                            </custom-template>
                            <div>BLOCK OVERRIDEN</div>
                            <custom-template>
                                <header>SLOT OVERRIDEN 2</header>
                                <main>Default main</main>
                                <footer>Default footer</footer>
                            </custom-template>
                        </div>
                    </main>
                </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_double_extends_on_main_template_and_component_two_different_components_different_parent(
        self,
    ):
        registry.register("blocked_and_slotted_component", gen_blocked_and_slotted_component())

        @register("extended_component")
        class _ExtendedComponent(Component):
            template: str = """
                {% extends "blocked_and_slotted_template.html" %}
                {% block before_custom %}
                    <div>BLOCK OVERRIDEN</div>
                {% endblock %}
            """

        @register("second_extended_component")
        class _SecondExtendedComponent(Component):
            template: str = """
                {% extends "blocked_and_slotted_template_2.html" %}
                {% block before_custom %}
                    <div>BLOCK OVERRIDEN</div>
                {% endblock %}
            """

        template: str = """
            {% extends 'block.html' %}
            {% load component_tags %}
            {% block body %}
                {% comp "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomp %}
                {% comp "second_extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN 2
                    {% endfill %}
                {% endcomp %}
            {% endblock %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))

        expected = """
            <!DOCTYPE html>
            <html lang="en">
                <body>
                    <main role="main">
                        <div class='container main-container'>
                            <div>BLOCK OVERRIDEN</div>
                            <custom-template>
                                <header>SLOT OVERRIDEN</header>
                                <main>Default main</main>
                                <footer>Default footer</footer>
                            </custom-template>
                            <div>BLOCK OVERRIDEN</div>
                            <custom-template>
                                <header>SLOT OVERRIDEN 2</header>
                                <main>Default main</main>
                                <footer>Default footer</footer>
                            </custom-template>
                        </div>
                    </main>
                </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_extends_on_component_one_component(self):
        registry.register("blocked_and_slotted_component", gen_blocked_and_slotted_component())

        @register("extended_component")
        class _ExtendedComponent(Component):
            template: str = """
                {% extends "blocked_and_slotted_template.html" %}
                {% block before_custom %}
                    <div>BLOCK OVERRIDEN</div>
                {% endblock %}
            """

        template: str = """
            {% load component_tags %}
            <!DOCTYPE html>
            <html lang="en">
            <body>
                {% comp "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomp %}
            </body>
            </html>
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))

        expected = """
            <!DOCTYPE html>
            <html lang="en">
                <body>
                    <div>BLOCK OVERRIDEN</div>
                    <custom-template>
                        <header>SLOT OVERRIDEN</header>
                        <main>Default main</main>
                        <footer>Default footer</footer>
                    </custom-template>
                </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_extends_on_component_two_component(self):
        registry.register("blocked_and_slotted_component", gen_blocked_and_slotted_component())

        @register("extended_component")
        class _ExtendedComponent(Component):
            template: str = """
                {% extends "blocked_and_slotted_template.html" %}
                {% block before_custom %}
                    <div>BLOCK OVERRIDEN</div>
                {% endblock %}
            """

        template: str = """
            {% load component_tags %}
            <!DOCTYPE html>
            <html lang="en">
            <body>
                {% comp "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomp %}
                {% comp "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN 2
                    {% endfill %}
                {% endcomp %}
            </body>
            </html>
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))

        expected = """
            <!DOCTYPE html>
            <html lang="en">
                <body>
                    <div>BLOCK OVERRIDEN</div>
                    <custom-template>
                        <header>SLOT OVERRIDEN</header>
                        <main>Default main</main>
                        <footer>Default footer</footer>
                    </custom-template>
                    <div>BLOCK OVERRIDEN</div>
                    <custom-template>
                        <header>SLOT OVERRIDEN 2</header>
                        <main>Default main</main>
                        <footer>Default footer</footer>
                    </custom-template>
                </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_double_extends_on_main_template_and_nested_component(self):
        registry.register("slotted_component", gen_slotted_component())
        registry.register("blocked_and_slotted_component", gen_blocked_and_slotted_component())

        @register("extended_component")
        class _ExtendedComponent(Component):
            template: str = """
                {% extends "blocked_and_slotted_template.html" %}
                {% block before_custom %}
                    <div>BLOCK OVERRIDEN</div>
                {% endblock %}
            """

        template: str = """
            {% extends 'block.html' %}
            {% load component_tags %}
            {% block body %}
                {% comp "slotted_component" %}
                    {% fill "main" %}
                        {% comp "extended_component" %}
                            {% fill "header" %}
                                SLOT OVERRIDEN
                            {% endfill %}
                        {% endcomp %}
                    {% endfill %}
                {% endcomp %}
            {% endblock %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))

        expected = """
            <!DOCTYPE html>
            <html lang="en">
                <body>
                    <main role="main">
                        <div class='container main-container'>
                            <custom-template>
                                <header>Default header</header>
                                <main>
                                    <div>BLOCK OVERRIDEN</div>
                                    <custom-template>
                                        <header>SLOT OVERRIDEN</header>
                                        <main>Default main</main>
                                        <footer>Default footer</footer>
                                    </custom-template>
                                </main>
                                <footer>Default footer</footer>
                            </custom-template>
                        </div>
                    </main>
                </body>
            </html>
        """

        assertHTMLEqual(rendered, expected)

    def test_double_extends_on_main_template_and_nested_component_and_include(self):
        registry.register("slotted_component", gen_slotted_component())
        registry.register("blocked_and_slotted_component", gen_blocked_and_slotted_component())

        @register("extended_component")
        class _ExtendedComponent(Component):
            template_file = "included.html"

        template: str = """
            {% extends 'block.html' %}
            {% load component_tags %}
            {% block body %}
                {% include 'included.html' %}
                {% compc "extended_component" %}
            {% endblock %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))

        expected = """
            <!DOCTYPE html>
            <html lang="en">
                <body>
                    <main role="main">
                        <div class='container main-container'>
                            Variable: <strong></strong>
                            Variable: <strong></strong>
                        </div>
                    </main>
                </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

        # second rendering after cache built
        rendered_2 = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))

        expected_2 = """
            <!DOCTYPE html>
            <html lang="en">
                <body>
                    <main role="main">
                        <div class='container main-container'>
                            Variable: <strong></strong>
                            Variable: <strong></strong>
                        </div>
                    </main>
                </body>
            </html>
        """
        assertHTMLEqual(rendered_2, expected_2)

    # In this case, `{% include %}` is NOT nested inside a `{% comp %}` tag.
    # We need to ensure that the component inside the `{% include %}` is rendered as if with deps_strategy="ignore",
    # so the parent template decides how to render the JS/CSS.
    # See https://github.com/django-components/django-components/issues/1296
    def test_component_with_media_inside_include(self):
        registry.register("test_component", gen_component_inside_include())

        template: str = """
            {% load component_tags %}
            <body>
                <outer>
                    {% include "component_inside_include_sub.html" %}
                </outer>
            </body>
        """

        # Dependency tags are prepended directly to the component's HTML  -  DJC_DEPS_STRATEGY has no effect.
        expected = """
            <body>
                <outer>
                    <link href="style.css" media="all" rel="stylesheet">
                    <script src="script.js"></script>
                    <div>Hello</div>
                </outer>
            </body>
        """

        rendered_raw = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        assertHTMLEqual(rendered_raw, expected)

        rendered = Template(template).render(Context())
        assertHTMLEqual(rendered, expected)

    # In this case, because `{% include %}` is rendered inside a `{% comp %}` tag,
    # then the component inside the `{% include %}` knows it's inside another component.
    # So it's always rendered as if with deps_strategy="ignore".
    # See https://github.com/django-components/django-components/issues/1296
    def test_component_with_media_inside_include_inside_component(self):
        registry.register("test_component", gen_component_inside_include())

        @register("component_inside_include")
        class CompInsideIncludeComponent(Component):
            template: str = """
                <body>
                    <outer>
                        {% include "component_inside_include_sub.html" %}
                    </outer>
                </body>
            """

        template: str = """
            {% load component_tags %}
            <html>
                {% compc "component_inside_include" %}
            </html>
        """

        expected = """
            <html>
                <body>
                    <outer>
                        <link href="style.css" media="all" rel="stylesheet">
                        <script src="script.js"></script>
                        <div>Hello</div>
                    </outer>
                </body>
            </html>
        """

        rendered_raw = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        assertHTMLEqual(rendered_raw, expected)

        rendered = Template(template).render(Context())
        assertHTMLEqual(rendered, expected)

    def test_component_inside_block(self):
        registry.register("slotted_component", gen_slotted_component())
        template: str = """
            {% extends "block.html" %}
            {% load component_tags %}
            {% block body %}
            {% comp "slotted_component" %}
                {% fill "header" %}{% endfill %}
                {% fill "main" %}
                TEST
                {% endfill %}
                {% fill "footer" %}{% endfill %}
            {% endcomp %}
            {% endblock %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <main role="main">
                    <div class='container main-container'>
                        <custom-template>
                            <header></header>
                            <main>TEST</main>
                            <footer></footer>
                        </custom-template>
                    </div>
                </main>
            </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_component_using_template_file_extends_relative_file(self):
        @register("relative_file_component_using_template_file")
        class RelativeFileComponentUsingTemplateFile(Component):
            template_file = "relative_extends.html"

        template: str = """
            {% load component_tags %}
            {% comp "relative_file_component_using_template_file" %}{% endcomp %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
              <body>
                <main role="main">
                  <div class='container main-container'>
                    BLOCK OVERRIDEN
                  </div>
                </main>
              </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    # Fix for compatibility with Django's `{% include %}` and `{% extends %}` tags.
    # See https://github.com/django-components/django-components/issues/1325
    def test_nested_component_with_include_and_extends_in_slot(self):
        @register("a_outer")
        class AOuterComponent(Component):
            template: str = """
                {% load component_tags %}
                <p>This is the outer component.</p>
                {% slot "a" default %}{% endslot %}
            """

        @register("b_inner")
        class BInnerComponent(Component):
            template: str = """
                {% load component_tags %}
                <p>This is the inner component.</p>
                {% slot "b" default %}{% endslot %}
            """

        template: str = """
            {% load component_tags %}
            {% comp "a_outer" %}
                {% comp "b_inner" %}
                    {% include "extends_compat_c_include.html" %}
                {% endcomp %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context({}))

        assertHTMLEqual(
            rendered,
            """
            <p>This is the outer component.</p>
            <p>This is the inner component.</p>
            <p>This template gets extended.</p>
            <p>This template extends another template.</p>
        """,
        )

    def test_double_include_template_with_extend(
        self,
    ):
        @register("simple_component")
        class SimpleComponent(Component):
            template: str = """
                {% slot 'content' %}{% endslot %}
            """

        # Confirm that this setup works in Django without components
        template1: str = """
            {% extends 'block.html' %}
            {% load component_tags %}
            {% block body %}
                {# history: [<Origin name='/Users/presenter/repos/django-components/tests/templates/included.html'>] #}
                {% include 'included.html' with variable="INCLUDED 1" %}
                {# history: [<Origin name='/Users/presenter/repos/django-components/tests/templates/included.html'>] #}
                {% include 'included.html' with variable="INCLUDED 2" %}
            {% endblock %}
        """
        rendered1 = Template(template1).render(Context())
        expected1 = """
            <!DOCTYPE html>
            <html lang="en">
              <body>
                <main role="main">
                  <div class='container main-container'>
                    Variable: <strong>INCLUDED 1</strong>
                    Variable: <strong>INCLUDED 2</strong>
                  </div>
                </main>
              </body>
            </html>
        """
        assertHTMLEqual(rendered1, expected1)

        template2: str = """
            {% extends 'block.html' %}
            {% load component_tags %}
            {% block body %}
                {% comp "simple_component" %}
                    {% fill "content" %}
                        {% include 'included.html' with variable="INCLUDED 1" %}
                        {% include 'included.html' with variable="INCLUDED 2" %}
                    {% endfill %}
                {% endcomp %}
            {% endblock %}
        """
        rendered2 = Template(template2).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))

        expected2 = """
            <!DOCTYPE html>
            <html lang="en">
              <body>
                <main role="main">
                  <div class='container main-container'>
                    Variable: <strong>INCLUDED 1</strong>
                    Variable: <strong>INCLUDED 2</strong>
                  </div>
                </main>
              </body>
            </html>
        """
        assertHTMLEqual(rendered2, expected2)
