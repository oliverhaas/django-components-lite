from collections.abc import Generator
from contextlib import contextmanager


def set_component_error_message(err: Exception, component_path: list[str]) -> None:
    """Prepend the component path to the exception's message."""
    if not hasattr(err, "_components"):
        err._components = []  # type: ignore[attr-defined]

    components = getattr(err, "_components", [])
    components = err._components = [*component_path, *components]  # type: ignore[attr-defined]

    comp_path = " > ".join(components)
    prefix = f"An error occured while rendering components {comp_path}:\n"

    # See https://stackoverflow.com/a/75549200/9788634 for accessing exception messages.
    if len(err.args) and err.args[0] is not None:
        orig_msg = str(err.args[0])
        if components and "An error occured while rendering components" in orig_msg:
            orig_msg = str(err.args[0]).split("\n", 1)[-1]
    else:
        # Some exceptions (e.g. Pydantic) don't store the message in `args`,
        # so also print the prefix to ensure the component path is visible.
        print(prefix)  # noqa: T201
        orig_msg = str(err)

    err.args = (prefix + orig_msg,)  # tuple of one


@contextmanager
def add_slot_to_error_message(component_name: str, slot_name: str) -> Generator[None, None, None]:
    """Append `<component>(slot:<name>)` to the component path on exceptions raised inside a SlotNode."""
    try:
        yield
    except Exception as err:
        if not hasattr(err, "_components"):
            err._components = []  # type: ignore[attr-defined]

        err._components.insert(0, f"{component_name}(slot:{slot_name})")  # type: ignore[attr-defined]
        raise err from None
