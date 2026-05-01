from django_components_lite import Component, register


@register("panel")
class Panel(Component):
    template_name = "panel/panel.html"

    def get_context_data(self, label):
        return {"label": label}
