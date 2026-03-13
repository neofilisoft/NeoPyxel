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


class LuaScriptingDock(QDockWidget):
    def __init__(self, app):
        super().__init__("Lua Scripting", app)
        self.app = app
        self.lua = LuaBridge()
        self.script_path = None

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        container = QWidget(self)
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("Lua Script"))
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            """-- Example:\n"
            "function on_update(entity_id, entity)\n"
            "  if entity ~= nil then\n"
            "    entity.x = entity.x + 1\n"
            "  end\n"
            "end\n"""
        )
        layout.addWidget(self.editor)

        button_row = QHBoxLayout()

        self.load_btn = QPushButton("Load .lua")
        self.load_btn.clicked.connect(self.load_script_file)
        button_row.addWidget(self.load_btn)

        self.exec_btn = QPushButton("Run Script")
        self.exec_btn.clicked.connect(self.execute_editor_script)
        button_row.addWidget(self.exec_btn)

        self.update_btn = QPushButton("Run on Selected")
        self.update_btn.clicked.connect(self.run_on_selected_entity)
        button_row.addWidget(self.update_btn)

        layout.addLayout(button_row)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        self.setWidget(container)

    def _set_status(self, message):
        self.status_label.setText(message)
        try:
            self.app.set_status(f"[Lua Plugin] {message}")
        except Exception:
            pass

    def load_script_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Lua script",
            self.app.current_project_dir or os.getcwd(),
            "Lua files (*.lua);;All files (*.*)",
        )
        if not path:
            return
        with open(path, "r", encoding="utf-8") as file:
            script = file.read()
        self.script_path = path
        self.editor.setPlainText(script)
        self._set_status(f"Loaded: {os.path.basename(path)}")

    def execute_editor_script(self):
        code = self.editor.toPlainText().strip()
        if not code:
            self._set_status("No script to execute")
            return
        try:
            self.lua.execute_script(code)
            self._set_status("Script executed")
        except Exception as exc:
            self._set_status(f"Script error: {exc}")

    def run_on_selected_entity(self):
        entity = getattr(self.app.engine_widget, "selected_entity", None)
        if entity is None:
            self._set_status("No selected entity")
            return

        payload = {
            "x": entity.rect.x,
            "y": entity.rect.y,
            "w": entity.rect.w,
            "h": entity.rect.h,
            "color": list(getattr(entity, "color", (0, 255, 0))),
        }
        entity_id = id(entity)

        try:
            result = self.lua.update_entity(entity_id, payload)
        except Exception as exc:
            self._set_status(f"on_update failed: {exc}")
            return

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
