C# TFCBM - The F*cking Clipboard Manager

This document provides a high-level overview of the TFCBM architecture, detailing the frameworks and technologies used for each component.

## High-Level Architecture

The application is composed of three main components:

1.  **UI (User Interface):** A desktop application that displays the clipboard history and allows the user to interact with it.
2.  **Backend Server & Agent:** A background process that listens for clipboard changes, processes the data, and communicates with the UI.
3.  **Database:** A local database that stores the clipboard history.

These components work together to provide a seamless clipboard management experience. The agent detects clipboard changes, the backend server processes and stores them in the database, and the UI displays the history to the user in real-time.

### UI (User Interface)

The user interface is a standalone desktop application.

*   **Framework:** [GTK4](https://www.gtk.org/) with [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/) for modern GNOME styling.
*   **Language:** Python
*   **Communication:** The UI communicates with the backend server via a WebSocket connection. It receives real-time updates (e.g., new clipboard items) and sends requests (e.g., to delete an item).
*   **Key Library:** `websockets` for WebSocket communication.

### Backend Server & Agent

The backend is a combination of a Python server and a GNOME Shell extension that acts as the clipboard monitoring agent.

*   **Python Server:**
    *   **Framework:** A custom server built using Python's standard libraries.
    *   **Language:** Python
    *   **Functionality:**
        *   Provides a WebSocket server for the UI to connect to.
        *   Receives notifications about new clipboard items from the GNOME extension.
        *   Processes clipboard data (e.g., creating thumbnails for images).
        *   Interacts with the database to store and retrieve clipboard items.
    *   **Key Library:** `websockets` for the WebSocket server.

*   **GNOME Shell Extension (Agent):**
    *   **Framework:** GNOME Shell Extension framework.
    *   **Language:** JavaScript (GJS)
    *   **Functionality:**
        *   Monitors the system's clipboard for changes at the OS level.
        *   When a change is detected, it notifies the Python backend server.
    *   **Location:** The code for the extension is in the `gnome-extension/` directory.

### Database

The database stores all clipboard history.

*   **Technology:** [SQLite](https://www.sqlite.org/index.html)
*   **Language:** Python is used to interact with the database.
*   **Functionality:**
    *   Stores clipboard items, including text, images, and metadata like timestamps.
    *   Provides methods for adding, retrieving, and deleting items.
*   **Location:** The database file is stored by default in the user's home directory at `~/.local/share/tfcbm/clipboard.db`, following standard Linux conventions.

## Technologies Used

*   **UI:** Python, GTK4, libadwaita
*   **Backend:** Python, WebSockets, GNOME Shell Extensions (JavaScript)
*   **Database:** SQLite
