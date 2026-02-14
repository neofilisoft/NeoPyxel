// neopyxel.d.ts - TypeScript declarations for NeoPyxel Engine

declare module 'neopyxel' {
  export interface Entity {
    x: number;
    y: number;
    width: number;
    height: number;
    color: [number, number, number];
  }

  export interface EngineConfig {
    backend: 'pygame' | 'opengl' | 'vulkan';
    internalResolution: [number, number];
    screenResolution: [number, number];
  }

  export interface EngineEvents {
    onEntityCreated: (entity: Entity) => void;
    onEntityDestroyed: (id: string) => void;
    onRender: (deltaTime: number) => void;
    onUpdate: (deltaTime: number) => void;
    onError: (error: Error) => void;
  }

  export class NeoPyxelEngine {
    constructor(canvas: HTMLCanvasElement, config?: Partial<EngineConfig>);
    createEntity(x: number, y: number, color: [number, number, number]): Entity;
    getEntities(): Entity[];
    update(dt: number): void;
    render(): void;
    destroy(): void;

    on<K extends keyof EngineEvents>(event: K, callback: EngineEvents[K]): this;
    off<K extends keyof EngineEvents>(event: K, callback: EngineEvents[K]): this;
    emit<K extends keyof EngineEvents>(event: K, ...args: Parameters<EngineEvents[K]>): boolean;

    start(): void;
    stop(): void;
    isRunning(): boolean;
  }

  export function init(options?: Partial<EngineConfig>): Promise<NeoPyxelEngine>;
  export type BackendType = 'pygame' | 'opengl' | 'vulkan';
  export type Resolution = [number, number];
  export type RGBColor = [number, number, number];
}