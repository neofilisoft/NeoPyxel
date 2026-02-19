
import json
import importlib.util
import os
import subprocess
import sys
import time

import pygame
from PyQt5.QtCore import QMimeData, Qt, QTimer
from PyQt5.QtGui import QColor, QDrag, QImage, QPainter
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from editor.ui import EditorUI
from engine.core import EntityManager
from engine.graphics.opengl_backend import OpenGLBackend
from engine.graphics.pygame_backend import PygameBackend
from engine.graphics.renderer import Renderer
from engine.graphics.vulkan_backend import VulkanBackend
from engine.lighting import DynamicLighting

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")


class PluginManager:
    def __init__(self, host_window):
        self.host_window = host_window
        self.modules = []
        self.instances = []

    def _log(self, message):
        try:
            self.host_window.set_status(message)
        except Exception:
            pass

    def _plugin_dirs(self, runtime_base_dir):
        candidates = [
            os.path.join(runtime_base_dir, "Plugins"),
            os.path.join(runtime_base_dir, "plugins"),
            os.path.join(runtime_base_dir, "Resource", "Plugins"),
            os.path.join(runtime_base_dir, "Resource", "plugins"),
        ]
        seen = set()
        unique = []
        for path in candidates:
            norm = os.path.normcase(os.path.abspath(path))
            if norm in seen:
                continue
            seen.add(norm)
            unique.append(path)
        return unique

    def load_plugins(self, runtime_base_dir):
        self.modules = []
        self.instances = []
        loaded_count = 0

        for plugin_dir in self._plugin_dirs(runtime_base_dir):
            if not os.path.isdir(plugin_dir):
                continue

            for filename in sorted(os.listdir(plugin_dir)):
                if not filename.endswith(".py") or filename.startswith("_"):
                    continue
                full_path = os.path.join(plugin_dir, filename)
                module_key = os.path.splitext(filename)[0]
                module_name = f"neopyxel_plugin_{module_key}_{loaded_count}"
                try:
                    spec = importlib.util.spec_from_file_location(module_name, full_path)
                    if not spec or not spec.loader:
                        self._log(f"Plugin skipped (invalid spec): {filename}")
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self.modules.append(module)

                    if hasattr(module, "register"):
                        module.register(self.host_window)
                    if hasattr(module, "Plugin"):
                        self.instances.append(module.Plugin())

                    loaded_count += 1
                    self._log(f"Plugin loaded: {filename}")
                except Exception as exc:
                    self._log(f"Plugin load failed: {filename} ({exc})")

        self._log(f"Plugin system ready: {loaded_count} plugin(s)")

    def emit(self, hook_name, *args, **kwargs):
        for module in self.modules:
            try:
                hook = getattr(module, hook_name, None)
                if callable(hook):
                    hook(*args, **kwargs)
            except Exception as exc:
                self._log(f"Plugin hook error: {module.__name__}.{hook_name} ({exc})")

        for instance in self.instances:
            try:
                hook = getattr(instance, hook_name, None)
                if callable(hook):
                    hook(*args, **kwargs)
            except Exception as exc:
                self._log(
                    f"Plugin hook error: {instance.__class__.__name__}.{hook_name} ({exc})"
                )


