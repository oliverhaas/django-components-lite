from django_components_lite import Component, register


@register("custom_app_lvl_comp")
class AppLvlCompComponent(Component):
    template_file = "app_lvl_comp.html"

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
