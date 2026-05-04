import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import ValidationError

from .schema import ConfigSchema


def _coerce_env_scalar(raw: str) -> Any:
    lower = raw.strip().lower()
    if lower in ("true", "1", "yes", "on"):
        return True
    if lower in ("false", "0", "no", "off"):
        return False
    try:
        if "." in raw.strip():
            return float(raw.strip())
        return int(raw.strip())
    except ValueError:
        return raw


def _set_nested(root: Dict[str, Any], parts: List[str], value: Any) -> None:
    cur = root
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if last:
            cur[part] = value
        else:
            existing = cur.get(part)
            if not isinstance(existing, dict):
                cur[part] = {}
            cur = cur[part]


def _env_tree_from_prefix(prefix: str = "ASSY_") -> Dict[str, Any]:
    tree: Dict[str, Any] = {}
    for raw_key, raw_val in os.environ.items():
        if not raw_key.startswith(prefix):
            continue
        suffix = raw_key[len(prefix) :].lower()
        parts = [p for p in suffix.split("__") if p]
        if not parts:
            continue
        val = _coerce_env_scalar(raw_val)
        _set_nested(tree, parts, val)
    return tree


class ConfigLoader:
    """Ładuje konfigurację: defaults (Pydantic) < YAML < zmienne środowiskowe ASSY_."""

    def __init__(self) -> None:
        self._defaults = ConfigSchema()

    def load_config(self, config_path: Optional[str] = None) -> ConfigSchema:
        config_dict = self._defaults.model_dump()

        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, encoding="utf-8") as f:
                    yaml_config = yaml.safe_load(f)
                if yaml_config:
                    config_dict = self._merge_dicts(config_dict, yaml_config)
            except Exception as e:
                raise RuntimeError(f"Error loading YAML config: {e}") from e

        env_tree = _env_tree_from_prefix()
        if env_tree:
            config_dict = self._merge_dicts(config_dict, env_tree)

        try:
            return ConfigSchema.model_validate(config_dict)
        except ValidationError as e:
            raise RuntimeError(f"Configuration validation error: {e}") from e

    def _merge_dicts(self, base_dict: Dict[str, Any], override_dict: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(base_dict)
        for key, value in override_dict.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result


config_loader = ConfigLoader()
