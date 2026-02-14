import pygame

class EditorUI:
    def __init__(self, font_size=24):
        pygame.font.init()
        self.font = pygame.font.SysFont("NotoSans", font_size)
        self.ui_color = (255, 255, 255)

    def draw_status(self, surface, clock, info_dict):
        y_offset = 10
        info_dict["FPS"] = int(clock.get_fps())
        for key, value in info_dict.items():
            text_surf = self.font.render(f"{key}: {value}", True, self.ui_color)
            surface.blit(text_surf, (10, y_offset))
            y_offset += 25

    def draw_cursor_info(self, surface, pos):
        coord_text = self.font.render(f"Pos: {pos}", True, (200, 200, 0))
        surface.blit(coord_text, (pos[0] + 10, pos[1] + 10))
