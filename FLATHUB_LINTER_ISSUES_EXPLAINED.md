# Flathub Linter Issues - Detailed Explanations

This document provides detailed explanations of each linter error found when validating your Flatpak submission for Flathub.

## Issue 1: Invalid URL Type in Metainfo (CRITICAL)

### What's Wrong?

**Location**: `org.tfcbm.ClipboardManager.metainfo.xml:69`

```xml
<url type="license">https://www.gnu.org/licenses/gpl-3.0.html</url>
```

**Problem**: AppStream specification does not recognize `"license"` as a valid URL type.

### Valid URL Types

According to the AppStream specification, the only valid URL types are:

- `homepage` - Project homepage
- `bugtracker` - Bug/issue tracker
- `donation` - Donation page
- `translate` - Translation/localization page
- `vcs-browser` - Source code repository browser (like GitHub)
- `contribute` - Contribution guidelines
- `contact` - Contact information
- `faq` - FAQ page
- `help` - Help/documentation page

### How to Fix

**Option 1**: Remove the license URL line entirely (recommended)
- The license is already specified in `<project_license>GPL-3.0-or-later</project_license>` on line 5
- This is sufficient for Flathub - no additional license URL is needed

**Option 2**: Change it to use `vcs-browser` type if you want to link to your repository's LICENSE file
```xml
<url type="vcs-browser">https://github.com/dyslechtchitect/tfcbm</url>
```

### Recommended Fix

Simply delete line 69. The license information is already properly declared in the `<project_license>` tag.

---

## Issue 2: Screenshot URLs Not Reachable (CRITICAL)

### What's Wrong?

**Location**: `org.tfcbm.ClipboardManager.metainfo.xml:37, 42, 47, 52, 57, 62`

Your metainfo.xml contains screenshot URLs like:
```xml
<image>https://raw.githubusercontent.com/yourusername/tfcbm/main/screenshots/general.png</image>
```

**Problems**:
1. The URLs contain placeholder text `"yourusername"` instead of your actual GitHub username
2. These URLs return 404 errors because they don't exist
3. One screenshot reference has a filename mismatch

### Your Actual Screenshots

You have the following screenshots in your `screenshots/` directory:
- `general.png` ✓
- `tags.png` ✓
- `search.png` ✓
- `secret.png` ✓
- `filters.png` ⚠️ (metainfo.xml references `filter.png` - singular)
- `settings.png` ✓

### How to Fix

Replace all instances of `yourusername` with your actual GitHub username: `dyslechtchitect`

**Before**:
```xml
<image>https://raw.githubusercontent.com/yourusername/tfcbm/main/screenshots/general.png</image>
```

**After**:
```xml
<image>https://raw.githubusercontent.com/dyslechtchitect/TFCBM/main/screenshots/general.png</image>
```

**Also fix the filename mismatch** on line 57:
```xml
<!-- Change this: -->
<image>https://raw.githubusercontent.com/yourusername/tfcbm/main/screenshots/filter.png</image>

<!-- To this: -->
<image>https://raw.githubusercontent.com/dyslechtchitect/TFCBM/main/screenshots/filters.png</image>
```

**Note**: Make sure your screenshots are committed and pushed to your GitHub repository's main branch before submitting to Flathub!

---

## Issue 3: App ID URL Not Reachable (WARNING)

### What's Wrong?

**Problem**: Flathub tried to access `https://tfcbm.org` and couldn't reach it (because the domain doesn't exist).

**Why is it checking this?**: When you use an app ID like `org.tfcbm.ClipboardManager`, Flathub's linter attempts to verify that the reversed domain `tfcbm.org` is owned/controlled by you to prevent app ID squatting.

### Can You Use GitHub URL Instead?

**Yes, absolutely!** You have two options:

**Option 1: Use GitHub-based App ID (RECOMMENDED)**

Change your app ID to be based on your GitHub repository:
- Current: `org.tfcbm.ClipboardManager`
- Recommended: `io.github.dyslechtchitect.tfcbm`

This is a common pattern for GitHub-hosted projects. You would need to rename:
- `org.tfcbm.ClipboardManager.yml` → `io.github.dyslechtchitect.tfcbm.yml`
- `org.tfcbm.ClipboardManager.metainfo.xml` → `io.github.dyslechtchitect.tfcbm.metainfo.xml`
- `org.tfcbm.ClipboardManager.desktop` → `io.github.dyslechtchitect.tfcbm.desktop`
- Update all references in these files

**Option 2: Keep current App ID and request exception**

If you prefer to keep `org.tfcbm.*`, you can request an exception from Flathub by documenting that:
- You don't own tfcbm.org
- This is a personal project
- The name is unique enough to avoid conflicts

Many personal projects get approved with this exception, especially if the name is distinctive.

**Option 3: Register the domain**

Buy `tfcbm.org` and make it point to your GitHub project page. This is overkill for most personal projects.

---

