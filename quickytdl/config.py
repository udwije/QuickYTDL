# quickytdl/config.py

import os
import json
from .utils import get_default_save_dir, ensure_directory

class ConfigManager:
    """
    Handles loading and saving user preferences (default save directory,
    auto‐shutdown flag) to a JSON config file in the user’s config folder.
    """
    def __init__(self):
        # sensible defaults
        self.default_save_dir = get_default_save_dir()
        self.auto_shutdown = False

        # determine where to store the config file
        self._config_path = self._get_config_path()

        # ensure the save directory from config always exists
        ensure_directory(self.default_save_dir)

    def _get_config_path(self) -> str:
        home = os.path.expanduser("~")
        if os.name == "nt":
            root = os.getenv("APPDATA", home)
        else:
            root = os.path.join(home, ".config")
        app_dir = os.path.join(root, "QuickYTDL")
        ensure_directory(app_dir)
        return os.path.join(app_dir, "config.json")

    def load(self) -> None:
        """
        Load config from disk, if it exists. Otherwise keep defaults.
        """
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.default_save_dir = data.get("default_save_dir", self.default_save_dir)
            self.auto_shutdown    = data.get("auto_shutdown",    self.auto_shutdown)
            # re-ensure in case the loaded path changed
            ensure_directory(self.default_save_dir)
        except FileNotFoundError:
            # no config yet—first run
            return
        except Exception as e:
            print(f"[Config] Error loading config: {e}")

    def save(self) -> None:
        """
        Write current settings to the config file.
        """
        data = {
            "default_save_dir": self.default_save_dir,
            "auto_shutdown":    self.auto_shutdown,
        }
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")
