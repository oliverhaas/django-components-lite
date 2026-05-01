from django_components import Component, register


@register("panel")
class Panel(Component):
    template_file = "panel/panel.html"

    def get_template_data(self, args, kwargs, slots, context):
        return kwargs
