import os
import importlib.util
from engine.scripting.lua_bridge import LuaBridge

class ScriptBridge:
    def __init__(self):
        self.plugins = []
        self.js_plugins = []
        self.lua_bridge = LuaBridge()

    def load_python_plugins(self, path="./plugins"):
        if not os.path.exists(path):
            os.makedirs(path)
        print(f"NeoPyxel: Loading Python Plugins from {path}")

    def load_lua_plugins(self, path="./plugins/lua"):
        if not os.path.exists(path):
            os.makedirs(path)
        for filename in os.listdir(path):
            if filename.endswith(".lua"):
                filepath = os.path.join(path, filename)
                self.lua_bridge.load_script(filepath)
                print(f"NeoPyxel: Loaded Lua plugin: {filename}")

    def update_plugins(self, entity_id):
        for plugin in self.plugins:
            if hasattr(plugin, 'on_update'):
                plugin.on_update(entity_id)
        self.lua_bridge.call_function('on_update', entity_id)       

    def execute_js_logic(self, js_code):
        print(f"Executing JavaScript: {js_code[:30]}")
