class Renderer:
    def __init__(self, backend, internal_res, screen_res):
        self.backend = backend
        self.internal_res = internal_res
        self.screen_res = screen_res
        self.backend.initialize(internal_res, screen_res)

    def render(self, entities, lighting=None, ui=None, clock=None):
        self.backend.begin_frame()

        # Draw entities
        for entity in entities:
            # For simplicity, assume entity.image is a pygame Surface
            self.backend.draw_surface(entity.image, entity.rect)

        # Apply lighting if any
        if lighting:
            # lighting.prepare() would be called earlier
            self.backend.apply_lighting(lighting.get_mask())

        # Draw UI if provided
        if ui and clock:
            # UI drawing methods now use backend's draw_text
            # We'll pass the backend to UI.draw_status
            ui.draw_status(self.backend, clock, {
                "FPS": int(clock.get_fps()),
                "Entities": len(entities)
            })

        self.backend.end_frame()
