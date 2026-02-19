import pygame

class DynamicLighting:
    def __init__(self, res):
        self.light_mask = pygame.Surface(res, pygame.SRCALPHA)
        self.lights = []

    def clear(self):
        self.light_mask.fill((30, 30, 50))  # ambient

    def add_light(self, pos, radius, color=(255, 200, 100)):
        light_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for r in range(radius, 0, -2):
            alpha = int(150 * (1 - r / radius))
            pygame.draw.circle(light_surf, (*color, alpha), (radius, radius), r)
        self.light_mask.blit(light_surf, (pos[0] - radius, pos[1] - radius), special_flags=pygame.BLEND_RGBA_ADD)

    def get_mask(self):
        return self.light_mask
