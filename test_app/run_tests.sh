#!/bin/bash
# Test runner for Shortcut Recorder POC
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

cd "$SCRIPT_DIR"

echo "=== Shortcut Recorder POC - Test Runner ==="
echo ""

# 1. Setup Python virtual environment if needed
if [ ! -d "$VENV_DIR" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv --system-site-packages "$VENV_DIR"
    echo "✓ Virtual environment created"
    echo ""
fi

# 2. Activate virtual environment
echo "🐍 Activating virtual environment..."
source "$VENV_DIR/bin/activate"
echo ""

# 3. Install/upgrade dependencies
if [ -f "requirements.txt" ]; then
    echo "📦 Installing/updating Python dependencies..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    echo "✓ Dependencies installed"
    echo ""
fi

# 4. Run tests with coverage
echo "🧪 Running integration tests..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run pytest with all configured options from pytest.ini
pytest "$@"

EXIT_CODE=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ All tests passed!"
    echo ""
    echo "📊 Coverage report generated in: htmlcov/index.html"
    echo "   View with: xdg-open htmlcov/index.html"
else
    echo "✗ Some tests failed (exit code: $EXIT_CODE)"
fi

echo ""

exit $EXIT_CODE
