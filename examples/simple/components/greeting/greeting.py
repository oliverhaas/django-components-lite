from django_components_lite import Component, register


@register("greeting")
class Greeting(Component):
    template_name = "greeting/greeting.html"

    def get_context_data(self, name="World"):
        return {"name": name}
