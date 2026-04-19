from django_components import Component, register


@register("card")
class Card(Component):
    template_file = "card/card.html"

    def get_template_data(self, args, kwargs, slots, context):
        return kwargs
