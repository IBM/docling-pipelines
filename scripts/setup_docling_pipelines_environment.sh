#!/usr/bin/env bash

################################################################################
# Docpipe Environment Setup Script
#
# Automates the setup of Docpipe pipeline prerequisites including:
# - Python 3.12 verification
# - uv package manager installation
# - Ollama installation and model downloads
# - OpenSearch setup with Podman/Docker
# - Python virtual environment and dependencies
#
# Usage:
#   ./scripts/setup_docling_pipelines_environment.sh [OPTIONS]
#
# Options:
#   --interactive              Enable interactive mode (prompts for choices)
#   --models MODEL1,MODEL2     Specify Ollama models (comma-separated)
#   --skip-ollama              Skip Ollama setup
#   --skip-opensearch          Skip OpenSearch setup
#   --skip-python              Skip Python environment setup
#   --help                     Show this help message
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration file
CONFIG_FILE=".docpipe_setup_config"
LOG_FILE="docpipe_setup.log"

# Default values
INTERACTIVE_MODE=false
SKIP_OLLAMA=false
SKIP_OPENSEARCH=false
SKIP_PYTHON=false
DEFAULT_MODELS="granite4,llama3.2,nomic-embed-text"
OLLAMA_MODELS=""

################################################################################
# Helper Functions
################################################################################

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

ask_yes_no() {
    local prompt="$1"
    local default="${2:-y}"

    if [ "$INTERACTIVE_MODE" = false ]; then
        return 0
    fi

    while true; do
        if [ "$default" = "y" ]; then
            read -p "$prompt [Y/n]: " response
            response=${response:-y}
        else
            read -p "$prompt [y/N]: " response
            response=${response:-n}
        fi

        case "$response" in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

detect_package_manager() {
    if command_exists brew; then
        echo "brew"
    elif command_exists apt-get; then
        echo "apt"
    elif command_exists dnf; then
        echo "dnf"
    elif command_exists yum; then
        echo "yum"
    else
        echo "unknown"
    fi
}

save_config() {
    local key="$1"
    local value="$2"

    if [ -f "$CONFIG_FILE" ]; then
        sed -i.bak "/^$key=/d" "$CONFIG_FILE" 2>/dev/null || true
    fi
    echo "$key=$value" >> "$CONFIG_FILE"
}

load_config() {
    local key="$1"

    if [ -f "$CONFIG_FILE" ]; then
        grep "^$key=" "$CONFIG_FILE" | cut -d'=' -f2- || echo ""
    else
        echo ""
    fi
}

show_help() {
    cat << EOF
Docpipe Environment Setup Script

Usage: $0 [OPTIONS]

Options:
    --interactive              Enable interactive mode (prompts for choices)
    --models MODEL1,MODEL2     Specify Ollama models to download (comma-separated)
                              Default: granite4,llama3.2,nomic-embed-text
    --skip-ollama              Skip Ollama setup
    --skip-opensearch          Skip OpenSearch setup
    --skip-python              Skip Python environment setup
    --help                     Show this help message

Examples:
    # Default mode (installs everything with defaults)
    $0

    # Interactive mode (prompts for choices)
    $0 --interactive

    # Custom models
    $0 --models granite4,nomic-embed-text

    # Skip specific components
    $0 --skip-ollama --skip-opensearch

EOF
    exit 0
}

################################################################################
# Parse Command Line Arguments
################################################################################

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --interactive)
                INTERACTIVE_MODE=true
                shift
                ;;
            --models)
                OLLAMA_MODELS="$2"
                shift 2
                ;;
            --skip-ollama)
                SKIP_OLLAMA=true
                shift
                ;;
            --skip-opensearch)
                SKIP_OPENSEARCH=true
                shift
                ;;
            --skip-python)
                SKIP_PYTHON=true
                shift
                ;;
            --help)
                show_help
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                ;;
        esac
    done
}

################################################################################
# Setup Functions
################################################################################

