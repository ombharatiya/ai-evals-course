"""A small JSON Schema validator (standard library only) for the subset the course schemas use.

Supported keywords: type (string or list), properties, required, additionalProperties (bool or
schema), items, enum, const, minimum, maximum, minLength, minItems, maxItems, pattern, anyOf,
and $ref to "#/$defs/<name>" inside the same document. Unknown keywords are ignored, so a full
validator (for example the jsonschema package) accepts the same files.

    from tools.jsonschema_lite import validate
    errors = validate(instance, schema)        # [] when the instance is valid
"""
from __future__ import annotations

import re

_TYPES = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def validate(instance, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    root = root if root is not None else schema
    errs: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            return [f"{path}: unsupported $ref {ref}"]
        target = root
        for part in ref[2:].split("/"):
            target = target[part]
        return validate(instance, target, root, path)
    if "anyOf" in schema:
        if not any(not validate(instance, s, root, path) for s in schema["anyOf"]):
            errs.append(f"{path}: matches none of anyOf")
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES[x](instance) for x in types):
            return errs + [f"{path}: expected {t}, got {type(instance).__name__}"]
    if "const" in schema and instance != schema["const"]:
        errs.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in enum {schema['enum']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append(f"{path}: {instance} > maximum {schema['maximum']}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{path}: shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append(f"{path}: {instance!r} does not match {schema['pattern']}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errs.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, item in enumerate(instance):
                errs += validate(item, schema["items"], root, f"{path}[{i}]")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in instance:
                errs.append(f"{path}: missing required {k!r}")
        for k, v in instance.items():
            if k in props:
                errs += validate(v, props[k], root, f"{path}.{k}")
            else:
                ap = schema.get("additionalProperties", True)
                if ap is False:
                    errs.append(f"{path}: unexpected property {k!r}")
                elif isinstance(ap, dict):
                    errs += validate(v, ap, root, f"{path}.{k}")
    return errs
