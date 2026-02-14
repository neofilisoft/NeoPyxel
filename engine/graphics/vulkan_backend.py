from .backend import GraphicsBackend

class VulkanBackend(GraphicsBackend):
    def __init__(self):
        raise NotImplementedError("Vulkan backend is a stub. Install Vulkan SDK and python-vulkan to use.")

    def initialize(self, internal_res, screen_res, title="NeoPyxel"):
        print("Vulkan backend not fully implemented. return OpenGLBackend.")
        # Fallback or raise error
        raise NotImplementedError("Vulkan backend is a stub.")

    def begin_frame(self):
        pass

    def draw_rect(self, rect, color):
        pass

    def draw_surface(self, surface, rect):
        pass

    def apply_lighting(self, light_mask):
        pass

    def draw_text(self, text, position, color, font):
        pass

    def end_frame(self):
        pass

    def get_internal_surface(self):
        return None

    def cleanup(self):
        pass
