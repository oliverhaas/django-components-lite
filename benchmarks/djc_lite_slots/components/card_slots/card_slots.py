from django_components_lite import Component, register


@register("card_slots")
class CardSlots(Component):
    template_name = "card_slots/card_slots.html"

    def get_context_data(self, variant):
        return {"variant": variant}
