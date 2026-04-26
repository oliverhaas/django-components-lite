import re

import pytest
from django.template import Context, Template, TemplateSyntaxError
from pytest_django.asserts import assertHTMLEqual

from django_components_lite import Component, Slot, register, registry


def _gen_slotted_component():
    class SlottedComponent(Component):
        template: str = """
            {% load component_tags %}
            <custom-template>
                <header>{% slot "header" %}Default header{% endslot %}</header>
                <main>{% slot "main" %}Default main{% endslot %}</main>
                <footer>{% slot "footer" %}Default footer{% endslot %}</footer>
            </custom-template>
        """

    return SlottedComponent


#######################
# TESTS
#######################


class TestComponentSlot:
    def test_slotted_template_basic(self):
        registry.register(name="test1", component=_gen_slotted_component())

        @register("test2")
        class SimpleComponent(Component):
            template_file = "test_templatetags_slot_fill/slotted-template-basic.html"

            def get_context_data(self, **kwargs):
                return {
                    "variable": kwargs["variable"],
                    "variable2": kwargs.get("variable2", "default"),
                }

        template_str: str = """
            {% load component_tags %}
            {% comp "test1" %}
                {% fill "header" %}
                    Custom header
                {% endfill %}
                {% fill "main" %}
                    {% comp "test2" variable="variable" %}{% endcomp %}
                {% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Custom header</header>
                <main>
                    Variable: <strong>variable</strong>
                </main>
                <footer>Default footer</footer>
            </custom-template>
        """,
        )

    def test_slotted_template_basic_self_closing(self):
        @register("test1")
        class SlottedComponent(Component):
            template: str = """
                {% load component_tags %}
                <custom-template>
                    <header>{% slot "header" %}{% endslot %}</header>
                    <main>{% slot "main" %}Default main{% endslot %}</main>
                    <footer>{% slot "footer" %}{% endslot %}</footer>
                </custom-template>
            """

        registry.register(name="test1", component=SlottedComponent)

        @register("test2")
        class SimpleComponent(Component):
            template_file = "test_templatetags_slot_fill/slotted-template-basic-self-closing.html"

            def get_context_data(self, **kwargs):
                return {
                    "variable": kwargs["variable"],
                    "variable2": kwargs.get("variable2", "default"),
                }

        template_str: str = """
            {% load component_tags %}
            {% comp "test1" %}
                {% fill "header" %}
                    {% compc "test2" variable="variable" %}
                {% endfill %}
                {% fill "main" %}{% endfill %}
                {% fill "footer" %}{% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        # NOTE: <main> is empty, because the fill is provided, even if empty
        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>
                    Variable: <strong>variable</strong>
                </header>
                <main></main>
                <footer></footer>
            </custom-template>
        """,
        )

    # NOTE: Second arg is the expected output of `{{ variable }}`
    def test_slotted_template_with_context_var(self):
        @register("test1")
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

        template_str: str = """
            {% load component_tags %}
            {% with my_first_variable="test123" %}
                {% comp "test1" variable="test456" %}
                    {% fill "main" %}
                        {{ my_first_variable }} - {{ variable }}
                    {% endfill %}
                    {% fill "footer" %}
                        {{ my_second_variable }}
                    {% endfill %}
                {% endcomp %}
            {% endwith %}
        """
        template = Template(template_str)
        rendered = template.render(Context({"my_second_variable": "test321"}))

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Default header</header>
                <main>test123 - </main>
                <footer>test321</footer>
            </custom-template>
        """,
        )

    def test_slotted_template_no_slots_filled(self):
        registry.register(name="test", component=_gen_slotted_component())

        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}{% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

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

    def test_slotted_template_without_slots(self):
        @register("test")
        class SlottedComponentNoSlots(Component):
            template: str = """
                <custom-template></custom-template>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}{% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        assertHTMLEqual(rendered, "<custom-template></custom-template>")

    def test_slotted_template_without_slots_and_single_quotes(self):
        @register("test")
        class SlottedComponentNoSlots(Component):
            template: str = """
                <custom-template></custom-template>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test' %}{% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        assertHTMLEqual(rendered, "<custom-template></custom-template>")

    def test_variable_fill_name(self):
        registry.register(name="test", component=_gen_slotted_component())
        template_str: str = """
            {% load component_tags %}
            {% with slotname="header" %}
                {% comp 'test' %}
                    {% fill slotname %}Hi there!{% endfill %}
                {% endcomp %}
            {% endwith %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))
        expected = """
        <custom-template>
            <header>Hi there!</header>
            <main>Default main</main>
            <footer>Default footer</footer>
        </custom-template>
        """
        assertHTMLEqual(rendered, expected)

    def test_missing_required_slot_raises_error(self):
        class Comp(Component):
            template: str = """
                {% load component_tags %}
                <div class="header-box">
                    <h1>{% slot "title" required %}{% endslot %}</h1>
                    <h2>{% slot "subtitle" %}{% endslot %}</h2>
                </div>
            """

        registry.register("test", Comp)

        template_str: str = """
            {% load component_tags %}
            {% comp 'test' %}
            {% endcomp %}
        """
        template = Template(template_str)

        with pytest.raises(TemplateSyntaxError, match=re.escape("Slot 'title' is marked as 'required'")):
            template.render(Context())

    # NOTE: This is relevant only for the "isolated" mode
    def test_slots_of_top_level_comps_can_access_full_outer_ctx(self):
        class SlottedComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <main>{% slot "main" default %}Easy to override{% endslot %}</main>
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "name": kwargs.get("name"),
                }

        registry.register("test", SlottedComponent)

        template_str: str = """
            {% load component_tags %}
            <body>
                {% comp "test" %}
                    ABC: {{ name }} {{ some }}
                {% endcomp %}
            </body>
        """
        self.template = Template(template_str)

        nested_ctx = Context({"DJC_DEPS_STRATEGY": "ignore"})
        # Check that the component can access vars across different context layers
        nested_ctx.push({"some": "var"})
        nested_ctx.push({"name": "carl"})
        rendered = self.template.render(nested_ctx)

        assertHTMLEqual(
            rendered,
            """
            <body>
                <div>
                    <main> ABC: carl var </main>
                </div>
            </body>
            """,
        )

    def test_target_default_slot_as_named(self):
        @register("test")
        class Comp(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <h1>{% slot "title" default %}Default title{% endslot %}</h1>
                    <h2>{% slot "subtitle" %}Default subtitle{% endslot %}</h2>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test' %}
                {% fill "default" %}Custom title{% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)

        rendered = template.render(Context())
        assertHTMLEqual(
            rendered,
            """
            <div>
                <h1> Custom title </h1>
                <h2> Default subtitle </h2>
            </div>
            """,
        )

    def test_raises_on_doubly_filled_slot__same_name(self):
        @register("test")
        class Comp(Component):
            template: str = """
                {% load component_tags %}
                <div class="header-box">
                    <h1>{% slot "title" default %}Default title{% endslot %}</h1>
                    <h2>{% slot "subtitle" %}Default subtitle{% endslot %}</h2>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test' %}
                {% fill "title" %}Custom title{% endfill %}
                {% fill "title" %}Another title{% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)

        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape(
                "Multiple fill tags cannot target the same slot name in component 'test': "
                "Detected duplicate fill tag name 'title'",
            ),
        ):
            template.render(Context())

    def test_raises_on_doubly_filled_slot__named_and_default(self):
        @register("test")
        class Comp(Component):
            template: str = """
                {% load component_tags %}
                <div class="header-box">
                    <h1>{% slot "title" default %}Default title{% endslot %}</h1>
                    <h2>{% slot "subtitle" %}Default subtitle{% endslot %}</h2>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test' %}
                {% fill "default" %}Custom title{% endfill %}
                {% fill "title" %}Another title{% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)

        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape(
                "Slot 'title' of component 'test' was filled twice: once explicitly and once implicitly as 'default'",
            ),
        ):
            template.render(Context())

    def test_raises_on_doubly_filled_slot__named_and_default_2(self):
        @register("test")
        class Comp(Component):
            template: str = """
                {% load component_tags %}
                <div class="header-box">
                    <h1>{% slot "default" default %}Default title{% endslot %}</h1>
                    <h2>{% slot "subtitle" %}Default subtitle{% endslot %}</h2>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test' %}
                {% fill "default" %}Custom title{% endfill %}
                {% fill "default" %}Another title{% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)

        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape(
                "Multiple fill tags cannot target the same slot name in component 'test': "
                "Detected duplicate fill tag name 'default'",
            ),
        ):
            template.render(Context())

    def test_multiple_slots_with_same_name_different_flags(self):
        class TestComp(Component):
            def get_context_data(self, **kwargs):
                return {"required": kwargs["required"]}

            template: str = """
                {% load component_tags %}
                <div>
                    {% if required %}
                        <main>{% slot "main" required %}1{% endslot %}</main>
                    {% endif %}
                    <div>{% slot "main" default %}2{% endslot %}</div>
                </div>
            """

        # 1. Specify the non-required slot by its name
        rendered1 = TestComp.render(
            kwargs={"required": False},
            slots={
                "main": "MAIN",
            },
        )

        # 2. Specify the non-required slot by the "default" name
        rendered2 = TestComp.render(
            kwargs={"required": False},
            slots={
                "default": "MAIN",
            },
        )

        assertHTMLEqual(rendered1, "<div><div>MAIN</div></div>")
        assertHTMLEqual(rendered2, "<div><div>MAIN</div></div>")

        # 3. Specify the required slot by its name
        rendered3 = TestComp.render(
            kwargs={"required": True},
            slots={
                "main": "MAIN",
            },
        )
        assertHTMLEqual(rendered3, "<div><main>MAIN</main><div>MAIN</div></div>")

        # 4. RAISES: Specify the required slot by the "default" name
        #    This raises because the slot that is marked as 'required' is NOT marked as 'default'.
        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape("Slot 'main' is marked as 'required'"),
        ):
            TestComp.render(
                kwargs={"required": True},
                slots={
                    "default": "MAIN",
                },
            )

    def test_slot_in_include(self):
        @register("slotted")
        class SlottedWithIncludeComponent(Component):
            template: str = """
                {% load component_tags %}
                {% include 'slotted_template.html' %}
            """

        template_str: str = """
            {% load component_tags %}
            {% comp "slotted" %}
                {% fill "header" %}Custom header{% endfill %}
                {% fill "main" %}Custom main{% endfill %}
                {% fill "footer" %}Custom footer{% endfill %}
            {% endcomp %}
        """

        rendered = Template(template_str).render(Context({}))

        expected = """
            <custom-template>
                <header>Custom header</header>
                <main>Custom main</main>
                <footer>Custom footer</footer>
            </custom-template>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_in_include_raises_if_isolated(self):
        @register("broken_component")
        class BrokenComponent(Component):
            template: str = """
                {% load component_tags %}
                {% include 'slotted_template.html' with context=None only %}
            """

        template_str: str = """
            {% load component_tags %}
            {% comp "broken_component" %}
                {% fill "header" %}Custom header {% endfill %}
                {% fill "main" %}Custom main{% endfill %}
                {% fill "footer" %}Custom footer{% endfill %}
            {% endcomp %}
        """

        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape("Encountered a SlotNode outside of a Component context."),
        ):
            Template(template_str).render(Context({}))


