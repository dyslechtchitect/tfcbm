# TFCBM Flatpak Submission Guide

## Overview

This guide will help you submit TFCBM to Flathub and publish the GNOME Extension to extensions.gnome.org.

## Prerequisites

Before you start, you'll need:

1. **GitHub Account** - For both Flathub and extensions.gnome.org
2. **Screenshots** - Take high-quality screenshots of your app (1280x720 or higher)
3. **Flatpak Builder** - Install with: `sudo dnf install flatpak-builder` (Fedora) or `sudo apt install flatpak-builder` (Debian/Ubuntu)

## Part 1: Building and Testing Flatpak Locally

### Step 1: Install Flatpak Builder

```bash
sudo dnf install flatpak-builder
```

### Step 2: Add Flathub Repository

```bash
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
```

### Step 3: Install GNOME Runtime

```bash
flatpak install flathub org.gnome.Platform//47 org.gnome.Sdk//47
```

**Note**: We use GNOME Platform 47 as the runtime even if you're running GNOME Shell 49.
The Flatpak runtime version is separate from your desktop GNOME Shell version.
Platform 47 is the current stable runtime on Flathub and your app will work perfectly
on any GNOME Shell version (including 49).

### Step 4: Build Your Flatpak

```bash
# Create build directory
mkdir -p build-dir

# Build the Flatpak
flatpak-builder --force-clean build-dir org.tfcbm.ClipboardManager.yml

# Install and test locally
flatpak-builder --user --install --force-clean build-dir org.tfcbm.ClipboardManager.yml

# Run your app
flatpak run org.tfcbm.ClipboardManager
```

### Step 5: Validate Your Metadata

```bash
# Install appstream-util
sudo dnf install libappstream-glib

# Validate the AppData file
appstream-util validate-relax org.tfcbm.ClipboardManager.metainfo.xml

# Validate desktop file
desktop-file-validate org.tfcbm.ClipboardManager.desktop
```

## Part 2: Preparing for Flathub Submission

### Step 1: Update Metadata with Real Information

Before submitting, you MUST update these files:

#### 1. Update `org.tfcbm.ClipboardManager.metainfo.xml`

- Replace `https://github.com/yourusername/tfcbm` with your actual GitHub URL
- Add actual screenshots to your GitHub repository
- Update screenshot URLs to point to your repository
- Update release date and version

#### 2. Update `gnome-extension/metadata.json`

- Replace `https://github.com/yourusername/tfcbm-gnome-extension` with your actual URL
- Ensure the UUID is correct: `tfcbm-clipboard-monitor@github.com`

### Step 2: Add Screenshots

1. Create a `screenshots` directory in your GitHub repository:
   ```bash
   mkdir screenshots
   ```

2. Take screenshots of your app (use GNOME Screenshot or similar)
   - Main window showing clipboard history
   - Settings page
   - Search/filter functionality
   - Tag management

3. Save screenshots as PNG files (1280x720 recommended)

4. Upload to GitHub and update URLs in metainfo.xml

### Step 3: Create a Flathub Repository

1. Go to https://github.com/flathub/flathub
2. Read the submission requirements
3. Fork the Flathub repository
4. Create a new repository for your app: `org.tfcbm.ClipboardManager`

### Step 4: Prepare Your Flathub Repository

Your Flathub repository should contain:

```
org.tfcbm.ClipboardManager/
├── org.tfcbm.ClipboardManager.yml          # Your Flatpak manifest
├── org.tfcbm.ClipboardManager.metainfo.xml # AppData file
└── org.tfcbm.ClipboardManager.desktop      # Desktop file
```

**Important**: Update the manifest to use `git` sources instead of `dir`:

```yaml
sources:
  - type: git
    url: https://github.com/yourusername/tfcbm
    tag: v1.0.0  # or commit hash
```

### Step 5: Submit to Flathub

1. Create a PR at https://github.com/flathub/flathub/pulls
2. Request to add your app repository
3. Fill out the PR template
4. Wait for review

## Part 3: Publishing GNOME Extension

