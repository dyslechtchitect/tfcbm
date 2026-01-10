project('tfcbm',
  version: '1.0.0',
  meson_version: '>= 0.59.0',
  license: 'GPL-3.0-or-later',
)

# Project information
application_id = 'io.github.dyslechtchitect.tfcbm'
python = import('python').find_installation('python3')

# Directories
prefix = get_option('prefix')
bindir = prefix / get_option('bindir')
datadir = prefix / get_option('datadir')
pkgdatadir = datadir / meson.project_name()
pkglibdir = prefix / 'lib' / meson.project_name()

# Install Python source files
install_subdir('ui', install_dir: pkglibdir)
install_subdir('server', install_dir: pkglibdir)
install_data('main.py', install_dir: pkglibdir)
install_data('settings.json', install_dir: pkglibdir)

# Install resources
install_subdir('resouces', install_dir: pkgdatadir)

# Install icons
install_data(
  'icons/hicolor/scalable/apps' / application_id + '.svg',
  install_dir: datadir / 'icons/hicolor/scalable/apps'
)

# Install desktop file
install_data(
  application_id + '.desktop',
  install_dir: datadir / 'applications'
)

# Install metainfo
install_data(
  application_id + '.metainfo.xml',
  install_dir: datadir / 'metainfo'
)

# Install D-Bus service file
install_data(
  application_id + '.service',
  install_dir: datadir / 'dbus-1/services'
)

# Create GNOME Shell extension zip package
gnome_extension_zip = custom_target('gnome-extension-zip',
  output: 'tfcbm-clipboard-monitor@github.com.zip',
  command: [
    python,
    files('build-extension-zip.py'),
    meson.project_source_root(),
    '@OUTPUT@'
  ],
  install: true,
  install_dir: pkgdatadir
)

# Install GNOME Shell extension files for Flatpak
# This allows the Flatpak app to install the extension on first run
install_subdir('gnome-extension',
  install_dir: datadir / 'gnome-shell/extensions/tfcbm-clipboard-monitor@github.com',
  strip_directory: true,
  exclude_files: ['install.sh', 'uninstall.sh', 'README.md', 'package.json']
)

# Configure and install wrapper scripts
conf_data = configuration_data()
conf_data.set('PYTHON', python.full_path())
conf_data.set('pkglibdir', pkglibdir)

configure_file(
  input: 'tfcbm-wrapper.sh',
  output: 'tfcbm',
  configuration: conf_data,
  install: true,
  install_dir: bindir,
  install_mode: 'rwxr-xr-x'
)

configure_file(
  input: 'tfcbm-install-extension.sh',
  output: 'tfcbm-install-extension',
  configuration: conf_data,
  install: true,
  install_dir: bindir,
  install_mode: 'rwxr-xr-x'
)
