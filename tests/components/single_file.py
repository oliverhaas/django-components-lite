from django_components_lite import Component, register


@register("single_file_component")
class SingleFileComponent(Component):
    template: str = "<div>{{ variable }}</div>"

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