check_python() {
    print_header "Checking Python 3.12"

    if command_exists python3.12; then
        local version=$(python3.12 --version | cut -d' ' -f2)
        log "Python 3.12 found: $version"
        save_config "PYTHON_VERSION" "$version"
        return 0
    elif command_exists python3; then
        local version=$(python3 --version | cut -d' ' -f2)
        local major=$(echo "$version" | cut -d'.' -f1)
        local minor=$(echo "$version" | cut -d'.' -f2)

        if [ "$major" = "3" ] && [ "$minor" = "12" ]; then
            log "Python 3.12 found: $version"
            save_config "PYTHON_VERSION" "$version"
            return 0
        fi
    fi

    log_error "Python 3.12 not found!"
    echo ""
    echo "Please install Python 3.12:"
    echo ""

    local os=$(detect_os)
    if [ "$os" = "macos" ]; then
        echo "  brew install python@3.12"
    elif [ "$os" = "linux" ]; then
        echo "  # Ubuntu/Debian:"
        echo "  sudo apt update"
        echo "  sudo apt install python3.12 python3.12-venv"
        echo ""
        echo "  # Fedora/RHEL:"
        echo "  sudo dnf install python3.12"
    fi
    echo ""

    return 1
}

install_uv() {
    print_header "Installing uv Package Manager"

    if command_exists uv; then
        local version=$(uv --version | cut -d' ' -f2)
        log "uv already installed: $version"
        save_config "UV_VERSION" "$version"
        return 0
    fi

    if ask_yes_no "Install uv package manager?" "y"; then
        log "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh

        # Source the shell config to get uv in PATH
        if [ -f "$HOME/.cargo/env" ]; then
            source "$HOME/.cargo/env"
        fi

        if command_exists uv; then
            local version=$(uv --version | cut -d' ' -f2)
            log "uv installed successfully: $version"
            save_config "UV_VERSION" "$version"
            return 0
        else
            log_error "uv installation failed. Please install manually."
            return 1
        fi
    else
        log_warning "Skipping uv installation"
        return 1
    fi
}

install_ollama() {
    print_header "Installing Ollama"

    if [ "$SKIP_OLLAMA" = true ]; then
        log_warning "Skipping Ollama setup (--skip-ollama flag)"
        return 0
    fi

    if command_exists ollama; then
        local version=$(ollama --version 2>&1 | head -n1 || echo "unknown")
        log "Ollama already installed: $version"
        save_config "OLLAMA_INSTALLED" "true"
        return 0
    fi

    if ! ask_yes_no "Install Ollama?" "y"; then
        log_warning "Skipping Ollama installation"
        return 0
    fi

    local os=$(detect_os)
    log "Installing Ollama for $os..."

    if [ "$os" = "macos" ]; then
        if command_exists brew; then
            brew install ollama
        else
            log_error "Homebrew not found. Please install from: https://ollama.ai/download"
            return 1
        fi
    elif [ "$os" = "linux" ]; then
        curl -fsSL https://ollama.ai/install.sh | sh
    else
        log_error "Unsupported OS. Please install from: https://ollama.ai/download"
        return 1
    fi

    if command_exists ollama; then
        log "Ollama installed successfully"
        save_config "OLLAMA_INSTALLED" "true"
        return 0
    else
        log_error "Ollama installation failed"
        return 1
    fi
}

start_ollama() {
    print_header "Starting Ollama Service"

    if [ "$SKIP_OLLAMA" = true ]; then
        return 0
    fi

    # Check if Ollama is already running
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        log "Ollama is already running"
        save_config "OLLAMA_RUNNING" "true"
        return 0
    fi

    log "Starting Ollama server..."

    # Start Ollama in background
    nohup ollama serve > ollama.log 2>&1 &
    local ollama_pid=$!

    # Wait for Ollama to start (max 30 seconds)
    local count=0
    while [ $count -lt 30 ]; do
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            log "Ollama started successfully (PID: $ollama_pid)"
            save_config "OLLAMA_RUNNING" "true"
            save_config "OLLAMA_PID" "$ollama_pid"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    log_error "Failed to start Ollama server"
    return 1
}

