"""Config loader: reads config/settings.yaml with env-var overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"


@dataclass(frozen=True)
class TLSConfig:
    enabled: bool = False


@dataclass(frozen=True)
class TemporalConfig:
    address: str
    namespace: str
    task_queue: str
    tls: TLSConfig
    api_key: str | None


@dataclass(frozen=True)
class TerraformConfig:
    networking_module: Path
    binary: str


@dataclass(frozen=True)
class Settings:
    temporal: TemporalConfig
    terraform: TerraformConfig


def _env_override(path: str, current: Any) -> Any:
    env_key = path.upper().replace(".", "_")
    raw = os.environ.get(env_key)
    if raw is None:
        return current
    if isinstance(current, bool):
        return raw.lower() in ("1", "true", "yes", "on")
    return raw


def load_settings(path: Path | None = None) -> Settings:
    source = path or DEFAULT_SETTINGS_PATH
    with source.open() as f:
        raw = yaml.safe_load(f) or {}

    t = raw.get("temporal", {})
    tls_raw = t.get("tls", {})
    tf = raw.get("terraform", {})

    temporal = TemporalConfig(
        address=_env_override("temporal.address", t.get("address", "localhost:7233")),
        namespace=_env_override("temporal.namespace", t.get("namespace", "default")),
        task_queue=_env_override(
            "temporal.task_queue", t.get("task_queue", "landing-zone-task-queue")
        ),
        tls=TLSConfig(
            enabled=_env_override("temporal.tls.enabled", tls_raw.get("enabled", False)),
        ),
        api_key=_env_override("temporal.api_key", tls_raw.get("api_key") or t.get("api_key")),
    )

    terraform = TerraformConfig(
        networking_module=REPO_ROOT
        / _env_override(
            "terraform.networking_module", tf.get("networking_module", "terraform/networking")
        ),
        binary=_env_override("terraform.binary", tf.get("binary", "terraform")),
    )

    return Settings(temporal=temporal, terraform=terraform)
