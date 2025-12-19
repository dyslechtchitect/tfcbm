# Quick Start Guide

## Run the Application

```bash
cd /home/ron/Documents/git/TFCBM/test_app
./run.sh
```

**What it does:**
1. Creates Python virtual environment with system site-packages (for GTK access)
2. Installs all Python dependencies
3. Installs GNOME Shell extension (if not already installed)
4. Launches the application

## Run Tests

```bash
./run_tests.sh
```

**Expected output:**
```
============================== 39 passed in 0.12s ==============================
✓ All tests passed!
```

## Test the Keyboard Shortcut

1. **Start the application**: `./run.sh`
2. **Press Ctrl+Shift+K** anywhere (even when window is hidden)
3. **Window should appear** and gain focus immediately
4. **Counter increments** each time you activate via shortcut
5. **No notification** should appear

## Troubleshooting

### App doesn't start - "No module named 'gi'"

**Solution:** Remove old venv and recreate:
```bash
rm -rf .venv
./run.sh
```

The script creates venv with `--system-site-packages` to access GTK.

## Success Indicators

✅ **Application loads** - Window appears
✅ **Tests pass** - All 39 tests green
✅ **Shortcut works** - Ctrl+Shift+K shows window
✅ **No notification** - Focus granted immediately

All working? You're good to go! 🚀
