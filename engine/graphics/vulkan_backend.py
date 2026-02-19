# engine/graphics/vulkan_backend.py
from .backend import GraphicsBackend
import warnings

class VulkanBackend(GraphicsBackend):
    def __init__(self):
        self.initialized = False

    def initialize(self, internal_res, screen_res, title="NeoPyxel"):
        warnings.warn("Vulkan backend is not fully implemented. Using OpenGL fallback.")
        # Fallback to OpenGL by importing and using it
        from .opengl_backend import OpenGLBackend
        self._fallback = OpenGLBackend()
        return self._fallback.initialize(internal_res, screen_res, title)

    def begin_frame(self):
        if hasattr(self, '_fallback'):
            return self._fallback.begin_frame()
        pass

    def draw_rect(self, rect, color):
        if hasattr(self, '_fallback'):
            return self._fallback.draw_rect(rect, color)
        pass

    def draw_surface(self, surface, rect):
        if hasattr(self, '_fallback'):
            return self._fallback.draw_surface(surface, rect)

    def apply_lighting(self, light_mask):
        if hasattr(self, '_fallback'):
            return self._fallback.apply_lighting(light_mask)

    def draw_text(self, text, position, color, font):
        if hasattr(self, '_fallback'):
            return self._fallback.draw_text(text, position, color, font)

    def end_frame(self):
        if hasattr(self, '_fallback'):
            return self._fallback.end_frame()

    def get_internal_surface(self):
        if hasattr(self, '_fallback'):
            return self._fallback.get_internal_surface()
        return None

    def cleanup(self):
        if hasattr(self, '_fallback'):
            return self._fallback.cleanup()
