
from django_components_lite import Component, register


# Used for testing the staticfiles finder in `test_staticfiles.py`
@register("staticfiles_component")
class RelativeFileWithPathObjComponent(Component):
    template_file = "staticfiles.html"

    class Media:
        js = "staticfiles.js"
        css = "staticfiles.css"

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
