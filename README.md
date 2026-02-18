# TFCBM

<p align="center">
  <img src="resouces/io.github.dyslechtchitect.tfcbm.logo.png" alt="TFCBM Logo" width="128" height="128">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue.svg" alt="License"></a>
  <a href="https://github.com/dyslechtchitect/tfcbm/releases/latest"><img src="https://img.shields.io/github/v/release/dyslechtchitect/tfcbm" alt="Release"></a>
</p>

A clipboard manager for Linux. Keeps a searchable history of everything you copy.

## Install

### AUR (Arch Linux)

Install with an AUR helper:

```bash
yay -S --noconfirm tfcbm
```

Or with `paru`:

```bash
paru -S --noconfirm tfcbm
```

Or build manually:

```bash
git clone https://aur.archlinux.org/tfcbm.git /tmp/tfcbm-aur
cd /tmp/tfcbm-aur
makepkg -si
```

### Snap Store

<p align="center">
  <a href="https://snapcraft.io/tfcbm">
    <img src="https://snapcraft.io/static/images/badges/en/snap-store-black.svg" alt="Get it from the Snap Store" height="48">
  </a>
</p>

Or install from the command line:

```bash
sudo snap install tfcbm
```

### Flatpak

<p align="center">
  <a href="https://dyslechtchitect.github.io/tfcbm/io.github.dyslechtchitect.tfcbm.flatpakref">
    <img src="https://img.shields.io/badge/Install-Click_to_Install-blue?style=for-the-badge&logo=flatpak" alt="Click to Install" height="48">
  </a>
</p>

Or install from the command line:

```bash
flatpak install https://dyslechtchitect.github.io/tfcbm/io.github.dyslechtchitect.tfcbm.flatpakref
```

Or download the `.flatpak` bundle from the [latest release](https://github.com/dyslechtchitect/tfcbm/releases/latest) and install manually:

```bash
flatpak install tfcbm-x86_64.flatpak
```

## Features

- Clipboard history for text, images, and files
- Search and filter
- Tags and organization
- Configurable keyboard shortcut
- Retention management

## Usage

Press `Ctrl+Escape` (configurable) to open. Click an item or press Enter to copy it back to the clipboard.

## Build and Install Locally

### AUR (Arch Linux)

```bash
sudo pacman -S --needed base-devel git python python-gobject gtk4 gdk-pixbuf2 meson xdotool
git clone https://aur.archlinux.org/tfcbm.git /tmp/tfcbm-aur
cd /tmp/tfcbm-aur
makepkg -si
```

(Or use `./aur-test.sh` from the source repo to automate this.)

### Snap

```bash
git clone https://github.com/dyslechtchitect/tfcbm.git
cd tfcbm
snapcraft
sudo snap install tfcbm_*.snap --dangerous
```

### Flatpak

```bash
flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49
git clone https://github.com/dyslechtchitect/tfcbm.git
cd tfcbm
flatpak-builder --user --install --force-clean build-dir io.github.dyslechtchitect.tfcbm.yml
```

## Screenshots

<p align="center">
  <img src="screenshots/general.png" alt="Main window" width="600">
</p>

<p align="center">
  <img src="screenshots/search.png" alt="Search" width="600">
</p>

<p align="center">
  <img src="screenshots/settings.png" alt="Settings" width="600">
</p>


## License

[GPL-3.0-or-later](LICENSE)
