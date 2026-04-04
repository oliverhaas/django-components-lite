import pytest

from django_components_lite import AlreadyRegisteredError, registry
from django_components_lite.autodiscovery import autodiscover


class TestAutodiscover:
    def test_autodiscover(self):
        all_components = registry.all().copy()
        assert "single_file_component" not in all_components
        assert "multi_file_component" not in all_components
        assert "relative_file_component" not in all_components
        assert "relative_file_pathobj_component" not in all_components

        try:
            modules = autodiscover(map_module=lambda p: "tests." + p if p.startswith("components") else p)
        except AlreadyRegisteredError:
            pytest.fail("Autodiscover should not raise AlreadyRegisteredError exception")

        assert "tests.components" in modules
        assert "tests.components.single_file" in modules
        assert "tests.components.staticfiles.staticfiles" in modules
        assert "tests.components.multi_file.multi_file" in modules
        assert "tests.components.relative_file_pathobj.relative_file_pathobj" in modules
        assert "tests.components.relative_file.relative_file" in modules
        assert "tests.test_app.components.app_lvl_comp.app_lvl_comp" in modules

        all_components = registry.all().copy()
        assert "single_file_component" in all_components
        assert "multi_file_component" in all_components
        assert "relative_file_component" in all_components
        assert "relative_file_pathobj_component" in all_components
