"""
This file is for logic that focuses on transforming the AST of template tags
into a form that can be used by the Nodes.
"""

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class TagParam:
    """
    TagParam represents a resolved arg or kwarg that will be passed to the tag function.

    {% component key=value ... %}

    TagParam represents an arg or kwarg that was resolved from a FilterExpression, and will
    be passed to the tag function. E.g.:

    component(key="value", ...)
    """

    # E.g. `name` in `name="John"`
    key: str | None
    # E.g. `"John"` in `name="John"`
    value: Any


def validate_params(
    func: Callable[..., Any],
    validation_signature: inspect.Signature,
    tag: str,
    params: list["TagParam"],
    extra_kwargs: dict[str, Any] | None = None,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """
    Validates a list of TagParam objects against this tag's function signature.

    Raises `TypeError` if the parameters don't match the function signature.
    """
    supports_code_objects = func is not None and hasattr(func, "__code__") and hasattr(func.__code__, "co_varnames")
    try:
        if supports_code_objects:
            args, kwargs = _validate_params_with_code(func, params, extra_kwargs)
        else:
            args, kwargs = _validate_params_with_signature(validation_signature, params, extra_kwargs)
        return args, kwargs
    except TypeError as e:
        err_msg = str(e)
        raise TypeError(f"Invalid parameters for tag '{tag}': {err_msg}") from None


def _validate_params_with_signature(
    signature: inspect.Signature,
    params: list[TagParam],
    extra_kwargs: dict[str, Any] | None = None,
) -> Any:
    """
    Apply a list of `TagParams` to another function, keeping the order of the params as they
    appeared in the template.
    """
    # Track state as we process parameters
    seen_kwargs = False  # To detect positional args after kwargs
    used_param_names = set()  # To detect duplicate kwargs
    validated_args = []
    validated_kwargs = {}

    # Get list of valid parameter names and analyze signature
    params_by_name = signature.parameters
    valid_params = list(params_by_name.keys())

    # Check if function accepts variable arguments (*args, **kwargs)
    has_var_positional = any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params_by_name.values())
    has_var_keyword = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params_by_name.values())

    # Find the last positional parameter index (excluding *args)
    max_positional_index = 0
    for i, signature_param in enumerate(params_by_name.values()):
        if signature_param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            max_positional_index = i + 1
        elif signature_param.kind == inspect.Parameter.VAR_POSITIONAL:
            # Don't count *args in max_positional_index
            break
        # Parameter.KEYWORD_ONLY
        # Parameter.VAR_KEYWORD
        else:
            break

    next_positional_index = 0

    # Process parameters in their original order
    for param in params:
        # This is a positional argument
        if param.key is None:
            if seen_kwargs:
                raise TypeError("positional argument follows keyword argument")

            # Only check position limit for non-variadic functions
            if not has_var_positional and next_positional_index >= max_positional_index:
                if max_positional_index == 0:
                    raise TypeError(f"takes 0 positional arguments but {next_positional_index + 1} was given")
                raise TypeError(f"takes {max_positional_index} positional argument(s) but more were given")

            # For non-variadic arguments, get the parameter name this maps to
            if next_positional_index < max_positional_index:
                param_name = valid_params[next_positional_index]
                # Check if this parameter was already provided as a kwarg
                if param_name in used_param_names:
                    raise TypeError(f"got multiple values for argument '{param_name}'")
                used_param_names.add(param_name)

            validated_args.append(param.value)
            next_positional_index += 1
        else:
            # This is a keyword argument
            seen_kwargs = True

            # Check for duplicate kwargs
            if param.key in used_param_names:
                raise TypeError(f"got multiple values for argument '{param.key}'")

            # Validate kwarg names if the function doesn't accept **kwargs
            if not has_var_keyword and param.key not in valid_params:
                raise TypeError(f"got an unexpected keyword argument '{param.key}'")

            validated_kwargs[param.key] = param.value
            used_param_names.add(param.key)

    # Add any extra kwargs - These are allowed only if the function accepts **kwargs
    if extra_kwargs:
        if not has_var_keyword:
            first_key = next(iter(extra_kwargs))
            raise TypeError(f"got an unexpected keyword argument '{first_key}'")
        validated_kwargs.update(extra_kwargs)

    # Check for missing required arguments and apply defaults
    for param_name, signature_param in params_by_name.items():
        if param_name in used_param_names or param_name in validated_kwargs:
            continue

        if signature_param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            if signature_param.default == inspect.Parameter.empty:
                raise TypeError(f"missing a required argument: '{param_name}'")
            if len(validated_args) <= next_positional_index:
                validated_kwargs[param_name] = signature_param.default
        elif signature_param.kind == inspect.Parameter.KEYWORD_ONLY:
            if signature_param.default == inspect.Parameter.empty:
                raise TypeError(f"missing a required argument: '{param_name}'")
            validated_kwargs[param_name] = signature_param.default

    # Return args and kwargs
    return validated_args, validated_kwargs


