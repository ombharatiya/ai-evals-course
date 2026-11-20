"""Read the policies.yaml files with the standard library.

The course writes YAML in a small subset: mappings and lists by indentation, and every scalar or
flow list written as JSON (double-quoted strings, numbers, true/false/null, [..], {..}). Any YAML
parser reads these files; this module reads exactly that subset and nothing more.

    from tools.mini_yaml import load
    data = load(open("world/global/policies.yaml").read())
"""
from __future__ import annotations

import json


def _lines(text: str):
    for raw in text.splitlines():
        if raw.lstrip().startswith("#") or not raw.strip():
            continue
        yield len(raw) - len(raw.lstrip(" ")), raw.strip()


def load(text: str):
    lines = list(_lines(text))
    value, i = _block(lines, 0, 0)
    if i != len(lines):
        raise ValueError(f"unparsed content at line {i + 1}: {lines[i][1]!r}")
    return value


def _scalar(s: str):
    return json.loads(s)


def _block(lines, i, indent):
    if i >= len(lines):
        return None, i
    if lines[i][1].startswith("- "):
        out = []
        while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
            item = lines[i][1][2:]
            if ":" in item and not item.startswith(("\"", "[", "{")):
                # a mapping that starts on the dash line
                sub = [(indent + 2, item)] + []
                j = i + 1
                while j < len(lines) and lines[j][0] > indent:
                    sub.append(lines[j])
                    j += 1
                val, _ = _block(sub, 0, indent + 2)
                out.append(val)
                i = j
            else:
                out.append(_scalar(item))
                i += 1
        return out, i
    out = {}
    while i < len(lines) and lines[i][0] == indent:
        key, _, rest = lines[i][1].partition(":")
        rest = rest.strip()
        if rest:
            out[key.strip()] = _scalar(rest)
            i += 1
        else:
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                val, i = _block(lines, i + 1, lines[i + 1][0])
            elif i + 1 < len(lines) and lines[i + 1][0] == indent and lines[i + 1][1].startswith("- "):
                val, i = _block(lines, i + 1, indent)
            else:
                val, i = None, i + 1
            out[key.strip()] = val
    return out, i
