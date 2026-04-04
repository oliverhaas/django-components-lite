"""Utilities for template tag parameter validation."""

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class TagParam:
    """A resolved arg or kwarg to be passed to a tag's render method."""

    key: str | None
    value: Any


def validate_params(
    func: Callable[..., Any],
    validation_signature: inspect.Signature,
    tag: str,
    params: list[TagParam],
    extra_kwargs: dict[str, Any] | None = None,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Validate params against the tag's render method signature."""
    try:
        return _validate_params(validation_signature, params, extra_kwargs)
    except TypeError as e:
        raise TypeError(f"Invalid parameters for tag '{tag}': {e}") from None


def _validate_params(
    signature: inspect.Signature,
    params: list[TagParam],
    extra_kwargs: dict[str, Any] | None = None,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Apply a list of TagParams to a function signature, preserving template order."""
    seen_kwargs = False
    used_param_names: set[str] = set()
    validated_args: list[Any] = []
    validated_kwargs: dict[str, Any] = {}

    params_by_name = signature.parameters
    valid_params = list(params_by_name.keys())

    has_var_positional = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params_by_name.values())
    has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params_by_name.values())

    # Count positional parameters (excluding *args)
    max_positional = 0
    for sig_param in params_by_name.values():
        if sig_param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            max_positional += 1
        else:
            break

    next_pos = 0

    for param in params:
        if param.key is None:
            # Positional arg
            if seen_kwargs:
                raise TypeError("positional argument follows keyword argument")
            if not has_var_positional and next_pos >= max_positional:
                raise TypeError(
                    f"takes {max_positional} positional argument(s) but {next_pos + 1} were given"
                    if max_positional > 0
                    else f"takes 0 positional arguments but {next_pos + 1} was given",
                )
            if next_pos < max_positional:
                name = valid_params[next_pos]
                if name in used_param_names:
                    raise TypeError(f"got multiple values for argument '{name}'")
                used_param_names.add(name)
            validated_args.append(param.value)
            next_pos += 1
        else:
            # Keyword arg
            seen_kwargs = True
            if param.key in used_param_names:
                raise TypeError(f"got multiple values for argument '{param.key}'")
            if not has_var_keyword and param.key not in valid_params:
                raise TypeError(f"got an unexpected keyword argument '{param.key}'")
            validated_kwargs[param.key] = param.value
            used_param_names.add(param.key)

    if extra_kwargs:
        if not has_var_keyword:
            raise TypeError(f"got an unexpected keyword argument '{next(iter(extra_kwargs))}'")
        validated_kwargs.update(extra_kwargs)

    # Check for missing required args and apply defaults
    for name, sig_param in params_by_name.items():
        if name in used_param_names or name in validated_kwargs:
            continue
        if (
            sig_param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            or sig_param.kind == inspect.Parameter.KEYWORD_ONLY
        ):
            if sig_param.default == inspect.Parameter.empty:
                raise TypeError(f"missing a required argument: '{name}'")
            validated_kwargs[name] = sig_param.default

    return tuple(validated_args), validated_kwargs
