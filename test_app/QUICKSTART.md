# Shortcut Recorder POC - Quick Start

## What This Proves

This POC demonstrates **the correct solution** to the focus-stealing problem on GNOME/Wayland that you, Gemini, and Grok struggled with for a month.

**The secret**: Use `org.gtk.Actions.Activate` instead of custom DBus methods.

## Quick Test (No Extension Required)

1. **Start the app:**
   ```bash
   cd test_app
   ./main.py
   ```

2. **Test the GAction manually:**
   ```bash
   gdbus call --session \
       --dest org.example.ShortcutRecorder \
       --object-path /org/example/ShortcutRecorder \
       --method org.gtk.Actions.Activate \
       "show-window" "[]" "{}"
   ```

3. **Observe**: The window appears AND gains focus immediately - no "Window is ready" notification!

## Full Installation (With Keyboard Shortcut)

1. **Install the extension:**
   ```bash
   ./install.sh
   ```

2. **Log out and log back in** (required on Wayland for new extensions)

3. **Enable the extension:**
   ```bash
   gnome-extensions enable shortcut-recorder-poc@example.org
   ```

4. **Start the app:**
   ```bash
   ./main.py
   ```

5. **Press `Ctrl+Shift+K`** anywhere - window toggles with focus!

## Why This Works

### The Problem (What You Tried Before)

```python
# ❌ WRONG: Custom DBus method
dbus_xml = """
<interface name="org.example.MyApp">
    <method name="Activate">
        <arg type="u" name="timestamp" direction="in"/>
    </method>
</interface>
"""
# Result: "Window is ready" notification, no focus
```

### The Solution (What TFCBM Does)

```python
# ✅ CORRECT: GApplication Action
show_action = Gio.SimpleAction.new("show-window", None)
show_action.connect("activate", self._on_show_window_action)
self.add_action(show_action)
# Result: Window appears with focus, no notification!
```

```javascript
// Extension calls it via org.gtk.Actions (not custom interface!)
Gio.DBus.session.call(
    APP_ID,
    APP_PATH,
    'org.gtk.Actions',  // ← The key!
    'Activate',
    new GLib.Variant('(sava{sv})', ['show-window', [], {}]),
    ...
);
```

## The Key Insight

- **Custom DBus methods** lose the activation context from GNOME Shell
- **GApplication Actions** (`org.gtk.Actions`) are privileged by the compositor
- Calls to `org.gtk.Actions.Activate` preserve the Shell's event context
- The compositor grants focus-stealing permission because it trusts `org.gtk.Actions`

## Architecture

```
User presses Ctrl+Shift+K
        ↓
GNOME Shell Extension catches it
        ↓
Extension calls: org.gtk.Actions.Activate("show-window", ...)
        ↓
GApplication receives action in Shell's context
        ↓
Window.present() → FOCUS GRANTED ✓
```

## Files

- `main.py` - GTK4 app with GAction (150 lines)
- `gnome-extension/extension.js` - GNOME Shell extension (75 lines)
- `gnome-extension/metadata.json` - Extension metadata
- `gnome-extension/schemas/*.gschema.xml` - Keybinding schema
- `install.sh` - One-command installation
- `uninstall.sh` - Clean removal

## Verification

After starting the app, verify the GAction is registered:

```bash
gdbus introspect --session \
    --dest org.example.ShortcutRecorder \
    --object-path /org/example/ShortcutRecorder \
    | grep -A 20 "org.gtk.Actions"
```

You should see the `Activate` method listed.

## Cleanup

```bash
./uninstall.sh
pkill -f "main.py"
```

---

**This is the solution you were looking for all along.**
