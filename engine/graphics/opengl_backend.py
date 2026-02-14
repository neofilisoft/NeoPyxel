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
        self.depth_tex = None
        self.post_fbo = None          # For post-processing
        self.post_texture = None
        self.bloom_fbo = None
        self.bloom_texture = None
        self.sprite_shader = None
        self.text_shader = None
        self.dof_shader = None
        self.quad_vao = None
        self.sprite_batch = []        # Temporary batching list

    def initialize(self, internal_res, screen_res, title="NeoPyxel"):
        self.internal_res = internal_res
        self.screen_res = screen_res

        # Create Pygame window with OpenGL context
        pygame.display.set_mode(screen_res, pygame.DOUBLEBUF | pygame.OPENGL)
        pygame.display.set_caption(title)
        self.ctx = moderngl.create_context()

        # Full-screen quad for post-processing
        vertices = np.array([
            -1.0, -1.0, 0.0, 1.0,
             1.0, -1.0, 1.0, 1.0,
            -1.0,  1.0, 0.0, 0.0,
             1.0,  1.0, 1.0, 0.0,
        ], dtype='f4')
        self.vbo = self.ctx.buffer(vertices)
        self.quad_vao = self.ctx.vertex_array(
            self.ctx.program(
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
            ),
            [(self.vbo, '2f 2f', 'in_vert', 'in_uv')]
        )

        # Main framebuffer (color + depth)
        self.texture = self.ctx.texture(internal_res, 3)
        self.depth_tex = self.ctx.depth_texture(internal_res)
        self.fbo = self.ctx.framebuffer(color_attachments=[self.texture], depth_attachment=self.depth_tex)

        # Post-processing framebuffer
        self.post_texture = self.ctx.texture(internal_res, 3)
        self.post_fbo = self.ctx.framebuffer(color_attachments=[self.post_texture])

        # Bloom framebuffer (optional)
        self.bloom_texture = self.ctx.texture(internal_res, 4)
        self.bloom_fbo = self.ctx.framebuffer(color_attachments=[self.bloom_texture])

        # Sprite shader (simple textured quad)
        self.sprite_shader = self.ctx.program(
            vertex_shader='''
                #version 330
                in vec2 in_pos;
                in vec2 in_uv;
                uniform mat4 projection;
                out vec2 uv;
                void main() {
                    gl_Position = projection * vec4(in_pos, 0.0, 1.0);
                    uv = in_uv;
                }
            ''',
            fragment_shader='''
                #version 330
                uniform sampler2D sprite_tex;
                in vec2 uv;
                out vec4 f_color;
                void main() {
                    f_color = texture(sprite_tex, uv);
                }
            '''
        )
        self.sprite_shader['projection'].write(self._ortho_matrix().astype('f4').tobytes())

        # Text shader (similar to sprite, but with color modulation)
        self.text_shader = self.ctx.program(
            vertex_shader='''
                #version 330
                in vec2 in_pos;
                in vec2 in_uv;
                uniform mat4 projection;
                out vec2 uv;
                void main() {
                    gl_Position = projection * vec4(in_pos, 0.0, 1.0);
                    uv = in_uv;
                }
            ''',
            fragment_shader='''
                #version 330
                uniform sampler2D text_tex;
                uniform vec4 text_color;
                in vec2 uv;
                out vec4 f_color;
                void main() {
                    vec4 tex = texture(text_tex, uv);
                    f_color = vec4(text_color.rgb, tex.a * text_color.a);
                }
            '''
        )
        self.text_shader['projection'].write(self._ortho_matrix().astype('f4').tobytes())

        # DOF shader (using depth texture)
        self.dof_shader = self.ctx.program(
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
                uniform sampler2D colorTex;
                uniform sampler2D depthTex;
                uniform float focalDistance;
                uniform float focalRange;
                in vec2 uv;
                out vec4 f_color;

                vec4 blur(sampler2D tex, vec2 uv, float amount) {
                    // Simple 3x3 box blur
                    vec4 col = vec4(0.0);
                    float step = amount * 0.002;
                    for (int x = -1; x <= 1; x++) {
                        for (int y = -1; y <= 1; y++) {
                            col += texture(tex, uv + vec2(x*step, y*step));
                        }
                    }
                    return col / 9.0;
                }

                void main() {
                    float depth = texture(depthTex, uv).r;
                    float blurAmount = smoothstep(0.0, focalRange, abs(depth - focalDistance));
                    f_color = blur(colorTex, uv, blurAmount);
                }
            '''
        )

        return self

    def _ortho_matrix(self):
        left, right = 0, self.internal_res[0]
        bottom, top = self.internal_res[1], 0  # flip Y to match pygame
        near, far = -1, 1
        return np.array([
            [2/(right-left), 0, 0, -(right+left)/(right-left)],
            [0, 2/(top-bottom), 0, -(top+bottom)/(top-bottom)],
            [0, 0, -2/(far-near), -(far+near)/(far-near)],
            [0, 0, 0, 1]
        ], dtype='f4')

    def begin_frame(self):
        self.fbo.use()
        self.fbo.clear(0.2, 0.2, 0.25, 1.0)
        self.sprite_batch.clear()

    def draw_surface(self, surface, rect):
        """Convert pygame Surface to texture and queue for rendering."""
        # Convert surface to raw RGBA data
        mode = 'RGBA' if surface.get_flags() & pygame.SRCALPHA else 'RGB'
        data = pygame.image.tostring(surface, mode, True)
        tex = self.ctx.texture(surface.get_size(), 4 if mode == 'RGBA' else 3, data)
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

        # For performance, we should batch sprites. Here we just draw now.
        self._draw_textured_quad(tex, rect)

    def _draw_textured_quad(self, tex, rect):
        """Helper to draw a textured quad at rect using sprite shader."""
        # Create vertex data for one quad (position and uv)
        x, y, w, h = rect.x, rect.y, rect.width, rect.height
        vertices = np.array([
            x,   y,   0, 0,
            x+w, y,   1, 0,
            x,   y+h, 0, 1,
            x+w, y+h, 1, 1
        ], dtype='f4')
        vbo = self.ctx.buffer(vertices)
        vao = self.ctx.vertex_array(self.sprite_shader, [(vbo, '2f 2f', 'in_pos', 'in_uv')])
        tex.use(0)
        vao.render(moderngl.TRIANGLE_STRIP)

    def draw_rect(self, rect, color):
        """Draw a filled rectangle using a temporary texture."""
        # Create a small 1x1 texture with the color
        surf = pygame.Surface((1, 1))
        surf.fill(color)
        self.draw_surface(surf, rect)

    def draw_text(self, text, position, color, font):
        """Render text using pygame.font and draw as texture."""
        if not text:
            return
        surf = font.render(text, True, color)
        # Position is top-left
        rect = pygame.Rect(position[0], position[1], surf.get_width(), surf.get_height())
        self.draw_surface(surf, rect)

    def apply_lighting(self, light_mask):
        """Apply light mask by blending with main texture using a shader."""
        # Convert light_mask (pygame Surface) to texture
        data = pygame.image.tostring(light_mask, 'RGBA', True)
        light_tex = self.ctx.texture(light_mask.get_size(), 4, data)
        light_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

        # Render main texture with light multiplication
        self.post_fbo.use()
        self.post_fbo.clear()
        self.texture.use(0)
        light_tex.use(1)
        # Use a simple shader that multiplies color by light alpha? 
        # For now, just blit main texture (no lighting) - placeholder
        # In real implementation, you'd use a shader that does color * light
        self.quad_vao.render(moderngl.TRIANGLE_STRIP)

        # Swap: post_fbo becomes the main texture for next steps
        self.texture, self.post_texture = self.post_texture, self.texture
        self.fbo, self.post_fbo = self.post_fbo, self.fbo

    def end_frame(self):
        # Apply post-processing (DOF)
        # Bind main texture and depth texture
        self.fbo.use()  # but we want to render to screen? Actually we need to render to screen with DOF.
        # We'll do: render main texture to screen using DOF shader
        self.ctx.screen.use()
        self.ctx.screen.clear()
        self.texture.use(0)
        self.depth_tex.use(1)
        self.dof_shader['colorTex'] = 0
        self.dof_shader['depthTex'] = 1
        self.dof_shader['focalDistance'] = 0.5   # Example values
        self.dof_shader['focalRange'] = 0.3
        self.quad_vao.render(moderngl.TRIANGLE_STRIP)
        pygame.display.flip()

    def get_internal_surface(self):
        # Not directly available in OpenGL mode; return None
        return None

    def cleanup(self):
        # Release OpenGL resources (automatic in Python, but can be explicit)
        pass
