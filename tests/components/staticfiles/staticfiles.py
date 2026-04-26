from django_components_lite import Component, register


# Used by the staticfiles finder tests in `test_finders.py`.
@register("staticfiles_component")
class StaticfilesComponent(Component):
    template_file = "staticfiles.html"

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
