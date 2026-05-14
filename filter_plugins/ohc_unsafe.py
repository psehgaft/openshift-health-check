from __future__ import annotations

import json

from ansible.utils.unsafe_proxy import wrap_var


def ohc_wrap_unsafe(value):
    return wrap_var(value)


def ohc_parse_checkpoint_json_unsafe(value):
    return wrap_var(json.loads(value))


class FilterModule(object):
    def filters(self):
        return {
            "ohc_wrap_unsafe": ohc_wrap_unsafe,
            "ohc_parse_checkpoint_json_unsafe": ohc_parse_checkpoint_json_unsafe,
        }