download_ollama_models() {
    print_header "Downloading Ollama Models"

    if [ "$SKIP_OLLAMA" = true ]; then
        return 0
    fi

    # Determine which models to download
    local models=""
    if [ -n "$OLLAMA_MODELS" ]; then
        models="$OLLAMA_MODELS"
    elif [ "$INTERACTIVE_MODE" = true ]; then
        echo "Available models:"
        echo "  1. granite4 (recommended, ~2.5GB)"
        echo "  2. llama3.2 (~2GB)"
        echo "  3. nomic-embed-text (optimized for embeddings, ~274MB)"
        echo ""
        read -p "Enter model numbers to download (comma-separated, e.g., 1,3) or 'all': " choice

        case "$choice" in
            all|ALL)
                models="$DEFAULT_MODELS"
                ;;
            *)
                models=""
                IFS=',' read -ra CHOICES <<< "$choice"
                for i in "${CHOICES[@]}"; do
                    case "$i" in
                        1) models="${models:+$models,}granite4";;
                        2) models="${models:+$models,}llama3.2";;
                        3) models="${models:+$models,}nomic-embed-text";;
                    esac
                done
                ;;
        esac
    else
        models="$DEFAULT_MODELS"
    fi

    if [ -z "$models" ]; then
        log_warning "No models selected for download"
        return 0
    fi

    log "Checking models to download: $models"

    # Get list of installed models from Ollama API
    local installed_models_json=""
    if installed_models_json=$(curl -s http://localhost:11434/api/tags 2>/dev/null); then
        log_info "Successfully queried Ollama API for installed models"
    else
        log_error "Failed to query Ollama API. Cannot verify installed models."
        log_warning "Proceeding with download attempts anyway..."
        installed_models_json=""
    fi

    IFS=',' read -ra MODEL_ARRAY <<< "$models"
    local models_downloaded=0
    local models_skipped=0
    local models_failed=0

    for model in "${MODEL_ARRAY[@]}"; do
        model=$(echo "$model" | xargs)  # Trim whitespace

        # Check if model is already installed
        local is_installed=false
        if [ -n "$installed_models_json" ]; then
            # Extract model names from JSON response
            # The JSON structure is: {"models":[{"name":"model:tag",...},...]}
            if echo "$installed_models_json" | grep -q "\"name\":\"${model}"; then
                is_installed=true
            fi
        fi

        if [ "$is_installed" = true ]; then
            log "Model $model is already installed - skipping download"
            save_config "OLLAMA_MODEL_${model}" "installed"
            models_skipped=$((models_skipped + 1))
        else
            log "Downloading $model..."
            if ollama pull "$model"; then
                log "Successfully downloaded $model"
                save_config "OLLAMA_MODEL_${model}" "installed"
                models_downloaded=$((models_downloaded + 1))
            else
                log_error "Failed to download $model"
                models_failed=$((models_failed + 1))
            fi
        fi
    done

    # Summary
    echo ""
    log_info "Model download summary:"
    log_info "  Downloaded: $models_downloaded"
    log_info "  Skipped (already installed): $models_skipped"
    if [ $models_failed -gt 0 ]; then
        log_info "  Failed: $models_failed"
    fi
    echo ""

    # Verify models
    log "Verifying installed models..."
    curl -s http://localhost:11434/api/tags | tee -a "$LOG_FILE"
}

install_container_runtime() {
    print_header "Installing Container Runtime (Podman/Docker)"

    if [ "$SKIP_OPENSEARCH" = true ]; then
        log_warning "Skipping container runtime setup (--skip-opensearch flag)"
        return 0
    fi

    # Check for Podman first
    if command_exists podman; then
        log "Podman already installed"
        save_config "CONTAINER_RUNTIME" "podman"

        # Check if podman machine is running (macOS)
        if [[ "$(detect_os)" == "macos" ]]; then
            if ! podman machine list 2>/dev/null | grep -q "Currently running"; then
                log "Starting Podman machine..."
                podman machine start || true
            fi
        fi
        return 0
    fi

    # Check for Docker
    if command_exists docker; then
        log "Docker already installed"
        save_config "CONTAINER_RUNTIME" "docker"
        return 0
    fi

    if ! ask_yes_no "Install Podman for running OpenSearch?" "y"; then
        log_warning "Skipping container runtime installation"
        return 0
    fi

    local os=$(detect_os)
    local pkg_mgr=$(detect_package_manager)

    log "Installing Podman..."

    if [ "$os" = "macos" ]; then
        if [ "$pkg_mgr" = "brew" ]; then
            brew install podman
            podman machine init
            podman machine start
        else
            log_error "Homebrew required for Podman installation on macOS"
            return 1
        fi
    elif [ "$os" = "linux" ]; then
        case "$pkg_mgr" in
            apt)
                sudo apt update
                sudo apt install -y podman
                ;;
            dnf)
                sudo dnf install -y podman
                ;;
            yum)
                sudo yum install -y podman
                ;;
            *)
                log_error "Unsupported package manager: $pkg_mgr"
                return 1
                ;;
        esac
    fi

    if command_exists podman; then
        log "Podman installed successfully"
        save_config "CONTAINER_RUNTIME" "podman"
        return 0
    else
        log_error "Podman installation failed"
        return 1
    fi
}

