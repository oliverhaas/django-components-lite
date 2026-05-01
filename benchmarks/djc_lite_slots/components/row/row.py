from django_components_lite import Component, register


@register("row")
class Row(Component):
    template_name = "row/row.html"

    def get_context_data(self, index):
        return {"index": index}
