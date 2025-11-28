"""Tests for WindowManager."""


def test_window_manager_default_size():
    from ui.managers.window_manager import WindowManager

    manager = WindowManager()
    width, height = manager.get_default_size()

    assert width == 350
    assert height == 800


def test_window_manager_custom_size():
    from ui.managers.window_manager import WindowManager

    manager = WindowManager(default_width=400, default_height=600)
    width, height = manager.get_default_size()

    assert width == 400
    assert height == 600


def test_window_manager_calculate_size_from_monitor():
    from ui.managers.window_manager import WindowManager

    manager = WindowManager()

    width, height = manager.calculate_size_from_monitor(1920, 1080)

    assert width == 1920 // 3
    assert height == 800


def test_window_manager_position_left():
    from ui.managers.window_manager import WindowManager

    manager = WindowManager(position="left")

    assert manager.position == "left"


def test_window_manager_position_right():
    from ui.managers.window_manager import WindowManager

    manager = WindowManager(position="right")

    assert manager.position == "right"


def test_window_manager_position_center():
    from ui.managers.window_manager import WindowManager

    manager = WindowManager(position="center")

    assert manager.position == "center"
