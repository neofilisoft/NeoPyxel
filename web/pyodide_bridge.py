# web/pyodide_bridge.py
import sys
import pygame
from engine.core import EntityManager
from engine.lighting import DynamicLighting
from engine.graphics.renderer import Renderer
from engine.graphics.opengl_backend import OpenGLBackend  # WebGL ใช้ OpenGL ES ผ่าน Emscripten
from editor.ui import EditorUI

class PyodideBridge:
    def __init__(self, canvas):
        self.canvas = canvas
        self.world = EntityManager()
        self.lighting = DynamicLighting((480, 270))

        self.backend = OpenGLBackend() 
        self.renderer = Renderer(self.backend, (480, 270), (1280, 720))
        self.ui = EditorUI(18)
        self.clock = pygame.time.Clock()
        
    def create_entity(self, x, y, color):
        self.world.add_entity(x, y, tuple(color))

    def get_entities(self):
        return [{'x': e.rect.x, 'y': e.rect.y, 'color': e.color} for e in self.world.get_all()]

    def update(self, dt):
        self.world.update_all()
        # TODO: อ่าน events จาก JavaScript
        self.renderer.render(self.world.get_all(), self.lighting, self.ui, self.clock)
        self.clock.tick(60)