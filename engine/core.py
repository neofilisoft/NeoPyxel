import pygame

class Entity:
    def __init__(self, x, y, width, height, color=(0, 255, 0)):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.image = pygame.Surface((width, height))
        self.image.fill(self.color)

    def update(self):
        pass

class EntityManager:
    def __init__(self):
        self.entities = []

    def add_entity(self, x, y, color=(0, 255, 0)):
        new_entity = Entity(x, y, 16, 16, color)
        self.entities.append(new_entity)

    def update_all(self):
        for entity in self.entities:
            entity.update()

    def get_all(self):
        return self.entities
