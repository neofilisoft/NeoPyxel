class DrawingTool:
    name = "Base"
    color = (255, 255, 255)


class PenTool(DrawingTool):
    name = "Pen"
    color = (60, 230, 120)


class LineTool(DrawingTool):
    name = "Line"
    color = (80, 220, 255)


class RectTool(DrawingTool):
    name = "Rect"
    color = (255, 190, 60)


class ToolManager:
    TOOLS = {
        "Pen": PenTool,
        "Line": LineTool,
        "Rect": RectTool,
    }

    @classmethod
    def color_for(cls, tool_name):
        tool_cls = cls.TOOLS.get(tool_name, DrawingTool)
        return tool_cls.color

    @staticmethod
    def line_points(start, end, step=8):
        x0, y0 = start
        x1, y1 = end
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy)) // max(1, step) + 1
        points = []
        for i in range(steps + 1):
            t = i / max(steps, 1)
            x = int(x0 + dx * t)
            y = int(y0 + dy * t)
            points.append((x, y))
        return points

    @staticmethod
    def rect_border_points(start, end, step=8):
        left = min(start[0], end[0])
        right = max(start[0], end[0])
        top = min(start[1], end[1])
        bottom = max(start[1], end[1])
        points = []
        for x in range(left, right + 1, max(1, step)):
            points.append((x, top))
            points.append((x, bottom))
        for y in range(top, bottom + 1, max(1, step)):
            points.append((left, y))
            points.append((right, y))
        return points
