# NeoPyxel Studio
NeoPyxel - Game Editor Tool

=======FEATURE=======
- Multi-Backend
- Dynamic Lighting
- Script Bridge
  
### Pyinstaller Build 
```pyinstaller --noconfirm --onedir --windowed --name "NeoPyxel" --contents-directory "Resource" --add-data "editor/static/bridge.js;editor/static" --add-data "editor/static;editor/static" --add-data "web;web" --add-data "plugins;plugins" --hidden-import "PyQt5.sip" --hidden-import "moderngl" --hidden-import "pygame" --hidden-import "numpy" --hidden-import "lupa" --additional-hooks-dir . main.py```
