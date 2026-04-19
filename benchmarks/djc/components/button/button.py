from django_components import Component, register


@register("button")
class Button(Component):
    template_file = "button/button.html"

    def get_template_data(self, args, kwargs, slots, context):
        return kwargs
