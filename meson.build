project('tfcbm',
  version: '1.0.3',
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

# Install Python source files (excluding test files)
install_subdir('ui', install_dir: pkglibdir, exclude_files: ['test_*.py'])
install_subdir('server', install_dir: pkglibdir, exclude_directories: ['test'])
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
  application_id + '.ClipboardService.service',
  install_dir: datadir / 'dbus-1/services'
)

# Install LICENSE file
install_data(
  'LICENSE',
  install_dir: datadir / 'licenses' / meson.project_name()
)

# Configure and install wrapper script
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

