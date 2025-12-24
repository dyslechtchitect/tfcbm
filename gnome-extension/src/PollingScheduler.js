import GLib from 'gi://GLib';

export class PollingScheduler {
    constructor(task, intervalMs = 250) {
        this.task = task;
        this.intervalMs = intervalMs;
        this.timeoutId = null;
    }

    start() {
        if (this.timeoutId) {
            return;
        }

        this.timeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, this.intervalMs, () => {
            this.task();
            return GLib.SOURCE_CONTINUE;
        });
    }

    stop() {
        if (this.timeoutId) {
            GLib.Source.remove(this.timeoutId);
            this.timeoutId = null;
        }
    }
}
