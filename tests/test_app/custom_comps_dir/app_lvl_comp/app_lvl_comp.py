from django_components_lite import Component, register


# Used for testing the template_loader
@register("custom_app_lvl_comp")
class AppLvlCompComponent(Component):
    template_file = "app_lvl_comp.html"

    class Media:
        js = "app_lvl_comp.js"
        css = "app_lvl_comp.css"

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
