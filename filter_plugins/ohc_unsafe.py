from __future__ import annotations

import ast
import json

from ansible.utils.unsafe_proxy import wrap_var


def _coerce_text(value):
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8")
    return value


def _parse_checkpoint_data(value):
    if isinstance(value, dict):
        return value
    text = _coerce_text(value)
    if not isinstance(text, str):
        raise TypeError(f"Unsupported checkpoint payload type: {type(value).__name__}")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = ast.literal_eval(text)
    if not isinstance(parsed, dict):
        raise TypeError(f"Checkpoint payload must decode to a mapping, got {type(parsed).__name__}")
    return parsed


def ohc_wrap_unsafe(value):
    return wrap_var(value)


def ohc_parse_checkpoint_json_unsafe(value):
    return wrap_var(_parse_checkpoint_data(value))


def ohc_checkpoint_get(value, path, default_value=""):
    data = _parse_checkpoint_data(value) if isinstance(value, (str, bytes, bytearray)) else value
    current = data
    for segment in str(path).split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return default_value
    return current


class FilterModule(object):
    def filters(self):
        return {
            "ohc_wrap_unsafe": ohc_wrap_unsafe,
            "ohc_parse_checkpoint_json_unsafe": ohc_parse_checkpoint_json_unsafe,
            "ohc_checkpoint_get": ohc_checkpoint_get,
        }
