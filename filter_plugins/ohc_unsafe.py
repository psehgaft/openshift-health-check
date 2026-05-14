from __future__ import annotations

import json

from ansible.utils.unsafe_proxy import wrap_var


def ohc_wrap_unsafe(value):
    return wrap_var(value)


def ohc_parse_checkpoint_json_unsafe(value):
    return wrap_var(json.loads(value))


def ohc_checkpoint_get(value, path, default_value=""):
    data = json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value
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
