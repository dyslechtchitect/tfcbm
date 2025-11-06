export class ClipboardEvent {
    constructor(type, content) {
        this.type = type;
        this.content = content;
        this.timestamp = Date.now();
    }

    equals(other) {
        return other &&
               this.type === other.type &&
               this.content === other.content;
    }

    toJSON() {
        return {
            type: this.type,
            content: this.content
        };
    }
}
