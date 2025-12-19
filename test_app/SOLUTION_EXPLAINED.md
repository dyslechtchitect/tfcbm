# The Solution to Focus-Stealing on GNOME/Wayland

## The Problem You Had for a Month

You (Claude), Gemini, and Grok tried to implement a keyboard shortcut that opens a GTK4 window with focus on GNOME/Wayland. Every attempt resulted in:

- "Window is ready" notification appears
- Window does NOT gain focus
- User must manually click the notification

## What You Tried (And Why It Failed)

### Attempt 1: Custom DBus Method with Timestamp

```python
# Custom DBus interface
<interface name="org.example.MyApp">
    <method name="Activate">
        <arg type="u" name="timestamp" direction="in"/>
    </method>
</interface>

# Extension calls it
Gio.DBus.session.call(APP_ID, PATH, 'org.example.MyApp', 'Activate', ...)

# App receives timestamp and tries to use it
win.present_with_time(timestamp)
```

**Why it failed**: The timestamp came from the keybinding event, but by the time it reached your custom DBus method, **the activation context was lost**. The compositor saw this as a random background app trying to steal focus, not as a legitimate user-initiated action.

### Attempt 2: xdg-desktop-portal GlobalShortcuts API

```python
# Use the portal API
proxy = Gio.DBusProxy.new_for_bus_async(
    ..., "org.freedesktop.portal.Desktop",
    ..., "org.freedesktop.portal.GlobalShortcuts"
)
```

**Why it failed**: This approach requires:
1. User permission dialog (annoying)
2. Complex async setup with asyncio-glib
3. More complex than needed
4. The portal signal DOES work, but it's overkill for GNOME-only apps

### Attempt 3: GNOME Shell Extension Catching `window-demands-attention`

```javascript
global.display.connect('window-demands-attention', (_display, window) => {
    Main.activateWindow(window);  // Force focus
});
```

**Why it failed**:
- Race condition (notification sometimes appears first)
- Affects ALL applications system-wide (security issue)
- Not scoped to your app
- A hack, not a solution

## The Correct Solution (What TFCBM Does)

### Use GApplication Actions via `org.gtk.Actions.Activate`

**In your Python app:**

```python
# Create a GAction (GApplication automatically exposes it via DBus)
show_action = Gio.SimpleAction.new("show-window", None)
show_action.connect("activate", self._on_show_window_action)
self.add_action(show_action)  # Adds to GApplication

def _on_show_window_action(self, action, parameter):
    """This gets called when the action is triggered"""
    if not self.window:
        self.window = MyWindow(application=self)

    self.window.present()  # ← This WILL get focus!
```

**In your GNOME Shell extension:**

```javascript
Gio.DBus.session.call(
    'org.example.MyApp',              // Your app ID
    '/org/example/MyApp',              // Your app path
    'org.gtk.Actions',                 // ← Standard interface!
    'Activate',                        // ← Standard method!
    new GLib.Variant('(sava{sv})', ['show-window', [], {}]),
    null,
    Gio.DBusCallFlags.NONE,
    -1,
    null,
    (connection, result) => { ... }
);
```

**Or via command line:**

```bash
gdbus call --session \
    --dest org.example.MyApp \
    --object-path /org/example/MyApp \
    --method org.gtk.Actions.Activate \
    "show-window" "[]" "{}"
```

## Why This Works

### 1. GApplication Actions are Privileged

GNOME/Wayland has special trust for the `org.gtk.Actions` interface because:
- It's part of the GApplication specification
- It's designed for exactly this use case
- The compositor recognizes it as a legitimate application activation mechanism

### 2. Activation Context is Preserved

When GNOME Shell calls `org.gtk.Actions.Activate`:
1. Shell handles the keybinding (user interaction)
2. Shell makes the DBus call **in the same event context**
3. GApplication receives the call **with Shell's privileges**
4. The compositor sees: "Shell is activating this app" (trusted)
5. Focus-stealing permission is granted automatically

