#!/bin/bash
# TFCBM Linting Script
# Auto-formats and lints Python and JavaScript code

set -e  # Exit on error

echo "=========================================="
echo "TFCBM Code Linting & Formatting"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ==========================================
# Python Linting
# ==========================================

echo -e "${YELLOW}==> Python Linting${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}Virtual environment not found. Please run ./load.sh first.${NC}"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Install Python linting tools if not already installed
echo "Installing Python linting tools..."
pip install -q black isort flake8 autopep8 autoflake 2>/dev/null || true

# Find all Python files (excluding venv and node_modules)
PYTHON_FILES=$(find . -name "*.py" \
    -not -path "./.venv/*" \
    -not -path "./node_modules/*" \
    -not -path "./.git/*")

if [ -z "$PYTHON_FILES" ]; then
    echo -e "${YELLOW}No Python files found.${NC}"
else
    echo -e "${GREEN}Found Python files:${NC}"
    echo "$PYTHON_FILES" | sed 's/^/  /'
    echo ""

    # 1. autoflake - Remove unused imports and variables
    echo "Running autoflake (removing unused imports)..."
    echo "$PYTHON_FILES" | xargs autoflake --in-place --remove-all-unused-imports --remove-unused-variables --remove-duplicate-keys

    # 2. isort - Sort imports
    echo "Running isort (import sorting)..."
    echo "$PYTHON_FILES" | xargs isort --quiet --profile black

    # 3. black - Code formatting
    echo "Running black (code formatting)..."
    echo "$PYTHON_FILES" | xargs black --quiet --line-length 120

    # 4. autopep8 - PEP 8 compliance
    echo "Running autopep8 (PEP 8 fixes)..."
    echo "$PYTHON_FILES" | xargs autopep8 --in-place --aggressive --aggressive --max-line-length 120

    # 4. flake8 - Linting (report only, no auto-fix)
    echo ""
    echo -e "${YELLOW}Running flake8 (linting report):${NC}"
    echo "$PYTHON_FILES" | xargs flake8 --max-line-length 120 --ignore=E203,E266,E501,W503 --extend-ignore=E402 || {
        echo -e "${YELLOW}⚠ Flake8 found some issues (non-critical)${NC}"
    }
fi

echo ""

# ==========================================
# JavaScript Linting
# ==========================================

echo -e "${YELLOW}==> JavaScript/Node.js Linting${NC}"
echo ""

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo -e "${RED}npm not found. Skipping JavaScript linting.${NC}"
else
    # Find all JavaScript files in gnome-extension
    JS_FILES=$(find gnome-extension -name "*.js" \
        -not -path "*/node_modules/*" \
        -not -path "*/.git/*" 2>/dev/null || true)

    if [ -z "$JS_FILES" ]; then
        echo -e "${YELLOW}No JavaScript files found.${NC}"
    else
        echo -e "${GREEN}Found JavaScript files:${NC}"
        echo "$JS_FILES" | sed 's/^/  /'
        echo ""

        # Install ESLint and Prettier if not already installed
        cd gnome-extension
        echo "Checking JavaScript linting tools..."

        # Check if package.json has lint scripts, if not add them
        if ! grep -q "\"lint\"" package.json 2>/dev/null; then
            echo "Setting up linting scripts in package.json..."
            npm install --save-dev --silent eslint prettier eslint-config-prettier eslint-plugin-prettier eslint-plugin-unused-imports 2>/dev/null || true
        fi

        # Create .eslintrc.json if it doesn't exist
        if [ ! -f ".eslintrc.json" ]; then
            echo "Creating .eslintrc.json..."
            cat > .eslintrc.json << 'EOF'
{
  "env": {
    "es6": true,
    "node": true
  },
  "extends": ["eslint:recommended", "prettier"],
  "plugins": ["prettier", "unused-imports"],
  "parserOptions": {
    "ecmaVersion": 2022,
    "sourceType": "module"
  },
  "rules": {
    "prettier/prettier": "warn",
    "no-unused-vars": "off",
    "unused-imports/no-unused-imports": "error",
    "unused-imports/no-unused-vars": [
      "warn",
      {
        "vars": "all",
        "varsIgnorePattern": "^_",
        "args": "after-used",
        "argsIgnorePattern": "^_"
      }
    ],
    "no-console": "off",
    "no-undef": "warn"
  },
  "globals": {
    "imports": "readonly",
    "global": "readonly",
    "log": "readonly",
    "logError": "readonly"
  }
}
EOF
        fi

        # Create .prettierrc if it doesn't exist
        if [ ! -f ".prettierrc" ]; then
            echo "Creating .prettierrc..."
            cat > .prettierrc << 'EOF'
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": true,
  "printWidth": 100,
  "tabWidth": 4,
  "useTabs": false
}
EOF
        fi

        # Run Prettier (auto-format)
        echo "Running Prettier (code formatting)..."
        npx prettier --write "**/*.js" --ignore-path .gitignore 2>/dev/null || {
            echo -e "${YELLOW}⚠ Prettier encountered some issues${NC}"
        }

        # Run ESLint with auto-fix
        echo "Running ESLint (auto-fix)..."
        npx eslint --fix "**/*.js" --ignore-path .gitignore 2>/dev/null || {
            echo -e "${YELLOW}⚠ ESLint found some issues (non-critical)${NC}"
        }

        cd "$SCRIPT_DIR"
    fi
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Linting Complete!"
echo -e "==========================================${NC}"
echo ""
echo "Summary:"
echo "  ✓ Python files formatted with black, isort, autopep8"
echo "  ✓ JavaScript files formatted with prettier, eslint"
echo ""
echo "You can now review the changes with:"
echo "  git diff"
echo ""
