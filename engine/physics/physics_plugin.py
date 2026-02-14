# engine/physics/physics_plugin.py
import ctypes
import os
import sys

class PhysicsPlugin:
    def __init__(self, dll_path):
        self.dll_path = dll_path
        self.lib = None
        self._load_dll()

    def _load_dll(self):
        if not os.path.exists(self.dll_path):
            raise FileNotFoundError(f"Physics DLL not found: {self.dll_path}")
        try:
            if sys.platform == 'win32':
                self.lib = ctypes.CDLL(self.dll_path)
            else:
                self.lib = ctypes.CDLL(self.dll_path)  # .so on Linux
        except Exception as e:
            raise RuntimeError(f"Failed to load physics library: {e}")

    def init(self, gravity=(0, -9.81, 0)):
        # สมมติว่า DLL มีฟังก์ชัน init_physics(float x, float y, float z)
        if hasattr(self.lib, 'init_physics'):
            self.lib.init_physics.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
            self.lib.init_physics(gravity[0], gravity[1], gravity[2])
        else:
            print("Warning: init_physics not found in DLL")

    def step(self, dt):
        if hasattr(self.lib, 'step_physics'):
            self.lib.step_physics.argtypes = [ctypes.c_float]
            self.lib.step_physics(dt)

    def create_body(self, x, y, z, shape_type):
        # สมมติว่าคืนค่า body id เป็น int
        if hasattr(self.lib, 'create_body'):
            self.lib.create_body.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int]
            self.lib.create_body.restype = ctypes.c_int
            return self.lib.create_body(x, y, z, shape_type)
        return -1
