import pygame

class EditorUI:
    def __init__(self, font_size=24):
        pygame.font.init()
        self.font = pygame.font.SysFont("NotoSans", font_size)
        self.ui_color = (255, 255, 255)

    def draw_status(self, backend, clock, info_dict):
        y_offset = 10
        info_dict["FPS"] = int(clock.get_fps())
        for key, value in info_dict.items():
            backend.draw_text(f"{key}: {value}", (10, y_offset), self.ui_color, self.font)
            y_offset += 25

    def draw_cursor_info(self, backend, pos):
        backend.draw_text(f"Pos: {pos}", (pos[0] + 10, pos[1] + 10), (200, 200, 0), self.font)
