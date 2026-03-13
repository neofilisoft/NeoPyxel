# NeoPyxel Studio
NeoPyxel - Game Editor Tool

======= FEATURE =======
- Multi-Backend
- Dynamic Lighting
- Script Bridge
- Plugin System
  
### Pyinstaller Build 
```pyinstaller --noconfirm --onedir --windowed --name "NeoPyxel" --contents-directory "Resource" --add-data "assets;assets" --add-data "editor/static/bridge.js;editor/static" --add-data "editor/static;editor/static" --add-data "web;web" --add-data "plugins;plugins" --hidden-import "PyQt5.sip" --hidden-import "moderngl" --hidden-import "pygame" --hidden-import "numpy" --hidden-import "lupa" --additional-hooks-dir . main.py```
```Copy-Item -Recurse -Force .\assets .\dist\NeoPyxel\Assets```
```Copy-Item -Recurse -Force .\plugins .\dist\NeoPyxel\Plugins```

### Built-in Plugin Example
- `plugins/lua_scripting_plugin.py` adds a dockable **Lua Scripting** panel.
- You can load `.lua` files, execute scripts, and run `on_update(entity_id, entity)` for the selected entity.

Example Lua:
```lua
function on_update(entity_id, entity)
  if entity ~= nil then
    entity.x = entity.x + 8
    entity.color = {255, 120, 40}
  end
  return entity
end
```
