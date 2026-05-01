from django_components import Component, register


@register("row")
class Row(Component):
    template_file = "row/row.html"

    def get_template_data(self, args, kwargs, slots, context):
        return kwargs
