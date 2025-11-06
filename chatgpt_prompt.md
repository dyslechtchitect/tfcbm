# ChatGPT Prompt: Event-Driven Clipboard Monitoring on GNOME Wayland

I'm trying to build a clipboard history manager in Python on Fedora 43 with GNOME Wayland. The goal is to monitor the clipboard and save text/images to a history list whenever something is copied.

## Current Problem

I've tried several approaches:

1. **PyGObject/GTK3** - `clipboard.wait_for_text()` and async `request_text()` both return `None` because background apps can't access clipboard on Wayland without focus

2. **wl-paste --watch** - Returns error: "Watch mode requires a compositor that supports the wlroots data-control protocol" (GNOME doesn't support this)

3. **Polling with wl-paste** - Works but causes issues:
   - Interferes with Chrome's right-click context menu when trying to copy images
   - Makes the UI jitter
   - Can't open right-click menu while script is running

## What I Need

An **event-driven** solution (not polling) that:
- Monitors clipboard changes in real-time on GNOME Wayland
- Doesn't interfere with other apps (Chrome, Firefox, etc.)
- Can capture both text and images
- Works in the background without requiring window focus
- Doesn't require root/special permissions

## Questions

1. Is there a Python library or D-Bus interface for clipboard monitoring on GNOME Wayland?
2. Can I use the XDG Desktop Portal for clipboard monitoring?
3. Are there any GNOME-specific clipboard APIs I should use?
4. What's the proper way to monitor clipboard on GNOME without polling?

Please provide code examples if possible. Currently using Python 3.13 with PyGObject 3.54.5 available.
