import os

import pygame
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QWidget

from editor.ui import EditorUI
from engine.core import EntityManager
from engine.graphics.opengl_backend import OpenGLBackend
from engine.graphics.pygame_backend import PygameBackend
from engine.graphics.renderer import Renderer
from engine.graphics.vulkan_backend import VulkanBackend
from engine.lighting import DynamicLighting
from module.constants import IMAGE_EXTENSIONS
from module.widget.PygameWidget.tool_manager import ToolManager

class PygameWidget(QWidget):
    def __init__(self, parent=None, backend_type="pygame"):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)

        self.timer = QTimer()
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

        self.backend_type = backend_type
        self.renderer = None
        self.world = None
        self.lighting = None
        self.ui = None
        self.clock = pygame.time.Clock()
        self.qimage = None

        self.project_assets_dir = None

        self.draw_tool = "Select"
        self.is_drawing = False
        self.drag_start = None
        self.last_pen_pos = None
        self.current_stroke_entities = []
        self.undo_stack = []
        self.selected_index = -1

        self.snap_enabled = True
        self.show_grid = True
        self.grid_size = 16
        self.editor_lighting_enabled = False
        self.show_runtime_stats = False
        self.hover_internal_pos = None
        self.drag_asset_rel = None
        self.drag_asset_size = (32, 32)
        self.grid_cache_image = None
        self.grid_cache_key = None
        self.needs_redraw = True

        self.on_world_changed = None
        self.on_selection_changed = None
        self.on_message = None

    def initialize_engine(self):
        internal_res = (480, 270)
        screen_res = (960, 540)
        win_id = self.winId()

        if self.backend_type == "pygame":
            os.environ["SDL_WINDOWID"] = str(int(win_id))
            os.environ["SDL_VIDEODRIVER"] = "windib"
        else:
            os.environ.pop("SDL_WINDOWID", None)
            os.environ.pop("SDL_VIDEODRIVER", None)

        if self.backend_type == "pygame":
            backend = PygameBackend()
        elif self.backend_type == "opengl":
            backend = OpenGLBackend()
        elif self.backend_type == "vulkan":
            backend = VulkanBackend()
        else:
            backend = PygameBackend()

        if self.renderer:
            self.renderer.cleanup()
        self.renderer = Renderer(backend, internal_res, screen_res)
        self.lighting = DynamicLighting(internal_res)
        self.world = EntityManager()
        self.ui = EditorUI(16)
        self.undo_stack.clear()
        self.selected_index = -1
        self._notify_world_changed()

    def set_assets_dir(self, assets_dir):
        self.project_assets_dir = assets_dir

    def set_grid_settings(self, snap_enabled, show_grid, grid_size):
        self.snap_enabled = bool(snap_enabled)
        self.show_grid = bool(show_grid)
        self.grid_size = max(2, int(grid_size))
        self.grid_cache_image = None
        self.grid_cache_key = None
        self.needs_redraw = True
        self.update()

    def set_editor_lighting(self, enabled):
        self.editor_lighting_enabled = bool(enabled)
        self.needs_redraw = True

    def update_frame(self):
        if not self.renderer or not self.world:
            return

        if not self.editor_lighting_enabled and not self.needs_redraw:
            return

        try:
            pygame.event.pump()
        except Exception:
            pass
        self.world.update_all()

        active_lighting = None
        if self.editor_lighting_enabled:
            mouse_pos = self.mapFromGlobal(self.cursor().pos())
            self.lighting.clear()
            if self.rect().contains(mouse_pos):
                internal_pos = self._to_internal(mouse_pos)
                if internal_pos:
                    self.lighting.add_light(internal_pos, 60)
            active_lighting = self.lighting

        ui = self.ui if self.show_runtime_stats else None
        clock = self.clock if self.show_runtime_stats else None
        self.renderer.render(self.world.get_all(), active_lighting, ui, clock)
        self.clock.tick(60)

        if self.backend_type == "pygame" and hasattr(self.renderer.backend, "internal_surface"):
            surf = self.renderer.backend.internal_surface
            if surf:
                data = pygame.image.tostring(surf, "RGB")
                # Copy image buffer to avoid dangling-memory artifacts and draw with fast scaling in paintEvent.
                self.qimage = QImage(data, surf.get_width(), surf.get_height(), QImage.Format_RGB888).copy()

        self.needs_redraw = False
        self.update()

    def paintEvent(self, event):
        if self.backend_type == "pygame" and self.qimage:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
            painter.drawImage(self.rect(), self.qimage)
            self._draw_grid_overlay(painter)
            self._draw_preview_overlay(painter)
            return

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(20, 22, 28))
        painter.setPen(Qt.white)
        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            "OpenGL/Vulkan render in separate window.\\nUse Backend > PYGAME for embedded viewport.",
        )

    def _draw_grid_overlay(self, painter):
        if not (self.show_grid and self.renderer and self.grid_size > 1):
            return
        internal_w, internal_h = self.renderer.internal_res
        step_x = self.width() * (self.grid_size / max(1, internal_w))
        step_y = self.height() * (self.grid_size / max(1, internal_h))
        if step_x < 4 or step_y < 4:
            return

        key = (self.width(), self.height(), round(step_x, 3), round(step_y, 3))
        if self.grid_cache_key != key or self.grid_cache_image is None:
            img = QImage(self.width(), self.height(), QImage.Format_ARGB32_Premultiplied)
            img.fill(0)
            gp = QPainter(img)
            gp.setPen(QColor(95, 110, 140, 70))
            x = 0.0
            while x <= self.width():
                gp.drawLine(int(x), 0, int(x), self.height())
                x += step_x
            y = 0.0
            while y <= self.height():
                gp.drawLine(0, int(y), self.width(), int(y))
                y += step_y
            gp.end()
            self.grid_cache_key = key
            self.grid_cache_image = img

        painter.drawImage(0, 0, self.grid_cache_image)

    def _draw_preview_overlay(self, painter):
        if not self.renderer:
            return

        if self.is_drawing and self.draw_tool in ("Line", "Rect") and self.drag_start and self.hover_internal_pos:
            sx, sy = self._to_widget(self.drag_start)
            ex, ey = self._to_widget(self.hover_internal_pos)
            painter.setPen(QColor(100, 210, 255, 220))
            if self.draw_tool == "Line":
                painter.drawLine(sx, sy, ex, ey)
            else:
                left = min(sx, ex)
                right = max(sx, ex)
                top = min(sy, ey)
                bottom = max(sy, ey)
                painter.drawRect(left, top, max(1, right - left), max(1, bottom - top))

        if self.drag_asset_rel and self.hover_internal_pos:
            gx, gy = self._to_widget(self.hover_internal_pos)
            gw = max(8, int(self.drag_asset_size[0] * (self.width() / self.renderer.internal_res[0])))
            gh = max(8, int(self.drag_asset_size[1] * (self.height() / self.renderer.internal_res[1])))
            painter.setBrush(QColor(80, 180, 255, 70))
            painter.setPen(QColor(130, 210, 255, 180))
            painter.drawRect(gx, gy, gw, gh)

    def dragEnterEvent(self, event):
        text = event.mimeData().text()
        if text and text.lower().endswith(IMAGE_EXTENSIONS):
            rel = self._to_asset_relative(text)
            self.drag_asset_rel = rel
            if rel and self.project_assets_dir:
                loaded = self._load_sprite_surface(os.path.join(self.project_assets_dir, rel))
                if loaded:
                    self.drag_asset_size = loaded.get_size()
                else:
                    self.drag_asset_size = (32, 32)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        internal_pos = self._to_internal(event.pos())
        if internal_pos:
            snapped = self._apply_snap(internal_pos)
            if snapped != self.hover_internal_pos:
                self.hover_internal_pos = snapped
                self.needs_redraw = True
                self.update()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.drag_asset_rel = None
        self.hover_internal_pos = None
        self.needs_redraw = True
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        asset_path = event.mimeData().text()
        internal_pos = self._to_internal(event.pos())
        if not internal_pos or not asset_path:
            self.drag_asset_rel = None
            self.hover_internal_pos = None
            self.needs_redraw = True
            self.update()
            event.ignore()
            return

        rel_path = self._to_asset_relative(asset_path)
        if not rel_path:
            self._message("Drop failed: sprite must be inside project assets folder")
            self.drag_asset_rel = None
            self.hover_internal_pos = None
            self.needs_redraw = True
            self.update()
            event.ignore()
            return

        internal_pos = self._apply_snap(internal_pos)
        added = self.add_sprite_entity(internal_pos[0], internal_pos[1], rel_path)
        if not added:
            self._message("Drop failed: could not load sprite")
            self.drag_asset_rel = None
            self.hover_internal_pos = None
            self.needs_redraw = True
            self.update()
            event.ignore()
            return

        self._message(f"Sprite added: {rel_path}")
        self.drag_asset_rel = None
        self.hover_internal_pos = None
        self.needs_redraw = True
        self.update()
        event.acceptProposedAction()

    def leaveEvent(self, event):
        self.hover_internal_pos = None
        self.needs_redraw = True
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if not (self.world and self.renderer):
            return
        internal_pos = self._to_internal(event.pos())
        if not internal_pos:
            return
        internal_pos = self._apply_snap(internal_pos)
        self.hover_internal_pos = internal_pos
        self.needs_redraw = True

        if event.button() == Qt.LeftButton:
            self.is_drawing = True
            self.drag_start = internal_pos
            self.last_pen_pos = internal_pos
            self.current_stroke_entities = []

            if self.draw_tool == "Select":
                index = self._find_nearest_entity(internal_pos[0], internal_pos[1], radius=20)
                self.set_selected_index(index)
                self.is_drawing = False
            elif self.draw_tool == "Pen":
                entity = self._add_rect_entity(
                    internal_pos[0],
                    internal_pos[1],
                    ToolManager.color_for("Pen"),
                )
                if entity:
                    self.current_stroke_entities.append(entity)
            elif self.draw_tool == "Eraser":
                removed = self._remove_nearest_entity(internal_pos[0], internal_pos[1], radius=20)
                if removed:
                    self.undo_stack.append({"type": "remove", "entities": removed})
                    self._notify_world_changed()
        elif event.button() == Qt.RightButton:
            removed = self._remove_nearest_entity(internal_pos[0], internal_pos[1], radius=20)
            if removed:
                self.undo_stack.append({"type": "remove", "entities": removed})
                self._notify_world_changed()

    def mouseMoveEvent(self, event):
        if not (self.world and self.renderer):
            return
        internal_pos = self._to_internal(event.pos())
        if internal_pos:
            snapped = self._apply_snap(internal_pos)
            if snapped != self.hover_internal_pos:
                self.hover_internal_pos = snapped
                self.needs_redraw = True
                self.update()
        if not self.is_drawing:
            return
        if self.draw_tool != "Pen":
            return
        if not (event.buttons() & Qt.LeftButton):
            return

        internal_pos = self._to_internal(event.pos())
        if not internal_pos:
            return
        internal_pos = self._apply_snap(internal_pos)
        if self.last_pen_pos and self._distance_sq(internal_pos, self.last_pen_pos) < 20:
            return

        entity = self._add_rect_entity(internal_pos[0], internal_pos[1], (60, 230, 120))
        if entity:
            self.current_stroke_entities.append(entity)
            self.last_pen_pos = internal_pos
            self._notify_world_changed()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self.is_drawing:
            return

        self.is_drawing = False
        end_pos = self._to_internal(event.pos()) or self.drag_start
        if not end_pos or not self.drag_start:
            return
        end_pos = self._apply_snap(end_pos)

        if self.draw_tool == "Line":
            added = self._draw_line_entities(self.drag_start, end_pos)
            if added:
                self.undo_stack.append({"type": "add", "entities": added})
                self._notify_world_changed()
        elif self.draw_tool == "Rect":
            added = self._draw_rect_entities(self.drag_start, end_pos)
            if added:
                self.undo_stack.append({"type": "add", "entities": added})
                self._notify_world_changed()
        elif self.draw_tool == "Pen" and self.current_stroke_entities:
            self.undo_stack.append({"type": "add", "entities": list(self.current_stroke_entities)})

        self.drag_start = None
        self.last_pen_pos = None
        self.current_stroke_entities = []
        self.hover_internal_pos = None
        self.needs_redraw = True
        self.update()

    def set_draw_tool(self, tool_name):
        self.draw_tool = tool_name

    def set_selected_index(self, index):
        if not self.world:
            self.selected_index = -1
        elif 0 <= index < len(self.world.entities):
            self.selected_index = index
        else:
            self.selected_index = -1
        if self.on_selection_changed:
            self.on_selection_changed(self.selected_index)

    def add_rect_entity(self, x, y, width=16, height=16, color=(0, 255, 0)):
        x, y = self._apply_snap((x, y))
        entity = self._add_rect_entity(x, y, color)
        if entity:
            entity.rect.width = width
            entity.rect.height = height
            entity.image = pygame.Surface((width, height))
            entity.image.fill(color)
            entity.sprite_path = None
            self._notify_world_changed()
            self.set_selected_index(len(self.world.entities) - 1)
        return entity

    def add_sprite_entity(self, x, y, sprite_rel_path):
        if not self.project_assets_dir:
            return None
        x, y = self._apply_snap((x, y))
        sprite_abs_path = os.path.join(self.project_assets_dir, sprite_rel_path)
        surface = self._load_sprite_surface(sprite_abs_path)
        if not surface:
            return None

        self.world.add_entity(x, y, (255, 255, 255))
        entity = self.world.entities[-1]
        entity.image = surface
        entity.rect.width = surface.get_width()
        entity.rect.height = surface.get_height()
        entity.color = (255, 255, 255)
        entity.sprite_path = sprite_rel_path.replace("\\", "/")

        self.undo_stack.append({"type": "add", "entities": [entity]})
        self._notify_world_changed()
        self.set_selected_index(len(self.world.entities) - 1)
        return entity

    def delete_selected_entity(self):
        if not self.world:
            return False
        if 0 <= self.selected_index < len(self.world.entities):
            entity = self.world.entities.pop(self.selected_index)
            data = [self._snapshot_entity(entity)]
            self.undo_stack.append({"type": "remove_full", "entities": data})
            self.set_selected_index(-1)
            self._notify_world_changed()
            return True
        return False

    def update_selected_entity(self, x, y, w, h, color):
        if not self.world:
            return False
        if not (0 <= self.selected_index < len(self.world.entities)):
            return False
        entity = self.world.entities[self.selected_index]
        entity.rect.x = x
        entity.rect.y = y

        if getattr(entity, "sprite_path", None):
            entity.color = (255, 255, 255)
        else:
            entity.rect.width = w
            entity.rect.height = h
            entity.color = tuple(color)
            entity.image = pygame.Surface((w, h))
            entity.image.fill(entity.color)

        self._notify_world_changed()
        return True

    def clear_scene(self):
        if not self.world:
            return
        self.world.entities.clear()
        self.undo_stack.clear()
        self.set_selected_index(-1)
        self._notify_world_changed()

    def get_scene_data(self):
        if not self.world:
            return []
        data = []
        for entity in self.world.entities:
            sprite_path = getattr(entity, "sprite_path", None)
            data.append(
                {
                    "x": entity.rect.x,
                    "y": entity.rect.y,
                    "w": entity.rect.width,
                    "h": entity.rect.height,
                    "color": [int(entity.color[0]), int(entity.color[1]), int(entity.color[2])],
                    "sprite": sprite_path,
                }
            )
        return data

    def load_scene_data(self, entities):
        self.clear_scene()
        for item in entities:
            x = int(item.get("x", 0))
            y = int(item.get("y", 0))
            sprite = item.get("sprite")
            if sprite:
                added = self.add_sprite_entity(x, y, sprite)
                if added:
                    continue
            w = max(1, int(item.get("w", 16)))
            h = max(1, int(item.get("h", 16)))
            color = item.get("color", [0, 255, 0])
            color = (int(color[0]), int(color[1]), int(color[2]))
            self.add_rect_entity(x, y, w, h, color)

        self.undo_stack.clear()
        self.set_selected_index(-1)

    def undo_last(self):
        if not self.world or not self.undo_stack:
            return False
        action = self.undo_stack.pop()

        if action["type"] == "add":
            for entity in action["entities"]:
                if entity in self.world.entities:
                    self.world.entities.remove(entity)
            self._notify_world_changed()
            return True

        if action["type"] in ("remove", "remove_full"):
            for saved in action["entities"]:
                self._restore_entity(saved)
            self._notify_world_changed()
            return True

        return False

    def _to_internal(self, qt_pos):
        if not self.renderer:
            return None
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return None
        internal_res = self.renderer.internal_res
        scale_x = internal_res[0] / w
        scale_y = internal_res[1] / h
        return (int(qt_pos.x() * scale_x), int(qt_pos.y() * scale_y))

    def _to_widget(self, internal_pos):
        if not self.renderer:
            return (0, 0)
        internal_w, internal_h = self.renderer.internal_res
        x = int((internal_pos[0] / max(1, internal_w)) * self.width())
        y = int((internal_pos[1] / max(1, internal_h)) * self.height())
        return (x, y)

    def _apply_snap(self, pos):
        if not self.snap_enabled or self.grid_size <= 1:
            return (int(pos[0]), int(pos[1]))
        gx = int(round(pos[0] / self.grid_size) * self.grid_size)
        gy = int(round(pos[1] / self.grid_size) * self.grid_size)
        return (gx, gy)

    def _to_asset_relative(self, asset_path):
        if not self.project_assets_dir:
            return None
        try:
            rel = os.path.relpath(asset_path, self.project_assets_dir)
            if rel.startswith(".."):
                return None
            return rel
        except Exception:
            return None

    def _add_rect_entity(self, x, y, color):
        self.world.add_entity(x, y, color)
        entity = self.world.entities[-1] if self.world.entities else None
        if entity:
            entity.sprite_path = None
        return entity

    def _load_sprite_surface(self, abs_path):
        if not os.path.exists(abs_path):
            return None
        try:
            loaded = pygame.image.load(abs_path)
            display_ready = pygame.display.get_init() and pygame.display.get_surface() is not None
            if not display_ready:
                return loaded
            if loaded.get_alpha() is not None:
                return loaded.convert_alpha()
            return loaded.convert()
        except Exception:
            return None

    def _restore_entity(self, saved):
        sprite_path = saved.get("sprite")
        if sprite_path:
            added = self.add_sprite_entity(saved["x"], saved["y"], sprite_path)
            if added:
                return
        self.add_rect_entity(
            saved["x"],
            saved["y"],
            saved.get("w", 16),
            saved.get("h", 16),
            tuple(saved.get("color", [0, 255, 0])),
        )

    def _snapshot_entity(self, entity):
        return {
            "x": int(entity.rect.x),
            "y": int(entity.rect.y),
            "w": int(entity.rect.width),
            "h": int(entity.rect.height),
            "color": [int(entity.color[0]), int(entity.color[1]), int(entity.color[2])],
            "sprite": getattr(entity, "sprite_path", None),
        }

    def _draw_line_entities(self, start, end):
        added = []
        for x, y in ToolManager.line_points(start, end, step=8):
            entity = self._add_rect_entity(x, y, ToolManager.color_for("Line"))
            if entity:
                added.append(entity)
        return added

    def _draw_rect_entities(self, start, end):
        added = []
        for x, y in ToolManager.rect_border_points(start, end, step=8):
            entity = self._add_rect_entity(x, y, ToolManager.color_for("Rect"))
            if entity:
                added.append(entity)
        return added

    def _find_nearest_entity(self, x, y, radius=20):
        if not self.world or not self.world.entities:
            return -1
        nearest = -1
        best = radius * radius
        for i, entity in enumerate(self.world.entities):
            cx, cy = entity.rect.centerx, entity.rect.centery
            d = (cx - x) * (cx - x) + (cy - y) * (cy - y)
            if d <= best:
                best = d
                nearest = i
        return nearest

    def _remove_nearest_entity(self, x, y, radius=20):
        idx = self._find_nearest_entity(x, y, radius)
        if idx < 0:
            return []
        entity = self.world.entities.pop(idx)
        self.set_selected_index(-1)
        return [self._snapshot_entity(entity)]

    def _distance_sq(self, a, b):
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        return dx * dx + dy * dy

    def _notify_world_changed(self):
        self.needs_redraw = True
        if self.on_world_changed:
            self.on_world_changed(self.get_scene_data())

    def _message(self, msg):
        if self.on_message:
            self.on_message(msg)

