from django_components_lite import Component, register


@register("button")
class Button(Component):
    template_name = "button/button.html"

    def get_context_data(self, label, variant, size, disabled):
        return {"label": label, "variant": variant, "size": size, "disabled": disabled}
