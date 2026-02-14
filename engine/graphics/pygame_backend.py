import pygame
from .backend import GraphicsBackend

class PygameBackend(GraphicsBackend):
    def __init__(self):
        self.internal_res = None
        self.screen_res = None
        self.internal_surface = None
        self.scaled_surface = None
        self.window = None

    def initialize(self, internal_res, screen_res, title="NeoPyxel"):
        self.internal_res = internal_res
        self.screen_res = screen_res
        self.internal_surface = pygame.Surface(internal_res)
        self.scaled_surface = pygame.Surface(screen_res)
        self.window = pygame.display.set_mode(screen_res, pygame.DOUBLEBUF | pygame.OPENGL)  # optional OpenGL flag
        pygame.display.set_caption(title)
        return self

    def begin_frame(self):
        self.internal_surface.fill((20, 20, 25))

    def draw_rect(self, rect, color):
        pygame.draw.rect(self.internal_surface, color, rect)

    def draw_surface(self, surface, rect):
        self.internal_surface.blit(surface, rect)

    def apply_lighting(self, light_mask):
        self.internal_surface.blit(light_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    def draw_text(self, text, position, color, font):
        text_surf = font.render(text, True, color)
        self.internal_surface.blit(text_surf, position)

    def end_frame(self):
        pygame.transform.scale(self.internal_surface, self.screen_res, self.scaled_surface)
        self.window.blit(self.scaled_surface, (0, 0))
        pygame.display.flip()

    def get_internal_surface(self):
        return self.internal_surface

    def cleanup(self):
        pygame.quit()