# -*- coding: utf-8 -*-
"""JSON configuration Profile Manager for GeoData Forge."""
import json
import os

from . import FORGE_VERSION


class ProfileManager:
    """Handles saving and loading generation parameters configuration profiles to/from JSON."""

    @staticmethod
    def save_profile(file_path, config):
        """Saves configuration dict to a JSON file.

        Args:
            file_path (str): Output profile JSON path.
            config (dict): Settings configurations.
        """
        try:
            # Force metadata key
            config["plugin_version"] = FORGE_VERSION
            config["software"] = "GeoData Forge"

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            raise IOError(f"Failed to write profile JSON: {str(e)}")

    @staticmethod
    def load_profile(file_path):
        """Loads configuration dictionary from a JSON file.

        Args:
            file_path (str): Input profile JSON path.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration profile not found: {file_path}")

        # Security: size guard against oversized/crafted JSON files
        file_size = os.path.getsize(file_path)
        if file_size > 5 * 1024 * 1024:
            raise ValueError(
                f"Profile file is too large ({file_size // 1024} KB). "
                f"Maximum allowed size is 5120 KB."
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            if not isinstance(config, dict):
                raise ValueError("Configuration profile must be a JSON dictionary object.")

            return config
        except json.JSONDecodeError as e:
            raise ValueError(f"Profile file contains malformed JSON syntax: {str(e)}")
        except Exception as e:
            raise IOError(f"Failed to load profile: {str(e)}")
