"""System information collection for debugging."""

import os
import subprocess
from pathlib import Path


def get_system_info() -> dict:
    """
    Collect system information for debugging.

    Returns:
        dict: System information including distro, GNOME version, session type, etc.
    """
    info = {
        'distro': 'Unknown',
        'distro_version': 'Unknown',
        'gnome_version': 'Unknown',
        'flatpak': False,
        'session_type': os.environ.get('XDG_SESSION_TYPE', 'Unknown'),
        'selinux': False,
        'apparmor': False,
    }

    # Detect distro
    try:
        if Path('/etc/fedora-release').exists():
            with open('/etc/fedora-release') as f:
                info['distro'] = 'Fedora'
                info['distro_version'] = f.read().strip()
        elif Path('/etc/os-release').exists():
            with open('/etc/os-release') as f:
                for line in f:
                    if line.startswith('NAME='):
                        info['distro'] = line.split('=')[1].strip('"')
                    elif line.startswith('VERSION_ID='):
                        info['distro_version'] = line.split('=')[1].strip('"')
    except Exception:
        pass

    # GNOME version
    try:
        result = subprocess.run(['gnome-shell', '--version'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            info['gnome_version'] = result.stdout.strip()
    except Exception:
        pass

    # Flatpak detection
    info['flatpak'] = 'FLATPAK_ID' in os.environ or os.path.exists('/.flatpak-info')

    # SELinux (Fedora)
    try:
        result = subprocess.run(['getenforce'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and 'Enforcing' in result.stdout:
            info['selinux'] = True
    except Exception:
        pass

    # AppArmor (Ubuntu)
    try:
        if Path('/sys/kernel/security/apparmor').exists():
            info['apparmor'] = True
    except Exception:
        pass

    return info


def log_system_info(logger):
    """
    Log system information at startup.

    Args:
        logger: Logger instance to use for logging
    """
    info = get_system_info()
    logger.info("=== System Information ===")
    logger.info(f"Distro: {info['distro']} {info['distro_version']}")
    logger.info(f"GNOME: {info['gnome_version']}")
    logger.info(f"Session: {info['session_type']}")
    logger.info(f"Flatpak: {info['flatpak']}")
    logger.info(f"SELinux: {info['selinux']}")
    logger.info(f"AppArmor: {info['apparmor']}")
    logger.info("==========================")
