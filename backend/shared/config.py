"""Config loader shared by all backend services.

Usage
-----
    from shared.config import get_config

    cfg = get_config("monitor")   # merges config/properties.yaml + monitor/default.yaml + monitor/{APP_ENV}.yaml
    cfg = get_config("bot")
    cfg = get_config("app")

Environment
-----------
    APP_ENV=dev   (default)  →  loads the **/dev.yaml overlay
    APP_ENV=prod             →  loads the **/prod.yaml overlay

Secrets
-------
    All credentials (tokens, keys, DB URLs) live in .env and are
    injected via ${oc.env:VAR_NAME} interpolation in properties.yaml.
    Other settings (thresholds, intervals, stock lists, …) live in YAML.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf

_CONFIG_ROOT = Path(__file__).resolve().parent.parent / "config"


@lru_cache(maxsize=None)
def get_config(service: str) -> DictConfig:
    """Load and cache config for *service* based on APP_ENV (default: dev).

    Merge order (later overrides earlier):
        config/properties.yaml
        config/<service>/default.yaml
        config/<service>/<APP_ENV>.yaml
    """
    load_dotenv()
    env = os.getenv("APP_ENV", "dev")
    cfg = OmegaConf.merge(
        OmegaConf.load(_CONFIG_ROOT / "properties.yaml"),
        OmegaConf.load(_CONFIG_ROOT / service / "default.yaml"),
        OmegaConf.load(_CONFIG_ROOT / service / f"{env}.yaml"),
    )
    assert isinstance(cfg, DictConfig)
    return cfg
