# TFCBM

<p align="center">
  <img src="resouces/io.github.dyslechtchitect.tfcbm.logo.png" alt="TFCBM Logo" width="128" height="128">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue.svg" alt="License"></a>
  <a href="https://flathub.org/apps/io.github.dyslechtchitect.tfcbm"><img src="https://img.shields.io/flathub/v/io.github.dyslechtchitect.tfcbm" alt="Flathub"></a>
</p>

A clipboard manager for Linux. Keeps a searchable history of everything you copy.

```bash
flatpak install flathub io.github.dyslechtchitect.tfcbm
```

## Features

- Clipboard history for text, images, and files
- Search and filter
- Tags and organization
- Configurable keyboard shortcut
- Retention management

## Usage

Press `Ctrl+Escape` (configurable) to open. Click an item or press Enter to copy it back to the clipboard.

## Build from Source

```bash
flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49
git clone https://github.com/dyslechtchitect/tfcbm.git
cd tfcbm
flatpak-builder --user --install --force-clean build-dir io.github.dyslechtchitect.tfcbm.yml
```
## Install

<a href="https://flathub.org/apps/io.github.dyslechtchitect.tfcbm">
  <img src="https://flathub.org/api/badge?locale=en" alt="Download on Flathub" width="200">
</a>

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
