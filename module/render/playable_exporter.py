def build_playable_script(scene_path, assets_path):
    scene_path = scene_path.replace("\\", "\\\\")
    assets_path = assets_path.replace("\\", "\\\\")
    return f"""import json
import os
import pygame

pygame.init()
screen = pygame.display.set_mode((1280, 720))
clock = pygame.time.Clock()

SCENE_PATH = r\"{scene_path}\"
ASSETS_DIR = r\"{assets_path}\"

with open(SCENE_PATH, \"r\", encoding=\"utf-8\") as f:
    scene = json.load(f)

entities = scene.get(\"entities\", [])
sprite_cache = {{}}

def get_sprite(rel_path):
    if rel_path in sprite_cache:
        return sprite_cache[rel_path]
    full = os.path.join(ASSETS_DIR, rel_path)
    try:
        spr = pygame.image.load(full)
        spr = spr.convert_alpha() if spr.get_alpha() is not None else spr.convert()
        sprite_cache[rel_path] = spr
        return spr
    except Exception:
        return None

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((20, 20, 25))
    for e in entities:
        x, y = e.get(\"x\", 0), e.get(\"y\", 0)
        w, h = e.get(\"w\", 16), e.get(\"h\", 16)
        sprite = e.get(\"sprite\")
        if sprite:
            spr = get_sprite(sprite)
            if spr:
                screen.blit(spr, (x, y))
                continue
        color = tuple(e.get(\"color\", [0, 255, 0]))
        pygame.draw.rect(screen, color, pygame.Rect(x, y, w, h))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
"""
