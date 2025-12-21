# TFCBM - Flathub Preparation & Code Review Plan

**Date:** 2025-12-21
**Project:** TFCBM (The F*cking Clipboard Manager)
**Target:** GNOME Software via Flathub
**Status:** Functional, NOT Flathub-ready

---

## Executive Summary

**Code Quality: 9/10** - Excellent architecture, clean design patterns, well-tested
**Packaging: 2/10** - Missing critical infrastructure for distribution

**Estimated Effort:** 1-2 weeks for one developer
**Blockers:** 8 critical issues, 12 high-priority issues
**Repository Size:** 201 MB → should be ~15-20 MB after cleanup

### Quick Assessment

✅ **What's Good:**
- Clean layered architecture (UI, Services, Domain)
- Proper dependency injection container
- Protocol-based design patterns
- Comprehensive test suite
- Well-documented codebase

❌ **What Blocks Flathub:**
- No build system (pyproject.toml, setup.py)
- Hardcoded absolute paths everywhere
- Missing D-Bus service files
- Missing appdata.xml metadata
- No Flatpak manifest
- Naming inconsistencies
- Potentially offensive app name

---

## Critical Issues (Must Fix Before Submission)

### 1. Missing Build System Files ⚠️ BLOCKER

**Current State:** No packaging infrastructure
**Impact:** Cannot be installed or distributed
**Effort:** 2 days

**Missing Files:**
```
❌ /pyproject.toml          # Modern Python packaging standard
❌ /setup.py                # Package metadata (or use pyproject.toml only)
❌ /MANIFEST.in             # Non-Python file inclusion rules
❌ /org.tfcbm.ClipboardManager.yaml  # Flatpak manifest
```

**Why This Matters:**
- Flathub requires a Flatpak manifest
- Python needs proper package metadata
- Resources (icons, CSS, etc.) must be included in package

---

### 2. Hardcoded Absolute Paths ⚠️ BLOCKER

**Current State:** Paths point to `/home/ron/Documents/git/TFCBM/`
**Impact:** App won't run for anyone else or in Flatpak sandbox
**Effort:** 1 day

**Files With Hardcoded Paths:**

```bash
# Desktop Entry
org.tfcbm.ClipboardManager.desktop:
  Exec=/home/ron/Documents/git/TFCBM/.venv/bin/python3 /home/ron/Documents/git/TFCBM/ui/main.py
  Icon=/home/ron/Documents/git/TFCBM/resouces/icon.svg

# Python Code (multiple files)
ui/main.py:
  CSS_PATH = "/home/ron/Documents/git/TFCBM/ui/style.css"

ui/application/css_loader.py:
  CSS file paths hardcoded

ui/builders/main_window_builder.py:
  loader_path = Path(__file__).parent.parent.parent / "resouces" / "loader.svg"
  # This one is OK (relative), but "resouces" is a typo
```

**Required Changes:**
- Use `pkg_resources` or `importlib.resources` for resource files
- Desktop file: `Exec=tfcbm` (installed command)
- Desktop file: `Icon=org.tfcbm.ClipboardManager` (theme icon name)
- Install resources to standard XDG locations

---

### 3. Missing D-Bus Service File ⚠️ BLOCKER

**Current State:** Desktop file declares `DBusActivatable=true` but no service
**Impact:** Desktop activation won't work
**Effort:** 1 hour

**What's Needed:**

Create `/data/org.tfcbm.ClipboardManager.service`:
```ini
[D-BUS Service]
Name=org.tfcbm.ClipboardManager
Exec=/app/bin/tfcbm
```

---

### 4. Missing Application Metadata ⚠️ BLOCKER

**Current State:** No appdata.xml file
**Impact:** Won't appear in GNOME Software, Flathub will reject
**Effort:** 1 day (including screenshots)

**What's Needed:**

Create `/data/org.tfcbm.ClipboardManager.appdata.xml`:
- App description
- Screenshots (at least 1, ideally 3-5)
- Release notes
- Developer info
- Content rating
- Update contact

