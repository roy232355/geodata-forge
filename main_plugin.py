# -*- coding: utf-8 -*-
"""GeoData Forge QGIS Plugin entry point — manages plugin lifecycle (init, unload, run)."""
import os
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .dialog import GeoDataForgeDialog


class GeoDataForgePlugin:
    """Plugin Lifecycle Manager for QGIS integration."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        """Initializes GUI menu items and toolbar icons."""
        plugin_dir = os.path.dirname(__file__)
        icon_path = os.path.join(plugin_dir, "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(icon, "GeoData Forge", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        # Add to Vector Toolbar and Vector Menu
        self.iface.addVectorToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu("GeoData Forge", self.action)

    def unload(self):
        """Removes menu items and toolbar icons."""
        if self.action:
            self.iface.removePluginVectorMenu("GeoData Forge", self.action)
            self.iface.removeVectorToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None

        if self.dialog:
            try:
                self.dialog.close()
                self.dialog.deleteLater()
            except Exception:
                pass
            self.dialog = None

    def run(self):
        """Triggered when the user clicks the plugin button or menu item."""
        if not self.dialog:
            self.dialog = GeoDataForgeDialog(self.iface)
        else:
            try:
                self.dialog.refresh_inputs()
            except Exception:
                pass
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