install_podman_compose() {
    print_header "Installing podman-compose"

    if [ "$SKIP_OPENSEARCH" = true ]; then
        return 0
    fi

    local runtime=$(load_config "CONTAINER_RUNTIME")

    if [ "$runtime" = "docker" ]; then
        if command_exists docker-compose; then
            log "docker-compose already available"
            return 0
        fi
    fi

    if command_exists podman-compose; then
        log "podman-compose already installed"
        return 0
    fi

    log "Installing podman-compose..."

    local os=$(detect_os)

    # On macOS, prefer pipx or brew to avoid PEP 668 issues
    if [ "$os" = "macos" ]; then
        if command_exists brew; then
            log "Using Homebrew to install podman-compose..."
            brew install podman-compose
        elif command_exists pipx; then
            log "Using pipx to install podman-compose..."
            # Set Python 3.12 explicitly to avoid Python 3.14 libexpat issues
            log_info "Setting PIPX_DEFAULT_PYTHON to python3.12 to avoid compatibility issues..."
            export PIPX_DEFAULT_PYTHON=python3.12
            pipx install --python python3.12 podman-compose
        else
            log_warning "Neither Homebrew nor pipx found."
            log_info "Installing pipx first..."
            if command_exists brew; then
                brew install pipx
                # Set Python 3.12 explicitly to avoid Python 3.14 libexpat issues
                log_info "Setting PIPX_DEFAULT_PYTHON to python3.12 to avoid compatibility issues..."
                export PIPX_DEFAULT_PYTHON=python3.12
                pipx install --python python3.12 podman-compose
            else
                log_error "Cannot install podman-compose. Please install manually:"
                log_error "  Option 1: brew install podman-compose"
                log_error "  Option 2: brew install pipx && PIPX_DEFAULT_PYTHON=python3.12 pipx install --python python3.12 podman-compose"
                return 1
            fi
        fi
    else
        # On Linux, try pip3 with --user flag to avoid system package conflicts
        if command_exists pip3; then
            log "Using pip3 to install podman-compose..."
            pip3 install --user podman-compose
        elif command_exists pip; then
            log "Using pip to install podman-compose..."
            pip install --user podman-compose
        else
            log_error "pip not found. Cannot install podman-compose"
            return 1
        fi
    fi

    if command_exists podman-compose; then
        log "podman-compose installed successfully"
        return 0
    else
        log_error "podman-compose installation failed"
        log_info "You may need to restart your shell or add ~/.local/bin to PATH"
        return 1
    fi
}

