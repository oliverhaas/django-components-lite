from django_components_lite import Component, register


@register("relative_file_component")
class RelativeFileComponent(Component):
    template_file = "relative_file.html"

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
