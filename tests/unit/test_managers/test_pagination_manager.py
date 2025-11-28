"""Tests for PaginationManager."""


def test_pagination_manager_initial_state():
    from ui.managers.pagination_manager import PaginationManager

    manager = PaginationManager(page_size=50)

    assert manager.offset == 0
    assert manager.has_more is True
    assert manager.loading is False
    assert manager.page_size == 50


def test_pagination_manager_start_loading():
    from ui.managers.pagination_manager import PaginationManager

    manager = PaginationManager()

    manager.start_loading()

    assert manager.loading is True


def test_pagination_manager_finish_loading_full_page():
    from ui.managers.pagination_manager import PaginationManager

    manager = PaginationManager(page_size=50)

    manager.start_loading()
    manager.finish_loading(items_loaded=50)

    assert manager.loading is False
    assert manager.offset == 50
    assert manager.has_more is True


def test_pagination_manager_finish_loading_partial_page():
    from ui.managers.pagination_manager import PaginationManager

    manager = PaginationManager(page_size=50)

    manager.start_loading()
    manager.finish_loading(items_loaded=30)

    assert manager.loading is False
    assert manager.offset == 30
    assert manager.has_more is False


def test_pagination_manager_reset():
    from ui.managers.pagination_manager import PaginationManager

    manager = PaginationManager(page_size=50)

    manager.start_loading()
    manager.finish_loading(items_loaded=50)
    manager.reset()

    assert manager.offset == 0
    assert manager.has_more is True
    assert manager.loading is False


def test_pagination_manager_can_load_more():
    from ui.managers.pagination_manager import PaginationManager

    manager = PaginationManager()

    assert manager.can_load_more() is True

    manager.start_loading()
    assert manager.can_load_more() is False

    manager.finish_loading(items_loaded=30)
    assert manager.can_load_more() is False