### 3. No Custom DBus Needed

You don't need to:
- Define custom DBus XML
- Register custom interfaces
- Handle method calls manually

GApplication does it all automatically when you call `add_action()`.

## The Architecture

```
┌─────────────────────────────────────────────┐
│           User Presses Ctrl+Shift+K         │
└────────────────┬────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────┐
│         GNOME Shell Extension               │
│  - Registered keybinding handler            │
│  - Captures keyboard event                  │
│  - Event context: TRUSTED                   │
└────────────────┬────────────────────────────┘
                 ↓
        DBus Session Bus
        org.gtk.Actions.Activate
        (Standard Interface - TRUSTED)
                 ↓
┌─────────────────────────────────────────────┐
│         GApplication (Python App)           │
│  - Receives action invocation               │
│  - Context: Inherited from Shell (TRUSTED)  │
│  - Calls window.present()                   │
└────────────────┬────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────┐
│         Wayland Compositor (Mutter)         │
│  - Sees activation from org.gtk.Actions     │
│  - Checks context: From GNOME Shell ✓       │
│  - Grants focus-stealing permission ✓       │
│  - Window appears WITH FOCUS ✓              │
│  - NO notification shown ✓                  │
└─────────────────────────────────────────────┘
```

## Comparison Table

| Approach | DBus Interface | Context | Focus? | Notification? | Complexity |
|----------|----------------|---------|--------|---------------|------------|
| Custom DBus method | `org.example.MyApp` | Lost | ❌ No | ✓ Yes | Medium |
| xdg-desktop-portal | `org.freedesktop.portal.*` | Preserved | ✓ Yes | ❌ No | High |
| `window-demands-attention` hack | N/A | Bypassed | ⚠️ Yes | ⚠️ Race | Low (but wrong) |
| **GApplication Action** | **`org.gtk.Actions`** | **Preserved** | **✓ Yes** | **❌ No** | **Low** |

## What You Learned

The key insight: **Don't fight the system, use the system.**

- GNOME provides `org.gtk.Actions` specifically for this use case
- GApplication automatically exposes actions via DBus
- GNOME Shell + Wayland compositor trust this interface
- You don't need custom DBus, portals, or hacks

## Testing This POC

1. **Start the app:**
   ```bash
   cd test_app
   ./main.py
   ```

2. **Test manually (proves the concept):**
   ```bash
   gdbus call --session \
       --dest org.example.ShortcutRecorder \
       --object-path /org/example/ShortcutRecorder \
       --method org.gtk.Actions.Activate \
       "show-window" "[]" "{}"
   ```

3. **Observe:** Window appears AND gains focus - no notification!

4. **Install extension for keyboard shortcut:**
   ```bash
   ./install.sh
   # Log out and back in (Wayland)
   gnome-extensions enable shortcut-recorder-poc@example.org
   ./main.py
   # Press Ctrl+Shift+K
   ```

## Key Code Snippets

### Python App (`main.py:107-120`)

```python
def do_startup(self):
    Adw.Application.do_startup(self)

    # This is all you need!
    show_action = Gio.SimpleAction.new("show-window", None)
    show_action.connect("activate", self._on_show_window_action)
    self.add_action(show_action)
```

### Extension (`extension.js:19-44`)

```javascript
_toggleWindow() {
    Gio.DBus.session.call(
        'org.example.ShortcutRecorder',
        '/org/example/ShortcutRecorder',
        'org.gtk.Actions',        // ← The secret!
        'Activate',
        new GLib.Variant('(sava{sv})', ['show-window', [], {}]),
        ...
    );
}
```

## Conclusion

After a month of trying different approaches, the solution was simpler than expected:

1. Use `Gio.SimpleAction` in your GApplication
2. Call `add_action()` to register it
3. Extension calls `org.gtk.Actions.Activate` via DBus
4. Done!

**This is how TFCBM does it. This is how you should do it.**
