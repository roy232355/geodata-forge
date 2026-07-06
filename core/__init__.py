# -*- coding: utf-8 -*-
"""Core component imports and dynamic version management for GeoData Forge."""
import os
import configparser


def _get_version():
    try:
        metadata_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "metadata.txt")
        if os.path.exists(metadata_path):
            config = configparser.ConfigParser()
            config.read(metadata_path, encoding='utf-8')
            return config.get('general', 'version', fallback='Unknown')
    except Exception:
        pass
    return "Unknown"


FORGE_VERSION = _get_version()
