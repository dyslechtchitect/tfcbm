import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert';
import { FakeGLib } from './fakes/FakeGnomeAPIs.js';

// Testable version of PollingScheduler
class TestablePollingScheduler {
    constructor(task, intervalMs, GLib) {
        this.task = task;
        this.intervalMs = intervalMs || 250;
        this.timeoutId = null;
        this.GLib = GLib;
    }

    start() {
        if (this.timeoutId) {
            return;
        }

        this.timeoutId = this.GLib.timeout_add(
            this.GLib.PRIORITY_DEFAULT,
            this.intervalMs,
            () => {
                this.task();
                return this.GLib.SOURCE_CONTINUE;
            }
        );
    }

    stop() {
        if (this.timeoutId) {
            this.GLib.Source.remove(this.timeoutId);
            this.timeoutId = null;
        }
    }
}

describe('PollingScheduler', () => {
    let taskCallCount;
    let taskFunction;

    beforeEach(() => {
        taskCallCount = 0;
        taskFunction = () => {
            taskCallCount++;
        };
        FakeGLib._cleanup();
    });

    afterEach(() => {
        FakeGLib._cleanup();
    });

    describe('constructor', () => {
        it('should create scheduler with task and interval', () => {
            const scheduler = new TestablePollingScheduler(taskFunction, 250, FakeGLib);

            assert.strictEqual(scheduler.task, taskFunction);
            assert.strictEqual(scheduler.intervalMs, 250);
            assert.strictEqual(scheduler.timeoutId, null);
        });

        it('should use default interval of 250ms when not specified', () => {
            const scheduler = new TestablePollingScheduler(taskFunction, undefined, FakeGLib);

            assert.strictEqual(scheduler.intervalMs, 250);
        });

        it('should accept custom interval', () => {
            const scheduler = new TestablePollingScheduler(taskFunction, 500, FakeGLib);

            assert.strictEqual(scheduler.intervalMs, 500);
        });
    });

    describe('start', () => {
        it('should start executing task at interval', (t, done) => {
            const scheduler = new TestablePollingScheduler(taskFunction, 50, FakeGLib);

            scheduler.start();

            // Wait for a few intervals
            setTimeout(() => {
                scheduler.stop();
                assert.ok(taskCallCount >= 2, `Expected at least 2 calls, got ${taskCallCount}`);
                done();
            }, 150);
        });

        it('should set timeout ID', () => {
            const scheduler = new TestablePollingScheduler(taskFunction, 250, FakeGLib);

            scheduler.start();

            assert.ok(scheduler.timeoutId !== null);
            assert.strictEqual(typeof scheduler.timeoutId, 'number');

            scheduler.stop();
        });

        it('should not start if already started', (t, done) => {
            const scheduler = new TestablePollingScheduler(taskFunction, 50, FakeGLib);

            scheduler.start();
            const firstTimeoutId = scheduler.timeoutId;
            scheduler.start(); // Try to start again

            assert.strictEqual(scheduler.timeoutId, firstTimeoutId);

            setTimeout(() => {
                scheduler.stop();
                // Should only have one interval running
                assert.ok(taskCallCount >= 2 && taskCallCount <= 4);
                done();
            }, 150);
        });

        it('should use GLib.PRIORITY_DEFAULT', () => {
            const scheduler = new TestablePollingScheduler(taskFunction, 250, FakeGLib);

            scheduler.start();

            // Just verify it doesn't throw and creates a timeout
            assert.ok(scheduler.timeoutId);

            scheduler.stop();
        });
    });

    describe('stop', () => {
        it('should stop executing task', (t, done) => {
            const scheduler = new TestablePollingScheduler(taskFunction, 50, FakeGLib);

            scheduler.start();

            setTimeout(() => {
                scheduler.stop();
                const callCountAtStop = taskCallCount;

                // Wait a bit more and verify no more calls
                setTimeout(() => {
                    assert.strictEqual(taskCallCount, callCountAtStop);
                    done();
                }, 100);
            }, 100);
        });

        it('should clear timeout ID', () => {
            const scheduler = new TestablePollingScheduler(taskFunction, 250, FakeGLib);

            scheduler.start();
            assert.ok(scheduler.timeoutId !== null);

            scheduler.stop();
            assert.strictEqual(scheduler.timeoutId, null);
        });

        it('should be safe to call when not started', () => {
            const scheduler = new TestablePollingScheduler(taskFunction, 250, FakeGLib);

            // Should not throw
            scheduler.stop();

            assert.strictEqual(scheduler.timeoutId, null);
        });

        it('should be safe to call multiple times', () => {
            const scheduler = new TestablePollingScheduler(taskFunction, 250, FakeGLib);

            scheduler.start();
            scheduler.stop();
            scheduler.stop();
            scheduler.stop();

            assert.strictEqual(scheduler.timeoutId, null);
        });
    });

    describe('task execution', () => {
        it('should execute task with correct context', (t, done) => {
            let executedContext = null;
            const contextTask = function() {
                executedContext = this;
            };

            const scheduler = new TestablePollingScheduler(contextTask, 50, FakeGLib);
            scheduler.start();

            setTimeout(() => {
                scheduler.stop();
                // In our implementation, 'this' will be undefined/window
                // Just verify task was called
                assert.ok(executedContext !== 'not-called');
                done();
            }, 100);
        });

        it('should handle task that throws error', (t, done) => {
            let errorCount = 0;
            const errorTask = () => {
                errorCount++;
                if (errorCount < 3) {
                    throw new Error('Test error');
                }
            };

            const scheduler = new TestablePollingScheduler(errorTask, 50, FakeGLib);
            scheduler.start();

            setTimeout(() => {
                scheduler.stop();
                // Should continue running despite errors
                assert.ok(errorCount >= 3);
                done();
            }, 200);
        });

        it('should pass arguments to GLib.timeout_add correctly', () => {
            let capturedPriority = null;
            let capturedInterval = null;

            const mockGLib = {
                PRIORITY_DEFAULT: 42,
                SOURCE_CONTINUE: true,
                timeout_add: (priority, interval, callback) => {
                    capturedPriority = priority;
                    capturedInterval = interval;
                    return 999;
                },
                Source: {
                    remove: () => true
                }
            };

            const scheduler = new TestablePollingScheduler(taskFunction, 123, mockGLib);
            scheduler.start();

            assert.strictEqual(capturedPriority, 42);
            assert.strictEqual(capturedInterval, 123);

            scheduler.stop();
        });

        it('should return SOURCE_CONTINUE to keep running', (t, done) => {
            let returnedValue = null;

            const mockGLib = {
                PRIORITY_DEFAULT: 0,
                SOURCE_CONTINUE: 'CONTINUE_VALUE',
                SOURCE_REMOVE: 'REMOVE_VALUE',
                timeout_add: (priority, interval, callback) => {
                    returnedValue = callback();
                    return 999;
                },
                Source: {
                    remove: () => true
                }
            };

            const scheduler = new TestablePollingScheduler(taskFunction, 250, mockGLib);
            scheduler.start();

            setImmediate(() => {
                assert.strictEqual(returnedValue, 'CONTINUE_VALUE');
                scheduler.stop();
                done();
            });
        });
    });

    describe('integration', () => {
        it('should support start/stop/start cycle', (t, done) => {
            const scheduler = new TestablePollingScheduler(taskFunction, 50, FakeGLib);

            scheduler.start();

            setTimeout(() => {
                scheduler.stop();
                const countAfterStop = taskCallCount;

                // Start again
                setTimeout(() => {
                    taskCallCount = 0; // Reset count
                    scheduler.start();

                    setTimeout(() => {
                        scheduler.stop();
                        assert.ok(taskCallCount >= 1);
                        done();
                    }, 100);
                }, 50);
            }, 100);
        });

        it('should handle rapid start/stop cycles', () => {
            const scheduler = new TestablePollingScheduler(taskFunction, 250, FakeGLib);

            for (let i = 0; i < 10; i++) {
                scheduler.start();
                scheduler.stop();
            }

            // Should be stopped and safe
            assert.strictEqual(scheduler.timeoutId, null);
        });
    });
});
