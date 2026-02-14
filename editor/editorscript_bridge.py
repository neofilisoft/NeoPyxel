import os

class ScriptBridge:
    def __init__(self):
        self.plugins = []

    def load_python_plugins(self, path="./plugins"):
        if not os.path.exists(path):
            os.makedirs(path)
        print(f"NeoPyxel: Loading Python Plugins from {path}")

    def execute_js_logic(self, js_code):

        print(f"Executing JavaScript: {js_code[:30]}")
