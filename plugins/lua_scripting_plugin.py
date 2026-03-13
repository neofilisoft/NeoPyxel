"""Lua scripting plugin for NeoPyxel Studio.

Provides a dockable editor to execute Lua snippets and run on_update hooks
against the currently selected entity.
"""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from engine.scripting.lua_bridge import LuaBridge


EXAMPLE_SCRIPT = """-- Example:
function on_update(entity_id, entity)
  if entity ~= nil then
    entity.x = entity.x + 1
  end
  return entity
end
"""


class LuaScriptingDock(QDockWidget):
    def __init__(self, app):
        super().__init__("Lua Scripting", app)
        self.app = app
        self.lua = LuaBridge()
        self.script_path = None

        lua_ready = self.lua.is_available()

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        container = QWidget(self)
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("Lua Script"))
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(EXAMPLE_SCRIPT)
        layout.addWidget(self.editor)

        button_row = QHBoxLayout()

        self.load_btn = QPushButton("Load .lua")
        self.load_btn.clicked.connect(self.load_script_file)
        button_row.addWidget(self.load_btn)

        self.exec_btn = QPushButton("Run Script")
        self.exec_btn.setEnabled(lua_ready)
        self.exec_btn.clicked.connect(self.execute_editor_script)
        button_row.addWidget(self.exec_btn)

        self.update_btn = QPushButton("Run on Selected")
        self.update_btn.setEnabled(lua_ready)
        self.update_btn.clicked.connect(self.run_on_selected_entity)
        button_row.addWidget(self.update_btn)

        layout.addLayout(button_row)

        self.status_label = QLabel(self.lua.get_status_message())
        layout.addWidget(self.status_label)

        self.setWidget(container)

@@ -134,29 +137,28 @@ class LuaScriptingDock(QDockWidget):
        if isinstance(result, dict):
            if "x" in result:
                entity.rect.x = int(result["x"])
            if "y" in result:
                entity.rect.y = int(result["y"])
            if "w" in result:
                entity.rect.w = int(result["w"])
            if "h" in result:
                entity.rect.h = int(result["h"])
            if "color" in result and isinstance(result["color"], (list, tuple)):
                color = tuple(int(c) for c in result["color"][:3])
                entity.color = color
                entity.image.fill(color)

        if hasattr(self.app.engine_widget, "notify_world_changed"):
            self.app.engine_widget.notify_world_changed()

        self._set_status("on_update executed")


class LuaScriptingPlugin:
    def __init__(self, app):
        self.dock = LuaScriptingDock(app)


def register(app):
    plugin = LuaScriptingPlugin(app)
    return plugin.dock