start_opensearch() {
    print_header "Starting OpenSearch"

    if [ "$SKIP_OPENSEARCH" = true ]; then
        log_warning "Skipping OpenSearch setup (--skip-opensearch flag)"
        return 0
    fi

    # Check if OpenSearch is already running
    if curl -s -u admin:MyStrongPass123! http://localhost:9200/_cluster/health >/dev/null 2>&1; then
        log "OpenSearch is already running"
        save_config "OPENSEARCH_RUNNING" "true"
        return 0
    fi

    if [ ! -f "docker/docker-compose.opensearch.yml" ]; then
        log_error "docker/docker-compose.opensearch.yml not found"
        return 1
    fi

    local runtime=$(load_config "CONTAINER_RUNTIME")

    log "Starting OpenSearch using $runtime..."

    if [ "$runtime" = "docker" ]; then
        docker-compose -f docker/docker-compose.opensearch.yml up -d
    else
        podman-compose -f docker/docker-compose.opensearch.yml up -d
    fi

    # Wait for OpenSearch to be ready (max 60 seconds)
    log "Waiting for OpenSearch to be ready..."
    local count=0
    while [ $count -lt 60 ]; do
        if curl -s -u admin:MyStrongPass123! http://localhost:9200/_cluster/health >/dev/null 2>&1; then
            log "OpenSearch started successfully"
            save_config "OPENSEARCH_RUNNING" "true"

            # Show cluster health
            log_info "Cluster health:"
            curl -s -u admin:MyStrongPass123! http://localhost:9200/_cluster/health?pretty | tee -a "$LOG_FILE"
            return 0
        fi
        sleep 2
        count=$((count + 2))
    done

    log_error "OpenSearch failed to start within 60 seconds"
    log_info "Check logs with: podman-compose -f docker/docker-compose.opensearch.yml logs"
    return 1
}

setup_python_environment() {
    print_header "Setting Up Python Environment"

    if [ "$SKIP_PYTHON" = true ]; then
        log_warning "Skipping Python environment setup (--skip-python flag)"
        return 0
    fi

    # Determine the correct project root path
    local project_root=""
    if [ -f "pyproject.toml" ]; then
        project_root="."
    elif [ -f "../pyproject.toml" ]; then
        project_root=".."
    else
        log_error "pyproject.toml not found. Please run from project root or scripts directory."
        return 1
    fi

    local original_dir=$(pwd)
    cd "$project_root"

    log "Creating virtual environment and installing dependencies..."
    log_info "Working directory: $(pwd)"

    if command_exists uv; then
        uv sync --extra dev
    else
        log_error "uv not found. Cannot set up Python environment"
        cd "$original_dir"
        return 1
    fi

    if [ -d ".venv" ]; then
        log "Virtual environment created successfully"
        save_config "VENV_PATH" "$(pwd)/.venv"

        # Test if docling-pipelines is available
        if [ -f ".venv/bin/docling-pipelines" ]; then
            log "docling-pipelines CLI installed successfully"
        fi
    else
        log_error "Virtual environment creation failed"
        cd "$original_dir"
        return 1
    fi

    cd "$original_dir"
}

verify_services() {
    print_header "Verifying Services"

    local all_ok=true

    # Check Ollama
    if [ "$SKIP_OLLAMA" = false ]; then
        log_info "Checking Ollama..."
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            log "Ollama: OK (http://localhost:11434)"
        else
            log_error "Ollama: NOT RUNNING"
            all_ok=false
        fi
    fi

    # Check OpenSearch
    if [ "$SKIP_OPENSEARCH" = false ]; then
        log_info "Checking OpenSearch..."
        if curl -s -u admin:MyStrongPass123! http://localhost:9200/_cluster/health >/dev/null 2>&1; then
            log "OpenSearch: OK (http://localhost:9200)"
            log "OpenSearch Dashboards: http://localhost:5601 (admin/MyStrongPass123!)"
        else
            log_error "OpenSearch: NOT RUNNING"
            all_ok=false
        fi
    fi

    if [ "$all_ok" = true ]; then
        log "All services verified successfully"
        return 0
    else
        log_warning "Some services are not running"
        return 1
    fi
}

