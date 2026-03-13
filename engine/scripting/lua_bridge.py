# engine/scripting/lua_bridge.py
import os

from lupa import LuaRuntime


class LuaBridge:
    def __init__(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.scripts = {}
        self._register_python_functions()

    def _register_python_functions(self):
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

    def execute_script(self, code):
        self.lua.execute(code)

    def load_script(self, filepath):
        with open(filepath, "r", encoding="utf-8") as file:
            code = file.read()
        name = os.path.basename(filepath)
        self.scripts[name] = code
        self.lua.execute(code)

    def call_function(self, func_name, *args):
        func = self.lua.globals().get(func_name)
        if func:
            return func(*args)
        return None

    def update_entity(self, entity_id, entity_data):
        return self.call_function("on_update", entity_id, entity_data)
