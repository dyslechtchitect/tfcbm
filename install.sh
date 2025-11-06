set -e
sudo dnf install -y gcc cairo-devel gobject-introspection-devel gtk3-devel pkg-config python3-devel
pip install -r requirements.txt
