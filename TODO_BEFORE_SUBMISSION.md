# TFCBM - Pre-Submission Checklist

## ⚠️ REQUIRED BEFORE SUBMISSION

### 1. UPDATE GITHUB URLs

Replace placeholder URLs in:

**File: `org.tfcbm.ClipboardManager.metainfo.xml`**
```xml
Line 33: <url type="homepage">https://github.com/dyslechtchitect/tfcbm</url>
Line 34: <url type="bugtracker">https://github.com/dyslechtchitect/tfcbm/issues</url>
Line 47: <image>https://raw.githubusercontent.com/dyslechtchitect/tfcbm/main/screenshots/main-window.png</image>
```

**File: `gnome-extension/metadata.json`**
```json
Line 14: "url": "https://github.com/dyslechtchitect/tfcbm-gnome-extension"
```

**File: `README.md`**
```markdown
Replace all instances of dyslechtchitect with your actual GitHub username
```

### 2. ADD SCREENSHOTS

Create `screenshots/` directory with:
- `main-window.png` (1280x720 or higher)
- `search-filter.png` (optional)
- `tags-management.png` (optional)

Take screenshots of:
- Main window with clipboard items
- Search/filter functionality
- Tag management (if applicable)

Then update the screenshot URL in `org.tfcbm.ClipboardManager.metainfo.xml`.

### 3. VERIFY LICENSE

Check that `LICENSE` file exists and matches GPL-3.0-or-later.

```bash
cat LICENSE | head -5
```

### 4. TEST LOCALLY

```bash
# Build and install
flatpak-builder --user --install --force-clean build-dir org.tfcbm.ClipboardManager.yml

# Run
flatpak run org.tfcbm.ClipboardManager

# Test full workflow:
# 1. Extension installs and enables
# 2. Clipboard monitoring works
# 3. UI displays items correctly
# 4. Quit from tray icon disables extension
```

### 5. CREATE GITHUB RELEASE

```bash
# Stage all changes
git add .

# Commit
git commit -m "chore: prepare for v1.0.0 release"

# Tag
git tag -a v1.0.0 -m "Release v1.0.0: Initial Flathub release"

# Push
`git push origin main
git push origin v1.0.0`
```

## 📦 FLATHUB SUBMISSION PROCESS

### Option 1: Via Flathub Website

1. Go to https://github.com/flathub/flathub
2. Click "New app submission" 
3. Follow the guided submission process
4. Provide your repository URL

### Option 2: Via Pull Request

1. Fork https://github.com/flathub/flathub
2. Add your manifest as `org.tfcbm.ClipboardManager.yml`
3. Create pull request
4. Wait for review from Flathub team

## ✅ VALIDATION COMMANDS

Run these before submitting:

```bash
# Validate AppStream metadata
appstream-util validate-relax org.tfcbm.ClipboardManager.metainfo.xml

# Validate desktop file
desktop-file-validate org.tfcbm.ClipboardManager.desktop

# Test build
flatpak-builder --force-clean build-dir org.tfcbm.ClipboardManager.yml
```

All should complete without errors.

## 📋 FILES FOR FLATHUB

These files will be used by Flathub:

**Required:**
- `org.tfcbm.ClipboardManager.yml` - Flatpak manifest
- `org.tfcbm.ClipboardManager.desktop` - Desktop entry
- `org.tfcbm.ClipboardManager.metainfo.xml` - AppStream metadata
- `LICENSE` - License file
- `README.md` - Project documentation

**Application Code:**
- `main.py` - Server entry point
- `ui/` - UI application
- `server/` - Backend server
- `gnome-extension/` - GNOME Shell extension
- `settings.yml` - Default settings
- `resouces/` - Resources (icons, etc.)
- `icons/` - Application icons

## 🚀 AFTER SUBMISSION

1. Monitor your Flathub pull request for reviewer feedback
2. Address any requested changes promptly
3. Once approved, your app will be published to Flathub
4. Users can install with: `flatpak install flathub org.tfcbm.ClipboardManager`

## 📞 NEED HELP?

- Flathub docs: https://docs.flathub.org/
- Flathub requirements: https://docs.flathub.org/docs/for-app-authors/requirements
- Contact: #flathub on Matrix

---

**Remember to delete this file before final submission!**
