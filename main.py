import sys
import os
import time
import pygame
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QAction,
    QActionGroup,
    QLabel,
    QMessageBox,
    QFileDialog,
    QInputDialog,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QImage, QColor

from engine.core import EntityManager
from engine.lighting import DynamicLighting
from engine.graphics.renderer import Renderer
from engine.graphics.pygame_backend import PygameBackend
from engine.graphics.opengl_backend import OpenGLBackend
from engine.graphics.vulkan_backend import VulkanBackend
from editor.ui import EditorUI

class PygameWidget(QWidget):
    def __init__(self, parent=None, backend_type="opengl"):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)  # ~60 FPS

        self.renderer = None
        self.world = None
        self.lighting = None
        self.ui = None
        self.clock = pygame.time.Clock()
        self.backend_type = backend_type

        # For Pygame embedding, we'll store a QImage version of the internal surface
        self.qimage = None

    def initialize_engine(self):
        internal_res = (480, 270)
        screen_res = (1280, 720)
        win_id = self.winId()

        if self.backend_type == "pygame":
            os.environ['SDL_WINDOWID'] = str(int(win_id))
            os.environ['SDL_VIDEODRIVER'] = 'windib'
        else:
            os.environ.pop('SDL_WINDOWID', None)
            os.environ.pop('SDL_VIDEODRIVER', None)

        # Choose backend
        if self.backend_type == "pygame":
            backend = PygameBackend()
        elif self.backend_type == "opengl":
            backend = OpenGLBackend()
        elif self.backend_type == "vulkan":
            backend = VulkanBackend()
        else:
            backend = OpenGLBackend()  # default
        if self.renderer:
            self.renderer.cleanup()

        self.renderer = Renderer(backend, internal_res, screen_res)
        self.lighting = DynamicLighting(internal_res)
        self.world = EntityManager()
        self.ui = EditorUI(18)

        # Add a sample entity
        self.world.add_entity(100, 100, (255, 100, 100))

    def update_frame(self):
        if not self.renderer:
            return

        self.world.update_all()

        # Dynamic lighting follows mouse
        mouse_pos = self.mapFromGlobal(self.cursor().pos())  # global to widget
        self.lighting.clear()
        if self.rect().contains(mouse_pos):
            internal_res = self.renderer.internal_res
            w = self.width()
            h = self.height()
            if w > 0 and h > 0:
                scale_x = internal_res[0] / w
                scale_y = internal_res[1] / h
                internal_mouse = (int(mouse_pos.x() * scale_x), int(mouse_pos.y() * scale_y))
                self.lighting.add_light(internal_mouse, 60)

        self.renderer.render(self.world.get_all(), self.lighting, self.ui, self.clock)
        self.clock.tick(60)

        # If using Pygame backend and we want to embed, capture the internal surface
        if self.backend_type == "pygame" and hasattr(self.renderer.backend, 'internal_surface'):
            # Convert pygame surface to QImage
            surf = self.renderer.backend.internal_surface
            # Ensure surf is not None and has data
            if surf:
                # Get the raw data
                data = pygame.image.tostring(surf, 'RGB')
                self.qimage = QImage(data, surf.get_width(), surf.get_height(), QImage.Format_RGB888)
                # Scale to widget size
                self.qimage = self.qimage.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.update()

    def paintEvent(self, event):
        if self.backend_type == "pygame" and self.qimage:
            painter = QPainter(self)
            painter.drawImage(self.rect(), self.qimage)
        else:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(40, 40, 40))
            painter.setPen(Qt.white)
            painter.drawText(self.rect(), Qt.AlignCenter, f"{self.backend_type.capitalize()} backend is running in its own window.")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.world and self.renderer:
            pos = event.pos()
            internal_res = self.renderer.internal_res
            w = self.width()
            h = self.height()
            if w > 0 and h > 0:
                scale_x = internal_res[0] / w
                scale_y = internal_res[1] / h
                internal_pos = (int(pos.x() * scale_x), int(pos.y() * scale_y))
                self.world.add_entity(internal_pos[0], internal_pos[1])

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NeoPyxel Engine - v0.4")
        self.setGeometry(100, 100, 1280, 720)
        self.showMaximized()
        self.current_project_dir = None

        pygame.init()
        
        # Create a central widget with a layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("No project loaded. Use menu to control.")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Engine widget
        self.engine_widget = PygameWidget(backend_type="pygame")  # Change as needed
        layout.addWidget(self.engine_widget)
        self.engine_widget.hide()

        self.create_menu_bar()

    def create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')
        new_act = QAction('New', self)
        new_act.setShortcut('Ctrl+N')
        new_act.triggered.connect(self.new_project)
        file_menu.addAction(new_act)

        open_act = QAction('Open', self)
        open_act.setShortcut('Ctrl+O')
        open_act.triggered.connect(self.open_project)
        file_menu.addAction(open_act)

        save_act = QAction('Save', self)
        save_act.setShortcut('Ctrl+S')
        save_act.triggered.connect(self.save_project)
        file_menu.addAction(save_act)

        save_as_act = QAction('Save As', self)
        save_as_act.setShortcut('Ctrl+Shift+S')
        save_as_act.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()

        settings_act = QAction('Settings', self)
        settings_act.triggered.connect(self.show_settings)
        file_menu.addAction(settings_act)

        file_menu.addSeparator()

        exit_act = QAction('Exit', self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # Edit menu
        edit_menu = menubar.addMenu('Edit')
        undo_act = QAction('Undo', self)
        undo_act.setShortcut('Ctrl+Z')
        undo_act.triggered.connect(lambda: self.status_label.setText("Undo is not available yet"))
        edit_menu.addAction(undo_act)

        # View menu
        view_menu = menubar.addMenu('View')
        status_act = QAction('Status Bar', self, checkable=True)
        status_act.setChecked(True)
        status_act.toggled.connect(self.status_label.setVisible)
        view_menu.addAction(status_act)

        # Mode menu
        mode_menu = menubar.addMenu('Mode')
        dark_act = QAction('Dark Mode', self)
        dark_act.triggered.connect(lambda: self.set_mode("dark"))
        mode_menu.addAction(dark_act)
        light_act = QAction('Light Mode', self)
        light_act.triggered.connect(lambda: self.set_mode("light"))
        mode_menu.addAction(light_act)

        # Draw menu
        draw_menu = menubar.addMenu('Draw')
        pen_act = QAction('Pen', self)
        pen_act.triggered.connect(lambda: self.set_draw_tool("Pen"))
        draw_menu.addAction(pen_act)
        shapes_act = QAction('Shapes', self)
        shapes_act.triggered.connect(lambda: self.set_draw_tool("Shapes"))
        draw_menu.addAction(shapes_act)

        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        options_act = QAction('Options', self)
        options_act.triggered.connect(self.show_settings)
        tools_menu.addAction(options_act)

        # Help menu
        help_menu = menubar.addMenu('Help')
        about_act = QAction('About', self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(about_act)

        # Add a backend switcher for demonstration
        backend_menu = menubar.addMenu('Backend')
        backend_group = QActionGroup(self)
        backend_group.setExclusive(True)
        self.backend_actions = {}
        for backend in ['pygame', 'opengl', 'vulkan']:
            display_names = {
                "pygame": "Pygame",
                "opengl": "OpenGL",
                "vulkan": "Vulkan"
            }
            display_name = display_names.get(backend, backend.capitalize())
            act = QAction(display_name, self, checkable=True)
            act.triggered.connect(lambda checked, b=backend: self.switch_backend(b))
            act.setChecked(backend == self.engine_widget.backend_type)
            backend_group.addAction(act)
            self.backend_actions[backend] = act
            backend_menu.addAction(act)

    def switch_backend(self, backend):
        if backend != "pygame":
            self.status_label.setText(f"{backend.upper()} is disabled in this build to prevent crashes")
            QMessageBox.warning(
                self,
                "Backend Not Available",
                f"{backend.upper()} backend is currently disabled because it may crash in the packaged app.",
            )
            if "pygame" in self.backend_actions:
                self.backend_actions["pygame"].setChecked(True)
            return

        print(f"Switching to {backend} backend...")

        self.engine_widget.timer.stop()

        if self.engine_widget.renderer:
            self.engine_widget.renderer.cleanup()
            self.engine_widget.renderer = None
        try:
            pygame.display.quit()
        except Exception:
            pass
        pygame.quit()
        time.sleep(0.05)

        os.environ.pop('SDL_WINDOWID', None)
        os.environ.pop('SDL_VIDEODRIVER', None)
        pygame.init()

        try:
            self.engine_widget.backend_type = backend
            self.engine_widget.initialize_engine()
            self.status_label.setText(f"Switched to {backend} backend")
        except Exception as e:
            print(f"Failed to initialize {backend} backend: {e}")

            fallback_backend = "pygame"
            self.status_label.setText(f"Failed to load {backend}, falling back to {fallback_backend}")
            self.engine_widget.backend_type = fallback_backend
            self.engine_widget.initialize_engine()

        self.engine_widget.timer.start(16)
        if hasattr(self, "backend_actions"):
            selected = self.engine_widget.backend_type
            if selected in self.backend_actions:
                self.backend_actions[selected].setChecked(True)

    def new_project(self):
        project_name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not project_name.strip():
            self.status_label.setText("New project canceled")
            return

        safe_name = "".join(ch for ch in project_name.strip() if ch not in '<>:"/\\|?*').strip()
        if not safe_name:
            self.status_label.setText("Invalid project name")
            return

        project_dir = os.path.join(self.get_runtime_base_dir(), safe_name)
        if os.path.exists(project_dir):
            QMessageBox.warning(self, "Project Exists", f"Folder already exists:\n{project_dir}")
            self.status_label.setText("Project creation failed: folder already exists")
            return

        os.makedirs(project_dir, exist_ok=False)
        self.current_project_dir = project_dir
        self.ensure_engine_visible()
        self.status_label.setText(f"New project created: {safe_name}")
        self.save_project()

    def open_project(self):
        base_dir = self.get_runtime_base_dir()
        selected = QFileDialog.getExistingDirectory(self, "Open Project Folder", base_dir)
        if not selected:
            self.status_label.setText("Open project canceled")
            return

        self.current_project_dir = selected
        self.ensure_engine_visible()
        self.status_label.setText(f"Opened project: {os.path.basename(selected) or selected}")

    def show_settings(self):
        print("Settings dialog")
        self.status_label.setText("Settings opened")

    def show_about(self):
        print("NeoPyxel Engine v0.4")
        self.status_label.setText("About NeoPyxel")
        QMessageBox.information(self, "About NeoPyxel", "NeoPyxel Engine v0.4")

    def set_mode(self, mode):
        if mode == "dark":
            self.setStyleSheet("QMainWindow { background: #1f1f1f; color: #f0f0f0; }")
            self.status_label.setText("Dark mode enabled")
        else:
            self.setStyleSheet("")
            self.status_label.setText("Light mode enabled")

    def set_draw_tool(self, tool_name):
        self.status_label.setText(f"Draw tool selected: {tool_name}")

    def get_runtime_base_dir(self):
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.getcwd()

    def ensure_engine_visible(self):
        if not self.engine_widget.isVisible():
            self.engine_widget.show()
        if not self.engine_widget.renderer:
            self.engine_widget.initialize_engine()

    def save_project(self):
        if not self.current_project_dir:
            self.status_label.setText("No project to save")
            QMessageBox.information(self, "Save", "Create or open a project first.")
            return

        project_file = os.path.join(self.current_project_dir, "project.neopyxel")
        with open(project_file, "w", encoding="utf-8") as f:
            f.write("name=NeoPyxelProject\n")
            f.write(f"path={self.current_project_dir}\n")
            f.write(f"backend={self.engine_widget.backend_type}\n")
        self.status_label.setText(f"Saved project: {project_file}")

    def save_project_as(self):
        base_dir = self.get_runtime_base_dir()
        selected = QFileDialog.getExistingDirectory(self, "Save Project As", base_dir)
        if not selected:
            self.status_label.setText("Save As canceled")
            return

        self.current_project_dir = selected
        self.save_project()

    def closeEvent(self, event):
        if hasattr(self, 'engine_widget') and self.engine_widget.renderer:
            self.engine_widget.renderer.backend.cleanup()
        pygame.quit()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
