#!/bin/bash
# Pre-commit hook script that runs lint-staged

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to frontend directory
cd "$SCRIPT_DIR"

# Load nvm if it exists
if [ -f "$HOME/.nvm/nvm.sh" ]; then
    export NVM_DIR="$HOME/.nvm"
    source "$NVM_DIR/nvm.sh"
    # Use the node version from .nvmrc if it exists
    if [ -f ".nvmrc" ]; then
        nvm use
    fi
fi

# Verify npm is available
if ! command -v npm &> /dev/null; then
    echo "Error: npm not found in PATH"
    echo "PATH=$PATH"
    echo "Please ensure Node.js and npm are installed"
    exit 1
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Run lint-staged
# lint-staged will automatically detect staged files via git
echo "Running lint-staged..."
npx lint-staged