### Step 1: Prepare Extension Package

The extension is already packaged: `tfcbm-gnome-extension.zip` (20KB)

### Step 2: Create extensions.gnome.org Account

1. Go to https://extensions.gnome.org/
2. Click "Register" or login with your GNOME account
3. Verify your email

### Step 3: Upload Extension

1. Go to https://extensions.gnome.org/upload/
2. Upload `tfcbm-gnome-extension.zip`
3. Fill in extension details:
   - **Name**: TFCBM Clipboard Monitor
   - **Description**: Use the description from `gnome-extension/metadata.json`
   - **Screenshot**: Upload a screenshot showing the extension in action
   - **URL**: Your GitHub repository

### Step 4: Extension Review

- The GNOME Extensions team will review your submission
- They may request changes
- Once approved, it will be published

## Part 4: Post-Submission Tasks

### Keep Your App Updated

When you release updates:

1. **For Flatpak/Flathub**:
   - Update version in metainfo.xml
   - Add new release entry to metainfo.xml
   - Update the manifest to point to new tag/commit
   - Submit PR to your Flathub repository

2. **For GNOME Extension**:
   - Update version in metadata.json
   - Create new zip package
   - Upload to extensions.gnome.org

## Testing Checklist

Before submission, verify:

- [ ] App runs correctly from Flatpak
- [ ] Icon appears in app launcher
- [ ] Desktop file is valid
- [ ] AppData file is valid
- [ ] All URLs are updated to your GitHub
- [ ] Screenshots are added
- [ ] Extension installs and enables correctly
- [ ] Extension works with all declared GNOME Shell versions
- [ ] License files are included
- [ ] README is up to date

## Common Issues and Solutions

### Flatpak Build Fails

**Problem**: Missing dependencies or wrong URLs

**Solution**:
- Check that all Python package URLs and SHA256 hashes are correct
- Run with `--verbose` flag to see detailed errors
- Check Flathub documentation for examples

### Extension Not Working

**Problem**: Extension doesn't enable or crashes

**Solution**:
- Check GNOME Shell version compatibility
- Look at GNOME Shell logs: `journalctl -f /usr/bin/gnome-shell`
- Test manually first: Copy to `~/.local/share/gnome-shell/extensions/`

### Validation Errors

**Problem**: appstream-util or desktop-file-validate shows errors

**Solution**:
- Fix all errors shown
- Warnings are okay but try to fix them too
- Check examples from other apps on Flathub

## Resources

- **Flathub Documentation**: https://docs.flathub.org/
- **Flatpak Builder Documentation**: https://docs.flatpak.org/en/latest/flatpak-builder.html
- **AppData Guidelines**: https://www.freedesktop.org/software/appstream/docs/
- **GNOME Extension Guidelines**: https://gjs.guide/extensions/
- **Desktop Entry Specification**: https://specifications.freedesktop.org/desktop-entry-spec/latest/

## Quick Commands Reference

```bash
# Build Flatpak
flatpak-builder --force-clean build-dir org.tfcbm.ClipboardManager.yml

# Install locally
flatpak-builder --user --install --force-clean build-dir org.tfcbm.ClipboardManager.yml

# Run app
flatpak run org.tfcbm.ClipboardManager

# Validate AppData
appstream-util validate-relax org.tfcbm.ClipboardManager.metainfo.xml

# Validate desktop file
desktop-file-validate org.tfcbm.ClipboardManager.desktop

# Test extension
gnome-extensions install tfcbm-gnome-extension.zip
gnome-extensions enable tfcbm-clipboard-monitor@github.com

# Package extension
cd gnome-extension && zip -r ../tfcbm-gnome-extension.zip . -x "*.git*" -x "*.idea*" -x "*.claude*"
```

## Getting Help

- **Flathub Matrix**: #flathub:matrix.org
- **GNOME Extensions**: https://discourse.gnome.org/c/extensions/11
- **Flatpak IRC**: #flatpak on irc.oftc.net

---

Good luck with your submission! The GNOME and Flatpak communities are helpful, so don't hesitate to ask questions.
