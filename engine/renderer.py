import pygame

class Renderer:
    def __init__(self, internal_res, screen_res):
        self.internal_res = internal_res
        self.screen_res = screen_res
        self.internal_surface = pygame.Surface(internal_res)
        self.scaled_surface = pygame.Surface(screen_res)

    def render(self, entities, lighting=None, ui=None, clock=None):
        """Render entities, apply lighting, draw UI, and return scaled surface."""
        self.internal_surface.fill((20, 20, 25))
        for entity in entities:
            self.internal_surface.blit(entity.image, entity.rect)

        if lighting:
            lighting.apply(self.internal_surface)

        if ui and clock:
            ui.draw_status(self.internal_surface, clock, {
                "FPS": int(clock.get_fps()),
                "Entities": len(entities)
            })

        pygame.transform.scale(self.internal_surface, self.screen_res, self.scaled_surface)
        return self.scaled_surface