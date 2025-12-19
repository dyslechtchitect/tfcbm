"""Integration tests for activation tracking."""
import pytest

from tests.helpers import IntegrationTestContext


class TestActivationTracker:
    """Test activation tracking functionality."""

    def setup_method(self):
        """Set up test context before each test."""
        self.context = IntegrationTestContext()

    def test_initial_count_is_zero(self):
        """
        GIVEN: A new activation tracker
        WHEN: Count is checked
        THEN: It should be zero
        """
        # GIVEN
        tracker = self.context.activation_tracker

        # WHEN
        count = tracker.count

        # THEN
        assert count == 0

    def test_increment_increases_count(self):
        """
        GIVEN: An activation tracker
        WHEN: Count is incremented
        THEN: Count should increase by one
        """
        # GIVEN
        tracker = self.context.activation_tracker

        # WHEN
        new_count = tracker.increment()

        # THEN
        assert new_count == 1
        assert tracker.count == 1

    def test_multiple_increments(self):
        """
        GIVEN: An activation tracker
        WHEN: Count is incremented multiple times
        THEN: Count should reflect total increments
        """
        # GIVEN
        tracker = self.context.activation_tracker

        # WHEN
        tracker.increment()
        tracker.increment()
        tracker.increment()

        # THEN
        assert tracker.count == 3

    def test_reset_clears_count(self):
        """
        GIVEN: An activation tracker with non-zero count
        WHEN: Reset is called
        THEN: Count should be zero
        """
        # GIVEN
        tracker = self.context.activation_tracker
        tracker.increment()
        tracker.increment()
        assert tracker.count == 2

        # WHEN
        tracker.reset()

        # THEN
        assert tracker.count == 0


class TestActivationObserver:
    """Test activation observer notifications."""

    def setup_method(self):
        """Set up test context before each test."""
        self.context = IntegrationTestContext()
        self.notified_count = None
        self.notification_count = 0

    def on_activation_count_changed(self, count: int):
        """Observer callback for count changes."""
        self.notified_count = count
        self.notification_count += 1

    def test_observer_notified_on_increment(self):
        """
        GIVEN: Tracker with registered observer
        WHEN: Count is incremented
        THEN: Observer should be notified
        """
        # GIVEN
        tracker = self.context.activation_tracker
        tracker.add_observer(self)

        # WHEN
        tracker.increment()

        # THEN
        assert self.notified_count == 1
        assert self.notification_count == 1

    def test_observer_notified_on_reset(self):
        """
        GIVEN: Tracker with non-zero count and registered observer
        WHEN: Reset is called
        THEN: Observer should be notified with zero
        """
        # GIVEN
        tracker = self.context.activation_tracker
        tracker.increment()
        tracker.increment()
        tracker.add_observer(self)

        # WHEN
        tracker.reset()

        # THEN
        assert self.notified_count == 0
        assert self.notification_count == 1

    def test_observer_notified_on_each_increment(self):
        """
        GIVEN: Tracker with registered observer
        WHEN: Count is incremented multiple times
        THEN: Observer should be notified each time
        """
        # GIVEN
        tracker = self.context.activation_tracker
        tracker.add_observer(self)

        # WHEN
        tracker.increment()
        tracker.increment()
        tracker.increment()

        # THEN
        assert self.notified_count == 3  # Last notified count
        assert self.notification_count == 3  # Total notifications

    def test_multiple_observers(self):
        """
        GIVEN: Tracker with multiple registered observers
        WHEN: Count is incremented
        THEN: All observers should be notified
        """
        # GIVEN
        tracker = self.context.activation_tracker

        observer1 = self
        observer2_count = None

        def observer2_callback(count: int):
            nonlocal observer2_count
            observer2_count = count

        # Mock observer 2
        class Observer2:
            def on_activation_count_changed(self, count: int):
                observer2_callback(count)

        observer2 = Observer2()
        tracker.add_observer(observer1)
        tracker.add_observer(observer2)

        # WHEN
        tracker.increment()

        # THEN
        assert self.notified_count == 1
        assert observer2_count == 1

    def test_remove_observer(self):
        """
        GIVEN: Tracker with registered observer
        WHEN: Observer is removed and count is incremented
        THEN: Observer should not be notified
        """
        # GIVEN
        tracker = self.context.activation_tracker
        tracker.add_observer(self)
        tracker.increment()  # First notification
        assert self.notification_count == 1

        # WHEN
        tracker.remove_observer(self)
        tracker.increment()

        # THEN
        assert self.notification_count == 1  # No new notification
