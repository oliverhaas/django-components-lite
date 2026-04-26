"""Template loader that loads templates from each Django app's components directory."""

from pathlib import Path

from django.template.loaders.filesystem import Loader as FilesystemLoader

from django_components_lite.util.loader import get_component_dirs


class DjcLoader(FilesystemLoader):
    def get_dirs(self, include_apps: bool = True) -> list[Path]:
        """Return component directories from `COMPONENTS.dirs` and per-app `components/` dirs."""
        return get_component_dirs(include_apps)


# Django convention names template loaders `Loader`; we use `DjcLoader` internally so
# different loaders are distinguishable, and re-export it as `Loader` for public use.
Loader = DjcLoader
