from django_components_lite import Component, register


@register("multi_file_component")
class MultFileComponent(Component):
    template_file = "multi_file/multi_file.html"

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
