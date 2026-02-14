class NeoPlugin {
    constructor(name) {
        this.name = name;
    }

    onUpdate(entityId) {
        console.log(`Entity ${entityId} is updating via JavaScript Plugin.`);
    }
}