def _validate_params_with_code(
    fn: Callable[..., Any],
    params: list["TagParam"],
    extra_kwargs: dict[str, Any] | None = None,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """
    Validate and process function parameters using __code__ attributes for better performance.
    This is the preferred implementation when the necessary attributes are available.

    This implementation is about 3x faster than signature-based validation.
    For context, see https://github.com/django-components/django-components/issues/935
    """
    code = fn.__code__
    defaults = fn.__defaults__ or ()
    kwdefaults = getattr(fn, "__kwdefaults__", None) or {}

    # Get parameter information from code object
    param_names = code.co_varnames[: code.co_argcount + code.co_kwonlyargcount]
    positional_count = code.co_argcount
    kwonly_count = code.co_kwonlyargcount
    has_var_positional = bool(code.co_flags & 0x04)  # CO_VARARGS
    has_var_keyword = bool(code.co_flags & 0x08)  # CO_VARKEYWORDS

    # Skip self and context parameters
    skip_params = 2
    param_names = param_names[skip_params:]
    positional_count = max(0, positional_count - skip_params)

    # Calculate required counts
    num_defaults = len(defaults)
    required_positional = positional_count - num_defaults

    # Track state
    seen_kwargs = False
    used_param_names = set()
    validated_args = []
    validated_kwargs = {}
    next_positional_index = 0

    # Process parameters in order
    for param in params:
        if param.key is None:
            # This is a positional argument
            if seen_kwargs:
                raise TypeError("positional argument follows keyword argument")

            # Check position limit for non-variadic functions
            if not has_var_positional and next_positional_index >= positional_count:
                if positional_count == 0:
                    raise TypeError("takes 0 positional arguments but 1 was given")
                raise TypeError(f"takes {positional_count} positional argument(s) but more were given")

            # For non-variadic arguments, get parameter name
            if next_positional_index < positional_count:
                param_name = param_names[next_positional_index]
                if param_name in used_param_names:
                    raise TypeError(f"got multiple values for argument '{param_name}'")
                used_param_names.add(param_name)

            validated_args.append(param.value)
            next_positional_index += 1
        else:
            # This is a keyword argument
            seen_kwargs = True

            # Check for duplicate kwargs
            if param.key in used_param_names:
                raise TypeError(f"got multiple values for argument '{param.key}'")

            # Validate kwarg names
            is_valid_kwarg = param.key in param_names[: positional_count + kwonly_count] or (  # Regular param
                has_var_keyword and param.key not in param_names
            )  # **kwargs param
            if not is_valid_kwarg:
                raise TypeError(f"got an unexpected keyword argument '{param.key}'")

            validated_kwargs[param.key] = param.value
            used_param_names.add(param.key)

    # Add any extra kwargs
    if extra_kwargs:
        if not has_var_keyword:
            first_key = next(iter(extra_kwargs))
            raise TypeError(f"got an unexpected keyword argument '{first_key}'")
        validated_kwargs.update(extra_kwargs)

    # Check for missing required arguments and apply defaults
    for i, param_name in enumerate(param_names):
        if param_name in used_param_names or param_name in validated_kwargs:
            continue

        if i < positional_count:  # Positional parameter
            if i < required_positional:
                raise TypeError(f"missing a required argument: '{param_name}'")
            if len(validated_args) <= i:
                default_index = i - required_positional
                validated_kwargs[param_name] = defaults[default_index]
        elif i < positional_count + kwonly_count:  # Keyword-only parameter
            if param_name not in kwdefaults:
                raise TypeError(f"missing a required argument: '{param_name}'")
            validated_kwargs[param_name] = kwdefaults[param_name]

    return tuple(validated_args), validated_kwargs
