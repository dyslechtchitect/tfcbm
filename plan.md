# Clipboard Manager Development Plan

## Phase 0: Stabilize Existing Prototype
### 0.1 Clean Up GNOME Extension
- Keep listening to clipboard events.
- Emit structured JSON messages over the existing socket.
- Include timestamps, item type, and metadata.

### 0.2 Harden Python Daemon
- Maintain the socket listener temporarily.
- Add a "ClipboardEvent" model.
- Use a queue/buffer for incoming events.
- Improve logging and error handling.

---

## Phase 1: Introduce a DBus API
### 1.1 Add DBus Service to the Daemon
Expose a DBus interface such as:
- `org.clipboard.Manager`
  - `GetHistory(limit)`
  - `ClearHistory()`
  - `Search(query)`
  - Signal: `NewClipboardItem(item_json)`

### 1.2 Signal Broadcasting
- On each new clipboard event:
  - Store event in memory.
  - Optionally persist to SQLite.
  - Emit a `NewClipboardItem` DBus signal.

---

## Phase 2: Add SQLite Persistence
### 2.1 Storage Layer
Create SQLite table:
```
id INTEGER PRIMARY KEY
timestamp INTEGER
content TEXT
type TEXT
hash TEXT UNIQUE
```

### 2.2 Add Indexes
- Index on timestamp.
- Optional: FTS5 index for full-text search.

### 2.3 Expose DBus `Search()`
- Query SQLite for search operations.

---

## Phase 3: Build GTK4 + Libadwaita UI
### 3.1 Create Minimal UI
- History list view.
- Search bar.
- Clear button.
- Preview panel.

### 3.2 Connect UI to Daemon
- Consume DBus API.
- Subscribe to `NewClipboardItem` signal.
- Use `Search(query)` for filtering.

---

## Phase 4: Evolve the GNOME Extension
### 4.1 Transition from Socket to DBus
- Replace socket output with DBus calls.
- Use `org.clipboard.Manager.NotifyClipboard(item_json)`.

### 4.2 Add Small Popup UI
- Compact history list.
- Quick actions.
- Button to launch full GTK app.

---

## Phase 5: Single Instance Enforcement
### 5.1 Daemon as systemd User Service
Example unit:
```
[Service]
ExecStart=/usr/bin/clipboard-daemon
Restart=always
```

### 5.2 DBus Activation
- Daemon auto-starts when DBus interface is accessed.

### 5.3 GTK App Single Instance
- Use `Gtk.Application` with a fixed application ID.

---

## Phase 6: Packaging & Fedora Readiness
### 6.1 Package Components
- RPM for daemon.
- RPM for GNOME extension.
- RPM for GTK app.
- DBus service file.
- Systemd user unit.
- SELinux policy.

### 6.2 GNOME Design Compliance
- Follow GNOME HIG.
- Keep UI minimal and modern.

### 6.3 Security Review
- Handle clipboard content safely.
- Respect privacy defaults.

### 6.4 Optional Future: Rust Rewrite
- Only if performance or memory constraints demand it.

---

## TLDR
1. Stabilize current JS extension + Python daemon.
2. Add DBus interface.
3. Add SQLite.
4. Build GTK4 UI.
5. Move extension to DBus.
6. Use systemd for reliability.
7. Package cleanly for Fedora.

This roadmap uses your existing code and gradually evolves it into a Fedora-native, GNOME-friendly architecture.

