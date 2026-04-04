import re

import pytest
from django.template import Context, Template, TemplateSyntaxError
from pytest_django.asserts import assertHTMLEqual

from django_components_lite import Component, NotRegistered, register, registry


def gen_slotted_component():
    class SlottedComponent(Component):
        template_file = "slotted_template.html"

    return SlottedComponent


def gen_slotted_component_with_context():
    class SlottedComponentWithContext(Component):
        template: str = """
            {% load component_tags %}
            <custom-template>
                <header>{% slot "header" %}Default header{% endslot %}</header>
                <main>{% slot "main" %}Default main{% endslot %}</main>
                <footer>{% slot "footer" %}Default footer{% endslot %}</footer>
            </custom-template>
        """

        def get_template_data(self, args, kwargs, slots, context):
            return {"variable": kwargs["variable"]}

    return SlottedComponentWithContext


#######################
# TESTS
#######################


class TestComponentTemplateTag:
    class SimpleComponent(Component):
        template: str = """
            Variable: <strong>{{ variable }}</strong>
        """

        def get_template_data(self, args, kwargs, slots, context):
            return {
                "variable": kwargs["variable"],
                "variable2": kwargs.get("variable2", "default"),
            }

    def test_single_component(self):
        registry.register(name="test", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% component "test" variable="variable" %}{% endcomponent %}
        """

        template = Template(simple_tag_template)
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, "Variable: <strong>variable</strong>\n")

    def test_single_component_self_closing(self):
        registry.register(name="test", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% component "test" variable="variable" /%}
        """

        template = Template(simple_tag_template)
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, "Variable: <strong>variable</strong>\n")

    def test_call_with_invalid_name(self):
        registry.register(name="test_one", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% component "test" variable="variable" %}{% endcomponent %}
        """

        template = Template(simple_tag_template)
        with pytest.raises(NotRegistered):
            template.render(Context({}))

    def test_component_called_with_positional_name(self):
        registry.register(name="test", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% component "test" variable="variable" %}{% endcomponent %}
        """

        template = Template(simple_tag_template)
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, "Variable: <strong>variable</strong>\n")

    def test_call_component_with_two_variables(self):
        @register("test")
        class IffedComponent(Component):
            template: str = """
                Variable: <strong>{{ variable }}</strong>
                {% if variable2 != "default" %}
                    Variable2: <strong>{{ variable2 }}</strong>
                {% endif %}
            """

            def get_template_data(self, args, kwargs, slots, context):
                return {
                    "variable": kwargs["variable"],
                    "variable2": kwargs.get("variable2", "default"),
                }

        simple_tag_template: str = """
            {% load component_tags %}
            {% component "test" variable="variable" variable2="hej" %}{% endcomponent %}
        """

        template = Template(simple_tag_template)
        rendered = template.render(Context({}))
        assertHTMLEqual(
            rendered,
            """
            Variable: <strong>variable</strong>
            Variable2: <strong>hej</strong>
            """,
        )

    def test_component_called_with_singlequoted_name(self):
        registry.register(name="test", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% component 'test' variable="variable" %}{% endcomponent %}
        """

        template = Template(simple_tag_template)
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, "Variable: <strong>variable</strong>\n")

    def test_raises_on_component_called_with_variable_as_name(self):
        registry.register(name="test", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% with component_name="test" %}
                {% component component_name variable="variable" %}{% endcomponent %}
            {% endwith %}
        """

        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape("Component name must be a string 'literal', got: component_name"),
        ):
            Template(simple_tag_template)

    def test_component_accepts_provided_and_default_parameters(self):
        @register("test")
        class ComponentWithProvidedAndDefaultParameters(Component):
            template: str = """
                Provided variable: <strong>{{ variable }}</strong>
                Default: <p>{{ default_param }}</p>
            """

            def get_template_data(self, args, kwargs, slots, context):
                return {
                    "variable": kwargs["variable"],
                    "default_param": kwargs.get("default_param", "default text"),
                }

        template_str: str = """
            {% load component_tags %}
            {% component "test" variable="provided value" %}
            {% endcomponent %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))
        assertHTMLEqual(
            rendered,
            """
            Provided variable: <strong>provided value</strong>
            Default: <p>default text</p>
            """,
        )


class TestMultiComponent:
    def test_both_components_render_correctly_with_no_slots(self):
        registry.register("first_component", gen_slotted_component())
        registry.register("second_component", gen_slotted_component_with_context())

        template_str: str = """
            {% load component_tags %}
            {% component 'first_component' %}
            {% endcomponent %}
            {% component 'second_component' variable='xyz' %}
            {% endcomponent %}
        """
        template = Template(template_str)
        rendered = template.render(Context())

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>
                    Default header
                </header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            <custom-template>
                <header>
                    Default header
                </header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    def test_both_components_render_correctly_with_slots(self):
        registry.register("first_component", gen_slotted_component())
        registry.register("second_component", gen_slotted_component_with_context())

        template_str: str = """
            {% load component_tags %}
            {% component 'first_component' %}
                {% fill "header" %}<p>Slot #1</p>{% endfill %}
            {% endcomponent %}
            {% component 'second_component' variable='xyz' %}
                {% fill "header" %}<div>Slot #2</div>{% endfill %}
            {% endcomponent %}
        """
        template = Template(template_str)
        rendered = template.render(Context())

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>
                    <p>Slot #1</p>
                </header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            <custom-template>
                <header>
                    <div>Slot #2</div>
                </header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    def test_both_components_render_correctly_when_only_first_has_slots(self):
        registry.register("first_component", gen_slotted_component())
        registry.register("second_component", gen_slotted_component_with_context())

        template_str: str = """
            {% load component_tags %}
            {% component 'first_component' %}
                {% fill "header" %}<p>Slot #1</p>{% endfill %}
            {% endcomponent %}
            {% component 'second_component' variable='xyz' %}
            {% endcomponent %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>
                    <p>Slot #1</p>
                </header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            <custom-template>
                <header>
                    Default header
                </header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    def test_both_components_render_correctly_when_only_second_has_slots(self):
        registry.register("first_component", gen_slotted_component())
        registry.register("second_component", gen_slotted_component_with_context())

        template_str: str = """
            {% load component_tags %}
            {% component 'first_component' %}
            {% endcomponent %}
            {% component 'second_component' variable='xyz' %}
                {% fill "header" %}<div>Slot #2</div>{% endfill %}
            {% endcomponent %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>
                    Default header
                </header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            <custom-template>
                <header>
                    <div>Slot #2</div>
                </header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )


class TestComponentIsolation:
    def test_instances_of_component_do_not_share_slots(self):
        @register("test")
        class SlottedComponent(Component):
            template: str = """
                {% load component_tags %}
                <custom-template>
                    <header>{% slot "header" %}Default header{% endslot %}</header>
                    <main>{% slot "main" %}Default main{% endslot %}</main>
                    <footer>{% slot "footer" %}Default footer{% endslot %}</footer>
                </custom-template>
            """

        template_str: str = """
            {% load component_tags %}
            {% component "test" %}
                {% fill "header" %}Override header{% endfill %}
            {% endcomponent %}
            {% component "test" %}
                {% fill "main" %}Override main{% endfill %}
            {% endcomponent %}
            {% component "test" %}
                {% fill "footer" %}Override footer{% endfill %}
            {% endcomponent %}
        """
        template = Template(template_str)

        template.render(Context({}))
        rendered = template.render(Context({}))

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Override header</header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            <custom-template>
                <header>Default header</header>
                <main>Override main</main>
                <footer>Default footer</footer>
            </custom-template>
            <custom-template>
                <header>Default header</header>
                <main>Default main</main>
                <footer>Override footer</footer>
            </custom-template>
        """,
        )