---

### 5. Desktop File Not in Standard Location ⚠️ BLOCKER

**Current State:** `org.tfcbm.ClipboardManager.desktop` in project root
**Impact:** Non-standard, won't be found by desktop environment
**Effort:** 30 minutes

**Required:**
- Move to `/data/applications/org.tfcbm.ClipboardManager.desktop`
- Fix hardcoded paths (see issue #2)
- Validate with `desktop-file-validate`

---

### 6. No Flatpak Manifest ⚠️ BLOCKER

**Current State:** No Flatpak build configuration
**Impact:** Cannot submit to Flathub
**Effort:** 1 day (including testing)

**What's Needed:**

Create `/org.tfcbm.ClipboardManager.yaml`:
- Runtime: org.gnome.Platform version 47
- SDK: org.gnome.Sdk version 47
- Finish args (permissions)
- Build modules
- Python dependencies
- GNOME extension packaging

---

### 7. Naming Inconsistencies ⚠️ HIGH

**Current State:** Mismatched IDs across components
**Impact:** Confusing, prevents proper integration
**Effort:** 2 hours

**Current Naming:**
```
Main App ID:       org.tfcbm.ClipboardManager        ✓
Extension UUID:    simple-clipboard@tfcbm            ✗
Extension Schema:  org.gnome.shell.extensions.simple-clipboard  ✗
Desktop File:      org.tfcbm.ClipboardManager.desktop  ✓
```

**Should Be:**
```
Main App ID:       org.tfcbm.ClipboardManager
Extension UUID:    clipboard-manager@tfcbm
Extension Schema:  org.gnome.shell.extensions.clipboard-manager
Desktop File:      org.tfcbm.ClipboardManager.desktop
```

**Files to Update:**
- `gnome-extension/metadata.json` - UUID
- `gnome-extension/schemas/*.gschema.xml` - Schema ID
- `gnome-extension/extension.js` - Schema references
- Recompile gschemas

---

### 8. Potentially Offensive App Name ⚠️ HIGH

**Current State:** "The F*cking Clipboard Manager"
**Impact:** May violate Flathub content guidelines
**Effort:** 1 day

**Recommendations:**
1. **Safe Option:** "TFCBM Clipboard Manager" (keep acronym, drop meaning)
2. **Descriptive:** "The Feature-Complete Clipboard Manager"
3. **Creative:** "The Functional Clipboard Manager"
4. **Keep it:** Ask Flathub reviewers (risky)

**Files to Update:**
- Desktop file `Comment` field
- All documentation
- README.md
- About dialog
- appdata.xml

---

## Repository Cleanup (Must Do)

### Dead Code to Remove

**1. Dead Shell Scripts** (3 files)
```bash
rm install.sh                  # Superseded by run.sh
rm check-extension.sh         # Subset of check_status.sh
rm uninstall_extension.sh     # Superseded by uninstall.sh
```

**2. Legacy Test Files in Root** (10 files)
```bash
# Move to tests/ or delete:
test_about_window.py
test_add_items.py
test_highlight.py
test_screenshot.py
test_thumbnail.py
test_ui_connection.py
test_ui_image.py
test_websocket_connection.py
test_websocket_max_size.py
test_websocket_max_size_client.py
```

**3. Backup Files** (3 files)
```bash
rm ui/main_original.py.backup
rm ui/main.py.backup
rm test_clipboard.py.old
```

**4. Repository Bloat** (114 MB!)
```bash
# Add to .gitignore:
gnome-extension/node_modules/  # 54 MB (regenerate on build)
.venv/                         # 60 MB (never commit venvs)
__pycache__/                   # Python cache
.pytest_cache/                 # Pytest cache
test_app/.venv/                # POC venv
logs/                          # Runtime logs

# Consider removing (46 MB):
test_app/  # Proof-of-concept - useful but large
```

**5. Directory Name Typo**
```bash
mv resouces/ resources/
# Update all references in code
```

**6. Duplicate Requirements File**
```bash
rm requierments.txt  # Typo + confusing (has system deps)
# Document system deps in README instead
```

### .gitignore Updates

Add to `.gitignore`:
```gitignore
# Virtual environments
.venv/
venv/
env/

# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd

# Test cache
.pytest_cache/
htmlcov/
.coverage

# IDE
.idea/
.vscode/
*.swp

# Logs
logs/
*.log

# Node
node_modules/
package-lock.json  # Keep this if you want reproducible builds

# Build artifacts
build/
dist/
*.egg-info/
```

---

## Code Quality Issues & Bad Patterns

### 1. Resource Loading (Multiple Files)

**Bad Pattern:**
```python
# Hardcoded absolute path
CSS_PATH = "/home/ron/Documents/git/TFCBM/ui/style.css"

# Fragile relative path
loader_path = Path(__file__).parent.parent.parent / "resouces" / "loader.svg"
```

**Good Pattern:**
```python
# Use importlib.resources (Python 3.9+)
from importlib.resources import files

def get_resource_path(resource_name):
    """Get path to a bundled resource."""
    return files('tfcbm.resources').joinpath(resource_name)

# Or use pkg_resources (older)
import pkg_resources
css_path = pkg_resources.resource_filename('tfcbm', 'style.css')
```

**Files to Fix:**
- `ui/main.py`
- `ui/application/css_loader.py`
- `ui/builders/main_window_builder.py`
- `ui/splash.py` (if loads images)

---

### 2. Settings/Config Paths

**Bad Pattern:**
```python
# Assumes current directory
with open("settings.yml") as f:
    settings = yaml.load(f)
```

**Good Pattern:**
```python
# Use XDG directories
from pathlib import Path
import os

def get_config_dir():
    """Get XDG config directory."""
    config_home = os.getenv('XDG_CONFIG_HOME', Path.home() / '.config')
    return Path(config_home) / 'tfcbm'

def get_data_dir():
    """Get XDG data directory."""
    data_home = os.getenv('XDG_DATA_HOME', Path.home() / '.local' / 'share')
    return Path(data_home) / 'tfcbm'
```

**Files to Check:**
- `settings.py`
- `database.py` (SQLite path)
- `ui/config/paths.py` (good - already has this!)

---

### 3. Desktop File Execution

**Bad Pattern:**
```ini
Exec=/home/ron/Documents/git/TFCBM/.venv/bin/python3 /home/ron/Documents/git/TFCBM/ui/main.py
```

**Good Pattern:**
```ini
Exec=tfcbm
```

**Requires:**
- Install script/entry point in `pyproject.toml`:
  ```toml
  [project.scripts]
  tfcbm = "tfcbm.ui.main:main"
  ```

---

### 4. Extension Schema Access

**Check:** Does extension properly reference installed schemas?

**File to Review:**
- `gnome-extension/extension.js`
- Should use: `ExtensionUtils.getSettings()` (uses installed schema)
- Not: Hardcoded paths

---

## Implementation Plan

### Phase 1: Critical Infrastructure (Week 1)

#### Day 1-2: Build System
- [ ] Create `pyproject.toml` with complete metadata
- [ ] Create `MANIFEST.in` for resource inclusion
- [ ] Set up entry points for `tfcbm` command
- [ ] Test local pip installation: `pip install -e .`

#### Day 3: Path Fixes
- [ ] Create resource loading utility module
- [ ] Fix all hardcoded paths in Python code
- [ ] Update desktop file with portable paths
- [ ] Create standard directory structure (`/data/`, `/resources/`)

#### Day 4: Desktop Integration Files
- [ ] Create D-Bus service file
- [ ] Move desktop file to `/data/applications/`
- [ ] Validate desktop file: `desktop-file-validate`
- [ ] Create GResources XML for icon bundling

#### Day 5: Naming Consistency
- [ ] Rename extension UUID
- [ ] Update extension schema ID
- [ ] Update all references in extension code
- [ ] Recompile gschemas

---

### Phase 2: Packaging (Week 2)

#### Day 6-7: Application Metadata
- [ ] Write appdata.xml with full metadata
- [ ] Take screenshots (3-5 high quality)
- [ ] Add release notes
- [ ] Validate: `appstreamcli validate org.tfcbm.ClipboardManager.appdata.xml`

#### Day 8-9: Flatpak Manifest
- [ ] Create initial manifest YAML
- [ ] Define runtime and SDK (GNOME 47)
- [ ] List all permissions (finish-args)
- [ ] Add Python dependencies as modules
- [ ] Package GNOME extension properly
- [ ] Test local Flatpak build

#### Day 10: Testing & Polish
- [ ] Build Flatpak locally
- [ ] Test in sandbox
- [ ] Fix any sandbox issues
- [ ] Run Flatpak linter: `flatpak-builder-lint`

---

### Phase 3: Cleanup (Concurrent)

#### Repository Cleanup
- [ ] Remove dead scripts (3 files)
- [ ] Move/remove legacy tests (10 files)
- [ ] Remove backup files (3 files)
- [ ] Fix `resouces/` → `resources/` typo
- [ ] Update .gitignore
- [ ] Remove node_modules from git
- [ ] Consider removing test_app/ (46 MB)

#### Code Cleanup
- [ ] Remove unused imports
- [ ] Fix any linting issues: `ruff check .`
- [ ] Format code: `black .`
- [ ] Update type hints where missing

---

### Phase 4: Documentation (Concurrent)

#### Update Documentation
- [ ] Update README with installation from Flatpak
- [ ] Document build process
- [ ] Update ARCHITECTURE.md if structure changed
- [ ] Consolidate or remove obsolete plan documents
- [ ] Add CONTRIBUTING.md with Flatpak build instructions

---

## Required File Templates

### 1. pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tfcbm"
version = "1.0.0"
description = "TFCBM Clipboard Manager for GNOME"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "GPL-3.0-or-later"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
keywords = ["clipboard", "gnome", "gtk", "manager"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: X11 Applications :: GTK",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Desktop Environment :: GNOME",
]

dependencies = [
    "PyGObject>=3.42.0",
    "websockets>=12.0",
    "Pillow>=10.0.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff",
    "black",
]

[project.urls]
Homepage = "https://github.com/yourusername/tfcbm"
Repository = "https://github.com/yourusername/tfcbm"
"Bug Tracker" = "https://github.com/yourusername/tfcbm/issues"

[project.scripts]
tfcbm = "tfcbm.ui.main:main"
tfcbm-server = "tfcbm.tfcbm_server:main"

[tool.setuptools]
packages = ["tfcbm", "tfcbm.ui", "tfcbm.ui.application", "tfcbm.ui.components",
            "tfcbm.ui.config", "tfcbm.ui.core", "tfcbm.ui.dialogs",
            "tfcbm.ui.domain", "tfcbm.ui.infrastructure", "tfcbm.ui.interfaces",
            "tfcbm.ui.managers", "tfcbm.ui.pages", "tfcbm.ui.rows",
            "tfcbm.ui.services", "tfcbm.ui.utils", "tfcbm.ui.windows"]

[tool.setuptools.package-data]
tfcbm = ["resources/*", "ui/*.css"]

[tool.black]
line-length = 100
target-version = ['py310']

[tool.ruff]
line-length = 100
```

---

### 2. MANIFEST.in

```
# Include documentation
include README.md
include LICENSE
include ARCHITECTURE.md
include FEATURES.md

# Include resource files
recursive-include resources *.svg *.png *.html

# Include CSS
recursive-include ui *.css

# Include GNOME extension
recursive-include gnome-extension *.js *.json
recursive-include gnome-extension/schemas *.xml *.compiled
recursive-include gnome-extension/src *.js

# Include desktop integration files
include data/*.desktop
include data/*.service
include data/*.appdata.xml
include data/*.gresource.xml

# Exclude development files
global-exclude __pycache__
global-exclude *.py[co]
global-exclude .DS_Store
global-exclude *.swp
prune .venv
prune venv
prune tests
prune docs
prune test_app
prune node_modules
```

---

### 3. D-Bus Service File

**File:** `/data/org.tfcbm.ClipboardManager.service`

```ini
[D-BUS Service]
Name=org.tfcbm.ClipboardManager
Exec=/app/bin/tfcbm
```

---

### 4. Desktop File (Fixed)

**File:** `/data/applications/org.tfcbm.ClipboardManager.desktop`

```ini
[Desktop Entry]
Type=Application
Name=TFCBM
GenericName=Clipboard Manager
Comment=Advanced clipboard manager for GNOME
Icon=org.tfcbm.ClipboardManager
Exec=tfcbm
Terminal=false
Categories=GNOME;GTK;Utility;
Keywords=clipboard;copy;paste;history;
StartupNotify=true
DBusActivatable=true
X-GNOME-UsesNotifications=true
```

---

### 5. AppData XML Template

**File:** `/data/org.tfcbm.ClipboardManager.appdata.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>org.tfcbm.ClipboardManager</id>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>GPL-3.0-or-later</project_license>
  <name>TFCBM</name>
  <summary>Advanced clipboard manager for GNOME</summary>

  <description>
    <p>
      TFCBM is a powerful clipboard manager for GNOME that helps you manage your
      clipboard history with ease. Features include:
    </p>
    <ul>
      <li>Unlimited clipboard history</li>
      <li>Tag and organize clipboard items</li>
      <li>Search through clipboard history</li>
      <li>Support for text, images, files, and URLs</li>
      <li>Secure password management with encryption</li>
      <li>Customizable keyboard shortcuts</li>
      <li>Beautiful GTK4/libadwaita interface</li>
    </ul>
  </description>

  <screenshots>
    <screenshot type="default">
      <caption>Main window showing clipboard history</caption>
      <image>https://example.com/screenshots/main-window.png</image>
    </screenshot>
    <screenshot>
      <caption>Tag management interface</caption>
      <image>https://example.com/screenshots/tags.png</image>
    </screenshot>
    <screenshot>
      <caption>Search and filter</caption>
      <image>https://example.com/screenshots/search.png</image>
    </screenshot>
  </screenshots>

  <url type="homepage">https://github.com/yourusername/tfcbm</url>
  <url type="bugtracker">https://github.com/yourusername/tfcbm/issues</url>
  <url type="help">https://github.com/yourusername/tfcbm/wiki</url>

  <developer_name>Your Name</developer_name>
  <update_contact>your.email@example.com</update_contact>

  <launchable type="desktop-id">org.tfcbm.ClipboardManager.desktop</launchable>

  <provides>
    <binary>tfcbm</binary>
    <dbus type="user">org.tfcbm.ClipboardManager</dbus>
  </provides>

  <releases>
    <release version="1.0.0" date="2025-12-21">
      <description>
        <p>Initial release</p>
        <ul>
          <li>Clipboard history management</li>
          <li>Tag organization</li>
          <li>Search functionality</li>
          <li>Password encryption</li>
        </ul>
      </description>
    </release>
  </releases>

  <content_rating type="oars-1.1" />

  <recommends>
    <control>keyboard</control>
    <control>pointing</control>
  </recommends>

  <requires>
    <display_length compare="ge">360</display_length>
  </requires>
</component>
```

---

### 6. Flatpak Manifest Template

**File:** `/org.tfcbm.ClipboardManager.yaml`

```yaml
app-id: org.tfcbm.ClipboardManager
runtime: org.gnome.Platform
runtime-version: '47'
sdk: org.gnome.Sdk
command: tfcbm

finish-args:
  # X11 + fallback to Wayland
  - --socket=fallback-x11
  - --socket=wayland

  # GPU acceleration
  - --device=dri

  # Clipboard access
  - --share=ipc

  # Network for WebSocket server
  - --share=network

  # Access to home directory for clipboard files
  - --filesystem=home

  # D-Bus access
  - --talk-name=org.freedesktop.secrets
  - --own-name=org.tfcbm.ClipboardManager

  # System bus for GNOME Shell extension
  - --talk-name=org.gnome.Shell

cleanup:
  - /include
  - /lib/pkgconfig
  - /share/man
  - '*.la'
  - '*.a'

modules:
  # Python dependencies
  - name: python-dependencies
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${PWD}"
        --prefix=${FLATPAK_DEST} PyGObject websockets Pillow pydantic pyyaml
    sources:
      - type: file
        url: https://files.pythonhosted.org/packages/.../PyGObject-3.48.0.tar.gz
        sha256: [hash]
      - type: file
        url: https://files.pythonhosted.org/packages/.../websockets-12.0.tar.gz
        sha256: [hash]
      - type: file
        url: https://files.pythonhosted.org/packages/.../Pillow-10.0.0.tar.gz
        sha256: [hash]
      - type: file
        url: https://files.pythonhosted.org/packages/.../pydantic-2.0.0.tar.gz
        sha256: [hash]
      - type: file
        url: https://files.pythonhosted.org/packages/.../PyYAML-6.0.tar.gz
        sha256: [hash]

  # Main application
  - name: tfcbm
    buildsystem: simple
    build-commands:
      # Install Python package
      - pip3 install --prefix=/app --no-deps .

      # Install desktop file
      - install -Dm644 data/applications/org.tfcbm.ClipboardManager.desktop
        /app/share/applications/org.tfcbm.ClipboardManager.desktop

      # Install D-Bus service
      - install -Dm644 data/org.tfcbm.ClipboardManager.service
        /app/share/dbus-1/services/org.tfcbm.ClipboardManager.service

      # Install appdata
      - install -Dm644 data/org.tfcbm.ClipboardManager.appdata.xml
        /app/share/metainfo/org.tfcbm.ClipboardManager.appdata.xml

      # Install icons
      - install -Dm644 resources/icon.svg
        /app/share/icons/hicolor/scalable/apps/org.tfcbm.ClipboardManager.svg
      - install -Dm644 resources/icon-256.png
        /app/share/icons/hicolor/256x256/apps/org.tfcbm.ClipboardManager.png

      # Install GNOME Shell extension
      - mkdir -p /app/share/gnome-shell/extensions/clipboard-manager@tfcbm
      - cp -r gnome-extension/* /app/share/gnome-shell/extensions/clipboard-manager@tfcbm/

      # Install GSettings schema
      - install -Dm644 gnome-extension/schemas/org.gnome.shell.extensions.clipboard-manager.gschema.xml
        /app/share/glib-2.0/schemas/org.gnome.shell.extensions.clipboard-manager.gschema.xml
      - glib-compile-schemas /app/share/glib-2.0/schemas

    sources:
      - type: dir
        path: .
```

---

### 7. GResources XML

**File:** `/data/org.tfcbm.ClipboardManager.gresource.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gresources>
  <gresource prefix="/org/tfcbm/ClipboardManager">
    <file compressed="true">ui/style.css</file>
    <file compressed="true">resources/icon.svg</file>
    <file compressed="true">resources/loader.svg</file>
    <file compressed="true">resources/logo.png</file>
  </gresource>
</gresources>
```

---

## Validation Checklist

### Before Building Flatpak

```bash
# Validate desktop file
desktop-file-validate data/applications/org.tfcbm.ClipboardManager.desktop

# Validate appdata
appstreamcli validate data/org.tfcbm.ClipboardManager.appdata.xml

# Validate GSettings schema
glib-compile-schemas --strict gnome-extension/schemas/

# Check Python packaging
python -m build
pip install dist/*.whl

# Run tests
pytest

# Lint Python code
ruff check .
black --check .

# Check for hardcoded paths
grep -r "/home/ron" .
grep -r "Documents/git/TFCBM" .
```

### Building Flatpak

```bash
# Install Flatpak builder
sudo dnf install flatpak-builder

# Add Flathub repository
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Install GNOME SDK
flatpak install flathub org.gnome.Platform//47 org.gnome.Sdk//47

# Build
flatpak-builder --force-clean build-dir org.tfcbm.ClipboardManager.yaml

# Test locally
flatpak-builder --run build-dir org.tfcbm.ClipboardManager.yaml tfcbm

# Install locally
flatpak-builder --user --install --force-clean build-dir org.tfcbm.ClipboardManager.yaml

# Run installed app
flatpak run org.tfcbm.ClipboardManager

# Check logs
flatpak run --log-to-stderr org.tfcbm.ClipboardManager

# Lint Flatpak
flatpak-builder-lint manifest org.tfcbm.ClipboardManager.yaml
flatpak-builder-lint builddir build-dir
flatpak-builder-lint repo repo
```

---

## Flathub Submission Checklist

### Pre-Submission

- [ ] App builds successfully with flatpak-builder
- [ ] App runs in Flatpak sandbox
- [ ] All features work in sandbox (test thoroughly!)
- [ ] No hardcoded paths remain
- [ ] Desktop file validates
- [ ] AppData validates
- [ ] Screenshots are high quality (1600x900+ recommended)
- [ ] No offensive content in user-visible strings
- [ ] License is clear (GPL-3.0-or-later)
- [ ] Source code is publicly accessible
- [ ] `flatpak-builder-lint` passes all checks

### Repository Structure for Flathub

Flathub expects a dedicated repository with:
```
flathub/org.tfcbm.ClipboardManager/
├── org.tfcbm.ClipboardManager.yaml
├── org.tfcbm.ClipboardManager.appdata.xml (copy)
├── flathub.json (optional metadata)
└── README.md (build instructions)
```

### Submission Process

1. Fork https://github.com/flathub/flathub
2. Create branch: `org.tfcbm.ClipboardManager`
3. Add manifest and metadata
4. Create pull request
5. Address reviewer feedback
6. Wait for approval (1-2 weeks typically)

### Common Rejection Reasons

- Hardcoded paths (check!)
- Missing or invalid appdata
- Low quality screenshots
- Offensive content
- License issues
- Security concerns (eval(), unsafe file operations)
- Excessive permissions
- Bundled binaries without source

---

## Post-Cleanup Repository Structure

```
tfcbm/
├── pyproject.toml                          # NEW
├── MANIFEST.in                             # NEW
├── org.tfcbm.ClipboardManager.yaml        # NEW - Flatpak manifest
├── README.md
├── LICENSE
├── ARCHITECTURE.md
├── FEATURES.md
├── .gitignore                              # UPDATED
│
├── data/                                   # NEW DIRECTORY
│   ├── applications/
│   │   └── org.tfcbm.ClipboardManager.desktop
│   ├── org.tfcbm.ClipboardManager.service
│   ├── org.tfcbm.ClipboardManager.appdata.xml
│   └── org.tfcbm.ClipboardManager.gresource.xml
│
├── resources/                              # RENAMED from resouces/
│   ├── icon.svg
│   ├── icon-256.png
│   ├── tfcbm.svg
│   ├── tfcbm-256.png
│   ├── logo.png
│   ├── loader.svg
│   └── loader.html
│
├── tfcbm/                                 # Source code (rename from root files)
│   ├── __init__.py
│   ├── tfcbm.py
│   ├── tfcbm_server.py
│   ├── database.py
│   ├── launcher.py
│   ├── tfcbm_activator.py
│   ├── settings.py
│   └── ui/                                # UI module
│       ├── __init__.py
│       ├── main.py
│       ├── splash.py
│       ├── style.css
│       ├── application/
│       ├── components/
│       ├── config/
│       ├── core/
│       ├── dialogs/
│       ├── domain/
│       ├── infrastructure/
│       ├── interfaces/
│       ├── managers/
│       ├── pages/
│       ├── rows/
│       ├── services/
│       ├── utils/
│       └── windows/
│
├── gnome-extension/
│   ├── extension.js
│   ├── metadata.json                      # UPDATED - new UUID
│   ├── package.json
│   ├── .eslintrc.json
│   ├── .prettierrc
│   ├── schemas/
│   │   └── org.gnome.shell.extensions.clipboard-manager.gschema.xml  # RENAMED
│   └── src/
│       ├── adapters/
│       ├── domain/
│       ├── ClipboardMonitorService.js
│       └── PollingScheduler.js
│   # NO node_modules/ (excluded from git)
│
├── tests/
│   ├── conftest.py
│   └── unit/
│       ├── test_application/
│       ├── test_components/
│       ├── test_config/
│       ├── test_core/
│       ├── test_managers/
│       ├── test_rows/
│       └── test_utils/
│
├── scripts/                               # RENAMED from root
│   ├── run.sh
│   ├── install_extension.sh
│   ├── uninstall.sh
│   ├── check_status.sh
│   ├── setup_keyboard_shortcut.sh
│   ├── diagnose_shortcut.sh
│   ├── tfcbm-activate.sh
│   ├── tfcbm-launcher.sh
│   ├── lint.sh
│   ├── load.sh
│   └── logs.sh
│
├── docs/                                  # Documentation
│   ├── screenshots/                       # NEW - for appdata
│   │   ├── main-window.png
│   │   ├── tags.png
│   │   └── search.png
│   └── (diagrams)
│
└── .pytest_cache/ (gitignored)
└── __pycache__/ (gitignored)
└── .venv/ (gitignored)
```

---

## Questions for Developer (Required Info)

Before proceeding with implementation, please provide:

1. **App Naming Decision:**
   - Keep "The F*cking Clipboard Manager"? (risky)
   - Change to what alternative?
   - Suggested: "TFCBM Clipboard Manager" (safe)

2. **Developer Information:**
   - Your name for metadata
   - Email for update contact
   - GitHub username/organization
   - Preferred license (GPL-3.0+, MIT, etc.)

3. **Version Information:**
   - What version to call this? (1.0.0 recommended)
   - Any prior releases?

4. **Extension Packaging:**
   - Should extension auto-install on first run?
   - Or manual installation required?

5. **Repository Cleanup:**
   - OK to delete `test_app/` directory? (46 MB)
   - Any other files you want to keep?

6. **Screenshots:**
   - Do you have screenshots already?
   - Need help taking/creating them?

---

## Success Criteria

When this plan is complete, you will have:

✅ Installable via Flatpak
✅ No hardcoded paths
✅ Proper GNOME integration
✅ Desktop file working
✅ D-Bus activation working
✅ Icons showing correctly
✅ Clean repository (<20 MB)
✅ All validators passing
✅ Ready for Flathub submission
✅ Professional appearance

---

## Next Steps

1. **Review this plan** - Make sure you agree with all changes
2. **Answer questions above** - Provide required information
3. **Start Phase 1** - Begin with build system creation
4. **Test incrementally** - Don't wait until the end to test
5. **Submit to Flathub** - Follow submission process

---

## Additional Resources

- **Flathub Documentation:** https://docs.flathub.org/
- **GNOME Developer Docs:** https://developer.gnome.org/
- **Python Packaging:** https://packaging.python.org/
- **AppStream Specification:** https://www.freedesktop.org/software/appstream/docs/
- **Desktop Entry Spec:** https://specifications.freedesktop.org/desktop-entry-spec/

---

**This plan is comprehensive and actionable. Follow it step-by-step and you'll have a Flathub-ready application in 1-2 weeks.**

Good luck! 🚀
