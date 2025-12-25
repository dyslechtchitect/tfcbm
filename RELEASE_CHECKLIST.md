# TFCBM Release Checklist

## Before You Submit - CRITICAL UPDATES NEEDED

### 🚨 MUST DO BEFORE SUBMISSION

#### 1. Update GitHub URLs

Replace all placeholder URLs with your actual GitHub repository URLs:

**Files to update:**
- `org.tfcbm.ClipboardManager.metainfo.xml`
  - Line 33: `<url type="homepage">`
  - Line 34: `<url type="bugtracker">`
  - Line 47: Screenshot URL

- `gnome-extension/metadata.json`
  - Line 14: `"url"` field

**Current placeholder**: `https://github.com/yourusername/tfcbm`
**Replace with**: Your actual repository URL

#### 2. Add Screenshots

1. Create `screenshots/` directory in your repository
2. Take these screenshots (1280x720 or higher):
   - [ ] Main window with clipboard items
   - [ ] Search/filter in action
   - [ ] Tag management
   - [ ] Settings page (if applicable)
3. Save as PNG files
4. Commit to GitHub
5. Update screenshot URLs in `org.tfcbm.ClipboardManager.metainfo.xml`

#### 3. Update Version and Release Info

In `org.tfcbm.ClipboardManager.metainfo.xml`:
- [ ] Update release date (currently: 2025-01-01)
- [ ] Set correct version number
- [ ] Add actual release notes

#### 4. Verify License

- [ ] Ensure LICENSE file exists in root directory
- [ ] Verify license in metainfo.xml matches actual license
- [ ] Update if needed (currently set to GPL-3.0-or-later)

## File Checklist

### ✅ Created Files (Ready)

- [x] `org.tfcbm.ClipboardManager.yml` - Flatpak manifest
- [x] `org.tfcbm.ClipboardManager.metainfo.xml` - AppData file
- [x] `org.tfcbm.ClipboardManager.desktop` - Desktop entry
- [x] `tfcbm-gnome-extension.zip` - Extension package (20KB)
- [x] `icons/` - Icon files in multiple sizes
- [x] `FLATPAK_SUBMISSION_GUIDE.md` - Submission instructions

### ⚠️ Files Needing Updates

- [ ] `org.tfcbm.ClipboardManager.metainfo.xml` - Update URLs and screenshots
- [ ] `gnome-extension/metadata.json` - Update URL
- [ ] Create `LICENSE` file if not exists
- [ ] Create `screenshots/` directory with actual screenshots

## Pre-Submission Testing

### Flatpak Testing

```bash
# Install flatpak-builder
sudo dnf install flatpak-builder

# Add Flathub
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Install GNOME runtime
flatpak install flathub org.gnome.Platform//47 org.gnome.Sdk//47

# Build and test
flatpak-builder --force-clean build-dir org.tfcbm.ClipboardManager.yml
flatpak-builder --user --install --force-clean build-dir org.tfcbm.ClipboardManager.yml

# Run the app
flatpak run org.tfcbm.ClipboardManager
```

**Test checklist:**
- [ ] App launches successfully
- [ ] Icon appears in launcher
- [ ] All features work
- [ ] No error messages in console
- [ ] Database and settings work correctly
- [ ] Clipboard monitoring works

### Extension Testing

```bash
# Install extension
gnome-extensions install tfcbm-gnome-extension.zip

# Enable extension
gnome-extensions enable tfcbm-clipboard-monitor@github.com

# Check for errors
journalctl -f /usr/bin/gnome-shell
```

**Test checklist:**
- [ ] Extension installs without errors
- [ ] Extension enables successfully
- [ ] Keyboard shortcut works (Ctrl+Escape)
- [ ] Clipboard monitoring works
- [ ] DBus communication with app works
- [ ] Works on all declared GNOME Shell versions (43-49)

### Validation

```bash
# Validate AppData
appstream-util validate-relax org.tfcbm.ClipboardManager.metainfo.xml

# Validate desktop file
desktop-file-validate org.tfcbm.ClipboardManager.desktop
```

**Expected result:**
- [ ] No errors (warnings are okay)
- [ ] All metadata is valid

## Git Repository Preparation

