# engine/scripting/lua_bridge.py
import os

from lupa import LuaRuntime


class LuaBridge:
    def __init__(self):
        self.lua = None
        self.scripts = {}
        self.available = False
        self.import_error = None
        self._init_runtime()

    def _init_runtime(self):
        try:
            from lupa import LuaRuntime  # Lazy import to avoid hard crash when packaged without lupa libs

            self.lua = LuaRuntime(unpack_returned_tuples=True)
            self.available = True
            self._register_python_functions()
        except Exception as exc:
            self.lua = None
            self.available = False
            self.import_error = exc

    def _register_python_functions(self):
        if not self.available:
            return
        self.lua.execute(
            '''
            function print_entity(entity)
                if entity == nil then
                    print("Entity is nil")
                    return
                end
                print("Entity at x=" .. tostring(entity.x) .. ", y=" .. tostring(entity.y))
            end
            '''
        )

    def is_available(self):
        return self.available

    def get_status_message(self):
        if self.available:
            return "Lua runtime ready"
        if self.import_error:
            return f"Lua runtime unavailable: {self.import_error}"
        return "Lua runtime unavailable"

    def execute_script(self, code):
        if not self.available:
            return None
        return self.lua.execute(code)

    def load_script(self, filepath):
        with open(filepath, "r", encoding="utf-8") as file:
            code = file.read()
        name = os.path.basename(filepath)
        self.scripts[name] = code
        if not self.available:
            return False
        self.lua.execute(code)
        return True

    def call_function(self, func_name, *args):
        if not self.available:
            return None
        func = self.lua.globals().get(func_name)
        if func:
            return func(*args)
        return None

    def update_entity(self, entity_id, entity_data):
        return self.call_function("on_update", entity_id, entity_data)
