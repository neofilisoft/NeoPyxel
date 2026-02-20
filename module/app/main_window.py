import json
import os
import shutil
import subprocess
import sys

import pygame
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from editor.editorscript_bridge import ScriptBridge
from module.app.plugin_manager import PluginManager
from module.constants import APP_VERSION, IMAGE_EXTENSIONS, MODEL_EXTENSIONS
from module.render.playable_exporter import build_playable_script
from module.widget.PygameWidget.pygame_widget import PygameWidget
from module.widget.Scene.scene3d_widget import Scene3DWidget
from module.widget.asset_list_widget import AssetListWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"NeoPyxel Studio - v{APP_VERSION}")
        self.setGeometry(100, 100, 1500, 880)
        self.showMaximized()

        self.current_project_dir = None
        self.current_project_name = None
        self.current_metadata_file = "project.npl"
        self.current_scene_name = "main.json"
        self.main_scene_name = "main.json"
        self.scene_files = ["main.json"]
        self.backend_preview_processes = []
        self.plugin_docks = []
        self.view_menu = None

        pygame.init()
        self.engine_widget = PygameWidget(backend_type="pygame")
        self.engine_widget.on_world_changed = self.refresh_entity_list
        self.engine_widget.on_selection_changed = self.on_viewport_selection_changed
        self.engine_widget.on_message = self.set_status
        self.scene3d_widget = Scene3DWidget()
        self.scene3d_widget.on_message = self.set_status
        self.viewport_stack = QStackedWidget()
        self.viewport_stack.addWidget(self.engine_widget)
        self.viewport_stack.addWidget(self.scene3d_widget)
        self.setCentralWidget(self.viewport_stack)

        self.apply_dark_theme()
        self.create_docks()
        self.create_menu_bar()
        self.script_bridge = ScriptBridge()
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_plugins(self.get_runtime_base_dir())
        self.plugin_manager.emit("on_app_start", self)
        self.on_grid_settings_changed()
        self.activate_3d_workspace()
        self.set_status("No project loaded. Use File > New or File > Open.")

    def apply_dark_theme(self):
        self.setStyleSheet(
            """
            QMainWindow { background-color: #11151e; color: #d6dae3; }
            QMenuBar { background-color: #151b25; color: #d6dae3; padding: 4px; }
            QMenuBar::item:selected { background: #283244; }
            QMenu { background-color: #151b25; color: #d6dae3; border: 1px solid #2a3446; }
            QMenu::item:selected { background-color: #283244; }
            QMenu#backend_menu::indicator {
                width: 10px;
                height: 10px;
                border-radius: 5px;
                margin-left: 6px;
                image: none;
            }
            QMenu#backend_menu::indicator:unchecked {
                border: 1px solid #4a5d7a;
                background: transparent;
            }
            QMenu#backend_menu::indicator:checked {
                border: 1px solid #75a7ff;
                background: #75a7ff;
            }
            QMessageBox {
                background-color: #121924;
            }
            QMessageBox QLabel {
                color: #e8f1ff;
                font-size: 12px;
            }
            QDockWidget { color: #d6dae3; border: 1px solid #222c3d; titlebar-close-icon: none; }
            QDockWidget::title { background: #171f2c; padding: 6px; text-align: left; }
            QListWidget, QTextEdit, QComboBox, QSpinBox {
                background-color: #121924;
                color: #cfd8e6;
                border: 1px solid #2b384e;
                selection-background-color: #28405d;
            }
            QPushButton {
                background-color: #1f2d40;
                color: #dbe7ff;
                border: 1px solid #35506f;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #2b3d55; }
            QLabel { color: #b9c8df; }
            QCheckBox { color: #cfd8e6; spacing: 6px; }
            QStatusBar { background-color: #141b27; color: #9fb7d7; }
            """
        )

    def create_menu_bar(self):
        menubar = self.menuBar()
        menubar.clear()

        file_menu = menubar.addMenu("File")
        new_act = QAction("New Project", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self.new_project)
        file_menu.addAction(new_act)

        open_act = QAction("Open Project", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_project)
        file_menu.addAction(open_act)

        save_act = QAction("Save", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_project)
        file_menu.addAction(save_act)

        import_model_act = QAction("Import Model", self)
        import_model_act.triggered.connect(self.import_model)
        file_menu.addAction(import_model_act)

        export_act = QAction("Export Playable", self)
        export_act.triggered.connect(self.export_playable_script)
        file_menu.addAction(export_act)

        exit_act = QAction("Exit", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        self.view_menu = menubar.addMenu("View")
        self._rebuild_view_menu()

        edit_menu = menubar.addMenu("Edit")
        undo_act = QAction("Undo", self)
        undo_act.setShortcut("Ctrl+Z")
        undo_act.triggered.connect(self.undo_action)
        edit_menu.addAction(undo_act)

        delete_act = QAction("Delete Selected", self)
        delete_act.setShortcut("Del")
        delete_act.triggered.connect(self.delete_selected_entity)
        edit_menu.addAction(delete_act)

        scene_menu = menubar.addMenu("Scene")
        use_2d_act = QAction("Use 2D Workspace", self)
        use_2d_act.setShortcut("Ctrl+2")
        use_2d_act.triggered.connect(self.activate_2d_workspace)
        scene_menu.addAction(use_2d_act)

        use_3d_act = QAction("Use 3D Workspace", self)
        use_3d_act.setShortcut("Ctrl+3")
        use_3d_act.triggered.connect(self.activate_3d_workspace)
        scene_menu.addAction(use_3d_act)

        add_cube_act = QAction("Add 3D Cube", self)
        add_cube_act.triggered.connect(self.add_3d_cube)
        scene_menu.addAction(add_cube_act)

        reset_3d_camera_act = QAction("Reset 3D Camera", self)
        reset_3d_camera_act.triggered.connect(self.reset_3d_camera)
        scene_menu.addAction(reset_3d_camera_act)

        scene_menu.addSeparator()

        new_scene_act = QAction("New Scene", self)
        new_scene_act.triggered.connect(self.new_scene)
        scene_menu.addAction(new_scene_act)

        set_main_act = QAction("Set As Main Scene", self)
        set_main_act.triggered.connect(self.set_current_as_main_scene)
        scene_menu.addAction(set_main_act)

        tools_menu = menubar.addMenu("Tools")
        draw_group = QActionGroup(self)
        draw_group.setExclusive(True)
        for tool in ["Select", "Pen", "Line", "Rect", "Eraser"]:
            act = QAction(tool, self, checkable=True)
            act.triggered.connect(lambda checked, t=tool: self.set_draw_tool(t))
            if tool == "Select":
                act.setChecked(True)
            draw_group.addAction(act)
            tools_menu.addAction(act)

        backend_menu = menubar.addMenu("Backend")
        backend_menu.setObjectName("backend_menu")
        self.backend_actions = {}
        backend_group = QActionGroup(self)
        backend_group.setExclusive(True)
        for backend in ["pygame", "opengl", "vulkan"]:
            act = QAction(backend.upper(), self, checkable=True)
            act.setChecked(backend == self.engine_widget.backend_type)
            act.triggered.connect(lambda checked, b=backend: self.switch_backend(b))
            self.backend_actions[backend] = act
            backend_group.addAction(act)
            backend_menu.addAction(act)

        help_menu = menubar.addMenu("Help")
        about_act = QAction("About", self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(about_act)

    def _rebuild_view_menu(self):
        if not self.view_menu:
            return

        self.view_menu.clear()
        base_docks = [
            ("Scene Graph", getattr(self, "scene_dock", None)),
            ("Assets", getattr(self, "assets_dock", None)),
            ("Inspector", getattr(self, "inspector_dock", None)),
            ("Output", getattr(self, "output_dock", None)),
        ]
        for _, dock in base_docks:
            if isinstance(dock, QDockWidget):
                self.view_menu.addAction(dock.toggleViewAction())

        if self.plugin_docks:
            self.view_menu.addSeparator()
            for dock in self.plugin_docks:
                if isinstance(dock, QDockWidget):
                    self.view_menu.addAction(dock.toggleViewAction())

    def register_plugin_dock(self, dock, area=Qt.RightDockWidgetArea, show_on_start=False):
        if not isinstance(dock, QDockWidget):
            return
        if dock.parent() is not self:
            self.addDockWidget(area, dock)
        if dock not in self.plugin_docks:
            self.plugin_docks.append(dock)
        if not show_on_start:
            dock.hide()
        self._rebuild_view_menu()

    def create_docks(self):
        self.scene_dock = QDockWidget("Scene Graph", self)
        self.scene_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        scene_widget = QWidget()
        scene_layout = QVBoxLayout(scene_widget)

        scene_layout.addWidget(QLabel("Scene File"))
        self.scene_selector = QComboBox()
        self.scene_selector.currentIndexChanged.connect(self.on_scene_selector_changed)
        scene_layout.addWidget(self.scene_selector)

        self.main_scene_label = QLabel("Main Scene: main.json")
        scene_layout.addWidget(self.main_scene_label)

        scene_layout.addWidget(QLabel("Grid / Snap"))
        self.show_grid_checkbox = QCheckBox("Show Grid")
        self.show_grid_checkbox.setChecked(True)
        self.show_grid_checkbox.toggled.connect(self.on_grid_settings_changed)
        scene_layout.addWidget(self.show_grid_checkbox)

        self.snap_checkbox = QCheckBox("Snap To Grid")
        self.snap_checkbox.setChecked(True)
        self.snap_checkbox.toggled.connect(self.on_grid_settings_changed)
        scene_layout.addWidget(self.snap_checkbox)

        self.lighting_checkbox = QCheckBox("Editor Lighting")
        self.lighting_checkbox.setChecked(False)
        self.lighting_checkbox.toggled.connect(self.on_grid_settings_changed)
        scene_layout.addWidget(self.lighting_checkbox)

        self.grid_size_spin = self._make_spin(4, 128, 16)
        self.grid_size_spin.setSingleStep(4)
        self.grid_size_spin.valueChanged.connect(self.on_grid_settings_changed)
        scene_layout.addWidget(QLabel("Grid Size"))
        scene_layout.addWidget(self.grid_size_spin)

        scene_layout.addWidget(QLabel("Entities"))
        self.entity_list = QListWidget()
        self.entity_list.currentRowChanged.connect(self.on_entity_row_changed)
        scene_layout.addWidget(self.entity_list)

        add_btn = QPushButton("Add Entity")
        add_btn.clicked.connect(self.add_entity_dialog)
        scene_layout.addWidget(add_btn)

        del_btn = QPushButton("Delete Entity")
        del_btn.clicked.connect(self.delete_selected_entity)
        scene_layout.addWidget(del_btn)

        self.scene_dock.setWidget(scene_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.scene_dock)

        self.assets_dock = QDockWidget("Assets", self)
        self.assets_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        assets_widget = QWidget()
        assets_layout = QVBoxLayout(assets_widget)
        self.assets_path_label = QLabel("assets: -")
        assets_layout.addWidget(self.assets_path_label)

        self.asset_list = AssetListWidget()
        self.asset_list.setDragEnabled(True)
        self.asset_list.itemDoubleClicked.connect(self.insert_selected_asset_to_viewport)
        assets_layout.addWidget(self.asset_list)
        self.assets_dock.setWidget(assets_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.assets_dock)

        self.inspector_dock = QDockWidget("Inspector", self)
        self.inspector_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        inspector_widget = QWidget()
        inspector_layout = QFormLayout(inspector_widget)

        self.pos_x_spin = self._make_spin(-10000, 10000)
        self.pos_y_spin = self._make_spin(-10000, 10000)
        self.width_spin = self._make_spin(1, 3000, 16)
        self.height_spin = self._make_spin(1, 3000, 16)
        self.color_r_spin = self._make_spin(0, 255, 0)
        self.color_g_spin = self._make_spin(0, 255, 255)
        self.color_b_spin = self._make_spin(0, 255, 0)
        self.sprite_label = QLabel("(none)")

        inspector_layout.addRow("X", self.pos_x_spin)
        inspector_layout.addRow("Y", self.pos_y_spin)
        inspector_layout.addRow("Width", self.width_spin)
        inspector_layout.addRow("Height", self.height_spin)
        inspector_layout.addRow("R", self.color_r_spin)
        inspector_layout.addRow("G", self.color_g_spin)
        inspector_layout.addRow("B", self.color_b_spin)
        inspector_layout.addRow("Sprite", self.sprite_label)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_inspector_changes)
        inspector_layout.addRow(apply_btn)

        self.inspector_dock.setWidget(inspector_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock)

        self.output_dock = QDockWidget("Output", self)
        self.output_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        self.output_dock.setWidget(self.output_log)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.output_dock)
        self._rebuild_view_menu()

    def _make_spin(self, min_value, max_value, value=0):
        spin = QSpinBox()
        spin.setRange(min_value, max_value)
        spin.setValue(value)
        return spin

    def set_status(self, message):
        self.statusBar().showMessage(message, 6000)
        if hasattr(self, "output_log"):
            self.output_log.append(message)

    def on_grid_settings_changed(self):
        self.engine_widget.set_grid_settings(
            self.snap_checkbox.isChecked(),
            self.show_grid_checkbox.isChecked(),
            self.grid_size_spin.value(),
        )
        self.engine_widget.set_editor_lighting(self.lighting_checkbox.isChecked())

    def activate_2d_workspace(self):
        self.viewport_stack.setCurrentWidget(self.engine_widget)
        self.ensure_engine_visible()
        self.set_status("2D workspace active")

    def activate_3d_workspace(self):
        self.viewport_stack.setCurrentWidget(self.scene3d_widget)
        self.scene3d_widget.setFocus()
        self.set_status("3D workspace active")

    def add_3d_cube(self):
        self.activate_3d_workspace()
        self.scene3d_widget.add_cube()
        self.set_status("3D cube added")

    def reset_3d_camera(self):
        self.scene3d_widget.reset_camera_view()
        self.set_status("3D camera reset")

    def set_draw_tool(self, tool_name):
        self.ensure_engine_visible()
        self.engine_widget.set_draw_tool(tool_name)
        self.set_status(f"Tool: {tool_name}")

    def switch_backend(self, backend):
        self.ensure_engine_visible()
        if backend in ("opengl", "vulkan"):
            launched = self.launch_backend_preview(backend)
            if launched:
                self.set_status(
                    f"{backend.upper()} preview launched in separate window. Editor viewport remains PYGAME for stability."
                )
                for name, action in self.backend_actions.items():
                    action.setChecked(name == backend)
            else:
                self.set_status(f"Failed to launch {backend.upper()} preview.")
                for name, action in self.backend_actions.items():
                    action.setChecked(name == "pygame")
            return

        # PYGAME editor viewport should not restart pygame every click.
        if self.engine_widget.backend_type != "pygame" or not self.engine_widget.renderer:
            self.engine_widget.backend_type = "pygame"
            try:
                self.engine_widget.initialize_engine()
            except Exception as exc:
                self.set_status(f"Failed to activate PYGAME viewport: {exc}")
                return

        self.engine_widget.set_assets_dir(self.assets_dir_for_current_project())
        self.engine_widget.needs_redraw = True
        self.engine_widget.update()
        self.set_status("Pygame viewport active")
        for name, action in self.backend_actions.items():
            action.setChecked(name == "pygame")

    def launch_backend_preview(self, backend):
        script = r'''
import sys
import pygame

backend = sys.argv[1] if len(sys.argv) > 1 else "opengl"
pygame.init()

if backend == "opengl":
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.set_mode((960, 540), pygame.DOUBLEBUF | pygame.OPENGL)
    try:
        import moderngl
        ctx = moderngl.create_context()
    except Exception:
        ctx = None
else:
    pygame.display.set_mode((960, 540))
    ctx = None

pygame.display.set_caption(f"NeoPyxel {backend.upper()} Preview")
clock = pygame.time.Clock()
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    if ctx:
        ctx.clear(0.07, 0.09, 0.13)
        pygame.display.flip()
    else:
        surf = pygame.display.get_surface()
        if surf:
            surf.fill((18, 24, 34))
            pygame.display.flip()
    clock.tick(60)

pygame.quit()
'''
        self._close_backend_previews()
        try:
            proc = subprocess.Popen(
                [sys.executable, "-c", script, backend],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.backend_preview_processes.append(proc)
            return True
        except Exception:
            return False

    def _close_backend_previews(self):
        alive = []
        for proc in self.backend_preview_processes:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
            else:
                if proc.poll() is None:
                    alive.append(proc)
        self.backend_preview_processes = alive

    def new_project(self):
        project_name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not project_name.strip():
            self.set_status("New project canceled")
            return

        safe_name = "".join(ch for ch in project_name.strip() if ch not in '<>:"/\\|?*').strip()
        if not safe_name:
            self.set_status("Invalid project name")
            return

        project_dir = os.path.join(self.get_runtime_base_dir(), safe_name)
        if os.path.exists(project_dir):
            QMessageBox.warning(self, "Project Exists", f"Folder already exists:\n{project_dir}")
            self.set_status("Project creation failed: folder already exists")
            return

        os.makedirs(project_dir, exist_ok=False)
        self.current_project_dir = project_dir
        self.current_project_name = safe_name

        self.scene_files = ["main.json"]
        self.current_scene_name = "main.json"
        self.main_scene_name = "main.json"

        self.ensure_project_structure()
        self.scene3d_widget.set_assets_root(self.assets_dir_for_current_project())
        self.scene3d_widget.reset_scene()
        self.ensure_engine_visible()
        self.engine_widget.clear_scene()
        self.save_current_scene_file()
        self.save_project_metadata()
        self.refresh_scene_selector()
        self.refresh_asset_browser()
        self.plugin_manager.emit(
            "on_project_opened",
            self.current_project_dir,
            self.assets_dir_for_current_project(),
        )
        self.activate_3d_workspace()
        self.set_status(f"Project created: {safe_name}")

    def open_project(self):
        selected = QFileDialog.getExistingDirectory(self, "Open Project Folder", self.get_runtime_base_dir())
        if not selected:
            self.set_status("Open project canceled")
            return

        metadata_path = os.path.join(selected, self.current_metadata_file)
        if not os.path.exists(metadata_path):
            QMessageBox.warning(
                self,
                "Invalid Project Folder",
                f"This folder has no {self.current_metadata_file} file:\n{selected}",
            )
            self.set_status(f"Open failed: {self.current_metadata_file} not found")
            return

        self.current_project_dir = selected
        self.current_project_name = os.path.basename(selected)
        self.ensure_project_structure()

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            self.current_project_name = metadata.get("name", self.current_project_name)
            self.main_scene_name = metadata.get("main_scene", "main.json")
            self.current_scene_name = metadata.get("last_scene", self.main_scene_name)
            self.scene_files = metadata.get("scenes", [self.main_scene_name])
            if self.main_scene_name not in self.scene_files:
                self.scene_files.insert(0, self.main_scene_name)
            backend_name = str(metadata.get("backend", "pygame")).lower()
            self.snap_checkbox.setChecked(bool(metadata.get("snap_enabled", True)))
            self.show_grid_checkbox.setChecked(bool(metadata.get("show_grid", True)))
            self.lighting_checkbox.setChecked(bool(metadata.get("editor_lighting", False)))
            self.grid_size_spin.setValue(int(metadata.get("grid_size", 16)))
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Project Metadata", f"Failed to read {self.current_metadata_file}:\n{exc}")
            self.set_status(f"Open failed: invalid {self.current_metadata_file}")
            return

        self.ensure_engine_visible()
        self.scene3d_widget.set_assets_root(self.assets_dir_for_current_project())
        self.engine_widget.set_assets_dir(self.assets_dir_for_current_project())
        self.load_scene_file(self.current_scene_name)
        self.refresh_scene_selector()
        self.refresh_asset_browser()
        self.switch_backend(backend_name if backend_name in ("pygame", "opengl", "vulkan") else "pygame")
        self.plugin_manager.emit(
            "on_project_opened",
            self.current_project_dir,
            self.assets_dir_for_current_project(),
        )
        self.activate_3d_workspace()
        self.set_status(f"Opened project: {self.current_project_name}")

    def save_project(self):
        if not self.current_project_dir:
            self.set_status("No project to save")
            return
        self.ensure_project_structure()
        self.save_current_scene_file()
        self.save_project_metadata()
        self.set_status("Project saved")

    def _ensure_project_before_import(self):
        if self.current_project_dir:
            return True

        msg = QMessageBox(self)
        msg.setWindowTitle("No Project Loaded")
        msg.setText("Import Model needs a project. Choose action:")
        open_btn = msg.addButton("Open Project", QMessageBox.AcceptRole)
        new_btn = msg.addButton("New Project", QMessageBox.ActionRole)
        cancel_btn = msg.addButton(QMessageBox.Cancel)
        msg.exec_()
        clicked = msg.clickedButton()

        if clicked == open_btn:
            self.open_project()
        elif clicked == new_btn:
            self.new_project()
        elif clicked == cancel_btn:
            return False

        return bool(self.current_project_dir)

    def import_model(self):
        if not self._ensure_project_before_import():
            self.set_status("Import model canceled")
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Model",
            self.current_project_dir,
            "3D Models (*.fbx *.obj *.abc *.blend *.ply)",
        )
        if not files:
            self.set_status("Import model canceled")
            return

        assets_dir = self.assets_dir_for_current_project()
        models_dir = os.path.join(assets_dir, "models")
        os.makedirs(models_dir, exist_ok=True)

        imported = 0
        for src in files:
            ext = os.path.splitext(src)[1].lower()
            if ext not in MODEL_EXTENSIONS:
                continue

            base_name = os.path.basename(src)
            target = os.path.join(models_dir, base_name)
            stem, ext_name = os.path.splitext(base_name)
            n = 1
            while os.path.exists(target):
                target = os.path.join(models_dir, f"{stem}_{n}{ext_name}")
                n += 1

            try:
                shutil.copy2(src, target)
            except Exception as exc:
                self.set_status(f"Import failed: {base_name} ({exc})")
                continue

            rel_model = os.path.relpath(target, assets_dir).replace("\\", "/")
            self.scene3d_widget.add_model_asset(rel_model, target)
            imported += 1

        self.refresh_asset_browser()
        if imported:
            self.activate_3d_workspace()
            self.set_status(f"Imported {imported} model(s) into assets/models")
        else:
            self.set_status("No supported model files imported")

    def save_project_metadata(self):
        metadata = {
            "name": self.current_project_name or "NeoPyxelProject",
            "version": APP_VERSION,
            "backend": self.engine_widget.backend_type,
            "main_scene": self.main_scene_name,
            "last_scene": self.current_scene_name,
            "scenes": self.scene_files,
            "snap_enabled": self.snap_checkbox.isChecked(),
            "show_grid": self.show_grid_checkbox.isChecked(),
            "editor_lighting": self.lighting_checkbox.isChecked(),
            "grid_size": self.grid_size_spin.value(),
        }
        path = os.path.join(self.current_project_dir, self.current_metadata_file)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def save_current_scene_file(self):
        scenes_dir = self.scenes_dir_for_current_project()
        os.makedirs(scenes_dir, exist_ok=True)
        path = os.path.join(scenes_dir, self.current_scene_name)
        scene_2d = self.engine_widget.get_scene_data()
        scene_3d = self.scene3d_widget.export_scene_data()
        mode = "3d" if self.viewport_stack.currentWidget() is self.scene3d_widget else "2d"
        payload = {
            "name": self.current_scene_name,
            "mode": mode,
            "entities": scene_2d,
            "entities2d": scene_2d,
            "entities3d": scene_3d,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load_scene_file(self, scene_name):
        if not self.current_project_dir:
            return
        path = os.path.join(self.scenes_dir_for_current_project(), scene_name)
        if not os.path.exists(path):
            self.engine_widget.clear_scene()
            self.scene3d_widget.reset_scene()
            self.current_scene_name = scene_name
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            entities_2d = payload.get("entities2d", payload.get("entities", []))
            entities_3d = payload.get("entities3d", [])
            scene_mode = str(payload.get("mode", "2d")).lower()
            self.engine_widget.set_assets_dir(self.assets_dir_for_current_project())
            self.scene3d_widget.set_assets_root(self.assets_dir_for_current_project())
            self.engine_widget.load_scene_data(entities_2d)
            self.scene3d_widget.load_scene_data(entities_3d)
            self.current_scene_name = scene_name
            self.plugin_manager.emit("on_scene_loaded", scene_name, entities_2d)
            self.set_status(f"Scene loaded: {scene_name}")
            if scene_mode == "3d":
                self.activate_3d_workspace()
        except Exception as exc:
            self.set_status(f"Failed to load scene {scene_name}: {exc}")

    def new_scene(self):
        if not self.current_project_dir:
            self.set_status("Create/Open project first")
            return

        name, ok = QInputDialog.getText(self, "New Scene", "Scene file name (without .json):")
        if not ok or not name.strip():
            return
        base = "".join(ch for ch in name.strip() if ch not in '<>:"/\\|?*')
        if not base:
            self.set_status("Invalid scene name")
            return

        scene_file = f"{base}.json"
        if scene_file in self.scene_files:
            self.set_status("Scene already exists")
            return

        self.save_current_scene_file()
        self.scene_files.append(scene_file)
        self.current_scene_name = scene_file
        self.engine_widget.clear_scene()
        self.scene3d_widget.reset_scene()
        self.save_current_scene_file()
        self.save_project_metadata()
        self.refresh_scene_selector()
        self.set_status(f"Scene created: {scene_file}")

    def set_current_as_main_scene(self):
        if not self.current_project_dir:
            self.set_status("Create/Open project first")
            return
        self.main_scene_name = self.current_scene_name
        self.main_scene_label.setText(f"Main Scene: {self.main_scene_name}")
        self.save_project_metadata()
        self.set_status(f"Main scene set: {self.main_scene_name}")

    def on_scene_selector_changed(self, index):
        if index < 0:
            return
        selected_scene = self.scene_selector.itemText(index)
        if not selected_scene or selected_scene == self.current_scene_name:
            return
        self.save_current_scene_file()
        self.load_scene_file(selected_scene)
        self.save_project_metadata()

    def refresh_scene_selector(self):
        self.scene_selector.blockSignals(True)
        self.scene_selector.clear()
        for scene in self.scene_files:
            self.scene_selector.addItem(scene)
        idx = self.scene_selector.findText(self.current_scene_name)
        if idx >= 0:
            self.scene_selector.setCurrentIndex(idx)
        self.scene_selector.blockSignals(False)
        self.main_scene_label.setText(f"Main Scene: {self.main_scene_name}")

    def refresh_asset_browser(self):
        self.asset_list.clear()
        assets_dir = self.assets_dir_for_current_project()
        self.assets_path_label.setText(f"assets: {assets_dir}")

        if not assets_dir or not os.path.exists(assets_dir):
            return

        for root, _, files in os.walk(assets_dir):
            for filename in files:
                if not filename.lower().endswith(IMAGE_EXTENSIONS):
                    continue
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, assets_dir).replace("\\", "/")
                item = QListWidgetItem(rel_path)
                item.setData(Qt.UserRole, abs_path)
                self.asset_list.addItem(item)

    def insert_selected_asset_to_viewport(self, item):
        if not item:
            return
        abs_path = item.data(Qt.UserRole)
        rel = os.path.relpath(abs_path, self.assets_dir_for_current_project()).replace("\\", "/")
        self.ensure_engine_visible()
        self.engine_widget.add_sprite_entity(100, 100, rel)
        self.set_status(f"Asset inserted: {rel}")

    def refresh_entity_list(self, scene_data):
        self.entity_list.blockSignals(True)
        self.entity_list.clear()
        for i, entity in enumerate(scene_data):
            sprite = entity.get("sprite")
            kind = f"Sprite:{sprite}" if sprite else "Rect"
            text = f"{i} | {kind} | ({entity['x']},{entity['y']}) {entity['w']}x{entity['h']}"
            self.entity_list.addItem(QListWidgetItem(text))
        self.entity_list.blockSignals(False)

    def on_entity_row_changed(self, row):
        self.engine_widget.set_selected_index(row)
        self.populate_inspector(row)

    def on_viewport_selection_changed(self, row):
        self.entity_list.blockSignals(True)
        self.entity_list.setCurrentRow(row)
        self.entity_list.blockSignals(False)
        self.populate_inspector(row)

    def populate_inspector(self, row):
        scene = self.engine_widget.get_scene_data()
        if not (0 <= row < len(scene)):
            self.sprite_label.setText("(none)")
            return
        entity = scene[row]
        self.pos_x_spin.setValue(entity["x"])
        self.pos_y_spin.setValue(entity["y"])
        self.width_spin.setValue(entity["w"])
        self.height_spin.setValue(entity["h"])
        self.color_r_spin.setValue(entity["color"][0])
        self.color_g_spin.setValue(entity["color"][1])
        self.color_b_spin.setValue(entity["color"][2])
        self.sprite_label.setText(entity.get("sprite") or "(none)")

    def apply_inspector_changes(self):
        row = self.entity_list.currentRow()
        ok = self.engine_widget.update_selected_entity(
            self.pos_x_spin.value(),
            self.pos_y_spin.value(),
            self.width_spin.value(),
            self.height_spin.value(),
            (self.color_r_spin.value(), self.color_g_spin.value(), self.color_b_spin.value()),
        )
        if ok:
            self.set_status(f"Entity {row} updated")
            self.refresh_entity_list(self.engine_widget.get_scene_data())
            self.entity_list.setCurrentRow(row)
        else:
            self.set_status("No selected entity")

    def add_entity_dialog(self):
        self.ensure_engine_visible()
        self.engine_widget.add_rect_entity(100, 100, 32, 32, (0, 255, 0))
        self.set_status("Rectangle entity added")

    def delete_selected_entity(self):
        self.ensure_engine_visible()
        if self.engine_widget.delete_selected_entity():
            self.set_status("Entity deleted")
        else:
            self.set_status("No selected entity")

    def undo_action(self):
        self.ensure_engine_visible()
        if self.engine_widget.undo_last():
            self.set_status("Undo completed")
        else:
            self.set_status("Nothing to undo")

    def export_playable_script(self):
        if not self.current_project_dir:
            self.set_status("No project to export")
            return

        self.save_project()
        export_path = os.path.join(self.current_project_dir, "play_game.py")
        scene_path = os.path.join(self.scenes_dir_for_current_project(), self.main_scene_name)
        assets_path = self.assets_dir_for_current_project()
        script = build_playable_script(scene_path, assets_path)

        with open(export_path, "w", encoding="utf-8") as f:
            f.write(script)
        self.set_status(f"Playable exported: {export_path}")

    def show_about(self):
        QMessageBox.information(
            self,
            "About NeoPyxel Studio",
            f"NeoPyxel Studio v{APP_VERSION}\n\n"
            "Scene editor with grid/snap.\n"
            "Assets drag-drop into viewport.\n"
            "OpenGL/Vulkan run as preview windows\n"
            "for stability.",
        )

    def ensure_project_structure(self):
        if not self.current_project_dir:
            return
        os.makedirs(self.assets_dir_for_current_project(), exist_ok=True)
        os.makedirs(self.scenes_dir_for_current_project(), exist_ok=True)

    def assets_dir_for_current_project(self):
        if not self.current_project_dir:
            return None
        return os.path.join(self.current_project_dir, "assets")

    def scenes_dir_for_current_project(self):
        if not self.current_project_dir:
            return None
        return os.path.join(self.current_project_dir, "scenes")

    def get_runtime_base_dir(self):
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.getcwd()

    def ensure_engine_visible(self):
        if hasattr(self, "viewport_stack"):
            self.viewport_stack.setCurrentWidget(self.engine_widget)
        initialized = False
        if not self.engine_widget.renderer:
            self.engine_widget.initialize_engine()
            initialized = True
        self.engine_widget.set_assets_dir(self.assets_dir_for_current_project())
        if initialized:
            self.set_status("Scene Viewport ready")

    def closeEvent(self, event):
        if hasattr(self, "plugin_manager"):
            self.plugin_manager.emit("on_before_close")
        if hasattr(self, "engine_widget") and self.engine_widget.timer:
            self.engine_widget.timer.stop()
        if hasattr(self, "scene3d_widget") and self.scene3d_widget.timer:
            self.scene3d_widget.timer.stop()
        self._close_backend_previews()
        if hasattr(self, "engine_widget") and self.engine_widget.renderer:
            self.engine_widget.renderer.cleanup()
        try:
            pygame.display.quit()
        except Exception:
            pass
        pygame.quit()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

