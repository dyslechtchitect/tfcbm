# GNOME Version Numbers Explained

## Your Question: "Why GNOME 47 when I'm running GNOME 49?"

Great question! Here's the explanation:

## Two Different Things

### 1. GNOME Shell (Your Desktop)
- **Your version**: GNOME Shell 49.2
- **What it is**: The desktop environment you're running
- **Where it matters**: The GNOME Extension

### 2. GNOME Platform (Flatpak Runtime)
- **Manifest version**: GNOME Platform 47
- **What it is**: The SDK/libraries your Flatpak app uses
- **Where it matters**: The Flatpak manifest

## Why This Works

Your Flatpak app built with **Platform 47** will run perfectly on **GNOME Shell 49** because:

1. **Runtime != Desktop Version**: The Flatpak runtime provides GTK4, Libadwaita, and other libraries. It's not tied to your GNOME Shell version.

2. **Backward/Forward Compatible**: Apps built with Platform 47 work on all modern GNOME versions (including 49).

3. **Flathub Standard**: Platform 47 is the current stable runtime on Flathub. Using it ensures maximum compatibility.

## What About Platform 49?

According to recent announcements (October 2025), GNOME Platform 49 is available, but:

- **For Flathub submission**, stick with **Platform 47** (stable, tested, recommended)
- Platform 49 might be too new and not yet the default on Flathub
- Your app doesn't need Platform 49 features - Platform 47 is perfect

## Your Extension is Correct

Your GNOME Extension `metadata.json` correctly declares:

```json
"shell-version": [
  "43", "44", "45", "46", "47", "48", "49"
]
```

This means:
- ✅ Extension works on Shell 43 through 49
- ✅ Includes your current Shell version (49)
- ✅ Future-proof for users on different versions

## Summary

```
┌─────────────────────────────────────────────────────────┐
│ Your Setup                                              │
├─────────────────────────────────────────────────────────┤
│ Desktop:              GNOME Shell 49.2                  │
│ Flatpak Runtime:      GNOME Platform 47                 │
│ Extension Supports:   Shell 43-49                       │
│                                                         │
│ ✅ Everything is configured correctly!                  │
└─────────────────────────────────────────────────────────┘
```

## If You Want to Use Platform 49

You *could* change the manifest to use Platform 49:

```yaml
runtime: org.gnome.Platform
runtime-version: '49'
sdk: org.gnome.Sdk
```

But you'd need to:
1. Check if Platform 49 SDK is available on Flathub
2. Install it: `flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49`
3. Test build compatibility

**Recommendation**: Stick with Platform 47 for Flathub submission. It's the safe, stable choice.

## Real-World Example

Many apps on Flathub use older Platform versions but run perfectly on newer GNOME:

- App built with Platform 45 → Works on GNOME 49 ✅
- App built with Platform 46 → Works on GNOME 49 ✅
- App built with Platform 47 → Works on GNOME 49 ✅

---

**Bottom Line**: Your manifest using Platform 47 is **correct and recommended** for Flathub submission, even though you're running GNOME Shell 49. They're different versioning schemes for different components.