## Issue 4: Arbitrary DBus Access (WARNING - May Need Exception)

### What's Wrong?

**Location**: `org.tfcbm.ClipboardManager.yml:14`

```yaml
- --socket=session-bus
```

**Problem**: This grants your app access to the entire session DBus, which is a broad permission. Flathub prefers apps use specific `--talk-name` permissions instead.

### Why Your App Needs This

Your clipboard manager legitimately needs DBus access for:
1. Communicating with GNOME Shell for clipboard monitoring
2. System notifications
3. Inter-process communication between app components

### Currently Declared Permissions

```yaml
- --socket=session-bus                      # Full session bus access
- --system-talk-name=org.freedesktop.DBus   # System bus access
- --talk-name=org.gnome.Shell               # GNOME Shell
- --talk-name=org.freedesktop.portal.Desktop # Portal access
- --talk-name=org.freedesktop.Flatpak       # Flatpak management
```

### How to Fix or Justify

**Option 1: Narrow down permissions (IDEAL)**

If possible, replace `--socket=session-bus` with specific services you actually use:
```yaml
# Instead of full session bus, use specific services:
- --talk-name=org.gnome.Shell
- --talk-name=org.freedesktop.Notifications
- --talk-name=org.gnome.SessionManager
- --own-name=org.tfcbm.ClipboardManager
# etc.
```

**Option 2: Request an exception (if necessary)**

If you genuinely need full session bus access (e.g., for dynamic service discovery), document why in your Flathub submission:
- Clipboard monitoring requires listening to multiple DBus signals
- Dynamic service communication between UI and backend
- GNOME Shell extension integration requires broader access

### System DBus Warning

```yaml
- --system-talk-name=org.freedesktop.DBus
```

This is also flagged. System bus access is rarely needed. Review if you actually use this. Most clipboard operations only need session bus.

---

## Issue 5: Flatpak Spawn Access (WARNING - Likely Legitimate)

### What's Wrong?

**Problem**: Your manifest includes `--talk-name=org.freedesktop.Flatpak` which gives the app ability to spawn processes outside the sandbox.

### Why Your App Needs This

**This is LEGITIMATE for your use case!** Your app needs to install the GNOME Shell extension, which requires running host commands.

Found in your manifest:
```yaml
# Allow talking to host for extension installation
- --talk-name=org.freedesktop.Flatpak
```

And your extension installer script uses:
```bash
# Running inside flatpak - use flatpak-spawn to run host commands
CMD_PREFIX="flatpak-spawn --host"
```

### How to Handle This

**Document it in your Flathub submission PR**:

When submitting, add a comment explaining:
```
This app requires flatpak-spawn access to install the GNOME Shell extension
on the host system. The extension is optional but provides seamless clipboard
monitoring integration. The installation is interactive and user-initiated.
```

This is a **valid use case** and reviewers will likely approve it once they understand the requirement.

---

## Summary of Required Fixes

### CRITICAL (Must Fix Before Submission)

1. ✅ **Remove or fix the license URL** (line 69 in metainfo.xml)
2. ✅ **Update screenshot URLs** - replace `yourusername` with `dyslechtchitect`
3. ✅ **Fix screenshot filename mismatch** - `filter.png` → `filters.png`
4. ✅ **Ensure screenshots are pushed to GitHub** main branch

### RECOMMENDED (Improve Your Submission)

5. ⚠️ **Consider changing App ID** to `io.github.dyslechtchitect.tfcbm` to avoid domain ownership questions

### DOCUMENTATION NEEDED (For Flathub Reviewers)

6. 📝 **Document why flatpak-spawn is needed** - GNOME extension installation
7. 📝 **Document why session-bus access is needed** - clipboard monitoring and DBus communication
8. 📝 **Consider narrowing DBus permissions** if possible

---

## Quick Fix Checklist

- [ ] Delete line 69 from `org.tfcbm.ClipboardManager.metainfo.xml` (license URL)
- [ ] Update all screenshot URLs: `yourusername` → `dyslechtchitect`
- [ ] Update screenshot URL: `screenshots/filter.png` → `screenshots/filters.png`
- [ ] Verify screenshot URLs work by visiting them in a browser
- [ ] App ID: change to `io.github.dyslechtchitect.*`
- [ ] Review and minimize DBus permissions if possible
- [ ] Remove `--system-talk-name=org.freedesktop.DBus` if not actually needed
- [ ] Prepare justification text for flatpak-spawn access
- [ ] Test build again with fixes: `flatpak run --command=flathub-build org.flatpak.Builder --install org.tfcbm.ClipboardManager.yml`
- [ ] Run linters again and verify errors are resolved

---

## Need Help?

- [Flathub Linter Documentation](https://docs.flathub.org/linter)
- [AppStream Specification](https://www.freedesktop.org/software/appstream/docs/)
- [Flatpak Permissions Reference](https://docs.flatpak.org/en/latest/sandbox-permissions.html)