class AssetListWidget(QListWidget):
    def startDrag(self, supported_actions):
        item = self.currentItem()
        if not item:
            return
        asset_path = item.data(Qt.UserRole)
        if not asset_path:
            return

        mime = QMimeData()
        mime.setText(asset_path)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.CopyAction)


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
                entity = self._add_rect_entity(internal_pos[0], internal_pos[1], (60, 230, 120))
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
        x0, y0 = start
        x1, y1 = end
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy)) // 8 + 1
        added = []
        for i in range(steps + 1):
            t = i / max(steps, 1)
            x = int(x0 + dx * t)
            y = int(y0 + dy * t)
            entity = self._add_rect_entity(x, y, (80, 220, 255))
            if entity:
                added.append(entity)
        return added

    def _draw_rect_entities(self, start, end):
        left = min(start[0], end[0])
        right = max(start[0], end[0])
        top = min(start[1], end[1])
        bottom = max(start[1], end[1])
        added = []
        step = 8
        for x in range(left, right + 1, step):
            e1 = self._add_rect_entity(x, top, (255, 190, 60))
            e2 = self._add_rect_entity(x, bottom, (255, 190, 60))
            if e1:
                added.append(e1)
            if e2:
                added.append(e2)
        for y in range(top, bottom + 1, step):
            e1 = self._add_rect_entity(left, y, (255, 190, 60))
            e2 = self._add_rect_entity(right, y, (255, 190, 60))
            if e1:
                added.append(e1)
            if e2:
                added.append(e2)
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NeoPyxel Studio - v1.0")
        self.setGeometry(100, 100, 1500, 880)
        self.showMaximized()

        self.current_project_dir = None
        self.current_project_name = None
        self.current_metadata_file = "project.npl"
        self.current_scene_name = "main.json"
        self.main_scene_name = "main.json"
        self.scene_files = ["main.json"]
        self.backend_preview_processes = []

        pygame.init()
        self.engine_widget = PygameWidget(backend_type="pygame")
        self.engine_widget.on_world_changed = self.refresh_entity_list
        self.engine_widget.on_selection_changed = self.on_viewport_selection_changed
        self.engine_widget.on_message = self.set_status
        self.setCentralWidget(self.engine_widget)
        self.engine_widget.hide()

        self.apply_dark_theme()
        self.create_menu_bar()
        self.create_docks()
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_plugins(self.get_runtime_base_dir())
        self.plugin_manager.emit("on_app_start", self)
        self.on_grid_settings_changed()
        self.set_status("No project loaded. Use File > New or File > Open.")

    def apply_dark_theme(self):
        self.setStyleSheet(
            """
            QMainWindow { background-color: #11151e; color: #d6dae3; }
            QMenuBar { background-color: #151b25; color: #d6dae3; padding: 4px; }
            QMenuBar::item:selected { background: #283244; }
            QMenu { background-color: #151b25; color: #d6dae3; border: 1px solid #2a3446; }
            QMenu::item:selected { background-color: #283244; }
            QMenu#backend_menu::indicator {
                width: 10px;
                height: 10px;
                border-radius: 5px;
                margin-left: 6px;
                image: none;
            }
            QMenu#backend_menu::indicator:unchecked {
                border: 1px solid #4a5d7a;
                background: transparent;
            }
            QMenu#backend_menu::indicator:checked {
                border: 1px solid #75a7ff;
                background: #75a7ff;
            }
            QMessageBox {
                background-color: #121924;
            }
            QMessageBox QLabel {
                color: #e8f1ff;
                font-size: 12px;
            }
            QDockWidget { color: #d6dae3; border: 1px solid #222c3d; titlebar-close-icon: none; }
            QDockWidget::title { background: #171f2c; padding: 6px; text-align: left; }
            QListWidget, QTextEdit, QComboBox, QSpinBox {
                background-color: #121924;
                color: #cfd8e6;
                border: 1px solid #2b384e;
                selection-background-color: #28405d;
            }
            QPushButton {
                background-color: #1f2d40;
                color: #dbe7ff;
                border: 1px solid #35506f;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #2b3d55; }
            QLabel { color: #b9c8df; }
            QCheckBox { color: #cfd8e6; spacing: 6px; }
            QStatusBar { background-color: #141b27; color: #9fb7d7; }
            """
        )

    def create_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        new_act = QAction("New Project", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self.new_project)
        file_menu.addAction(new_act)

        open_act = QAction("Open Project", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_project)
        file_menu.addAction(open_act)

        save_act = QAction("Save", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_project)
        file_menu.addAction(save_act)

        file_menu.addSeparator()

        export_act = QAction("Export Playable", self)
        export_act.triggered.connect(self.export_playable_script)
        file_menu.addAction(export_act)

        file_menu.addSeparator()

        exit_act = QAction("Exit", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        scene_menu = menubar.addMenu("Scene")
        new_scene_act = QAction("New Scene", self)
        new_scene_act.triggered.connect(self.new_scene)
        scene_menu.addAction(new_scene_act)

        set_main_act = QAction("Set As Main Scene", self)
        set_main_act.triggered.connect(self.set_current_as_main_scene)
        scene_menu.addAction(set_main_act)

        edit_menu = menubar.addMenu("Edit")
        undo_act = QAction("Undo", self)
        undo_act.setShortcut("Ctrl+Z")
        undo_act.triggered.connect(self.undo_action)
        edit_menu.addAction(undo_act)

        delete_act = QAction("Delete Selected", self)
        delete_act.setShortcut("Del")
        delete_act.triggered.connect(self.delete_selected_entity)
        edit_menu.addAction(delete_act)

        tools_menu = menubar.addMenu("Tools")
        draw_group = QActionGroup(self)
        draw_group.setExclusive(True)
        for tool in ["Select", "Pen", "Line", "Rect", "Eraser"]:
            act = QAction(tool, self, checkable=True)
            act.triggered.connect(lambda checked, t=tool: self.set_draw_tool(t))
            if tool == "Select":
                act.setChecked(True)
            draw_group.addAction(act)
            tools_menu.addAction(act)

        backend_menu = menubar.addMenu("Backend")
        backend_menu.setObjectName("backend_menu")
        self.backend_actions = {}
        backend_group = QActionGroup(self)
        backend_group.setExclusive(True)
        for backend in ["pygame", "opengl", "vulkan"]:
            act = QAction(backend.upper(), self, checkable=True)
            act.setChecked(backend == self.engine_widget.backend_type)
            act.triggered.connect(lambda checked, b=backend: self.switch_backend(b))
            self.backend_actions[backend] = act
            backend_group.addAction(act)
            backend_menu.addAction(act)

        help_menu = menubar.addMenu("Help")
        about_act = QAction("About", self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(about_act)

    def create_docks(self):
        self.scene_dock = QDockWidget("Scene Graph", self)
        self.scene_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        scene_widget = QWidget()
        scene_layout = QVBoxLayout(scene_widget)

        scene_layout.addWidget(QLabel("Scene File"))
        self.scene_selector = QComboBox()
        self.scene_selector.currentIndexChanged.connect(self.on_scene_selector_changed)
        scene_layout.addWidget(self.scene_selector)

        self.main_scene_label = QLabel("Main Scene: main.json")
        scene_layout.addWidget(self.main_scene_label)

        scene_layout.addWidget(QLabel("Grid / Snap"))
        self.show_grid_checkbox = QCheckBox("Show Grid")
        self.show_grid_checkbox.setChecked(True)
        self.show_grid_checkbox.toggled.connect(self.on_grid_settings_changed)
        scene_layout.addWidget(self.show_grid_checkbox)

        self.snap_checkbox = QCheckBox("Snap To Grid")
        self.snap_checkbox.setChecked(True)
        self.snap_checkbox.toggled.connect(self.on_grid_settings_changed)
        scene_layout.addWidget(self.snap_checkbox)

        self.lighting_checkbox = QCheckBox("Editor Lighting")
        self.lighting_checkbox.setChecked(False)
        self.lighting_checkbox.toggled.connect(self.on_grid_settings_changed)
        scene_layout.addWidget(self.lighting_checkbox)

        self.grid_size_spin = self._make_spin(4, 128, 16)
        self.grid_size_spin.setSingleStep(4)
        self.grid_size_spin.valueChanged.connect(self.on_grid_settings_changed)
        scene_layout.addWidget(QLabel("Grid Size"))
        scene_layout.addWidget(self.grid_size_spin)

        scene_layout.addWidget(QLabel("Entities"))
        self.entity_list = QListWidget()
        self.entity_list.currentRowChanged.connect(self.on_entity_row_changed)
        scene_layout.addWidget(self.entity_list)

        add_btn = QPushButton("Add Entity")
        add_btn.clicked.connect(self.add_entity_dialog)
        scene_layout.addWidget(add_btn)

        del_btn = QPushButton("Delete Entity")
        del_btn.clicked.connect(self.delete_selected_entity)
        scene_layout.addWidget(del_btn)

        self.scene_dock.setWidget(scene_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.scene_dock)

        self.assets_dock = QDockWidget("Assets", self)
        self.assets_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        assets_widget = QWidget()
        assets_layout = QVBoxLayout(assets_widget)
        self.assets_path_label = QLabel("assets: -")
        assets_layout.addWidget(self.assets_path_label)

        self.asset_list = AssetListWidget()
        self.asset_list.setDragEnabled(True)
        self.asset_list.itemDoubleClicked.connect(self.insert_selected_asset_to_viewport)
        assets_layout.addWidget(self.asset_list)
        self.assets_dock.setWidget(assets_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.assets_dock)

        self.inspector_dock = QDockWidget("Inspector", self)
        self.inspector_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        inspector_widget = QWidget()
        inspector_layout = QFormLayout(inspector_widget)

        self.pos_x_spin = self._make_spin(-10000, 10000)
        self.pos_y_spin = self._make_spin(-10000, 10000)
        self.width_spin = self._make_spin(1, 3000, 16)
        self.height_spin = self._make_spin(1, 3000, 16)
        self.color_r_spin = self._make_spin(0, 255, 0)
        self.color_g_spin = self._make_spin(0, 255, 255)
        self.color_b_spin = self._make_spin(0, 255, 0)
        self.sprite_label = QLabel("(none)")

        inspector_layout.addRow("X", self.pos_x_spin)
        inspector_layout.addRow("Y", self.pos_y_spin)
        inspector_layout.addRow("Width", self.width_spin)
        inspector_layout.addRow("Height", self.height_spin)
        inspector_layout.addRow("R", self.color_r_spin)
        inspector_layout.addRow("G", self.color_g_spin)
        inspector_layout.addRow("B", self.color_b_spin)
        inspector_layout.addRow("Sprite", self.sprite_label)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_inspector_changes)
        inspector_layout.addRow(apply_btn)

        self.inspector_dock.setWidget(inspector_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock)

        self.output_dock = QDockWidget("Output", self)
        self.output_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        self.output_dock.setWidget(self.output_log)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.output_dock)

    def _make_spin(self, min_value, max_value, value=0):
        spin = QSpinBox()
        spin.setRange(min_value, max_value)
        spin.setValue(value)
        return spin

    def set_status(self, message):
        self.statusBar().showMessage(message, 6000)
        if hasattr(self, "output_log"):
            self.output_log.append(message)

    def on_grid_settings_changed(self):
        self.engine_widget.set_grid_settings(
            self.snap_checkbox.isChecked(),
            self.show_grid_checkbox.isChecked(),
            self.grid_size_spin.value(),
        )
        self.engine_widget.set_editor_lighting(self.lighting_checkbox.isChecked())

    def set_draw_tool(self, tool_name):
        self.ensure_engine_visible()
        self.engine_widget.set_draw_tool(tool_name)
        self.set_status(f"Tool: {tool_name}")

    def switch_backend(self, backend):
        self.ensure_engine_visible()
        if backend in ("opengl", "vulkan"):
            launched = self.launch_backend_preview(backend)
            if launched:
                self.set_status(
                    f"{backend.upper()} preview launched in separate window. Editor viewport remains PYGAME for stability."
                )
                for name, action in self.backend_actions.items():
                    action.setChecked(name == backend)
            else:
                self.set_status(f"Failed to launch {backend.upper()} preview.")
                for name, action in self.backend_actions.items():
                    action.setChecked(name == "pygame")
            return

        # PYGAME editor viewport should not restart pygame every click.
        if self.engine_widget.backend_type != "pygame" or not self.engine_widget.renderer:
            self.engine_widget.backend_type = "pygame"
            try:
                self.engine_widget.initialize_engine()
            except Exception as exc:
                self.set_status(f"Failed to activate PYGAME viewport: {exc}")
                return

        self.engine_widget.set_assets_dir(self.assets_dir_for_current_project())
        self.engine_widget.needs_redraw = True
        self.engine_widget.update()
        self.set_status("Pygame viewport active")
        for name, action in self.backend_actions.items():
            action.setChecked(name == "pygame")

    def launch_backend_preview(self, backend):
        script = r'''
import sys
import pygame

backend = sys.argv[1] if len(sys.argv) > 1 else "opengl"
pygame.init()

if backend == "opengl":
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.set_mode((960, 540), pygame.DOUBLEBUF | pygame.OPENGL)
    try:
        import moderngl
        ctx = moderngl.create_context()
    except Exception:
        ctx = None
else:
    pygame.display.set_mode((960, 540))
    ctx = None

pygame.display.set_caption(f"NeoPyxel {backend.upper()} Preview")
clock = pygame.time.Clock()
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    if ctx:
        ctx.clear(0.07, 0.09, 0.13)
        pygame.display.flip()
    else:
        surf = pygame.display.get_surface()
        if surf:
            surf.fill((18, 24, 34))
            pygame.display.flip()
    clock.tick(60)

pygame.quit()
'''
        self._close_backend_previews()
        try:
            proc = subprocess.Popen(
                [sys.executable, "-c", script, backend],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.backend_preview_processes.append(proc)
            return True
        except Exception:
            return False

    def _close_backend_previews(self):
        alive = []
        for proc in self.backend_preview_processes:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
            else:
                if proc.poll() is None:
                    alive.append(proc)
        self.backend_preview_processes = alive

    def new_project(self):
        project_name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not project_name.strip():
            self.set_status("New project canceled")
            return

        safe_name = "".join(ch for ch in project_name.strip() if ch not in '<>:"/\\|?*').strip()
        if not safe_name:
            self.set_status("Invalid project name")
            return

        project_dir = os.path.join(self.get_runtime_base_dir(), safe_name)
        if os.path.exists(project_dir):
            QMessageBox.warning(self, "Project Exists", f"Folder already exists:\n{project_dir}")
            self.set_status("Project creation failed: folder already exists")
            return

        os.makedirs(project_dir, exist_ok=False)
        self.current_project_dir = project_dir
        self.current_project_name = safe_name

        self.scene_files = ["main.json"]
        self.current_scene_name = "main.json"
        self.main_scene_name = "main.json"

        self.ensure_project_structure()
        self.ensure_engine_visible()
        self.engine_widget.clear_scene()
        self.save_current_scene_file()
        self.save_project_metadata()
        self.refresh_scene_selector()
        self.refresh_asset_browser()
        self.plugin_manager.emit(
            "on_project_opened",
            self.current_project_dir,
            self.assets_dir_for_current_project(),
        )

        self.set_status(f"Project created: {safe_name}")

    def open_project(self):
        selected = QFileDialog.getExistingDirectory(self, "Open Project Folder", self.get_runtime_base_dir())
        if not selected:
            self.set_status("Open project canceled")
            return

        metadata_path = os.path.join(selected, self.current_metadata_file)
        if not os.path.exists(metadata_path):
            QMessageBox.warning(
                self,
                "Invalid Project Folder",
                f"This folder has no {self.current_metadata_file} file:\n{selected}",
            )
            self.set_status(f"Open failed: {self.current_metadata_file} not found")
            return

        self.current_project_dir = selected
        self.current_project_name = os.path.basename(selected)
        self.ensure_project_structure()

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            self.current_project_name = metadata.get("name", self.current_project_name)
            self.main_scene_name = metadata.get("main_scene", "main.json")
            self.current_scene_name = metadata.get("last_scene", self.main_scene_name)
            self.scene_files = metadata.get("scenes", [self.main_scene_name])
            if self.main_scene_name not in self.scene_files:
                self.scene_files.insert(0, self.main_scene_name)
            backend_name = str(metadata.get("backend", "pygame")).lower()
            self.snap_checkbox.setChecked(bool(metadata.get("snap_enabled", True)))
            self.show_grid_checkbox.setChecked(bool(metadata.get("show_grid", True)))
            self.lighting_checkbox.setChecked(bool(metadata.get("editor_lighting", False)))
            self.grid_size_spin.setValue(int(metadata.get("grid_size", 16)))
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Project Metadata", f"Failed to read {self.current_metadata_file}:\n{exc}")
            self.set_status(f"Open failed: invalid {self.current_metadata_file}")
            return

        self.ensure_engine_visible()
        self.engine_widget.set_assets_dir(self.assets_dir_for_current_project())
        self.load_scene_file(self.current_scene_name)
        self.refresh_scene_selector()
        self.refresh_asset_browser()
        self.switch_backend(backend_name if backend_name in ("pygame", "opengl", "vulkan") else "pygame")
        self.plugin_manager.emit(
            "on_project_opened",
            self.current_project_dir,
            self.assets_dir_for_current_project(),
        )
        self.set_status(f"Opened project: {self.current_project_name}")

    def save_project(self):
        if not self.current_project_dir:
            self.set_status("No project to save")
            return
        self.ensure_project_structure()
        self.save_current_scene_file()
        self.save_project_metadata()
        self.set_status("Project saved")

    def save_project_metadata(self):
        metadata = {
            "name": self.current_project_name or "NeoPyxelProject",
            "version": "1.0",
            "backend": self.engine_widget.backend_type,
            "main_scene": self.main_scene_name,
            "last_scene": self.current_scene_name,
            "scenes": self.scene_files,
            "snap_enabled": self.snap_checkbox.isChecked(),
            "show_grid": self.show_grid_checkbox.isChecked(),
            "editor_lighting": self.lighting_checkbox.isChecked(),
            "grid_size": self.grid_size_spin.value(),
        }
        path = os.path.join(self.current_project_dir, self.current_metadata_file)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def save_current_scene_file(self):
        scenes_dir = self.scenes_dir_for_current_project()
        os.makedirs(scenes_dir, exist_ok=True)
        path = os.path.join(scenes_dir, self.current_scene_name)
        payload = {
            "name": self.current_scene_name,
            "entities": self.engine_widget.get_scene_data(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load_scene_file(self, scene_name):
        if not self.current_project_dir:
            return
        path = os.path.join(self.scenes_dir_for_current_project(), scene_name)
        if not os.path.exists(path):
            self.engine_widget.clear_scene()
            self.current_scene_name = scene_name
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            entities = payload.get("entities", [])
            self.engine_widget.set_assets_dir(self.assets_dir_for_current_project())
            self.engine_widget.load_scene_data(entities)
            self.current_scene_name = scene_name
            self.plugin_manager.emit("on_scene_loaded", scene_name, entities)
            self.set_status(f"Scene loaded: {scene_name}")
        except Exception as exc:
            self.set_status(f"Failed to load scene {scene_name}: {exc}")

    def new_scene(self):
        if not self.current_project_dir:
            self.set_status("Create/Open project first")
            return

        name, ok = QInputDialog.getText(self, "New Scene", "Scene file name (without .json):")
        if not ok or not name.strip():
            return
        base = "".join(ch for ch in name.strip() if ch not in '<>:"/\\|?*')
        if not base:
            self.set_status("Invalid scene name")
            return

        scene_file = f"{base}.json"
        if scene_file in self.scene_files:
            self.set_status("Scene already exists")
            return

        self.save_current_scene_file()
        self.scene_files.append(scene_file)
        self.current_scene_name = scene_file
        self.engine_widget.clear_scene()
        self.save_current_scene_file()
        self.save_project_metadata()
        self.refresh_scene_selector()
        self.set_status(f"Scene created: {scene_file}")

    def set_current_as_main_scene(self):
        if not self.current_project_dir:
            self.set_status("Create/Open project first")
            return
        self.main_scene_name = self.current_scene_name
        self.main_scene_label.setText(f"Main Scene: {self.main_scene_name}")
        self.save_project_metadata()
        self.set_status(f"Main scene set: {self.main_scene_name}")

    def on_scene_selector_changed(self, index):
        if index < 0:
            return
        selected_scene = self.scene_selector.itemText(index)
        if not selected_scene or selected_scene == self.current_scene_name:
            return
        self.save_current_scene_file()
        self.load_scene_file(selected_scene)
        self.save_project_metadata()

    def refresh_scene_selector(self):
        self.scene_selector.blockSignals(True)
        self.scene_selector.clear()
        for scene in self.scene_files:
            self.scene_selector.addItem(scene)
        idx = self.scene_selector.findText(self.current_scene_name)
        if idx >= 0:
            self.scene_selector.setCurrentIndex(idx)
        self.scene_selector.blockSignals(False)
        self.main_scene_label.setText(f"Main Scene: {self.main_scene_name}")

    def refresh_asset_browser(self):
        self.asset_list.clear()
        assets_dir = self.assets_dir_for_current_project()
        self.assets_path_label.setText(f"assets: {assets_dir}")

        if not assets_dir or not os.path.exists(assets_dir):
            return

        for root, _, files in os.walk(assets_dir):
            for filename in files:
                if not filename.lower().endswith(IMAGE_EXTENSIONS):
                    continue
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, assets_dir).replace("\\", "/")
                item = QListWidgetItem(rel_path)
                item.setData(Qt.UserRole, abs_path)
                self.asset_list.addItem(item)

    def insert_selected_asset_to_viewport(self, item):
        if not item:
            return
        abs_path = item.data(Qt.UserRole)
        rel = os.path.relpath(abs_path, self.assets_dir_for_current_project()).replace("\\", "/")
        self.ensure_engine_visible()
        self.engine_widget.add_sprite_entity(100, 100, rel)
        self.set_status(f"Asset inserted: {rel}")

    def refresh_entity_list(self, scene_data):
        self.entity_list.blockSignals(True)
        self.entity_list.clear()
        for i, entity in enumerate(scene_data):
            sprite = entity.get("sprite")
            kind = f"Sprite:{sprite}" if sprite else "Rect"
            text = f"{i} | {kind} | ({entity['x']},{entity['y']}) {entity['w']}x{entity['h']}"
            self.entity_list.addItem(QListWidgetItem(text))
        self.entity_list.blockSignals(False)

    def on_entity_row_changed(self, row):
        self.engine_widget.set_selected_index(row)
        self.populate_inspector(row)

    def on_viewport_selection_changed(self, row):
        self.entity_list.blockSignals(True)
        self.entity_list.setCurrentRow(row)
        self.entity_list.blockSignals(False)
        self.populate_inspector(row)

    def populate_inspector(self, row):
        scene = self.engine_widget.get_scene_data()
        if not (0 <= row < len(scene)):
            self.sprite_label.setText("(none)")
            return
        entity = scene[row]
        self.pos_x_spin.setValue(entity["x"])
        self.pos_y_spin.setValue(entity["y"])
        self.width_spin.setValue(entity["w"])
        self.height_spin.setValue(entity["h"])
        self.color_r_spin.setValue(entity["color"][0])
        self.color_g_spin.setValue(entity["color"][1])
        self.color_b_spin.setValue(entity["color"][2])
        self.sprite_label.setText(entity.get("sprite") or "(none)")

    def apply_inspector_changes(self):
        row = self.entity_list.currentRow()
        ok = self.engine_widget.update_selected_entity(
            self.pos_x_spin.value(),
            self.pos_y_spin.value(),
            self.width_spin.value(),
            self.height_spin.value(),
            (self.color_r_spin.value(), self.color_g_spin.value(), self.color_b_spin.value()),
        )
        if ok:
            self.set_status(f"Entity {row} updated")
            self.refresh_entity_list(self.engine_widget.get_scene_data())
            self.entity_list.setCurrentRow(row)
        else:
            self.set_status("No selected entity")

    def add_entity_dialog(self):
        self.ensure_engine_visible()
        self.engine_widget.add_rect_entity(100, 100, 32, 32, (0, 255, 0))
        self.set_status("Rectangle entity added")

    def delete_selected_entity(self):
        self.ensure_engine_visible()
        if self.engine_widget.delete_selected_entity():
            self.set_status("Entity deleted")
        else:
            self.set_status("No selected entity")

    def undo_action(self):
        self.ensure_engine_visible()
        if self.engine_widget.undo_last():
            self.set_status("Undo completed")
        else:
            self.set_status("Nothing to undo")

    def export_playable_script(self):
        if not self.current_project_dir:
            self.set_status("No project to export")
            return

        self.save_project()
        export_path = os.path.join(self.current_project_dir, "play_game.py")
        scene_path = os.path.join(self.scenes_dir_for_current_project(), self.main_scene_name).replace("\\", "\\\\")
        assets_path = self.assets_dir_for_current_project().replace("\\", "\\\\")

        script = f"""import json
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

        with open(export_path, "w", encoding="utf-8") as f:
            f.write(script)
        self.set_status(f"Playable exported: {export_path}")

    def show_about(self):
        QMessageBox.information(
            self,
            "About NeoPyxel Studio",
            "NeoPyxel Studio v1.0\n\n"
            "Scene editor with grid/snap.\n"
            "Assets drag-drop into viewport.\n"
            "OpenGL/Vulkan run as preview windows\n"
            "for stability.",
        )

    def ensure_project_structure(self):
        if not self.current_project_dir:
            return
        os.makedirs(self.assets_dir_for_current_project(), exist_ok=True)
        os.makedirs(self.scenes_dir_for_current_project(), exist_ok=True)

    def assets_dir_for_current_project(self):
        if not self.current_project_dir:
            return None
        return os.path.join(self.current_project_dir, "assets")

    def scenes_dir_for_current_project(self):
        if not self.current_project_dir:
            return None
        return os.path.join(self.current_project_dir, "scenes")

    def get_runtime_base_dir(self):
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.getcwd()

    def ensure_engine_visible(self):
        if not self.engine_widget.isVisible():
            self.engine_widget.show()
            self.set_status("Scene Viewport ready")
        if not self.engine_widget.renderer:
            self.engine_widget.initialize_engine()
        self.engine_widget.set_assets_dir(self.assets_dir_for_current_project())

    def closeEvent(self, event):
        if hasattr(self, "plugin_manager"):
            self.plugin_manager.emit("on_before_close")
        if hasattr(self, "engine_widget") and self.engine_widget.timer:
            self.engine_widget.timer.stop()
        self._close_backend_previews()
        if hasattr(self, "engine_widget") and self.engine_widget.renderer:
            self.engine_widget.renderer.cleanup()
        try:
            pygame.display.quit()
        except Exception:
            pass
        pygame.quit()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