show_summary() {
    print_header "Setup Summary"

    echo ""
    echo -e "${GREEN}Setup completed!${NC}"
    echo ""
    echo "Configuration saved to: $CONFIG_FILE"
    echo "Setup log saved to: $LOG_FILE"
    echo ""

    if [ "$SKIP_PYTHON" = false ]; then
        echo -e "${BLUE}Next Steps:${NC}"
        echo ""
        echo "1. Activate the virtual environment:"
        echo "   source .venv/bin/activate"
        echo ""
        echo "2. Set PYTHONPATH (from project root):"
        echo "   export PYTHONPATH=\"\$(pwd)/src:\${PYTHONPATH}\""
        echo ""
        echo "3. Verify installation:"
        echo "   docling-pipelines --help"
        echo ""
        echo "4. List available operators:"
        echo "   docling-pipelines --list-operators"
        echo ""
        echo "5. Run your first flow:"
        echo "   docling-pipelines --flow-file path/to/flow.json"
        echo ""
    fi

    if [ "$SKIP_OLLAMA" = false ]; then
        echo -e "${BLUE}Ollama:${NC}"
        echo "  Server: http://localhost:11434"
        echo "  Test: curl http://localhost:11434/api/tags"
        echo ""
    fi

    if [ "$SKIP_OPENSEARCH" = false ]; then
        echo -e "${BLUE}OpenSearch:${NC}"
        echo "  API: http://localhost:9200"
        echo "  Dashboards: http://localhost:5601"
        echo "  Username: admin"
        echo ""
    fi

    echo -e "${BLUE}Documentation:${NC}"
    echo "  User Guide: USER_GUIDE_PIPELINE_SETUP.md"
    echo "  Architecture: ARCHITECTURE.md"
    echo "  Sample flows: sample_flows/README.md"
    echo ""
}

################################################################################
# Git Intercept Setup
################################################################################

setup_git_intercept() {
    print_header "Setting Up Git Intercept"

    local git_intercept='
# Docpipe Git Intercept
git() {
    # Block --no-verify on commit
    if [ "$1" = "commit" ]; then
        for arg in "$@"; do
            if [ "$arg" = "--no-verify" ] || [ "$arg" = "-n" ]; then
                echo "Error: The --no-verify (-n) option has been disabled on this system."
                return 1
            fi
        done
    fi

    # Require confirmation before any push
    if [ "$1" = "push" ]; then
        echo ""
        echo "Have you verified that the pre-commit checks are passing with no failures?"
        echo "Also, if you plan to raise a PR, remember to include the pre-commit hook output in your GitHub PR description."
        echo ""
        printf "If yes, then proceed with the push? (Y/N): "
        read -r answer
        case "$answer" in
            [Yy]) ;;
            *)
                echo "Push aborted."
                return 1
                ;;
        esac
    fi

    # Pass everything to the real git binary
    command git "$@"
}
# End Docpipe Git Intercept'

    local shell_config=""
    if [ -f "$HOME/.zshrc" ]; then
        shell_config="$HOME/.zshrc"
    elif [ -f "$HOME/.bashrc" ]; then
        shell_config="$HOME/.bashrc"
    else
        log_error "No .zshrc or .bashrc found. Cannot install git intercept."
        return 1
    fi

    # Avoid duplicate entries
    if grep -q "Docpipe Git Intercept" "$shell_config"; then
        log "Git intercept already present in $shell_config — skipping"
        return 0
    fi

    echo "$git_intercept" >> "$shell_config"
    log "Git intercept added to $shell_config"
    log_info "Run 'source $shell_config' or open a new terminal for it to take effect."
}

################################################################################
# Main Execution
################################################################################

main() {
    # Initialize log file
    echo "Docpipe Setup Log - $(date)" > "$LOG_FILE"

    print_header "Docpipe Environment Setup"

    log "Starting setup process..."
    log "OS: $(detect_os)"
    log "Package Manager: $(detect_package_manager)"

    if [ "$INTERACTIVE_MODE" = true ]; then
        log "Running in INTERACTIVE mode"
    else
        log "Running in DEFAULT mode (use --interactive for prompts)"
    fi

    # Setting up git intercept command capability in .zshrc or .bashrc.
    setup_git_intercept

    # Run setup steps
    check_python || exit 1
    install_uv || log_warning "Continuing without uv"

    if [ "$SKIP_OLLAMA" = false ]; then
        install_ollama
        start_ollama
        download_ollama_models
    fi

    if [ "$SKIP_OPENSEARCH" = false ]; then
        install_container_runtime
        install_podman_compose
        start_opensearch
    fi

    if [ "$SKIP_PYTHON" = false ]; then
        setup_python_environment
    fi

    verify_services
    show_summary

    log "Setup completed successfully!"
}

# Parse arguments and run main
parse_arguments "$@"
main

exit 0
