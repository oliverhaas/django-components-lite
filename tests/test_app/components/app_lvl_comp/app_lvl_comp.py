from django_components_lite import Component, register


@register("app_lvl_comp")
class AppLvlCompComponent(Component):
    template_name = "app_lvl_comp.html"

    class Media:
        css = ["app_lvl_comp.css"]
        js = ["app_lvl_comp.js"]

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
