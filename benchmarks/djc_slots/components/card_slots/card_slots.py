from django_components import Component, register


@register("card_slots")
class CardSlots(Component):
    template_file = "card_slots/card_slots.html"

    def get_template_data(self, args, kwargs, slots, context):
        return kwargs
