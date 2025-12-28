#!/bin/bash
set -e

# TFCBM CI Local Runner
# Convenience script for running GitHub Actions workflows locally with act

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if act is installed
if ! command -v act &> /dev/null; then
    echo -e "${RED}Error: 'act' is not installed.${NC}"
    echo "Please install it:"
    echo "  Fedora: sudo dnf install act"
    echo "  Ubuntu: curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash"
    echo "  Homebrew: brew install act"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker is not running.${NC}"
    echo "Please start Docker and try again."
    exit 1
fi

# Function to display usage
usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  test                Run Python and Node.js tests"
    echo "  flatpak [VERSION]   Build Flatpak for specific GNOME version (45-49)"
    echo "  flatpak-all         Build Flatpak for all GNOME versions (45-49)"
    echo "  lint                Run flatpak-builder-lint"
    echo "  all                 Run all jobs (tests, flatpak for GNOME 49, and lint)"
    echo "  help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 test"
    echo "  $0 flatpak 49"
    echo "  $0 flatpak-all"
    echo "  $0 lint"
    echo "  $0 all"
    exit 0
}

# Function to run tests
run_tests() {
    echo -e "${GREEN}Running tests...${NC}"
    act -j test
}

# Function to run Flatpak build for a specific version
run_flatpak() {
    local version=$1

    if [[ ! "$version" =~ ^4[5-9]$ ]]; then
        echo -e "${RED}Error: Invalid GNOME version. Must be 45-49.${NC}"
        exit 1
    fi

    echo -e "${GREEN}Building Flatpak for GNOME $version...${NC}"
    act -j flatpak --matrix gnome-version:"$version"
}

# Function to run Flatpak build for all versions
run_flatpak_all() {
    echo -e "${GREEN}Building Flatpak for all GNOME versions (45-49)...${NC}"

    for version in 45 46 47 48 49; do
        echo -e "${YELLOW}Building for GNOME $version...${NC}"
        run_flatpak "$version"
    done

    echo -e "${GREEN}All Flatpak builds completed!${NC}"
}

# Function to run linting
run_lint() {
    echo -e "${GREEN}Running flatpak-builder-lint...${NC}"
    act -j lint
}

# Function to run all jobs
run_all() {
    echo -e "${GREEN}Running all CI jobs...${NC}"

    echo -e "${YELLOW}Step 1/3: Running tests...${NC}"
    run_tests

    echo -e "${YELLOW}Step 2/3: Building Flatpak for GNOME 49...${NC}"
    run_flatpak 49

    echo -e "${YELLOW}Step 3/3: Running linting...${NC}"
    run_lint

    echo -e "${GREEN}All CI jobs completed!${NC}"
}

# Main script logic
case "${1:-help}" in
    test)
        run_tests
        ;;
    flatpak)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please specify GNOME version (45-49)${NC}"
            echo "Example: $0 flatpak 49"
            exit 1
        fi
        run_flatpak "$2"
        ;;
    flatpak-all)
        run_flatpak_all
        ;;
    lint)
        run_lint
        ;;
    all)
        run_all
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo -e "${RED}Error: Unknown command '$1'${NC}"
        echo ""
        usage
        ;;
esac

echo -e "${GREEN}Done!${NC}"
