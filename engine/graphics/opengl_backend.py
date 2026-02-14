import pygame
import moderngl
import numpy as np
from .backend import GraphicsBackend

class OpenGLBackend(GraphicsBackend):
    def __init__(self):
        self.ctx = None
        self.internal_res = None
        self.screen_res = None
        self.window = None
        self.program = None
        self.texture = None
        self.fbo = None

    def initialize(self, internal_res, screen_res, title="NeoPyxel"):
        self.internal_res = internal_res
        self.screen_res = screen_res

        # Pygame window with OpenGL context
        pygame.display.set_mode(screen_res, pygame.DOUBLEBUF | pygame.OPENGL)
        pygame.display.set_caption(title)
        self.ctx = moderngl.create_context()

        # Simple shader program (passthrough)
        self.program = self.ctx.program(
            vertex_shader='''
                #version 330
                in vec2 in_vert;
                in vec2 in_uv;
                out vec2 uv;
                void main() {
                    gl_Position = vec4(in_vert, 0.0, 1.0);
                    uv = in_uv;
                }
            ''',
            fragment_shader='''
                #version 330
                uniform sampler2D texture0;
                in vec2 uv;
                out vec4 f_color;
                void main() {
                    f_color = texture(texture0, uv);
                }
            '''
        )

        # Full-screen quad
        vertices = np.array([
            -1.0, -1.0, 0.0, 1.0,
             1.0, -1.0, 1.0, 1.0,
            -1.0,  1.0, 0.0, 0.0,
             1.0,  1.0, 1.0, 0.0,
        ], dtype='f4')
        self.vbo = self.ctx.buffer(vertices)
        self.vao = self.ctx.vertex_array(self.program, [(self.vbo, '2f 2f', 'in_vert', 'in_uv')])

        # Texture to render onto
        self.texture = self.ctx.texture(internal_res, 3)
        self.fbo = self.ctx.framebuffer(color_attachments=[self.texture])
        return self

    def begin_frame(self):
        self.fbo.clear(0.2, 0.2, 0.25, 1.0)  # dark background

    def draw_rect(self, rect, color):
        
        pass

    def draw_surface(self, surface, rect):
        # Convert pygame surface to texture and draw
        # This is complex; we'll keep it as a stub.
        pass

    def apply_lighting(self, light_mask):
        # Lighting would be done via shaders – stub
        pass

    def draw_text(self, text, position, color, font):
        # Text rendering requires texture atlases – stub
        pass

    def end_frame(self):
        self.ctx.screen.use()
        self.texture.use(0)
        self.vao.render(moderngl.TRIANGLE_STRIP)
        pygame.display.flip()

    def get_internal_surface(self):
        # Not directly available in OpenGL mode
        return None

    def cleanup(self):
        # Release OpenGL resources
        pass