class TestComponentSlotDefault:
    def test_default_slot_is_fillable_by_implicit_fill_content(self):
        @register("test_comp")
        class ComponentWithDefaultSlot(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <main>{% slot "main" default %}Easy to override{% endslot %}</main>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test_comp' %}
              <p>This fills the 'main' slot.</p>
            {% endcomp %}
        """
        template = Template(template_str)

        expected = """
        <div>
          <main>
            <p>This fills the 'main' slot.</p>
          </main>
        </div>
        """
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, expected)

    def test_default_slot_is_fillable_by_explicit_fill_content(self):
        @register("test_comp")
        class ComponentWithDefaultSlot(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <main>{% slot "main" default %}Easy to override{% endslot %}</main>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test_comp' %}
              {% fill "main" %}<p>This fills the 'main' slot.</p>{% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        expected = """
            <div>
                <main>
                    <p>This fills the 'main' slot.</p>
                </main>
            </div>
        """
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, expected)

    def test_multiple_default_slots_with_same_name(self):
        @register("test_comp")
        class ComponentWithDefaultSlot(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <main>{% slot "main" default %}1{% endslot %}</main>
                    <div>{% slot "main" default %}2{% endslot %}</div>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test_comp' %}
              {% fill "main" %}<p>This fills the 'main' slot.</p>{% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        expected = """
            <div>
                <main><p>This fills the 'main' slot.</p></main>
                <div><p>This fills the 'main' slot.</p></div>
            </div>
        """
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, expected)

    def test_multiple_default_slots_with_different_names(self):
        @register("test_comp")
        class ComponentWithDefaultSlot(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <main>{% slot "main" default %}1{% endslot %}</main>
                    <div>{% slot "other" default %}2{% endslot %}</div>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test_comp' %}
              {% fill "main" %}<p>This fills the 'main' slot.</p>{% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)

        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape(
                "Only one component slot may be marked as 'default', found 'main' and 'other'",
            ),
        ):
            template.render(Context({}))

    def test_error_raised_when_default_and_required_slot_not_filled(self):
        @register("test_comp")
        class ComponentWithDefaultAndRequiredSlot(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <header>{% slot "header" %}Your Header Here{% endslot %}</header>
                    <main>{% slot "main" default required %}Easy to override{% endslot %}</main>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test_comp' %}
            {% endcomp %}
        """
        template = Template(template_str)

        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape("Slot 'main' is marked as 'required'"),
        ):
            template.render(Context())

    def test_fill_tag_can_occur_within_component_nested_in_implicit_fill(self):
        registry.register("slotted", _gen_slotted_component())

        @register("test_comp")
        class ComponentWithDefaultSlot(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <main>{% slot "main" default %}Easy to override{% endslot %}</main>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test_comp' %}
              {% comp "slotted" %}
                {% fill "header" %}This Is Allowed{% endfill %}
                {% fill "main" %}{% endfill %}
                {% fill "footer" %}{% endfill %}
              {% endcomp %}
            {% endcomp %}
        """
        template = Template(template_str)
        expected = """
            <div>
                <main>
                    <custom-template>
                        <header>This Is Allowed</header>
                        <main></main>
                        <footer></footer>
                    </custom-template>
                </main>
            </div>
        """
        rendered = template.render(Context({}))
        assertHTMLEqual(rendered, expected)

    def test_error_from_mixed_implicit_and_explicit_fill_content(self):
        @register("test_comp")
        class ComponentWithDefaultSlot(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <main>{% slot "main" default %}Easy to override{% endslot %}</main>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test_comp' %}
                {% fill "main" %}Main content{% endfill %}
                <p>And add this too!</p>
            {% endcomp %}
        """
        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape(
                "Illegal content passed to component 'test_comp'. Explicit 'fill' tags cannot occur alongside other text",
            ),
        ):
            Template(template_str).render(Context({}))

    def test_comments_permitted_inside_implicit_fill_content(self):
        @register("test_comp")
        class ComponentWithDefaultSlot(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <main>{% slot "main" default %}Easy to override{% endslot %}</main>
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test_comp' %}
              <p>Main Content</p>
              {% comment %}
              This won't show up in the rendered HTML
              {% endcomment %}
              {# Nor will this #}
            {% endcomp %}
        """
        rendered = Template(template_str).render(Context())
        assertHTMLEqual(
            rendered,
            """
            <div>
                <main><p>Main Content</p></main>
            </div>
            """,
        )

    def test_implicit_fill_when_no_slot_marked_default(self):
        registry.register("test_comp", _gen_slotted_component())
        template_str: str = """
            {% load component_tags %}
            {% comp 'test_comp' %}
              <p>Component with no 'default' slot still accepts the fill, it just won't render it</p>
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context())
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

    def test_implicit_fill_when_slot_marked_default_not_rendered(self):
        @register("test_comp")
        class ConditionalSlotted(Component):
            def get_context_data(self, **kwargs):
                return {"var": kwargs["var"]}

            template: str = """
                {% load component_tags %}
                <custom-template>
                    {% if var %}
                        <header>{% slot "header" default %}Default header{% endslot %}</header>
                    {% endif %}
                    <main>{% slot "main" %}Default main{% endslot %}</main>
                    <footer>{% slot "footer" %}Default footer{% endslot %}</footer>
                </custom-template>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test_comp' var=var %}
              123
            {% endcomp %}
        """
        template = Template(template_str)

        rendered_truthy = template.render(Context({"var": True}))
        assertHTMLEqual(
            rendered_truthy,
            """
            <custom-template>
                <header>123</header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

        rendered_falsy = template.render(Context({"var": False}))
        assertHTMLEqual(
            rendered_falsy,
            """
            <custom-template>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )


class TestPassthroughSlots:
    def test_if_for(self):
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

            def get_context_data(self, **kwargs):
                return {
                    "name": kwargs.get("name"),
                }

        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% if slot_names %}
                    {% for slot in slot_names %}
                        {% fill name=slot fallback="fallback" %}
                            OVERRIDEN_SLOT "{{ slot }}" - INDEX {{ forloop.counter0 }} - ORIGINAL "{{ fallback }}"
                        {% endfill %}
                    {% endfor %}
                {% endif %}

                {% if 1 > 2 %}
                    {% fill "footer" %}
                        FOOTER
                    {% endfill %}
                {% endif %}
            {% endcomp %}
        """
        template = Template(template_str)

        rendered = template.render(Context({"slot_names": ["header", "main"]}))
        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>
                    OVERRIDEN_SLOT "header" - INDEX 0 - ORIGINAL "Default header"
                </header>
                <main>
                    OVERRIDEN_SLOT "main" - INDEX 1 - ORIGINAL "Default main"
                </main>
                <footer>
                    Default footer
                </footer>
            </custom-template>
            """,
        )

    def test_with(self):
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

            def get_context_data(self, **kwargs):
                return {
                    "name": kwargs.get("name"),
                }

        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% with slot="header" %}
                    {% fill name=slot fallback="fallback" %}
                        OVERRIDEN_SLOT "{{ slot }}" - ORIGINAL "{{ fallback }}"
                    {% endfill %}
                {% endwith %}
            {% endcomp %}
        """
        template = Template(template_str)

        rendered = template.render(Context())
        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>
                    OVERRIDEN_SLOT "header" - ORIGINAL "Default header"
                </header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    def test_if_for_raises_on_content_outside_fill(self):
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

            def get_context_data(self, **kwargs):
                return {
                    "name": kwargs.get("name"),
                }

        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% if slot_names %}
                    {% for slot in slot_names %}
                        {{ forloop.counter0 }}
                        {% fill name=slot fallback="fallback" %}
                            OVERRIDEN_SLOT
                        {% endfill %}
                    {% endfor %}
                {% endif %}

                {% if 1 > 2 %}
                    {% fill "footer" %}
                        FOOTER
                    {% endfill %}
                {% endif %}
            {% endcomp %}
        """
        template = Template(template_str)

        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape("Illegal content passed to component 'test'"),
        ):
            template.render(Context({"slot_names": ["header", "main"]}))

    def test_slots_inside_loops(self):
        @register("test_comp")
        class OuterComp(Component):
            def get_context_data(self, **kwargs):
                return {
                    "slots": ["header", "main", "footer"],
                }

            template: str = """
                {% load component_tags %}
                {% for slot_name in slots %}
                    <div>
                        {% slot name=slot_name %}
                            {{ slot_name }}
                        {% endslot %}
                    </div>
                {% endfor %}
            """

        template_str: str = """
            {% load component_tags %}
            {% comp "test_comp" %}
                {% fill "header" %}
                    CUSTOM HEADER
                {% endfill %}
                {% fill "main" %}
                    CUSTOM MAIN
                {% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context())

        expected = """
            <div>CUSTOM HEADER</div>
            <div>CUSTOM MAIN</div>
            <div>footer</div>
        """
        assertHTMLEqual(rendered, expected)

    def test_passthrough_slots(self):
        registry.register("slotted", _gen_slotted_component())

        @register("test_comp")
        class OuterComp(Component):
            def get_context_data(self, **kwargs):
                return {
                    "slots": self.slots,
                }

            template: str = """
                {% load component_tags %}
                <div>
                    {% comp "slotted" %}
                        {% for slot_name in slots %}
                            {% fill name=slot_name %}
                                {% slot name=slot_name %}{% endslot %}
                            {% endfill %}
                        {% endfor %}
                    {% endcomp %}
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp "test_comp" %}
                {% fill "header" %}
                    CUSTOM HEADER
                {% endfill %}
                {% fill "main" %}
                    CUSTOM MAIN
                {% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context())

        expected = """
            <div>
                <custom-template>
                    <header>CUSTOM HEADER</header>
                    <main>CUSTOM MAIN</main>
                    <footer>Default footer</footer>
                </custom-template>
            </div>
        """
        assertHTMLEqual(rendered, expected)

    # NOTE: Ideally we'd (optionally) raise an error / warning here, but it's not possible
    # with current implementation. So this tests serves as a documentation of the current behavior.
    def test_passthrough_slots_unknown_fills_ignored(self):
        registry.register("slotted", _gen_slotted_component())

        @register("test_comp")
        class OuterComp(Component):
            def get_context_data(self, **kwargs):
                return {
                    "slots": self.slots,
                }

            template: str = """
                {% load component_tags %}
                <div>
                    {% comp "slotted" %}
                        {% for slot_name in slots %}
                            {% fill name=slot_name %}
                                {% slot name=slot_name %}{% endslot %}
                            {% endfill %}
                        {% endfor %}
                    {% endcomp %}
                </div>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp "test_comp" %}
                {% fill "header1" %}
                    CUSTOM HEADER
                {% endfill %}
                {% fill "main" %}
                    CUSTOM MAIN
                {% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context())

        expected = """
            <div>
                <custom-template>
                    <header>Default header</header>
                    <main>CUSTOM MAIN</main>
                    <footer>Default footer</footer>
                </custom-template>
            </div>
        """
        assertHTMLEqual(rendered, expected)


# See https://github.com/django-components/django-components/issues/698
class TestNestedSlots:
    def _gen_nested_slots_component(self):
        class NestedSlots(Component):
            template: str = """
                {% load component_tags %}
                {% slot 'wrapper' %}
                    <div>
                        Wrapper Default
                        {% slot 'parent1' %}
                            <div>
                                Parent1 Default
                                {% slot 'child1' %}
                                    <div>
                                        Child 1 Default
                                    </div>
                                {% endslot %}
                            </div>
                        {% endslot %}
                        {% slot 'parent2' %}
                            <div>
                                Parent2 Default
                            </div>
                        {% endslot %}
                    </div>
                {% endslot %}
            """

        return NestedSlots

    def test_empty(self):
        registry.register("example", self._gen_nested_slots_component())
        template_str: str = """
            {% load component_tags %}
            {% comp 'example' %}
            {% endcomp %}
        """

        rendered = Template(template_str).render(Context())
        expected = """
            <div>
                Wrapper Default
                <div>
                    Parent1 Default
                    <div>
                        Child 1 Default
                    </div>
                </div>
                <div>
                    Parent2 Default
                </div>
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_override_outer(self):
        registry.register("example", self._gen_nested_slots_component())
        template_str: str = """
            {% load component_tags %}
            {% comp 'example' %}
                {% fill 'wrapper' %}
                    <div>
                        Entire Wrapper Replaced
                    </div>
                {% endfill %}
            {% endcomp %}
        """

        rendered = Template(template_str).render(Context())
        expected = """
            <div>
                Entire Wrapper Replaced
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_override_middle(self):
        registry.register("example", self._gen_nested_slots_component())
        template_str: str = """
            {% load component_tags %}
            {% comp 'example' %}
                {% fill 'parent1' %}
                    <div>
                        Parent1 Replaced
                    </div>
                {% endfill %}
            {% endcomp %}
        """

        rendered = Template(template_str).render(Context())
        expected = """
            <div>
                Wrapper Default
                <div>
                    Parent1 Replaced
                </div>
                <div>
                    Parent2 Default
                </div>
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_override_inner(self):
        registry.register("example", self._gen_nested_slots_component())
        template_str: str = """
            {% load component_tags %}
            {% comp 'example' %}
                {% fill 'child1' %}
                    <div>
                        Child1 Replaced
                    </div>
                {% endfill %}
            {% endcomp %}
        """

        rendered = Template(template_str).render(Context())
        expected = """
            <div>
                Wrapper Default
                <div>
                    Parent1 Default
                    <div>
                        Child1 Replaced
                    </div>
                </div>
                <div>
                    Parent2 Default
                </div>
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_override_all(self):
        registry.register("example", self._gen_nested_slots_component())
        template_str: str = """
            {% load component_tags %}
            {% comp 'example' %}
                {% fill 'child1' %}
                    <div>
                        Child1 Replaced
                    </div>
                {% endfill %}
                {% fill 'parent1' %}
                    <div>
                        Parent1 Replaced
                    </div>
                {% endfill %}
                {% fill 'wrapper' %}
                    <div>
                        Entire Wrapper Replaced
                    </div>
                {% endfill %}
            {% endcomp %}
        """

        rendered = Template(template_str).render(Context())
        expected = """
            <div>
                Entire Wrapper Replaced
            </div>
        """
        assertHTMLEqual(rendered, expected)


class TestSlottedTemplateRegression:
    def test_slotted_template_that_uses_missing_variable(self):
        @register("test")
        class SlottedComponentWithMissingVariable(Component):
            template: str = """
                {% load component_tags %}
                <custom-template>
                    {{ missing_context_variable }}
                    <header>{% slot "header" %}Default header{% endslot %}</header>
                    <main>{% slot "main" %}Default main{% endslot %}</main>
                    <footer>{% slot "footer" %}Default footer{% endslot %}</footer>
                </custom-template>
            """

        template_str: str = """
            {% load component_tags %}
            {% comp 'test' %}{% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

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


class TestSlotFallback:
    def test_basic(self):
        registry.register("test", _gen_slotted_component())
        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "header" fallback="header" %}Before: {{ header }}{% endfill %}
                {% fill "main" fallback="main" %}{{ main }}{% endfill %}
                {% fill "footer" fallback="footer" %}{{ footer }}, after{% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Before: Default header</header>
                <main>Default main</main>
                <footer>Default footer, after</footer>
            </custom-template>
            """,
        )

    def test_multiple_calls(self):
        registry.register("test", _gen_slotted_component())
        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "header" fallback="header" %}
                    First: {{ header }};
                    Second: {{ header }}
                {% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>First: Default header; Second: Default header</header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
        """,
        )

    def test_under_if_and_forloop(self):
        registry.register("test", _gen_slotted_component())
        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "header" fallback="header" %}
                    {% for i in range %}
                        {% if forloop.first %}
                            First {{ header }}
                        {% else %}
                            Later {{ header }}
                        {% endif %}
                    {% endfor %}
                {% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({"range": range(3)}))

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>First Default header Later Default header Later Default header</header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    def test_nested_fills(self):
        registry.register("test", _gen_slotted_component())
        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "header" fallback="header1" %}
                    header1_in_header1: {{ header1 }}
                    {% comp "test" %}
                        {% fill "header" fallback="header2" %}
                            header1_in_header2: {{ header1 }}
                            header2_in_header2: {{ header2 }}
                        {% endfill %}
                        {% fill "footer" fallback="footer2" %}
                            header1_in_footer2: {{ header1 }}
                            footer2_in_footer2: {{ footer2 }}
                        {% endfill %}
                    {% endcomp %}
                {% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>
                    header1_in_header1: Default header
                    <custom-template>
                        <header>
                            header1_in_header2: Default header
                            header2_in_header2: Default header
                        </header>
                        <main>Default main</main>
                        <footer>
                            header1_in_footer2: Default header
                            footer2_in_footer2: Default footer
                        </footer>
                    </custom-template>
                </header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )


