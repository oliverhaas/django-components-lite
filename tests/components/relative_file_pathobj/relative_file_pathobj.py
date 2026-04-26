from django_components_lite import Component, register


@register("relative_file_pathobj_component")
class RelativeFilePathObjComponent(Component):
    template_file = "relative_file_pathobj.html"

    def get_context_data(self, **kwargs):
        return {"variable": kwargs["variable"]}
