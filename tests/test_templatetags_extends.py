"""Catch-all for tests that use template tags and don't fit other files"""

from django.template import Context, Template
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
                {% component "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomponent %}
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
                {% component "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomponent %}
                {% component "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN 2
                    {% endfill %}
                {% endcomponent %}
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
                {% component "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomponent %}
                {% component "second_extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN 2
                    {% endfill %}
                {% endcomponent %}
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
                {% component "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomponent %}
                {% component "second_extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN 2
                    {% endfill %}
                {% endcomponent %}
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
                {% component "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomponent %}
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
                {% component "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN
                    {% endfill %}
                {% endcomponent %}
                {% component "extended_component" %}
                    {% fill "header" %}
                        SLOT OVERRIDEN 2
                    {% endfill %}
                {% endcomponent %}
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
                {% component "slotted_component" %}
                    {% fill "main" %}
                        {% component "extended_component" %}
                            {% fill "header" %}
                                SLOT OVERRIDEN
                            {% endfill %}
                        {% endcomponent %}
                    {% endfill %}
                {% endcomponent %}
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
                {% component "extended_component" / %}
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

    def test_slots_inside_extends(self):
        registry.register("slotted_component", gen_slotted_component())

        @register("slot_inside_extends")
        class SlotInsideExtendsComponent(Component):
            template: str = """
                {% extends "block_in_slot_in_component.html" %}
            """

        template: str = """
            {% load component_tags %}
            {% component "slot_inside_extends" %}
                {% fill "body" %}
                    BODY_FROM_FILL
                {% endfill %}
            {% endcomponent %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <custom-template>
                    <header></header>
                    <main>BODY_FROM_FILL</main>
                    <footer>Default footer</footer>
                </custom-template>
            </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_slots_inside_include(self):
        registry.register("slotted_component", gen_slotted_component())

        @register("slot_inside_include")
        class SlotInsideIncludeComponent(Component):
            template: str = """
                {% include "block_in_slot_in_component.html" %}
            """

        template: str = """
            {% load component_tags %}
            {% component "slot_inside_include" %}
                {% fill "body" %}
                    BODY_FROM_FILL
                {% endfill %}
            {% endcomponent %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <custom-template>
                    <header></header>
                    <main>BODY_FROM_FILL</main>
                    <footer>Default footer</footer>
                </custom-template>
            </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    # In this case, `{% include %}` is NOT nested inside a `{% component %}` tag.
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

    # In this case, because `{% include %}` is rendered inside a `{% component %}` tag,
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
                {% component "component_inside_include" / %}
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
            {% component "slotted_component" %}
                {% fill "header" %}{% endfill %}
                {% fill "main" %}
                TEST
                {% endfill %}
                {% fill "footer" %}{% endfill %}
            {% endcomponent %}
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

    def test_block_inside_component(self):
        registry.register("slotted_component", gen_slotted_component())

        template: str = """
            {% extends "block_in_component.html" %}
            {% block body %}
            <div>
                58 giraffes and 2 pantaloons
            </div>
            {% endblock %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <custom-template>
                    <header></header>
                    <main>
                        <div> 58 giraffes and 2 pantaloons </div>
                    </main>
                    <footer>Default footer</footer>
                </custom-template>
            </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_block_inside_component_parent(self):
        registry.register("slotted_component", gen_slotted_component())

        @register("block_in_component_parent")
        class BlockInCompParent(Component):
            template_file = "block_in_component_parent.html"

        template: str = """
            {% load component_tags %}
            {% component "block_in_component_parent" %}{% endcomponent %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <custom-template>
                    <header></header>
                    <main>
                        <div> 58 giraffes and 2 pantaloons </div>
                    </main>
                    <footer>Default footer</footer>
                </custom-template>
            </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_block_does_not_affect_inside_component(self):
        """
        Assert that when we call a component with `{% component %}`, that
        the `{% block %}` will NOT affect the inner component.
        """
        registry.register("slotted_component", gen_slotted_component())

        @register("block_inside_slot_v1")
        class BlockInSlotInComponent(Component):
            template_file = "block_in_slot_in_component.html"

        template: str = """
            {% load component_tags %}
            {% component "block_inside_slot_v1" %}
                {% fill "body" %}
                    BODY_FROM_FILL
                {% endfill %}
            {% endcomponent %}
            {% block inner %}
                wow
            {% endblock %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <custom-template>
                    <header></header>
                    <main>BODY_FROM_FILL</main>
                    <footer>Default footer</footer>
                </custom-template>
            </body>
            </html>
            wow
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_inside_block__slot_default_block_default(self):
        registry.register("slotted_component", gen_slotted_component())

        @register("slot_inside_block")
        class _SlotInsideBlockComponent(Component):
            template: str = """
                {% extends "slot_inside_block.html" %}
            """

        template: str = """
            {% load component_tags %}
            {% component "slot_inside_block" %}{% endcomponent %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <custom-template>
                    <header></header>
                    <main>
                        Helloodiddoo
                        Default inner
                    </main>
                    <footer>Default footer</footer>
                </custom-template>
            </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_inside_block__slot_default_block_override(self):
        registry.clear()
        registry.register("slotted_component", gen_slotted_component())

        @register("slot_inside_block")
        class _SlotInsideBlockComponent(Component):
            template: str = """
                {% extends "slot_inside_block.html" %}
                {% block inner %}
                    INNER BLOCK OVERRIDEN
                {% endblock %}
            """

        template: str = """
            {% load component_tags %}
            {% component "slot_inside_block" %}{% endcomponent %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <custom-template>
                    <header></header>
                    <main>
                        Helloodiddoo
                        INNER BLOCK OVERRIDEN
                    </main>
                    <footer>Default footer</footer>
                </custom-template>
            </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_inside_block__slot_overriden_block_default(self):
        registry.register("slotted_component", gen_slotted_component())

        @register("slot_inside_block")
        class _SlotInsideBlockComponent(Component):
            template: str = """
                {% extends "slot_inside_block.html" %}
            """

        template: str = """
            {% load component_tags %}
            {% component "slot_inside_block" %}
                {% fill "body" %}
                    SLOT OVERRIDEN
                {% endfill %}
            {% endcomponent %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <custom-template>
                    <header></header>
                    <main>
                        Helloodiddoo
                        SLOT OVERRIDEN
                    </main>
                    <footer>Default footer</footer>
                </custom-template>
            </body>
            </html>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_inside_block__slot_overriden_block_overriden(self):
        registry.register("slotted_component", gen_slotted_component())

        @register("slot_inside_block")
        class _SlotInsideBlockComponent(Component):
            template: str = """
                {% extends "slot_inside_block.html" %}
                {% block inner %}
                    {% load component_tags %}
                    {% slot "new_slot" %}{% endslot %}
                {% endblock %}
                whut
            """

        # NOTE: The "body" fill will NOT show up, because we override the `inner` block
        # with a different slot. But the "new_slot" WILL show up.
        template: str = """
            {% load component_tags %}
            {% component "slot_inside_block" %}
                {% fill "body" %}
                    SLOT_BODY__OVERRIDEN
                {% endfill %}
                {% fill "new_slot" %}
                    SLOT_NEW__OVERRIDEN
                {% endfill %}
            {% endcomponent %}
        """
        rendered = Template(template).render(Context({"DJC_DEPS_STRATEGY": "ignore"}))
        expected = """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <custom-template>
                    <header></header>
                    <main>
                        Helloodiddoo
                        SLOT_NEW__OVERRIDEN
                    </main>
                    <footer>Default footer</footer>
                </custom-template>
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
            {% component "relative_file_component_using_template_file" %}{% endcomponent %}
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
                {% slot "a" default / %}
            """

        @register("b_inner")
        class BInnerComponent(Component):
            template: str = """
                {% load component_tags %}
                <p>This is the inner component.</p>
                {% slot "b" default / %}
            """

        template: str = """
            {% load component_tags %}
            {% component "a_outer" %}
                {% component "b_inner" %}
                    {% include "extends_compat_c_include.html" %}
                {% endcomponent %}
            {% endcomponent %}
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
                {% slot 'content' / %}
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
                {% component "simple_component" %}
                    {% fill "content" %}
                        {% include 'included.html' with variable="INCLUDED 1" %}
                        {% include 'included.html' with variable="INCLUDED 2" %}
                    {% endfill %}
                {% endcomponent %}
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
