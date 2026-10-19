#!/bin/bash

# Author: Konstantin M.J. Winkel, M.Sc.

# Project Utility Script
# Usage: ./project_utils.sh [setup|clean]

set -e  # Exit immediately if a command exits with a non-zero status

# Determine the project root (directory where this script resides)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# source shell utils
source shell_utils/shell-utils.sh

cmd_clean() {
    clean_python_cache "$PROJECT_ROOT"
}

cmd_setup() {
    log_info "Running setup in: $PROJECT_ROOT"

    # Change to project root
    cd "$PROJECT_ROOT" || { log_error "Failed to change directory to $PROJECT_ROOT"; exit 1; }

    # Check and install python packages
    check_python_packages "importlib" || install_python_packages "importlib"

    log_info "Setup complete."
}

# Main Logic
case "${1:-}" in
    setup)
        cmd_setup
        ;;
    clean)
        cmd_clean
        ;;
    *)
        echo "Usage: $0 {setup|clean}"
        echo ""
        echo "Commands:"
        echo "  setup   - Installs python dependencies"
        echo "  clean   - Removes all '__pycache__' folders recursively"
        exit 1
        ;;
esac