```bash
# Add all new files
git add org.tfcbm.ClipboardManager.*
git add icons/
git add FLATPAK_SUBMISSION_GUIDE.md
git add RELEASE_CHECKLIST.md

# Commit
git commit -m "Add Flatpak and GNOME Extension packaging

- Add Flatpak manifest for Flathub submission
- Add AppData XML metadata
- Add desktop entry file
- Generate icons in all required sizes
- Package GNOME Extension for extensions.gnome.org
- Add submission guides and documentation
"

# Tag release
git tag -a v1.0.0 -m "Release v1.0.0"

# Push (update origin URL first!)
git remote set-url origin https://github.com/yourusername/tfcbm.git
git push origin master
git push origin v1.0.0
```

## Flathub Submission Steps

### 1. Prepare Flathub Manifest

Update `org.tfcbm.ClipboardManager.yml` to use git sources:

```yaml
sources:
  - type: git
    url: https://github.com/yourusername/tfcbm
    tag: v1.0.0
    # OR use commit hash:
    # commit: abc123def456...
```

### 2. Create Flathub Repository

1. Go to: https://github.com/flathub/flathub
2. Read: https://docs.flathub.org/docs/for-app-authors/submission
3. Create PR requesting new app repository

### 3. Set Up Your Flathub Repo

Once approved, your repo will be: `https://github.com/flathub/org.tfcbm.ClipboardManager`

Add these files:
- `org.tfcbm.ClipboardManager.yml`
- `org.tfcbm.ClipboardManager.metainfo.xml`
- `org.tfcbm.ClipboardManager.desktop`
- `README.md` (optional but recommended)

### 4. Submit for Review

- Create PR to flathub/flathub
- Fill out template
- Wait for review

## GNOME Extension Submission Steps

### 1. Create Account

- Go to: https://extensions.gnome.org/
- Register or login
- Verify email

### 2. Upload Extension

- Go to: https://extensions.gnome.org/upload/
- Upload: `tfcbm-gnome-extension.zip`
- Fill in details
- Submit for review

### 3. Extension Details

**Name**: TFCBM Clipboard Monitor

**Description**:
```
Monitors clipboard changes and provides integration with the TFCBM application.

Features:
• Automatic clipboard monitoring for text, images, and files
• Keyboard shortcut for quick access (Ctrl+Escape)
• System tray integration
• Secure DBus communication with TFCBM app

Privacy: All clipboard data is only sent to the TFCBM application running locally on your system via DBus. No data is sent to external servers.

Requires: TFCBM application (available on Flathub)
```

**URL**: Your GitHub repository
**Screenshot**: Take a screenshot showing the extension icon and keyboard shortcut in action

## Post-Submission

### Flathub

- Monitor your PR for reviewer comments
- Make requested changes
- Once merged, your app will appear on Flathub within 24 hours

### Extensions.gnome.org

- Check your submission status
- Respond to any review comments
- Once approved, extension is live immediately

## Future Updates

### Releasing New Versions

1. Update code in your repository
2. Update version in `org.tfcbm.ClipboardManager.metainfo.xml`
3. Add new release entry to metainfo.xml
4. Create git tag: `git tag -a v1.1.0 -m "Release v1.1.0"`
5. Push tag: `git push origin v1.1.0`

**For Flatpak:**
- Update manifest to point to new tag
- Commit to Flathub repository
- PR is auto-created and built

**For Extension:**
- Update version in `metadata.json`
- Create new zip
- Upload to extensions.gnome.org

## Quick Reference

**Current Files:**
- Flatpak manifest: `org.tfcbm.ClipboardManager.yml`
- AppData: `org.tfcbm.ClipboardManager.metainfo.xml`
- Desktop file: `org.tfcbm.ClipboardManager.desktop`
- Extension package: `tfcbm-gnome-extension.zip`
- Icons: `icons/hicolor/{size}/apps/org.tfcbm.ClipboardManager.{png,svg}`

**Important IDs:**
- App ID: `org.tfcbm.ClipboardManager`
- Extension UUID: `tfcbm-clipboard-monitor@github.com`
- DBus service: `org.tfcbm.ClipboardManager`

**Support:**
- Flathub Matrix: #flathub:matrix.org
- GNOME Discourse: https://discourse.gnome.org/c/extensions/11

---

## Summary: What You Need To Do Now

1. **Update all GitHub URLs** in metainfo.xml and metadata.json
2. **Add screenshots** to your repository and update URLs
3. **Test the Flatpak build** locally
4. **Test the extension** installation and functionality
5. **Create a GitHub release** with tag v1.0.0
6. **Submit to Flathub** following the guide
7. **Submit extension** to extensions.gnome.org

That's it! Follow the FLATPAK_SUBMISSION_GUIDE.md for detailed instructions.
