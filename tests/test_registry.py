import pytest
from django.template import Library

from django_components_lite import (
    AlreadyRegisteredError,
    Component,
    ComponentRegistry,
    NotRegisteredError,
    all_registries,
    register,
    registry,
)


class MockComponent(Component):
    pass


class MockComponent2(Component):
    pass


class MockComponentView(Component):
    def get(self, request, *args, **kwargs):
        pass


class TestComponentRegistry:
    def test_register_class_decorator(self):
        assert not registry.has("decorated_component")

        @register("decorated_component")
        class TestComponent(Component):
            pass

        assert registry.has("decorated_component")
        assert registry.get("decorated_component") == TestComponent

        # Cleanup
        registry.unregister("decorated_component")
        assert not registry.has("decorated_component")

    def test_register_class_decorator_custom_registry(self):
        my_lib = Library()
        my_reg = ComponentRegistry(library=my_lib)

        default_registry_comps_before = len(registry.all())

        assert my_reg.all() == {}

        @register("decorated_component", registry=my_reg)
        class TestComponent(Component):
            pass

        assert my_reg.all() == {"decorated_component": TestComponent}

        # Check that the component was NOT added to the default registry
        default_registry_comps_after = len(registry.all())
        assert default_registry_comps_before == default_registry_comps_after

    def test_simple_register(self):
        custom_registry = ComponentRegistry()
        custom_registry.register(name="testcomponent", component=MockComponent)
        assert custom_registry.all() == {"testcomponent": MockComponent}

    def test_register_two_components(self):
        custom_registry = ComponentRegistry()
        custom_registry.register(name="testcomponent", component=MockComponent)
        custom_registry.register(name="testcomponent2", component=MockComponent)
        assert custom_registry.all() == {
            "testcomponent": MockComponent,
            "testcomponent2": MockComponent,
        }

    def test_unregisters_only_unused_tags(self):
        custom_library = Library()
        custom_registry = ComponentRegistry(library=custom_library)
        assert custom_registry._tags == {}

        # NOTE: We preserve the default component tags
        assert "comp" not in custom_registry.library.tags

        # Register two components that use the same tag
        custom_registry.register(name="testcomponent", component=MockComponent)
        custom_registry.register(name="testcomponent2", component=MockComponent)

        assert custom_registry._tags == {
            "comp": {"testcomponent", "testcomponent2"},
        }

        assert "comp" in custom_registry.library.tags

        # Unregister only one of the components. The tags should remain
        custom_registry.unregister(name="testcomponent")

        assert custom_registry._tags == {
            "comp": {"testcomponent2"},
        }

        assert "comp" in custom_registry.library.tags

        # Unregister the second components. The tags should be removed
        custom_registry.unregister(name="testcomponent2")

        assert custom_registry._tags == {}
        assert "comp" not in custom_registry.library.tags

    def test_prevent_registering_different_components_with_the_same_name(self):
        custom_registry = ComponentRegistry()
        custom_registry.register(name="testcomponent", component=MockComponent)
        with pytest.raises(AlreadyRegisteredError):
            custom_registry.register(name="testcomponent", component=MockComponent2)

    def test_allow_duplicated_registration_of_the_same_component(self):
        custom_registry = ComponentRegistry()
        try:
            custom_registry.register(name="testcomponent", component=MockComponentView)
            custom_registry.register(name="testcomponent", component=MockComponentView)
        except AlreadyRegisteredError:
            pytest.fail("Should not raise AlreadyRegisteredError")

    def test_simple_unregister(self):
        custom_registry = ComponentRegistry()
        custom_registry.register(name="testcomponent", component=MockComponent)
        custom_registry.unregister(name="testcomponent")
        assert custom_registry.all() == {}

    def test_raises_on_failed_unregister(self):
        custom_registry = ComponentRegistry()
        with pytest.raises(NotRegisteredError):
            custom_registry.unregister(name="testcomponent")


class TestRegistryHelpers:
    def test_all_registries(self):
        # Default registry
        assert len(all_registries()) == 1

        reg = ComponentRegistry()

        assert len(all_registries()) == 2

        del reg

        assert len(all_registries()) == 1
