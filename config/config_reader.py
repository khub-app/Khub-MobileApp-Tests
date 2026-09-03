import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_FILE = Path(__file__).parent / "config.yaml"


class ConfigReader:
    """Loads config/config.yaml once per process and resolves an environment block."""

    _cache = None

    def __init__(self, config_file: Path = DEFAULT_CONFIG_FILE):
        if ConfigReader._cache is None:
            with open(config_file, "r", encoding="utf-8") as f:
                ConfigReader._cache = yaml.safe_load(f)
        self._data = ConfigReader._cache

    def get_environment(self, env_name: str | None = None) -> dict:
        env_name = env_name or os.environ.get("MOBILE_ENV") or self._data["default_environment"]
        try:
            env = dict(self._data["environments"][env_name])
        except KeyError:
            raise ValueError(
                f"Unknown environment '{env_name}'. Available: {list(self._data['environments'])}"
            )

        app_path = env.get("app_path")
        if app_path:
            env["app_path"] = str(PROJECT_ROOT / app_path)

        return env

    def get_backend_api(self, name: str = "preprod") -> dict:
        try:
            return dict(self._data["backend_api"][name])
        except KeyError:
            raise ValueError(
                f"Unknown backend_api entry '{name}'. Available: {list(self._data.get('backend_api', {}))}"
            )
