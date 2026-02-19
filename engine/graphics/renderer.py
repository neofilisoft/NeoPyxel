class Renderer:
    def __init__(self, backend, internal_res, screen_res):
        self.backend = backend
        self.internal_res = internal_res
        self.screen_res = screen_res
        self.backend.initialize(internal_res, screen_res)

    def render(self, entities, lighting=None, ui=None, clock=None):
        self.backend.begin_frame()
        for entity in entities:
            self.backend.draw_surface(entity.image, entity.rect)
        if lighting:
            self.backend.apply_lighting(lighting.get_mask())
        if ui and clock:
            ui.draw_status(self.backend, clock, {"Entities": len(entities)})
        self.backend.end_frame()
