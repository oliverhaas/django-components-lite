# Initial implementation based on attributes.py from django-web-components
# See https://github.com/Xzya/django-web-components/blob/b43eb0c832837db939a6f8c1980334b0adfdd6e4/django_web_components/templatetags/components.py
# And https://github.com/Xzya/django-web-components/blob/b43eb0c832837db939a6f8c1980334b0adfdd6e4/django_web_components/attributes.py

import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from django.template import Context
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import SafeString, mark_safe

from django_components_lite.node import BaseNode

ClassValue = Sequence["ClassValue"] | str | dict[str, bool]
StyleDict = dict[str, str | int | Literal[False] | None]
StyleValue = Sequence["StyleValue"] | str | StyleDict


class HtmlAttrsNode(BaseNode):
    """Render an HTML attribute string from `attrs` over `defaults`, with extra kwargs merged in.

    Example - given `attrs = {"class": "my-class"}`,
    `{% html_attrs attrs defaults class="extra" %}` renders `class="my-class extra"`.
    """

    tag = "html_attrs"
    end_tag = None  # inline-only
    allowed_flags = ()

    def render(
        self,
        context: Context,
        attrs: dict | None = None,
        defaults: dict | None = None,
        **kwargs: Any,
    ) -> SafeString:
        final_attrs = {}
        final_attrs.update(defaults or {})
        final_attrs.update(attrs or {})
        final_attrs = merge_attributes(final_attrs, kwargs)

        return format_attributes(final_attrs)


def format_attributes(attributes: Mapping[str, Any]) -> str:
    """Format a dict of attributes into an HTML attribute string."""
    attr_list = []

    for key, value in attributes.items():
        if value is None or value is False:
            continue
        if value is True:
            attr_list.append(conditional_escape(key))
        else:
            attr_list.append(format_html('{}="{}"', key, value))

    return mark_safe(SafeString(" ").join(attr_list))  # noqa: S308


def merge_attributes(*attrs: dict) -> dict:
    """Merge HTML attribute dicts; same-key values join with a space, with `class`/`style` handled like Vue's `mergeProps`."""
    result: dict = {}

    classes: list[ClassValue] = []
    styles: list[StyleValue] = []
    for attrs_dict in attrs:
        for key, value in attrs_dict.items():
            if key == "class":
                classes.append(value)
            elif key == "style":
                styles.append(value)
            elif key in result:
                result[key] = str(result[key]) + " " + str(value)
            else:
                result[key] = value

    # `class`/`style` use Vue-style merging.
    if classes:
        result["class"] = normalize_class(classes)
    if styles:
        result["style"] = normalize_style(styles)

    return result


def normalize_class(value: ClassValue) -> str:
    """Normalize a class value (str, dict of `{name: truthy}`, or list of either) into a class string."""
    res: dict[str, bool] = {}
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        for item in value:
            # NOTE: Differs from Vue: a later falsy entry removes an earlier truthy one.
            # `["my-class", "extra-class", {"extra-class": False}]` -> `"my-class"`.
            normalized = _normalize_class(item)
            res.update(normalized)
    elif isinstance(value, dict):
        res = value
    else:
        raise TypeError(f"Invalid class value: {value}")

    res_str = ""
    for key, val in res.items():
        if val:
            res_str += key + " "
    return res_str.strip()


whitespace_re = re.compile(r"\s+")


# Like `normalize_class` but returns the intermediate dict.
def _normalize_class(value: ClassValue) -> dict[str, bool]:
    res: dict[str, bool] = {}
    if isinstance(value, str):
        class_parts = whitespace_re.split(value)
        res.update({part: True for part in class_parts if part})
    elif isinstance(value, (list, tuple)):
        for item in value:
            normalized = _normalize_class(item)
            res.update(normalized)
    elif isinstance(value, dict):
        res = value
    else:
        raise TypeError(f"Invalid class value: {value}")
    return res


def normalize_style(value: StyleValue) -> str:
    """Normalize a style value (str, dict, or list of either) into a CSS style string; `None`/`False` entries are dropped."""
    res: StyleDict = {}
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        for item in value:
            normalized = _normalize_style(item)
            res.update(normalized)
    elif isinstance(value, dict):
        res = _normalize_style(value)
    else:
        raise TypeError(f"Invalid style value: {value}")

    # Drop `None`/`False` so those properties don't render.
    res_parts = []
    for key, val in res.items():
        if val is not None and val is not False:
            res_parts.append(f"{key}: {val};")
    return " ".join(res_parts).strip()


def _normalize_style(value: StyleValue) -> StyleDict:
    res: StyleDict = {}
    if isinstance(value, str):
        normalized = parse_string_style(value)
        res.update(normalized)
    elif isinstance(value, (list, tuple)):
        for item in value:
            normalized = _normalize_style(item)
            res.update(normalized)
    elif isinstance(value, dict):
        # Skip `None` entries so they don't override later values.
        for key, val in value.items():
            if val is not None:
                res[key] = val
    else:
        raise TypeError(f"Invalid style value: {value}")
    return res


# Match CSS comments `/* ... */`
style_comment_re = re.compile(r"/\*.*?\*/", re.DOTALL)
# Split CSS properties by semicolon, but not inside parentheses
list_delimiter_re = re.compile(r";(?![^(]*\))", re.DOTALL)
# Split CSS property name and value
property_delimiter_re = re.compile(r":(.+)", re.DOTALL)


def parse_string_style(css_text: str) -> StyleDict:
    """Parse an inline CSS style string into a `{property: value}` dict; CSS comments are stripped."""
    css_text = style_comment_re.sub("", css_text)

    ret: StyleDict = {}

    # Split by semicolon, but not inside parentheses (e.g. `rgb(0, 0, 0)`).
    for item in list_delimiter_re.split(css_text):
        if item:
            parts = property_delimiter_re.split(item)
            if len(parts) > 1:
                ret[parts[0].strip()] = parts[1].strip()
    return ret
