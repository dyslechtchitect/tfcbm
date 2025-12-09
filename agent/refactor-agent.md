# Backend (Agent) Refactoring Plan

## 1. Introduction & Goals

This document provides a comprehensive plan for refactoring the monolithic `tfcbm_server.py` script into a modern, maintainable, and testable backend application housed within the `agent/` directory.

The primary goals of this refactor are:
- **Readability & Maintainability:** Make the codebase easier to understand, modify, and extend.
- **Testability:** Enable comprehensive unit and integration testing to ensure reliability.
- **SOLID & DRY Principles:** Decompose the application into logical, single-responsibility components and eliminate redundant code.
- **Dependency Injection (DI):** Decouple components to improve modularity and testability.
- **Performance:** Preserve and optimize performance-critical operations.
- **Functionality:** Preserve 100% of the existing functionality.

## 2. Analysis of Current Architecture (`tfcbm_server.py`)

The current backend is a single, large script that functions as a "God Object." It violates several core software design principles, making it difficult to manage.

-   **Single Responsibility Principle (SRP) Violation:** The script is responsible for everything:
    -   Handling Unix socket connections from the GNOME extension.
    -   Running a WebSocket server for UI communication.
    -   Managing all business logic for clipboard data processing (text, images, files, thumbnails).
    -   Handling every client action via a massive `if/elif` block in the `websocket_handler`.
    -   Managing global state (client sets, database locks, in-memory history).

-   **Tight Coupling:** Logic is tightly bound to specific libraries (`websockets`, `socket`), the database implementation (`ClipboardDB`), and the GTK event loop (`GLib.idle_add`). This makes it impossible to test or swap out components.

-   **Global State:** The use of global variables (`ws_clients`, `db_lock`, `last_known_id`) makes the application state implicit and hard to reason about, especially in a multi-threaded/async environment.

-   **Poor Testability:** It is not possible to unit test any single piece of business logic (e.g., "delete item" or "add tag") without setting up the entire server and database infrastructure.

## 3. Proposed Architecture (Post-Refactor)

To address these issues, we will decompose the application into a clean, layered package structure within the `agent/` directory.

### Proposed Directory Structure

```
agent/
├── __init__.py           # Makes 'agent' a package
├── main.py               # Composition Root: Initializes and starts the application
│
├── core/
│   ├── __init__.py
│   ├── database.py       # (Moved and potentially refactored)
│   └── settings.py       # (Moved)
│
├── services/
│   ├── __init__.py
│   ├── broadcast_service.py # Handles broadcasting new items to WebSocket clients
│   ├── clipboard_service.py # Handles processing and storing new clipboard items
│   └── thumbnail_service.py # Manages thumbnail generation
│
├── transport/
│   ├── __init__.py
│   ├── unix_socket_server.py
│   └── websocket_server.py
│
├── handlers/               # Handles specific WebSocket actions
│   ├── __init__.py
│   ├── history_handler.py    # Handles get_history, get_recently_pasted
│   ├── item_handler.py       # Handles delete_item, update_item_name, get_full_image
│   ├── search_handler.py
│   └── tag_handler.py        # Handles all tag-related actions
│
└── utils/
    ├── __init__.py
    └── file_processor.py   # Logic from `process_file` function
```

### Dependency Flow Diagram

```mermaid
graph TD
    subgraph main.py (Composition Root)
        A[Database] --> B{ClipboardService};
        A --> C{Handlers};
        B --> D[UnixSocketServer];
        E[BroadcastService] --> B;
        F[WebSocketServer] --> E;
        C --> F;
    end

    subgraph transport
        D -- receives data --> B;
        F -- routes actions --> C;
    end

    subgraph services
        B; E;
    end

    subgraph handlers
        C;
    end
```

## 4. Core Refactoring Strategy: DI and Separation of Concerns

**1. Dependency Injection (DI):** The new `main.py` will serve as the **Composition Root**. It will instantiate all classes and inject dependencies through their constructors. For example, it will create the `Database` and `BroadcastService` objects, then pass them to the `ClipboardService` when it's created.

**2. Separation of Layers:**
-   **`transport`:** This layer's only job is communication. The `UnixSocketServer` listens for data and passes it to a service layer object. It doesn't know *what* the data is. The `WebSocketServer` listens for messages and routes them to the appropriate handler. It doesn't know how to *process* those messages.
-   **`services`:** This layer contains the core business logic. `ClipboardService` handles the deduplication and storage of new items. `BroadcastService` maintains the list of connected clients and sends them messages.
-   **`handlers`:** This layer replaces the giant `if/elif` block. The `WebSocketServer` will have a router that maps the `"action"` field of a message (e.g., `"get_tags"`) to the corresponding method on the `TagHandler` class. This makes the code for handling actions clean, decoupled, and easy to test.

## 5. Testing Strategy

This new architecture makes the codebase highly testable.

-   **Unit Testing:** Each handler and service can be tested in complete isolation.
    -   To test the `TagHandler`, you can create an instance of it and pass a **mock Database object**. You can then call its methods and assert that the mock database was called with the correct parameters, without ever touching a real database file.
    -   To test the `ClipboardService`, you can pass it a mock database and a mock broadcast service to verify that it correctly processes data and attempts to broadcast it.
-   **Integration Testing:** You can test the integration between components by using real objects instead of mocks. For example, you can test the `TagHandler` with a real (in-memory) `SQLite` database to ensure the SQL queries are correct.

## 6. Performance & Functionality

-   **Functionality:** All logic from `tfcbm_server.py` will be carefully moved to its new home in the appropriate service or handler, ensuring 100% of functionality is preserved.
-   **Performance:**
    -   The `ThreadPoolExecutor` for thumbnail generation is a good pattern and will be preserved, likely encapsulated withinRz the `ThumbnailService`.
    -   For a significant performance boost, we should consider replacing the standard `sqlite3` driver with an asynchronous one like **`aiosqlite`**. Since the WebSocket server runs on `asyncio`, making database calls non-blocking will improve responsiveness, especially during high-load situations.

## 7. Step-by-Step Refactoring Plan (TDD Approach)

1.  **Setup:** Create the new directory structure outlined in section 3. Move `database.py` and `settings.py` to `agent/core/`.
2.  **Test & Extract Utilities:** Create `agent/utils/` and move utility functions (like `process_file`) there. Write unit tests for them.
3.  **Test & Extract Services:** One by one, create the service classes (`ClipboardService`, etc.). For each service, write a failing unit test first, then copy the relevant logic from `tfcbm_server.py` into the new class, and adapt it until the test passes. Use mock objects for dependencies.
4.  **Test & Extract Handlers:** Do the same for the handlers. For each `elif action == ...` block in the old `websocket_handler`, create a corresponding method in a new `Handler` class and write a unit test for it.
5.  **Build the Transport Layer:** Create the `UnixSocketServer` and `WebSocketServer` classes. The logic will be taken from the server setup loops in the original script, but they will now call the injected service/handler objects instead of containing the logic themselves.
6.  **Compose the Application:** Implement `agent/main.py`. This script will import all the new components, instantiate them, inject the dependencies, and start the servers.
7.  **Finalize:** Once the new `agent` application is running and all functionality is verified, the old `tfcbm_server.py` and `backend.py` files can be safely deleted.
