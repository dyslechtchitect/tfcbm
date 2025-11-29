export class ClipboardEvent {
    constructor(type, content, formattedContent = null, formatType = null) {
        this.type = type;
        this.content = content;
        this.formattedContent = formattedContent;
        this.formatType = formatType;
        this.timestamp = Date.now();
    }

    equals(other) {
        return (
            other &&
            this.type === other.type &&
            this.content === other.content &&
            this.formattedContent === other.formattedContent &&
            this.formatType === other.formatType
        );
    }

    toJSON() {
        const json = {
            type: this.type,
            content: this.content,
        };

        // Only include formatted fields if they exist
        if (this.formattedContent !== null) {
            json.formatted_content = this.formattedContent;
        }
        if (this.formatType !== null) {
            json.format_type = this.formatType;
        }

        return json;
    }
}
