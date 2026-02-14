# engine/scripting/lua_bridge.py
import lupa
from lupa import LuaRuntime

class LuaBridge:
    def __init__(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.scripts = {}
        self._register_python_functions()

    def _register_python_functions(self):
        # ให้ Lua เรียก Python function ได้
        self.lua.execute('''
            function print_entity(entity)
                print("Entity at x=" .. entity.x .. ", y=" .. entity.y)
            end
        ''')
        # สามารถเพิ่มฟังก์ชันอื่น ๆ เช่น create_entity, etc.

    def load_script(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        name = os.path.basename(filepath)
        self.scripts[name] = code
        # compile and store function if needed
        self.lua.execute(code)

    def call_function(self, func_name, *args):
        if func_name in self.lua.globals():
            return self.lua.globals()[func_name](*args)
        return None

    def update_entity(self, entity_id, entity_data):
        # เรียก Lua function ถ้ามี
        self.call_function('on_update', entity_id, entity_data)
