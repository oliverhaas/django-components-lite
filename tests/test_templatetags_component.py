import re

import pytest
from django.template import Context, Template, TemplateSyntaxError
from pytest_django.asserts import assertHTMLEqual

from django_components_lite import Component, NotRegisteredError, register, registry


def gen_slotted_component():
    class SlottedComponent(Component):
        template_name = "slotted_template.html"

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

        def get_context_data(self, **kwargs):
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

        def get_context_data(self, **kwargs):
            return {
                "variable": kwargs["variable"],
                "variable2": kwargs.get("variable2", "default"),
            }

    def test_single_component(self):
        registry.register(name="test", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% comp "test" variable="variable" %}{% endcomp %}
        """

        template = Template(simple_tag_template)
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, "Variable: <strong>variable</strong>\n")

    def test_single_component_self_closing(self):
        registry.register(name="test", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% compc "test" variable="variable" %}
        """

        template = Template(simple_tag_template)
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, "Variable: <strong>variable</strong>\n")

    def test_call_with_invalid_name(self):
        registry.register(name="test_one", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% comp "test" variable="variable" %}{% endcomp %}
        """

        template = Template(simple_tag_template)
        with pytest.raises(NotRegisteredError):
            template.render(Context({}))

    def test_component_called_with_positional_name(self):
        registry.register(name="test", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% comp "test" variable="variable" %}{% endcomp %}
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

            def get_context_data(self, **kwargs):
                return {
                    "variable": kwargs["variable"],
                    "variable2": kwargs.get("variable2", "default"),
                }

        simple_tag_template: str = """
            {% load component_tags %}
            {% comp "test" variable="variable" variable2="hej" %}{% endcomp %}
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
            {% comp 'test' variable="variable" %}{% endcomp %}
        """

        template = Template(simple_tag_template)
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, "Variable: <strong>variable</strong>\n")

    def test_raises_on_component_called_with_variable_as_name(self):
        registry.register(name="test", component=self.SimpleComponent)

        simple_tag_template: str = """
            {% load component_tags %}
            {% with component_name="test" %}
                {% comp component_name variable="variable" %}{% endcomp %}
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

            def get_context_data(self, **kwargs):
                return {
                    "variable": kwargs["variable"],
                    "default_param": kwargs.get("default_param", "default text"),
                }

        template_str: str = """
            {% load component_tags %}
            {% comp "test" variable="provided value" %}
            {% endcomp %}
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
            {% comp 'first_component' %}
            {% endcomp %}
            {% comp 'second_component' variable='xyz' %}
            {% endcomp %}
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
            {% comp 'first_component' %}
                {% fill "header" %}<p>Slot #1</p>{% endfill %}
            {% endcomp %}
            {% comp 'second_component' variable='xyz' %}
                {% fill "header" %}<div>Slot #2</div>{% endfill %}
            {% endcomp %}
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
            {% comp 'first_component' %}
                {% fill "header" %}<p>Slot #1</p>{% endfill %}
            {% endcomp %}
            {% comp 'second_component' variable='xyz' %}
            {% endcomp %}
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
            {% comp 'first_component' %}
            {% endcomp %}
            {% comp 'second_component' variable='xyz' %}
                {% fill "header" %}<div>Slot #2</div>{% endfill %}
            {% endcomp %}
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
            {% comp "test" %}
                {% fill "header" %}Override header{% endfill %}
            {% endcomp %}
            {% comp "test" %}
                {% fill "main" %}Override main{% endfill %}
            {% endcomp %}
            {% comp "test" %}
                {% fill "footer" %}Override footer{% endfill %}
            {% endcomp %}
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
            {% comp "test" %}
                {{ anything }}
            {% endcomp %}
        """
        Template(template_str)

    def test_text_outside_fill_tag_is_not_error_when_no_fill_tags(self):
        registry.register("test", gen_slotted_component())
        # As of v0.28 this is valid, provided the component registered under "test"
        # contains a slot tag marked as 'default'. This is verified outside
        # template compilation time.
        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}
                Text
            {% endcomp %}
        """
        Template(template_str)

    def test_text_outside_fill_tag_is_error_when_fill_tags(self):
        registry.register("test", gen_slotted_component())
        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% lorem 3 w random %}
                {% fill "header" %}{% endfill %}
            {% endcomp %}
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
            {% comp "test" %}
            {% fill "header" %}{% endfill %}
        """
        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape("Unclosed tag on line 3: 'comp'"),
        ):
            Template(template_str)


class TestComponentNodeParseFinalize:
    """A previous parse's stale `finalize` callback (fired when its registry or
    subclass is GC'd) must not pop a newer dict entry registered under the same
    start_tag. Otherwise the next parse raises `KeyError: 'comp'`.
    """

    def test_stale_finalize_does_not_drop_replacement_entry(self, monkeypatch):
        from django_components_lite.component import component_node_subclasses_by_name

        captured: list = []
        import django_components_lite.component as component_mod

        real_finalize = component_mod.finalize

        def capturing_finalize(obj, func, *args, **kwargs):
            captured.append(func)
            return real_finalize(obj, func, *args, **kwargs)

        monkeypatch.setattr(component_mod, "finalize", capturing_finalize)

        registry.register("race_a", gen_slotted_component())
        Template('{% load component_tags %}{% compc "race_a" %}')

        stale_callbacks = list(captured)
        assert stale_callbacks, "expected ComponentNode.parse to register finalize callbacks"

        # Mimic conftest teardown + a fresh test starting on the same start_tag.
        component_node_subclasses_by_name.clear()
        registry.unregister("race_a")

        registry.register("race_b", gen_slotted_component())
        Template('{% load component_tags %}{% compc "race_b" %}')
        assert "compc" in component_node_subclasses_by_name

        # Now fire each stale callback (simulating delayed GC from the prior parse).
        # They must not wipe the newer entry.
        for cb in stale_callbacks:
            cb()

        assert "compc" in component_node_subclasses_by_name
