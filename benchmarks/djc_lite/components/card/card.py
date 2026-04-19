from django_components_lite import Component, register


@register("card")
class Card(Component):
    template_name = "card/card.html"

    def get_context_data(self, title, body, variant, footer):
        return {"title": title, "body": body, "variant": variant, "footer": footer}
