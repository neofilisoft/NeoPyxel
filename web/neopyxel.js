// web/neopyxel.js
class NeoPyxelEngine {
  constructor(canvas) {
    this.canvas = canvas;
    this.module = null;
    this.initWasm();
  }

  async initWasm() {
    this.module = await Module({
      canvas: this.canvas,
      onRuntimeInitialized: () => {
        // Python runtime
        this.pyBridge = this.module.pybridges;
      }
    });
  }

  createEntity(x, y, color) {
    if (this.pyBridge) {
      this.pyBridge.createEntity(x, y, color);
    }
  }

  getEntities() {
    if (this.pyBridge) {
      return this.pyBridge.getEntities();
    }
    return [];
  }

  update(dt) {
    // send dt to Python game loop
    if (this.pyBridge) {
      this.pyBridge.update(dt);
    }
  }

  render() {
    // WebGL render Pygame/SDL ผ่าน Emscripten
  }
}

// Export for TypeScript
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { NeoPyxelEngine };
}
