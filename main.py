import sys
import pygame
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QAction
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QPainter, QImage, QCursor

from engine.renderer import Renderer
from engine.lighting import DynamicLighting
from engine.core import EntityManager
from editor.ui import EditorUI

class PygameWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)  # ~60 FPS

        self.engine_renderer = None
        self.world = None
        self.lighting = None
        self.ui = None
        self.clock = pygame.time.Clock()
        self.scaled_surface = None

    def set_engine(self, renderer, world, lighting, ui):
        self.engine_renderer = renderer
        self.world = world
        self.lighting = lighting
        self.ui = ui

    def update_frame(self):
        if not self.engine_renderer:
            return

        # Game logic update
        self.world.update_all()

        # Dynamic lighting follows mouse
        mouse_pos = self.mapFromGlobal(QCursor.pos())
        self.lighting.clear()
        if self.rect().contains(mouse_pos):
            internal_res = self.engine_renderer.internal_res
            widget_size = self.size()
            scale_x = internal_res[0] / widget_size.width() if widget_size.width() else 1
            scale_y = internal_res[1] / widget_size.height() if widget_size.height() else 1
            internal_mouse = (int(mouse_pos.x() * scale_x), int(mouse_pos.y() * scale_y))
            self.lighting.add_light(internal_mouse, 60)

        # Render frame
        self.scaled_surface = self.engine_renderer.render(
            self.world.get_all(), self.lighting, self.ui, self.clock
        )
        self.clock.tick(60)          # Update clock for FPS
        self.update()                 # Trigger paint event

    def paintEvent(self, event):
        if self.scaled_surface:
            # Convert Pygame surface to QImage
            data = pygame.image.tostring(self.scaled_surface, 'RGB')
            image = QImage(data, self.scaled_surface.get_width(),
                           self.scaled_surface.get_height(), QImage.Format_RGB888)
            painter = QPainter(self)
            painter.drawImage(0, 0, image)
            painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.world:
            pos = event.pos()
            internal_res = self.engine_renderer.internal_res
            widget_size = self.size()
            scale_x = internal_res[0] / widget_size.width() if widget_size.width() else 1
            scale_y = internal_res[1] / widget_size.height() if widget_size.height() else 1
            internal_pos = (int(pos.x() * scale_x), int(pos.y() * scale_y))
            self.world.add_entity(internal_pos[0], internal_pos[1])

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NeoPyxel Engine - v0.1")
        self.setGeometry(100, 100, 1280, 720)

        # Initialize Pygame
        pygame.init()

        # Create engine components
        internal_res = (480, 270)   # Low-res for pixel art
        screen_res = (1280, 720)    # Output resolution
        self.renderer = Renderer(internal_res, screen_res)
        self.lighting = DynamicLighting(internal_res)
        self.world = EntityManager()
        self.ui = EditorUI(18)

        # Add a sample entity
        self.world.add_entity(100, 100, (255, 100, 100))

        # Central widget with Pygame surface
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.pygame_widget = PygameWidget()
        self.pygame_widget.set_engine(self.renderer, self.world, self.lighting, self.ui)
        layout.addWidget(self.pygame_widget)

        # Create menu bar
        self.create_menu_bar()

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

    # Placeholder actions
    def new_project(self): print("New project")
    def open_project(self): print("Open project")
    def show_settings(self): print("Settings dialog")
    def show_about(self): print("NeoPyxel Engine v0.1")

    def closeEvent(self, event):
        pygame.quit()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()