class TestScopedSlot:
    def test_slot_data(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" abc=abc var123=var123 %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "abc": "def",
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "my_slot" data="slot_data_in_fill" %}
                    {{ slot_data_in_fill.abc }}
                    {{ slot_data_in_fill.var123 }}
                {% endfill %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context())
        expected = """
            <div>
                def
                456
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_data_with_flags(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" default abc=abc var123=var123 required %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "abc": "def",
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "my_slot" data="slot_data_in_fill" %}
                    {{ slot_data_in_fill.abc }}
                    {{ slot_data_in_fill.var123 }}
                {% endfill %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context())
        expected = """
            <div>
                def
                456
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_data_with_slot_fallback(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" abc=abc var123=var123 %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "abc": "def",
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "my_slot" data="slot_data_in_fill" fallback="fallback" %}
                    {{ fallback }}
                    {{ slot_data_in_fill.abc }}
                    {{ slot_data_in_fill.var123 }}
                {% endfill %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context())
        expected = """
            <div>
                Default text
                def
                456
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_data_with_variable(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot slot_name abc=abc var123=var123 default required %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "slot_name": "my_slot",
                    "abc": "def",
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "my_slot" data="slot_data_in_fill" %}
                    {{ slot_data_in_fill.abc }}
                    {{ slot_data_in_fill.var123 }}
                {% endfill %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context())
        expected = """
            <div>
                def
                456
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_data_with_named_slot(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" default required abc="def" var123=var123 %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "my_slot" data="slot_data_in_fill" %}
                    {{ slot_data_in_fill.abc }}
                    {{ slot_data_in_fill.var123 }}
                {% endfill %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context())
        expected = """
            <div>
                def
                456
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_data_and_fallback_on_default_slot(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    <b>{% slot "slot_a" abc=abc var123=var123 %} Default text A {% endslot %}</b>
                    <b>{% slot "slot_b" abc=abc var123=var123 default %} Default text B {% endslot %}</b>
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "abc": "xyz",
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill name="default" data="slot_data_in_fill" fallback="slot_var" %}
                    {{ slot_data_in_fill.abc }}
                    {{ slot_var }}
                    {{ slot_data_in_fill.var123 }}
                {% endfill %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context())
        expected = """
            <div>
                <b>Default text A</b>
                <b>xyz Default text B 456</b>
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_data_raises_on_slot_data_and_slot_fallback_same_var(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" abc=abc var123=var123 %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "abc": "def",
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "my_slot" data="slot_var" fallback="slot_var" %}
                    {{ slot_var }}
                {% endfill %}
            {% endcomp %}
        """
        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape(
                "Fill 'my_slot' received the same string for slot fallback (fallback=...) and slot data (data=...)",
            ),
        ):
            Template(template).render(Context())

    def test_slot_data_fill_without_data(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" abc=abc var123=var123 %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "abc": "def",
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "my_slot" %}
                    overriden
                {% endfill %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context())
        expected = "<div> overriden </div>"
        assertHTMLEqual(rendered, expected)

    def test_slot_data_fill_without_slot_data(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" %}Default text{% endslot %}
                </div>
            """

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "my_slot" data="data" %}
                    {{ data|safe }}
                {% endfill %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context())
        expected = "<div> {} </div>"
        assertHTMLEqual(rendered, expected)

    def test_slot_data_no_fill(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" abc=abc var123=var123 %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "abc": "def",
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context())
        expected = "<div> Default text </div>"
        assertHTMLEqual(rendered, expected)

    def test_slot_data_fill_with_variables(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" abc=abc var123=var123 %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "abc": "def",
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill fill_name data=data_var %}
                    {{ slot_data_in_fill.abc }}
                    {{ slot_data_in_fill.var123 }}
                {% endfill %}
            {% endcomp %}
        """
        rendered = Template(template).render(
            Context(
                {
                    "fill_name": "my_slot",
                    "data_var": "slot_data_in_fill",
                },
            ),
        )

        expected = """
            <div>
                def
                456
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_slot_data_fill_with_named_fill(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" abc=abc var123=var123 %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "abc": "def",
                    "var123": 456,
                }

        template: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "my_slot" data="slot_data_in_fill" %}
                    {{ slot_data_in_fill.abc }}
                    {{ slot_data_in_fill.var123 }}
                {% endfill %}
            {% endcomp %}
        """
        rendered = Template(template).render(Context())

        expected = """
            <div>
                def
                456
            </div>
        """
        assertHTMLEqual(rendered, expected)

    def test_nested_fills(self):
        @register("test")
        class TestComponent(Component):
            template: str = """
                {% load component_tags %}
                <div>
                    {% slot "my_slot" abc=abc input=input %}Default text{% endslot %}
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "abc": "def",
                    "input": kwargs["input"],
                }

        template_str: str = """
            {% load component_tags %}
            {% comp "test" input=1 %}
                {% fill "my_slot" data="data1" %}
                    data1_in_slot1: {{ data1|safe }}
                    {% comp "test" input=2 %}
                        {% fill "my_slot" data="data2" %}
                            data1_in_slot2: {{ data1|safe }}
                            data2_in_slot2: {{ data2|safe }}
                        {% endfill %}
                    {% endcomp %}
                {% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        rendered = template.render(Context({}))

        assertHTMLEqual(
            rendered,
            """
            <div>
                data1_in_slot1: {'abc': 'def', 'input': 1}
                <div>
                    data1_in_slot2: {'abc': 'def', 'input': 1}
                    data2_in_slot2: {'abc': 'def', 'input': 2}
                </div>
            </div>
            """,
        )


class TestDuplicateSlot:
    def _gen_duplicate_slot_component(self):
        class DuplicateSlotComponent(Component):
            template: str = """
                {% load component_tags %}
                <header>{% slot "header" %}Default header{% endslot %}</header>
                {# Slot name 'header' used twice. #}
                <main>{% slot "header" %}Default main header{% endslot %}</main>
                <footer>{% slot "footer" %}Default footer{% endslot %}</footer>
            """

            def get_context_data(self, **kwargs):
                return {
                    "name": kwargs.get("name"),
                }

        return DuplicateSlotComponent

    def _gen_duplicate_slot_nested_component(self):
        class DuplicateSlotNestedComponent(Component):
            template: str = """
                {% load component_tags %}
                {% slot "header" %}START{% endslot %}
                <div class="dashboard-component">
                {% comp "calendar" date="2020-06-06" %}
                    {% fill "header" %}  {# fills and slots with same name relate to diff. things. #}
                        {% slot "header" %}NESTED{% endslot %}
                    {% endfill %}
                    {% fill "body" %}Here are your to-do items for today:{% endfill %}
                {% endcomp %}
                <ol>
                    {% for item in items %}
                        <li>{{ item }}</li>
                        {% slot "header" %}LOOP {{ item }} {% endslot %}
                    {% endfor %}
                </ol>
                </div>
            """

            def get_context_data(self, **kwargs):
                return {
                    "items": kwargs["items"],
                }

        return DuplicateSlotNestedComponent

    def _gen_calendar_component(self):
        class CalendarComponent(Component):
            """Nested in ComponentWithNestedComponent."""

            template: str = """
                {% load component_tags %}
                <div class="calendar-component">
                <h1>
                    {% slot "header" %}Today's date is <span>{{ date }}</span>{% endslot %}
                </h1>
                <main>
                    {% slot "body" %}
                        You have no events today.
                    {% endslot %}
                </main>
                </div>
            """

        return CalendarComponent

    def test_duplicate_slots(self):
        registry.register(name="duplicate_slot", component=self._gen_duplicate_slot_component())
        registry.register(name="calendar", component=self._gen_calendar_component())

        template_str: str = """
            {% load component_tags %}
            {% comp "duplicate_slot" name=comp_input %}
                {% fill "header" %}
                    Name: {{ name }}
                {% endfill %}
                {% fill "footer" %}
                    Hello
                {% endfill %}
            {% endcomp %}
        """
        self.template = Template(template_str)

        rendered = self.template.render(Context({"name": "Jannete", "comp_input": None}))
        assertHTMLEqual(
            rendered,
            """
            <header>Name: Jannete</header>
            <main>Name: Jannete</main>
            <footer>Hello</footer>
            """,
        )

    def test_duplicate_slots_fallback(self):
        registry.register(name="duplicate_slot", component=self._gen_duplicate_slot_component())
        registry.register(name="calendar", component=self._gen_calendar_component())

        template_str: str = """
            {% load component_tags %}
            {% comp "duplicate_slot" %}
            {% endcomp %}
        """
        self.template = Template(template_str)
        rendered = self.template.render(Context({}))

        # NOTE: Slots should have different fallbacks even though they use the same name
        assertHTMLEqual(
            rendered,
            """
            <header>Default header</header>
            <main>Default main header</main>
            <footer>Default footer</footer>
            """,
        )

    def test_duplicate_slots_nested(self):
        registry.register(name="duplicate_slot_nested", component=self._gen_duplicate_slot_nested_component())
        registry.register(name="calendar", component=self._gen_calendar_component())

        template_str: str = """
            {% load component_tags %}
            {% comp "duplicate_slot_nested" items=items %}
                {% fill "header" %}
                    OVERRIDDEN!
                {% endfill %}
            {% endcomp %}
        """
        self.template = Template(template_str)
        rendered = self.template.render(Context({"items": [1, 2, 3]}))

        # NOTE: Slots should have different fallbacks even though they use the same name
        assertHTMLEqual(
            rendered,
            """
            OVERRIDDEN!
            <div class="dashboard-component">
                <div class="calendar-component">
                    <h1>
                        OVERRIDDEN!
                    </h1>
                    <main>
                        Here are your to-do items for today:
                    </main>
                </div>

                <ol>
                    <li>1</li>
                    OVERRIDDEN!
                    <li>2</li>
                    OVERRIDDEN!
                    <li>3</li>
                    OVERRIDDEN!
                </ol>
            </div>
            """,
        )

    def test_duplicate_slots_nested_fallback(self):
        registry.register(name="duplicate_slot_nested", component=self._gen_duplicate_slot_nested_component())
        registry.register(name="calendar", component=self._gen_calendar_component())

        template_str: str = """
            {% load component_tags %}
            {% comp "duplicate_slot_nested" items=items %}
            {% endcomp %}
        """
        self.template = Template(template_str)
        rendered = self.template.render(Context({"items": [1, 2, 3]}))

        # NOTE: Slots should have different fallbacks even though they use the same name
        assertHTMLEqual(
            rendered,
            """
            START
            <div class="dashboard-component">
                <div class="calendar-component">
                    <h1>
                        NESTED
                    </h1>
                    <main>
                        Here are your to-do items for today:
                    </main>
                </div>

                <ol>
                    <li>1</li>
                    LOOP 1
                    <li>2</li>
                    LOOP 2
                    <li>3</li>
                    LOOP 3
                </ol>
            </div>
            """,
        )


class TestSlotFillTemplateSyntaxError:
    def test_fill_with_no_parent_is_error(self):
        template_str: str = """
            {% load component_tags %}
            {% fill "header" %}contents{% endfill %}
        """
        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape(
                "FillNode.render() (AKA {% fill ... %} block) cannot be rendered outside of a Component context",
            ),
        ):
            Template(template_str).render(Context({}))

    def test_non_unique_fill_names_is_error(self):
        registry.register("test", _gen_slotted_component())

        template_str: str = """
            {% load component_tags %}
            {% comp "test" %}
                {% fill "header" %}Custom header {% endfill %}
                {% fill "header" %}Other header{% endfill %}
            {% endcomp %}
        """
        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape(
                "Multiple fill tags cannot target the same slot name in component 'test': "
                "Detected duplicate fill tag name 'header'",
            ),
        ):
            Template(template_str).render(Context({}))

    def test_non_unique_fill_names_is_error_via_vars(self):
        registry.register("test", _gen_slotted_component())

        template_str: str = """
            {% load component_tags %}
            {% with var1="header" var2="header" %}
                {% comp "test" %}
                    {% fill var1 %}Custom header {% endfill %}
                    {% fill var2 %}Other header{% endfill %}
                {% endcomp %}
            {% endwith %}
        """
        with pytest.raises(
            TemplateSyntaxError,
            match=re.escape(
                "Multiple fill tags cannot target the same slot name in component 'test': "
                "Detected duplicate fill tag name 'header'",
            ),
        ):
            Template(template_str).render(Context({}))


class TestSlotBehavior:
    # NOTE: This is standalone function instead of setUp, so we can configure
    # Django settings per test with `@override_settings`
    def make_template(self) -> Template:
        class SlottedComponent(Component):
            template: str = """
                {% load component_tags %}
                <custom-template>
                    <header>{% slot "header" %}Default header{% endslot %}</header>
                    <main>{% slot "main" %}Default main{% endslot %}</main>
                    <footer>{% slot "footer" %}Default footer{% endslot %}</footer>
                </custom-template>
            """

            def get_context_data(self, **kwargs):
                return {
                    "name": kwargs.get("name"),
                }

        registry.register("test", SlottedComponent)

        template_str: str = """
            {% load component_tags %}
            {% comp "test" name='Igor' %}
                {% fill "header" %}
                    Name: {{ name }}
                {% endfill %}
                {% fill "main" %}
                    Day: {{ day }}
                {% endfill %}
                {% fill "footer" %}
                    {% comp "test" name='Joe2' %}
                        {% fill "header" %}
                            Name2: {{ name }}
                        {% endfill %}
                        {% fill "main" %}
                            Day2: {{ day }}
                        {% endfill %}
                    {% endcomp %}
                {% endfill %}
            {% endcomp %}
        """
        return Template(template_str)

    def test_slot_context__isolated(self):
        template = self.make_template()
        # {{ name }} should be "Jannete" everywhere
        rendered = template.render(Context({"day": "Monday", "name": "Jannete"}))
        assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Name: Jannete</header>
                <main>Day: Monday</main>
                <footer>
                    <custom-template>
                        <header>Name2: Jannete</header>
                        <main>Day2: Monday</main>
                        <footer>Default footer</footer>
                    </custom-template>
                </footer>
            </custom-template>
            """,
        )

        # {{ name }} should be empty everywhere
        rendered2 = template.render(Context({"day": "Monday"}))
        assertHTMLEqual(
            rendered2,
            """
            <custom-template>
                <header>Name: </header>
                <main>Day: Monday</main>
                <footer>
                    <custom-template>
                        <header>Name2: </header>
                        <main>Day2: Monday</main>
                        <footer>Default footer</footer>
                    </custom-template>
                </footer>
            </custom-template>
            """,
        )


class TestSlotInput:
    def test_slots_accessible_when_python_render(self):
        seen_slots: dict = {}

        @register("test")
        class SlottedComponent(Component):
            template: str = """
                {% load component_tags %}
                <header>{% slot "header" %}Default header{% endslot %}</header>
                <main>{% slot "main" %}Default main header{% endslot %}</main>
                <footer>{% slot "footer" %}Default footer{% endslot %}</footer>
            """

            def get_context_data(self, **kwargs):
                nonlocal seen_slots
                seen_slots = self.slots

        assert seen_slots == {}

        template_str: str = """
            {% load component_tags %}
            {% comp "test" input=1 %}
                {% fill "header" data="data1" %}
                    data1_in_slot1: {{ data1|safe }}
                {% endfill %}
                {% fill "main" %}{% endfill %}
            {% endcomp %}
        """
        template = Template(template_str)
        template.render(Context())

        assert list(seen_slots.keys()) == ["header", "main"]
        assert callable(seen_slots["header"])
        assert callable(seen_slots["main"])
        assert "footer" not in seen_slots

    def test_slots_normalized_as_slot_instances(self):
        seen_slots: dict[str, Slot] = {}

        @register("test")
        class SlottedComponent(Component):
            template: str = """
                {% load component_tags %}
                <header>{% slot "header" %}Default header{% endslot %}</header>
                <main>{% slot "main" %}Default main header{% endslot %}</main>
                <footer>{% slot "footer" %}Default footer{% endslot %}</footer>
            """

            def get_context_data(self, **kwargs):
                nonlocal seen_slots
                seen_slots = self.slots

        assert seen_slots == {}

        header_slot: Slot = Slot(lambda _ctx: "HEADER_SLOT")
        main_slot_str = "MAIN_SLOT"
        footer_slot_fn = lambda _ctx: "FOOTER_SLOT"  # noqa: E731

        SlottedComponent.render(
            slots={
                "header": header_slot,
                "main": main_slot_str,
                "footer": footer_slot_fn,
            },
        )

        assert isinstance(seen_slots["header"], Slot)
        assert seen_slots["header"](Context(), None, None) == "HEADER_SLOT"  # type: ignore[arg-type]

        assert isinstance(seen_slots["main"], Slot)
        assert seen_slots["main"](Context(), None, None) == "MAIN_SLOT"  # type: ignore[arg-type]

        assert isinstance(seen_slots["footer"], Slot)
        assert seen_slots["footer"](Context(), None, None) == "FOOTER_SLOT"  # type: ignore[arg-type]
