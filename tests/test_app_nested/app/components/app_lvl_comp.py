from django_components_lite import Component, register


# Used for testing the template_loader
@register("nested_app_lvl_comp")
class AppLvlCompComponent(Component):
    template = """
        {{ variable }}
    """

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
