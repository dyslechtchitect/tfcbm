import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

export default class TestExtension extends Extension {
    enable() {
        console.log('Test extension enabled');
    }
    disable() {
        console.log('Test extension disabled');
    }
}