class TestComponentTemplateSyntaxError:
    def test_variable_outside_fill_tag_compiles_w_out_error(self):
        registry.register("test", gen_slotted_component())
        # As of v0.28 this is valid, provided the component registered under "test"
        # contains a slot tag marked as 'default'. This is verified outside
        # template compilation time.
        template_str: str = """
            {% load component_tags %}
            {% component "test" %}
                {{ anything }}
            {% endcomponent %}
        """
        Template(template_str)

    def test_text_outside_fill_tag_is_not_error_when_no_fill_tags(self):
        registry.register("test", gen_slotted_component())
        # As of v0.28 this is valid, provided the component registered under "test"
        # contains a slot tag marked as 'default'. This is verified outside
        # template compilation time.
        template_str: str = """
            {% load component_tags %}
            {% component "test" %}
                Text
            {% endcomponent %}
        """
        Template(template_str)

    def test_text_outside_fill_tag_is_error_when_fill_tags(self):
        registry.register("test", gen_slotted_component())
        template_str: str = """
            {% load component_tags %}
            {% component "test" %}
                {% lorem 3 w random %}
                {% fill "header" %}{% endfill %}
            {% endcomponent %}
        """
        template = Template(template_str)

        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape(
                "Illegal content passed to component 'test'. Explicit 'fill' tags cannot occur alongside other text",
            ),
        ):
            template.render(Context())

    def test_unclosed_component_is_error(self):
        registry.register("test", gen_slotted_component())

        template_str: str = """
            {% load component_tags %}
            {% component "test" %}
            {% fill "header" %}{% endfill %}
        """
        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape("Unclosed tag on line 3: 'component'"),
        ):
            Template(template_str)
