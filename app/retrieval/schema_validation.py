"""JSON Schema loading and validation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_instance(instance: dict[str, Any], schema_path: Path) -> None:
    schema = load_json(schema_path)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(instance)


def validate_yaml(path: Path, schema_path: Path) -> dict[str, Any]:
    instance = load_yaml(path)
    validate_instance(instance, schema_path)
    return instance
