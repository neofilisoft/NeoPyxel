import math
import os

from PyQt5.QtCore import QRect, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QWidget

class Scene3DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.update)
        self.timer.start()

        self.camera_target = [0.0, 0.0, 0.0]
        self.camera_yaw = 0.8
        self.camera_pitch = 0.55
        self.camera_distance = 10.0
        self.fov_deg = 60.0

        self.drag_mode = None
        self.last_mouse_pos = None
        self.drag_entity_index = -1
        self.drag_plane_y = 0.0
        self.drag_offset_xz = [0.0, 0.0]
        self.rotate_axis = None
        self.gizmo_handles = {}
        self.view_axis_handles = {}
        self.reset_button_rect = QRect()
        self.corner_gizmo_center = (0.0, 0.0)
        self.corner_gizmo_radius = 0.0
        self.view_gizmo_click_axis = None
        self.view_gizmo_dragged = False
        self.entities = []
        self.selected_index = -1
        self.assets_root = None
        self.on_message = None
        self.reset_scene()

    def reset_scene(self):
        self.entities = [
            {
                "name": "Cube",
                "kind": "cube",
                "pos": [0.0, 0.5, 0.0],
                "rot": [0.0, 0.0, 0.0],
                "size": 1.0,
                "color": QColor(220, 220, 220),
            }
        ]
        self.selected_index = 0
        self.camera_target = [0.0, 0.0, 0.0]
        self.camera_distance = 10.0
        self.camera_yaw = 0.8
        self.camera_pitch = 0.55
        self.update()

    def reset_camera_view(self):
        self.camera_target = [0.0, 0.0, 0.0]
        self.camera_distance = 10.0
        self.camera_yaw = 0.8
        self.camera_pitch = 0.55
        self.update()
        if self.on_message:
            self.on_message("3D camera reset")

    def _message(self, text):
        if self.on_message:
            self.on_message(text)

    def set_assets_root(self, assets_root):
        self.assets_root = assets_root

    def export_scene_data(self):
        exported = []
        for ent in self.entities:
            color = ent.get("color", QColor(220, 220, 220))
            if isinstance(color, QColor):
                color_data = [color.red(), color.green(), color.blue()]
            else:
                color_data = [220, 220, 220]
            payload = {
                "name": str(ent.get("name", "Entity")),
                "kind": str(ent.get("kind", "cube")),
                "pos": [float(v) for v in ent.get("pos", [0.0, 0.5, 0.0])[:3]],
                "rot": [float(v) for v in ent.get("rot", [0.0, 0.0, 0.0])[:3]],
                "size": float(ent.get("size", 1.0)),
                "color": color_data,
            }
            model_path = ent.get("model_path")
            if model_path:
                payload["model_path"] = str(model_path).replace("\\", "/")
            exported.append(payload)
        return exported

    def load_scene_data(self, scene_entities):
        loaded = []
        if isinstance(scene_entities, list):
            for i, raw in enumerate(scene_entities):
                if not isinstance(raw, dict):
                    continue
                pos = raw.get("pos", [0.0, 0.5, 0.0])
                rot = raw.get("rot", [0.0, 0.0, 0.0])
                color_raw = raw.get("color", [220, 220, 220])
                if not isinstance(pos, (list, tuple)) or len(pos) < 3:
                    pos = [0.0, 0.5, 0.0]
                if not isinstance(rot, (list, tuple)) or len(rot) < 3:
                    rot = [0.0, 0.0, 0.0]
                if not isinstance(color_raw, (list, tuple)) or len(color_raw) < 3:
                    color_raw = [220, 220, 220]

                kind = str(raw.get("kind", "cube")).lower()
                model_path = str(raw.get("model_path", "")).replace("\\", "/")
                wireframe = None
                if (
                    kind == "model"
                    and model_path
                    and model_path.lower().endswith(".obj")
                    and self.assets_root
                ):
                    abs_model = os.path.join(self.assets_root, model_path)
                    if os.path.exists(abs_model):
                        wireframe = self._load_obj_wireframe(abs_model)

                loaded.append(
                    {
                        "name": str(raw.get("name", f"Entity{i+1}")),
                        "kind": "model" if kind == "model" else "cube",
                        "model_path": model_path if kind == "model" else "",
                        "wireframe": wireframe,
                        "pos": [float(pos[0]), float(pos[1]), float(pos[2])],
                        "rot": [float(rot[0]), float(rot[1]), float(rot[2])],
                        "size": max(0.01, float(raw.get("size", 1.0))),
                        "color": QColor(
                            int(max(0, min(255, color_raw[0]))),
                            int(max(0, min(255, color_raw[1]))),
                            int(max(0, min(255, color_raw[2]))),
                        ),
                    }
                )

        self.entities = loaded if loaded else [
            {
                "name": "Cube",
                "kind": "cube",
                "pos": [0.0, 0.5, 0.0],
                "rot": [0.0, 0.0, 0.0],
                "size": 1.0,
                "color": QColor(220, 220, 220),
            }
        ]
        self.selected_index = 0 if self.entities else -1
        self.update()

    def add_cube(self):
        idx = len(self.entities) + 1
        self.entities.append(
            {
                "name": f"Cube{idx}",
                "kind": "cube",
                "pos": [0.0, 0.5, 0.0],
                "rot": [0.0, 0.0, 0.0],
                "size": 1.0,
                "color": QColor(220, 220, 220),
            }
        )
        self.selected_index = len(self.entities) - 1
        self.update()

    def add_model_asset(self, model_rel_path, model_abs_path=None):
        idx = len(self.entities) + 1
        ext = os.path.splitext(model_rel_path)[1].lower()
        wireframe = None
        if ext == ".obj" and model_abs_path and os.path.exists(model_abs_path):
            wireframe = self._load_obj_wireframe(model_abs_path)

        self.entities.append(
            {
                "name": os.path.basename(model_rel_path) or f"Model{idx}",
                "kind": "model",
                "model_path": model_rel_path.replace("\\", "/"),
                "wireframe": wireframe,
                "pos": [0.0, 0.5, -0.8 * (idx - 1)],
                "rot": [0.0, 0.0, 0.0],
                "size": 1.0,
                "color": QColor(175, 205, 235),
            }
        )
        self.selected_index = len(self.entities) - 1
        self.update()
        return True

    def _load_obj_wireframe(self, abs_path):
        vertices = []
        edges = set()
        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                for raw in f:
                    line = raw.strip()
                    if line.startswith("v "):
                        parts = line.split()
                        if len(parts) >= 4:
                            vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
                    elif line.startswith("f "):
                        parts = line.split()[1:]
                        indices = []
                        for tok in parts:
                            base = tok.split("/")[0]
                            if not base:
                                continue
                            try:
                                vi = int(base)
                            except ValueError:
                                continue
                            if vi < 0:
                                vi = len(vertices) + vi + 1
                            vi -= 1
                            if 0 <= vi < len(vertices):
                                indices.append(vi)
                        for i in range(len(indices)):
                            a = indices[i]
                            b = indices[(i + 1) % len(indices)]
                            if a != b:
                                edges.add((min(a, b), max(a, b)))
        except Exception:
            return None

        if not vertices or not edges:
            return None

        min_x = min(v[0] for v in vertices)
        min_y = min(v[1] for v in vertices)
        min_z = min(v[2] for v in vertices)
        max_x = max(v[0] for v in vertices)
        max_y = max(v[1] for v in vertices)
        max_z = max(v[2] for v in vertices)
        cx = (min_x + max_x) * 0.5
        cy = (min_y + max_y) * 0.5
        cz = (min_z + max_z) * 0.5
        sx = max_x - min_x
        sy = max_y - min_y
        sz = max_z - min_z
        scale = 1.0 / max(1e-6, max(sx, sy, sz))

        normalized = []
        for vx, vy, vz in vertices:
            normalized.append([(vx - cx) * scale, (vy - cy) * scale, (vz - cz) * scale])

        return {"vertices": normalized, "edges": list(edges)}

    def _entity_rot(self, ent):
        if "rot" not in ent:
            ent["rot"] = [0.0, float(ent.get("rot_y", 0.0)), 0.0]
        return ent["rot"]

    def _camera_vectors(self):
        cp = math.cos(self.camera_pitch)
        sp = math.sin(self.camera_pitch)
        cy = math.cos(self.camera_yaw)
        sy = math.sin(self.camera_yaw)

        cam_pos = [
            self.camera_target[0] + self.camera_distance * cp * sy,
            self.camera_target[1] + self.camera_distance * sp,
            self.camera_target[2] + self.camera_distance * cp * cy,
        ]

        fx = self.camera_target[0] - cam_pos[0]
        fy = self.camera_target[1] - cam_pos[1]
        fz = self.camera_target[2] - cam_pos[2]
        fl = max(1e-6, math.sqrt(fx * fx + fy * fy + fz * fz))
        forward = [fx / fl, fy / fl, fz / fl]

        up = [0.0, 1.0, 0.0]
        rx = forward[1] * up[2] - forward[2] * up[1]
        ry = forward[2] * up[0] - forward[0] * up[2]
        rz = forward[0] * up[1] - forward[1] * up[0]
        rl = max(1e-6, math.sqrt(rx * rx + ry * ry + rz * rz))
        right = [rx / rl, ry / rl, rz / rl]

        ux = right[1] * forward[2] - right[2] * forward[1]
        uy = right[2] * forward[0] - right[0] * forward[2]
        uz = right[0] * forward[1] - right[1] * forward[0]
        upv = [ux, uy, uz]
        return cam_pos, forward, right, upv

    def _project_point(self, point):
        w = max(1, self.width())
        h = max(1, self.height())
        aspect = w / max(1.0, float(h))
        tan_half = math.tan(math.radians(self.fov_deg) * 0.5)

        cam_pos, forward, right, upv = self._camera_vectors()
        rx = point[0] - cam_pos[0]
        ry = point[1] - cam_pos[1]
        rz = point[2] - cam_pos[2]

        vx = rx * right[0] + ry * right[1] + rz * right[2]
        vy = rx * upv[0] + ry * upv[1] + rz * upv[2]
        vz = rx * forward[0] + ry * forward[1] + rz * forward[2]
        if vz <= 0.05:
            return None

        ndc_x = vx / (vz * tan_half * aspect)
        ndc_y = vy / (vz * tan_half)
        sx = (ndc_x * 0.5 + 0.5) * w
        sy = (0.5 - ndc_y * 0.5) * h
        return sx, sy, vz

    def _ray_from_screen(self, sx, sy):
        w = max(1, self.width())
        h = max(1, self.height())
        aspect = w / max(1.0, float(h))
        tan_half = math.tan(math.radians(self.fov_deg) * 0.5)
        ndc_x = (2.0 * sx / w) - 1.0
        ndc_y = 1.0 - (2.0 * sy / h)

        cam_pos, forward, right, upv = self._camera_vectors()
        dx = (
            forward[0]
            + right[0] * ndc_x * tan_half * aspect
            + upv[0] * ndc_y * tan_half
        )
        dy = (
            forward[1]
            + right[1] * ndc_x * tan_half * aspect
            + upv[1] * ndc_y * tan_half
        )
        dz = (
            forward[2]
            + right[2] * ndc_x * tan_half * aspect
            + upv[2] * ndc_y * tan_half
        )
        dlen = max(1e-6, math.sqrt(dx * dx + dy * dy + dz * dz))
        direction = [dx / dlen, dy / dlen, dz / dlen]
        return cam_pos, direction

    def _intersect_plane_y(self, sx, sy, plane_y):
        origin, direction = self._ray_from_screen(sx, sy)
        if abs(direction[1]) < 1e-6:
            return None
        t = (plane_y - origin[1]) / direction[1]
        if t <= 0.0:
            return None
        return [
            origin[0] + direction[0] * t,
            origin[1] + direction[1] * t,
            origin[2] + direction[2] * t,
        ]

    def _rotate_local(self, x, y, z, rot):
        rx, ry, rz = rot
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)

        x1 = x
        y1 = y * cx - z * sx
        z1 = y * sx + z * cx

        x2 = x1 * cy + z1 * sy
        y2 = y1
        z2 = -x1 * sy + z1 * cy

        x3 = x2 * cz - y2 * sz
        y3 = x2 * sz + y2 * cz
        z3 = z2
        return x3, y3, z3

    def _transform_local(self, local, ent):
        px, py, pz = ent["pos"]
        scale = float(ent.get("size", 1.0))
        rot = self._entity_rot(ent)
        rx, ry, rz = self._rotate_local(local[0] * scale, local[1] * scale, local[2] * scale, rot)
        return [px + rx, py + ry, pz + rz]

    def _draw_grid(self, painter):
        painter.setRenderHint(QPainter.Antialiasing, False)
        extent = 20
        for i in range(-extent, extent + 1):
            color = QColor(80, 92, 112, 120 if i % 5 else 180)
            if i == 0:
                color = QColor(205, 65, 65, 210)
            painter.setPen(color)
            a = self._project_point([i, 0.0, -extent])
            b = self._project_point([i, 0.0, extent])
            if a and b:
                painter.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))

        for j in range(-extent, extent + 1):
            color = QColor(80, 92, 112, 120 if j % 5 else 180)
            if j == 0:
                color = QColor(65, 130, 205, 210)
            painter.setPen(color)
            a = self._project_point([-extent, 0.0, j])
            b = self._project_point([extent, 0.0, j])
            if a and b:
                painter.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))

        painter.setPen(QColor(75, 200, 100, 220))
        a = self._project_point([0.0, 0.0, 0.0])
        b = self._project_point([0.0, 2.0, 0.0])
        if a and b:
            painter.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))

    def _cube_vertices(self, ent):
        size = float(ent.get("size", 1.0))
        hx = size * 0.5
        hy = size * 0.5
        hz = size * 0.5
        local = [
            [-hx, -hy, -hz],
            [hx, -hy, -hz],
            [hx, hy, -hz],
            [-hx, hy, -hz],
            [-hx, -hy, hz],
            [hx, -hy, hz],
            [hx, hy, hz],
            [-hx, hy, hz],
        ]
        return [self._transform_local(v, {"pos": ent["pos"], "size": 1.0, "rot": self._entity_rot(ent)}) for v in local]

    def _entity_wireframe(self, ent):
        if ent.get("kind") == "model":
            wf = ent.get("wireframe")
            if wf and wf.get("vertices") and wf.get("edges"):
                verts = [self._transform_local(v, ent) for v in wf["vertices"]]
                return verts, wf["edges"]

        verts = self._cube_vertices(ent)
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        ]
        return verts, edges

    def _draw_cube(self, painter, idx, ent):
        verts, edges = self._entity_wireframe(ent)
        proj = [self._project_point(v) for v in verts]

        line_color = QColor(ent["color"])
        if idx == self.selected_index:
            line_color = QColor(255, 198, 92)
        painter.setPen(line_color)
        for a, b in edges:
            pa = proj[a]
            pb = proj[b]
            if pa and pb:
                painter.drawLine(int(pa[0]), int(pa[1]), int(pb[0]), int(pb[1]))

        if ent.get("kind") == "model":
            center = self._project_point(ent["pos"])
            if center:
                painter.setPen(QColor(170, 188, 210))
                painter.drawText(int(center[0]) + 8, int(center[1]) - 10, ent.get("name", "Model"))

        if idx == self.selected_index:
            self._draw_gizmo(painter, ent["pos"])

    def _draw_gizmo(self, painter, center):
        self.gizmo_handles = {}
        base = self._project_point(center)
        if not base:
            return
        axes = [
            ("x", [center[0] + 1.2, center[1], center[2]], QColor(230, 80, 80)),
            ("y", [center[0], center[1] + 1.2, center[2]], QColor(90, 220, 120)),
            ("z", [center[0], center[1], center[2] + 1.2], QColor(90, 150, 230)),
        ]
        for axis_name, end_point, color in axes:
            p = self._project_point(end_point)
            if not p:
                continue
            painter.setPen(color)
            painter.drawLine(int(base[0]), int(base[1]), int(p[0]), int(p[1]))
            painter.setBrush(color)
            painter.drawEllipse(int(p[0]) - 3, int(p[1]) - 3, 6, 6)
            self.gizmo_handles[axis_name] = {"start": (base[0], base[1]), "end": (p[0], p[1])}

    def _distance_to_segment(self, px, py, ax, ay, bx, by):
        vx = bx - ax
        vy = by - ay
        seg_len2 = vx * vx + vy * vy
        if seg_len2 <= 1e-6:
            dx = px - ax
            dy = py - ay
            return math.sqrt(dx * dx + dy * dy)
        t = ((px - ax) * vx + (py - ay) * vy) / seg_len2
        t = max(0.0, min(1.0, t))
        qx = ax + vx * t
        qy = ay + vy * t
        dx = px - qx
        dy = py - qy
        return math.sqrt(dx * dx + dy * dy)

    def _draw_corner_orientation(self, painter):
        self.view_axis_handles = {}
        box = 84
        margin = 18
        cx = self.width() - margin - box * 0.5
        cy = margin + box * 0.5
        radius = 26
        self.corner_gizmo_center = (cx, cy)
        self.corner_gizmo_radius = radius + 10

        painter.setBrush(QColor(9, 14, 24, 195))
        painter.setPen(QColor(64, 86, 120, 210))
        painter.drawEllipse(int(cx - radius - 10), int(cy - radius - 10), int((radius + 10) * 2), int((radius + 10) * 2))

        _, forward, right, upv = self._camera_vectors()
        axis_data = []
        world_axes = [
            ("x", [1.0, 0.0, 0.0], QColor(236, 70, 70)),
            ("y", [0.0, 1.0, 0.0], QColor(120, 228, 90)),
            ("z", [0.0, 0.0, 1.0], QColor(72, 154, 242)),
        ]
        for name, axis, color in world_axes:
            sx = cx + (axis[0] * right[0] + axis[1] * right[1] + axis[2] * right[2]) * radius
            sy = cy - (axis[0] * upv[0] + axis[1] * upv[1] + axis[2] * upv[2]) * radius
            depth = axis[0] * forward[0] + axis[1] * forward[1] + axis[2] * forward[2]
            axis_data.append((depth, name, sx, sy, color))

        axis_data.sort()
        for _, name, sx, sy, color in axis_data:
            painter.setPen(color)
            painter.drawLine(int(cx), int(cy), int(sx), int(sy))
            painter.setBrush(color)
            painter.drawEllipse(int(sx) - 7, int(sy) - 7, 14, 14)
            painter.setPen(QColor(8, 16, 30))
            painter.drawText(int(sx) - 4, int(sy) + 4, name.upper())
            self.view_axis_handles[name] = (sx, sy)

        reset_w = 78
        reset_h = 24
        reset_gap = 14
        reset_x = int(cx - (reset_w * 0.5))
        reset_y = int(cy + radius + reset_gap)
        self.reset_button_rect = QRect(reset_x, reset_y, reset_w, reset_h)
        painter.setBrush(QColor(35, 53, 80, 225))
        painter.setPen(QColor(86, 124, 176))
        painter.drawRoundedRect(self.reset_button_rect, 6, 6)
        painter.setPen(QColor(228, 235, 245))
        painter.drawText(self.reset_button_rect, Qt.AlignCenter, "Reset")

    def _align_camera_to_axis(self, axis_name):
        if axis_name == "x":
            self.camera_yaw = math.pi * 0.5
            self.camera_pitch = 0.0
        elif axis_name == "y":
            self.camera_pitch = 1.25
        elif axis_name == "z":
            self.camera_yaw = 0.0
            self.camera_pitch = 0.0
        self.update()
        self._message(f"View aligned to {axis_name.upper()} axis")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(28, 32, 40))
        self._draw_grid(painter)
        for idx, ent in enumerate(self.entities):
            self._draw_cube(painter, idx, ent)
        self._draw_corner_orientation(painter)

        painter.setPen(QColor(190, 205, 225))
        painter.drawText(
            12,
            22,
            "3D Workspace (Orbit:RMB Pan:MMB Zoom:Wheel Move:LMB Drag Rotate:Object Gizmo, Corner Gizmo Drag)",
        )

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta != 0:
            scale = 0.9 if delta > 0 else 1.1
            self.camera_distance = max(2.0, min(60.0, self.camera_distance * scale))
            self.update()

    def mousePressEvent(self, event):
        self.last_mouse_pos = event.pos()
        if event.button() == Qt.RightButton:
            self.drag_mode = "orbit"
            return
        if event.button() == Qt.MiddleButton:
            self.drag_mode = "pan"
            return
        if event.button() == Qt.LeftButton:
            if self.reset_button_rect.contains(event.pos()):
                self.reset_camera_view()
                return

            for axis_name, pos in self.view_axis_handles.items():
                dx = pos[0] - event.x()
                dy = pos[1] - event.y()
                if (dx * dx + dy * dy) <= (14.0 * 14.0):
                    self.drag_mode = "view_gizmo_orbit"
                    self.view_gizmo_click_axis = axis_name
                    self.view_gizmo_dragged = False
                    return

            cdx = self.corner_gizmo_center[0] - event.x()
            cdy = self.corner_gizmo_center[1] - event.y()
            if (cdx * cdx + cdy * cdy) <= (self.corner_gizmo_radius * self.corner_gizmo_radius):
                self.drag_mode = "view_gizmo_orbit"
                self.view_gizmo_click_axis = None
                self.view_gizmo_dragged = False
                return

            selected_center = None
            if 0 <= self.selected_index < len(self.entities):
                selected = self.entities[self.selected_index]
                selected_center = self._project_point(selected["pos"])

            if self.selected_index >= 0:
                for axis_name, axis_data in self.gizmo_handles.items():
                    start = axis_data["start"]
                    end = axis_data["end"]
                    dxh = end[0] - event.x()
                    dyh = end[1] - event.y()
                    near_handle = (dxh * dxh + dyh * dyh) <= (16.0 * 16.0)
                    near_axis_line = (
                        self._distance_to_segment(
                            event.x(),
                            event.y(),
                            start[0],
                            start[1],
                            end[0],
                            end[1],
                        )
                        <= 8.0
                    )
                    if near_handle or near_axis_line:
                        self.drag_entity_index = self.selected_index
                        self.rotate_axis = axis_name
                        self.drag_mode = "rotate_axis"
                        return

            if selected_center:
                dxs = selected_center[0] - event.x()
                dys = selected_center[1] - event.y()
                if (dxs * dxs + dys * dys) <= (24.0 * 24.0):
                    self.drag_entity_index = self.selected_index
                    self.drag_mode = "move_entity"
                    self.drag_plane_y = self.entities[self.drag_entity_index]["pos"][1]
                    hit = self._intersect_plane_y(event.x(), event.y(), self.drag_plane_y)
                    if hit:
                        ent = self.entities[self.drag_entity_index]
                        self.drag_offset_xz = [
                            ent["pos"][0] - hit[0],
                            ent["pos"][2] - hit[2],
                        ]
                    else:
                        self.drag_offset_xz = [0.0, 0.0]
                    return

            nearest = -1
            best = 18.0 * 18.0
            for idx, ent in enumerate(self.entities):
                p = self._project_point(ent["pos"])
                if not p:
                    continue
                dx = p[0] - event.x()
                dy = p[1] - event.y()
                d2 = dx * dx + dy * dy
                if d2 < best:
                    best = d2
                    nearest = idx
            self.selected_index = nearest
            self.update()

    def mouseMoveEvent(self, event):
        if not self.last_mouse_pos or not self.drag_mode:
            return
        dx = event.x() - self.last_mouse_pos.x()
        dy = event.y() - self.last_mouse_pos.y()
        self.last_mouse_pos = event.pos()

        if self.drag_mode == "orbit":
            self.camera_yaw += dx * 0.008
            self.camera_pitch -= dy * 0.008
            self.camera_pitch = max(-1.25, min(1.25, self.camera_pitch))
            self.update()
            return

        if self.drag_mode == "pan":
            _, _, right, upv = self._camera_vectors()
            scale = 0.005 * self.camera_distance
            self.camera_target[0] -= right[0] * dx * scale
            self.camera_target[1] -= upv[1] * dy * scale
            self.camera_target[2] -= right[2] * dx * scale
            self.update()
            return

        if self.drag_mode == "view_gizmo_orbit":
            if abs(dx) + abs(dy) > 1:
                self.view_gizmo_dragged = True
            self.camera_yaw += dx * 0.010
            self.camera_pitch -= dy * 0.010
            self.camera_pitch = max(-1.25, min(1.25, self.camera_pitch))
            self.update()
            return

        if self.drag_mode == "move_entity":
            if 0 <= self.drag_entity_index < len(self.entities):
                hit = self._intersect_plane_y(event.x(), event.y(), self.drag_plane_y)
                if hit:
                    ent = self.entities[self.drag_entity_index]
                    ent["pos"][0] = hit[0] + self.drag_offset_xz[0]
                    ent["pos"][2] = hit[2] + self.drag_offset_xz[1]
                    self.update()
            return

        if self.drag_mode == "rotate_axis":
            if 0 <= self.drag_entity_index < len(self.entities):
                ent = self.entities[self.drag_entity_index]
                rot = self._entity_rot(ent)
                axis = self.rotate_axis or "y"
                if axis == "x":
                    rot[0] += ((-dy + dx * 0.35) * 0.01)
                elif axis == "y":
                    rot[1] += ((dx + dy * 0.35) * 0.01)
                elif axis == "z":
                    rot[2] += ((dx - dy) * 0.008)
                self.update()
            return

    def mouseReleaseEvent(self, event):
        if self.drag_mode == "view_gizmo_orbit":
            if self.view_gizmo_click_axis and not self.view_gizmo_dragged:
                self._align_camera_to_axis(self.view_gizmo_click_axis)
        self.drag_mode = None
        self.drag_entity_index = -1
        self.rotate_axis = None
        self.view_gizmo_click_axis = None
        self.view_gizmo_dragged = False
        self.last_mouse_pos = None

