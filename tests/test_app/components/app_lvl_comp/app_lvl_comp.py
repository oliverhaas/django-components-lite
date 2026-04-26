from django_components_lite import Component, register


@register("app_lvl_comp")
class AppLvlCompComponent(Component):
    template_file = "app_lvl_comp.html"
    js_file = "app_lvl_comp.js"
    css_file = "app_lvl_comp.css"

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
