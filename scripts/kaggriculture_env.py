"""Load the current Kaggriculture environment on the project's Python 3.9 runtime."""

from __future__ import annotations

import importlib.util
import json
import random
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_ROOT = (
    PROJECT_ROOT
    / ".vendor"
    / "kaggle-environments"
    / "kaggle_environments"
    / "envs"
    / "kaggriculture"
)
ENV_SOURCE = ENV_ROOT / "kaggriculture.py"
ENV_SPEC = ENV_ROOT / "kaggriculture.json"
ENV_NAME = "kaggriculture_local"


def _install_seed_compatibility() -> None:
    """Backport the one utility used by the newest environment plugin."""
    import kaggle_environments.utils as utils

    if hasattr(utils, "resolve_episode_seed"):
        return

    def resolve_episode_seed(env, *, config_key="seed", fallback=None):
        if not hasattr(env, "info") or env.info is None:
            env.info = {}
        seed = env.info.get("seed")
        config = env.configuration
        if seed is None:
            seed = config.get(config_key) if isinstance(config, dict) else getattr(config, config_key, None)
        if seed is None:
            seed = fallback() if fallback is not None else random.randrange(2**31)
        try:
            setattr(config, config_key, None)
        except (AttributeError, TypeError):
            config[config_key] = None
        env.info["seed"] = seed
        return seed

    utils.resolve_episode_seed = resolve_episode_seed


def load_environment():
    """Register and return the official environment module plus Kaggle core."""
    import kaggle_environments

    if not ENV_SOURCE.exists() or not ENV_SPEC.exists():
        raise FileNotFoundError(
            "Official Kaggriculture plugin is missing. Run the setup command in README.md."
        )

    _install_seed_compatibility()
    module_spec = importlib.util.spec_from_file_location("kaggriculture_local_module", ENV_SOURCE)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)

    if ENV_NAME not in kaggle_environments.environments:
        specification = json.loads(ENV_SPEC.read_text(encoding="utf-8"))
        kaggle_environments.register(
            ENV_NAME,
            {
                "specification": specification,
                "interpreter": module.interpreter,
                "renderer": module.renderer,
                "html_renderer": module.html_renderer,
                "agents": module.agents,
            },
        )
    return kaggle_environments, module

