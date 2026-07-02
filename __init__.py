# -*- coding: utf-8 -*-


def classFactory(iface):
    """Factory function to load the plugin class in QGIS.

    Args:
        iface: An interface to the running QGIS instance.
    """
    from .main_plugin import GeoDataForgePlugin

    return GeoDataForgePlugin(iface)
