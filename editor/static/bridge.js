class NeoPlugin {
    constructor(name) {
        this.name = name;
    }

    onUpdate(entityId) {
        // Simulation Logic
        console.log(`Entity ${entityId} is updating via JavaScript Plugin.`);
    }
}
