import sys
import pygame
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QAction
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QImage, QCursor

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
        self.timer.start(16)

        self.renderer = None
        self.world = None
        self.lighting = None
        self.ui = None
        self.clock = pygame.time.Clock()
        self.scaled_surface = None  # only used for PygameBackend
        self.backend_type = backend_type

    def initialize_engine(self):
        internal_res = (480, 270)
        screen_res = (1280, 720)

        # Choose backend
        if self.backend_type == "pygame":
            backend = PygameBackend()
        elif self.backend_type == "opengl":
            backend = OpenGLBackend()
        elif self.backend_type == "vulkan":
            backend = VulkanBackend()
        else:
            backend = OpenGLBackend()  # default

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
        mouse_pos = self.mapFromGlobal(QCursor.pos())
        self.lighting.clear()
        if self.rect().contains(mouse_pos):
            internal_res = self.renderer.internal_res
            widget_size = self.size()
            scale_x = internal_res[0] / widget_size.width() if widget_size.width() else 1
            scale_y = internal_res[1] / widget_size.height() if widget_size.height() else 1
            internal_mouse = (int(mouse_pos.x() * scale_x), int(mouse_pos.y() * scale_y))
            self.lighting.add_light(internal_mouse, 60)

        self.renderer.render(self.world.get_all(), self.lighting, self.ui, self.clock)
        self.clock.tick(60)
        self.update()

    def paintEvent(self, event):
        # For PygameBackend, we need to get the final surface; for others, the backend draws itself.
        if isinstance(self.renderer.backend, PygameBackend):
            # Pygame renders to its own window, so we don't need to paint in Qt.
            # However, if we want to embed, we'd need to use a different approach.
            pass
        else:
            # For OpenGL/Vulkan, the backend draws directly to the Pygame window,
            # which is a separate window. To embed, we'd need to render to a texture and draw in Qt.
            # This is complex; for simplicity, we'll keep Pygame window separate.
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.world:
            pos = event.pos()
            internal_res = self.renderer.internal_res
            widget_size = self.size()
            scale_x = internal_res[0] / widget_size.width() if widget_size.width() else 1
            scale_y = internal_res[1] / widget_size.height() if widget_size.height() else 1
            internal_pos = (int(pos.x() * scale_x), int(pos.y() * scale_y))
            self.world.add_entity(internal_pos[0], internal_pos[1])

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NeoPyxel Engine - v0.2")
        self.setGeometry(100, 100, 1280, 720)

        pygame.init()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        from PyQt5.QtWidgets import QLabel
        label = QLabel("No Project.\nUse menu to control.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        self.create_menu_bar()

        # Initialize engine with desired backend (default opengl)
        self.engine_widget = PygameWidget(backend_type="opengl")
        self.engine_widget.initialize_engine()

    def create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')
        new_act = QAction('New', self)
        new_act.triggered.connect(self.new_project)
        file_menu.addAction(new_act)

        open_act = QAction('Open', self)
        open_act.triggered.connect(self.open_project)
        file_menu.addAction(open_act)

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
        edit_menu.addAction('Undo')

        # View menu
        view_menu = menubar.addMenu('View')
        status_act = QAction('Status Bar', self, checkable=True)
        status_act.setChecked(True)
        view_menu.addAction(status_act)

        # Mode menu
        mode_menu = menubar.addMenu('Mode')
        mode_menu.addAction('Dark Mode')
        mode_menu.addAction('Light Mode')

        # Draw menu
        draw_menu = menubar.addMenu('Draw')
        draw_menu.addAction('Pen')
        draw_menu.addAction('Shapes')

        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        tools_menu.addAction('Options')

        # Help menu
        help_menu = menubar.addMenu('Help')
        about_act = QAction('About', self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(about_act)

    def new_project(self): print("New project")
    def open_project(self): print("Open project")
    def show_settings(self): print("Settings dialog")
    def show_about(self): print("NeoPyxel Engine v0.2")

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
