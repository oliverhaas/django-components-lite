from django_components_lite import Component, register


@register("alert")
class Alert(Component):
    template_name = "alert/alert.html"

    def get_context_data(self, level, message, dismissible):
        return {"level": level, "message": message, "dismissible": dismissible}
