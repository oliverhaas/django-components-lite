from django_components import Component, register


@register("alert")
class Alert(Component):
    template_file = "alert/alert.html"

    def get_template_data(self, args, kwargs, slots, context):
        return kwargs
