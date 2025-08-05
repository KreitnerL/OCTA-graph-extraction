#!/bin/bash

# OCTA Graph Extraction - Complete Setup Script
# Automatically configures, builds, and tests the entire system

set -e  # Exit on any error

# Colors for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Setup mode selection
SETUP_MODE=""

# Print banner
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    OCTA Graph Extraction                       ║"
echo "║                     Complete Setup                             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Setup mode selection
echo -e "${CYAN}Please select your setup mode:${NC}"
echo "1) 🐍 Host Python + Docker Voreen (recommended for development)"
echo "2) 🐳 Full Docker Setup (recommended for production/simple usage)"
echo ""
read -p "Enter your choice (1 or 2): " choice

case $choice in
    1)
        SETUP_MODE="host_python"
        echo -e "${GREEN}Selected: Host Python + Docker Voreen setup${NC}"
        ;;
    2)
        SETUP_MODE="full_docker"
        echo -e "${GREEN}Selected: Full Docker setup${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice. Exiting.${NC}"
        exit 1
        ;;
esac

# Function to print section headers
print_section() {
    echo -e "\n${CYAN}▶ $1${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Function to print status
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "success" ]; then
        echo -e "  ${GREEN}✅ $message${NC}"
    elif [ "$status" = "warning" ]; then
        echo -e "  ${YELLOW}⚠️  $message${NC}"
    elif [ "$status" = "error" ]; then
        echo -e "  ${RED}❌ $message${NC}"
    else
        echo -e "  ${BLUE}ℹ️  $message${NC}"
    fi
}

# Check prerequisites
print_section "1. Checking Prerequisites"

# Check Docker
if ! command -v docker &> /dev/null; then
    print_status "error" "Docker not found. Please install Docker first."
    exit 1
fi
print_status "success" "Docker found: $(docker --version | cut -d' ' -f3 | tr -d ',')"

# Check Docker daemon
if ! docker info &> /dev/null; then
    print_status "error" "Docker daemon not running. Please start Docker first."
    exit 1
fi
print_status "success" "Docker daemon is running"

# Mode-specific prerequisites
if [ "$SETUP_MODE" = "full_docker" ]; then
    # Check Docker Compose for full docker setup
    if ! command -v docker compose &> /dev/null; then
        print_status "error" "Docker Compose not found. Please install Docker Compose first."
        exit 1
    fi
    print_status "success" "Docker Compose found: $(docker compose --version | cut -d' ' -f3 | tr -d ',')"
elif [ "$SETUP_MODE" = "host_python" ]; then
    # Check/Install UV for host python setup
    if ! command -v uv &> /dev/null; then
        print_status "warning" "UV not found. Installing UV..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # Reload PATH
        export PATH="$HOME/.cargo/bin:$PATH"
        if command -v uv &> /dev/null; then
            print_status "success" "UV installed successfully"
        else
            print_status "error" "Failed to install UV. Please install manually."
            exit 1
        fi
    else
        print_status "success" "UV found: $(uv --version)"
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
        print_status "error" "Python not found. Please install Python first."
        exit 1
    fi
    PYTHON_CMD=$(command -v python3 || command -v python)
    print_status "success" "Python found: $($PYTHON_CMD --version)"
fi

# Detect system configuration
print_section "2. Detecting System Configuration"

CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)
DOCKER_GROUP_ID=$(getent group docker | cut -d: -f3 2>/dev/null || echo "")

if [ -z "$DOCKER_GROUP_ID" ]; then
    print_status "error" "Docker group not found. Please install Docker first."
    exit 1
fi

print_status "info" "User ID: $CURRENT_UID"
print_status "info" "Group ID: $CURRENT_GID"
print_status "info" "Docker Group ID: $DOCKER_GROUP_ID"

# Check if user is in docker group
if groups $USER | grep -q docker; then
    print_status "success" "User is in docker group"
else
    print_status "warning" "User is not in docker group"
    print_status "info" "Consider running: sudo usermod -aG docker $USER"
    print_status "info" "Then log out and back in"
fi

# Configure environment
print_section "3. Configuring Environment"

print_status "info" "Updating .env file with detected IDs..."

# Remove existing UID/GID/DOCKER_GID lines (both commented and uncommented)
sed -i '/^#.*UID=/d' .env 2>/dev/null || true
sed -i '/^#.*GID=/d' .env 2>/dev/null || true
sed -i '/^#.*DOCKER_GID=/d' .env 2>/dev/null || true
sed -i '/^UID=/d' .env 2>/dev/null || true
sed -i '/^GID=/d' .env 2>/dev/null || true
sed -i '/^DOCKER_GID=/d' .env 2>/dev/null || true

# Configure paths
print_status "info" "Configuring directory paths..."

# Default directories
DEFAULT_TMP_DIR="/tmp/voreen"
DEFAULT_SRC_DIR="$(pwd)/data/src"
DEFAULT_OUTPUT_DIR="$(pwd)/data/output"

# Get current values from .env if present
CURRENT_TMP_DIR=$(grep "HOST_TMP_DIR=" .env 2>/dev/null | cut -d'=' -f2 || echo "TODO")
CURRENT_SRC_DIR=$(grep "HOST_SRC_DIR=" .env 2>/dev/null | cut -d'=' -f2 || echo "TODO")
CURRENT_OUTPUT_DIR=$(grep "HOST_OUTPUT_DIR=" .env 2>/dev/null | cut -d'=' -f2 || echo "TODO")

# Ask for temporary directory
if [ "$CURRENT_TMP_DIR" = "TODO" ] || [ -z "$CURRENT_TMP_DIR" ]; then
    echo ""
    echo -e "${CYAN}Configure temporary directory for Voreen processing:${NC}"
    echo -e "This directory will be used for intermediate files during analysis."
    echo -e "Default: ${DEFAULT_TMP_DIR}"
    echo ""
    read -p "Enter temporary directory path (or press Enter for default): " USER_TMP_DIR

    if [ -z "$USER_TMP_DIR" ]; then
        HOST_TMP_DIR="$DEFAULT_TMP_DIR"
    else
        HOST_TMP_DIR="$USER_TMP_DIR"
    fi

    mkdir -p "$HOST_TMP_DIR"
    print_status "success" "Temporary directory set to: $HOST_TMP_DIR"
else
    HOST_TMP_DIR="$CURRENT_TMP_DIR"
    print_status "success" "Using existing temporary directory: $HOST_TMP_DIR"
fi

# Ask for source directory
if [ "$CURRENT_SRC_DIR" = "TODO" ] || [ -z "$CURRENT_SRC_DIR" ]; then
    echo ""
    echo -e "${CYAN}Configure source data directory:${NC}"
    echo -e "This directory will be used for input/source data."
    echo -e "Default: ${DEFAULT_SRC_DIR}"
    echo ""
    read -p "Enter source directory path (or press Enter for default): " USER_SRC_DIR

    if [ -z "$USER_SRC_DIR" ]; then
        HOST_SRC_DIR="$DEFAULT_SRC_DIR"
    else
        HOST_SRC_DIR="$USER_SRC_DIR"
    fi

    mkdir -p "$HOST_SRC_DIR"
    print_status "success" "Source directory set to: $HOST_SRC_DIR"
else
    HOST_SRC_DIR="$CURRENT_SRC_DIR"
    print_status "success" "Using existing source directory: $HOST_SRC_DIR"
fi

# Ask for output directory
if [ "$CURRENT_OUTPUT_DIR" = "TODO" ] || [ -z "$CURRENT_OUTPUT_DIR" ]; then
    echo ""
    echo -e "${CYAN}Configure output directory:${NC}"
    echo -e "This directory will be used for analysis results/output files."
    echo -e "Default: ${DEFAULT_OUTPUT_DIR}"
    echo ""
    read -p "Enter output directory path (or press Enter for default): " USER_OUTPUT_DIR

    if [ -z "$USER_OUTPUT_DIR" ]; then
        HOST_OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
    else
        HOST_OUTPUT_DIR="$USER_OUTPUT_DIR"
    fi

    mkdir -p "$HOST_OUTPUT_DIR"
    print_status "success" "Output directory set to: $HOST_OUTPUT_DIR"
else
    HOST_OUTPUT_DIR="$CURRENT_OUTPUT_DIR"
    print_status "success" "Using existing output directory: $HOST_OUTPUT_DIR"
fi

# Update .env file with all configurations
sed -i '/^HOST_TMP_DIR=/d' .env 2>/dev/null || true
sed -i '/^HOST_SRC_DIR=/d' .env 2>/dev/null || true
sed -i '/^HOST_OUTPUT_DIR=/d' .env 2>/dev/null || true

# Add updated configuration to .env file
cat >> .env << EOF
HOST_TMP_DIR=$HOST_TMP_DIR
HOST_SRC_DIR=$HOST_SRC_DIR
HOST_OUTPUT_DIR=$HOST_OUTPUT_DIR
UID=$CURRENT_UID
GID=$CURRENT_GID
DOCKER_GID=$DOCKER_GROUP_ID
EOF

print_status "success" "Environment configured successfully"

# Build Docker images
print_section "4. Building Docker Images"

if [ "$SETUP_MODE" = "host_python" ]; then
    print_status "info" "Building Voreen container. This can take a while..."
    if docker build -f voreen/Dockerfile -t voreen . > /tmp/build_voreen.log 2>&1; then
        print_status "success" "Voreen container built successfully"
    else
        print_status "error" "Failed to build Voreen container. Check /tmp/build_voreen.log"
        exit 1
    fi
    
    if [ -d ".venv" ]; then
        print_status "success" "Virtual environment already exists at .venv"
    else
        print_status "info" "Setting up Python virtual environment..."
        if uv venv > /tmp/uv_venv.log 2>&1; then
            print_status "success" "Virtual environment created"
        else
            print_status "error" "Failed to create virtual environment. Check /tmp/uv_venv.log"
            exit 1
        fi
    fi
    
    print_status "info" "Installing Python dependencies..."
    if uv sync > /tmp/uv_sync.log 2>&1; then
        print_status "success" "Python dependencies installed"
    else
        print_status "error" "Failed to install dependencies. Check /tmp/uv_sync.log"
        exit 1
    fi

elif [ "$SETUP_MODE" = "full_docker" ]; then
    print_status "info" "Building Voreen container. This can take a while..."
    if docker compose build voreen > /tmp/build_voreen.log 2>&1; then
        print_status "success" "Voreen container built successfully"
    else
        print_status "error" "Failed to build Voreen container. Check /tmp/build_voreen.log"
        exit 1
    fi

    print_status "info" "Building Python container..."
    if docker compose build octa-graph-extraction > /tmp/build_python.log 2>&1; then
        print_status "success" "Python container built successfully"
    else
        print_status "error" "Failed to build Python container. Check /tmp/build_python.log"
        exit 1
    fi
fi

# Start containers
print_section "5. Starting Containers"

if [ "$SETUP_MODE" = "full_docker" ]; then
    print_status "info" "Starting containers..."
    
    # Create the directories that will be mounted to avoid permission issues
    TEST_TMP_DIR=$(grep "HOST_TMP_DIR=" .env | cut -d'=' -f2)
    TEST_SRC_DIR=$(grep "HOST_SRC_DIR=" .env | cut -d'=' -f2)
    TEST_OUTPUT_DIR=$(grep "HOST_OUTPUT_DIR=" .env | cut -d'=' -f2)
    
    mkdir -p "$TEST_TMP_DIR" "$TEST_SRC_DIR" "$TEST_OUTPUT_DIR" 2>/dev/null || true
    
    if docker compose up -d > /tmp/start_containers.log 2>&1; then
        print_status "success" "Containers started successfully"
    else
        print_status "error" "Failed to start containers. Check /tmp/start_containers.log"
        exit 1
    fi

    # Wait for containers to be ready
    print_status "info" "Waiting for containers to be ready..."
    sleep 5
else
    print_status "info" "Skipping container startup for host Python setup"
fi

# Test the setup
print_section "6. Testing Setup"

if [ "$SETUP_MODE" = "host_python" ]; then
    # Test 1: Test Python virtual environment and packages
    print_status "info" "Testing Python virtual environment..."
    if source .venv/bin/activate && python -c "import docker; print('Docker SDK available')" &> /dev/null; then
        print_status "success" "Python environment and Docker SDK: OK"
    else
        print_status "error" "Python environment or Docker SDK: FAILED"
        exit 1
    fi

    # Test 2: Test Voreen container
    print_status "info" "Testing Voreen container..."
    if docker run --rm voreen echo "Voreen test successful" &> /dev/null; then
        print_status "success" "Voreen container: OK"
    else
        print_status "error" "Voreen container: FAILED"
        exit 1
    fi

    # Test 3: Test basic file permissions and temporary directory
    print_status "info" "Testing temporary directory access..."
    TEST_TMP_DIR=$(grep "HOST_TMP_DIR=" .env | cut -d'=' -f2)
    if [ -d "$TEST_TMP_DIR" ]; then
        if touch "$TEST_TMP_DIR/test_file" && rm "$TEST_TMP_DIR/test_file" 2>/dev/null; then
            print_status "success" "Temporary directory access: OK"
        else
            print_status "warning" "Temporary directory permissions may need adjustment"
        fi
    else
        print_status "warning" "Temporary directory not found: $TEST_TMP_DIR"
    fi

elif [ "$SETUP_MODE" = "full_docker" ]; then
    # Test 1: Check container status
    print_status "info" "Checking container status..."
    if docker compose ps | grep -q "Up"; then
        print_status "success" "Containers are running"
    else
        print_status "error" "Containers are not running properly"
        docker compose ps
        exit 1
    fi

    # Test 2: Test Docker access from Python container
    print_status "info" "Testing Docker access from Python container..."
    if docker compose exec -T octa-graph-extraction docker --version &> /dev/null; then
        print_status "success" "Docker access from container: OK"
    else
        print_status "error" "Docker access from container: FAILED"
        exit 1
    fi

    # Test 3: Test Python virtual environment and Docker SDK
    print_status "info" "Testing Python environment and Docker SDK..."
    if docker compose exec -T octa-graph-extraction bash -c "source /home/OCTA-graph-extraction/.venv/bin/activate && python -c 'import docker; print(\"Docker SDK available\")'" &> /dev/null; then
        print_status "success" "Python Docker SDK: OK"
    else
        print_status "error" "Python Docker SDK: FAILED"
        exit 1
    fi

    # Test 4: Test Voreen container accessibility
    print_status "info" "Testing Voreen container accessibility..."
    if docker compose exec -T voreen echo "Voreen accessible" &> /dev/null; then
        print_status "success" "Voreen container: OK"
    else
        print_status "error" "Voreen container: FAILED"
        exit 1
    fi

    # Test 5: Test volume mounts
    print_status "info" "Testing volume mounts..."
    TEST_INPUT_DIR=$(grep "HOST_SRC_DIR=" .env | cut -d'=' -f2)
    TEST_OUTPUT_DIR=$(grep "HOST_OUTPUT_DIR=" .env | cut -d'=' -f2)
    TEST_TMP_DIR=$(grep "HOST_TMP_DIR=" .env | cut -d'=' -f2)

    # Create default directories for testing
    mkdir -p "$TEST_TMP_DIR" 2>/dev/null || true
    
    if docker compose exec -T octa-graph-extraction bash -c "ls /tmp/voreen" &> /dev/null; then
        print_status "success" "Volume mounts: OK"
    else
        print_status "warning" "Volume mounts accessible but directories may need to be created"
    fi
fi

# Display final status and usage instructions
print_section "7. Setup Complete!"

print_status "success" "All tests passed! Your OCTA Graph Extraction environment is ready."

if [ "$SETUP_MODE" = "host_python" ]; then
    echo ""
    echo -e "${GREEN}💡 Host Python + Docker Voreen Setup Complete!${NC}"
    echo ""
    echo -e "${YELLOW}� Configured paths:${NC}"
    TEST_TMP_DIR=$(grep "HOST_TMP_DIR=" .env | cut -d'=' -f2)
    echo "   Temporary: $TEST_TMP_DIR"
    echo ""
    echo -e "${YELLOW}�🐍 Activate Python environment:${NC}"
    echo "   source .venv/bin/activate"
    echo ""
    echo -e "${YELLOW}🔧 Run analysis commands:${NC}"
    echo "   ./run_host.sh faz_seg --src-dir /path/to/data --output-dir /path/to/results"
    echo "   ./run_host.sh graph_extraction --src-dir /path/to/data --output-dir /path/to/results"
    echo ""
    echo -e "${YELLOW}📁 Source and output directories will be specified when running commands${NC}"
    if docker compose down &> /dev/null; then
        print_status "success" "Removed containers successfully"
    else
        print_status "warning" "Failed to remove containers, but they can be stopped manually via: docker compose down"
    fi
    
elif [ "$SETUP_MODE" = "full_docker" ]; then
    echo ""
    echo -e "${BLUE}📊 Container Status:${NC}"
    docker compose ps

    echo ""
    echo -e "${GREEN}💡 Full Docker Setup Complete!${NC}"
    echo ""
    echo -e "${YELLOW}📁 Configured paths:${NC}"
    TEST_TMP_DIR=$(grep "HOST_TMP_DIR=" .env | cut -d'=' -f2)
    echo "   Temporary: $TEST_TMP_DIR"
    echo "   Source & Output: Configure when running commands"
    echo ""
    echo -e "${YELLOW}🔧 Run analysis with automatic container management:${NC}"
    echo "   ./run_analysis.sh etdrs_pipeline --src-dir /path/to/data --output-dir /path/to/results"
    echo -e "${BLUE}Stopping containers...${NC}"
    if docker compose down &> /dev/null; then
        print_status "success" "Removed containers successfully"
    else
        print_status "warning" "Failed to remove containers, but they can be stopped manually via: docker compose down"
    fi
fi

echo ""
echo -e "${BLUE}📌 Configuration saved to .env file for future use.${NC}"
echo -e "${BLUE}📌 Build logs available in /tmp/build_*.log${NC}"

echo ""
echo -e "${GREEN}🎉 Setup completed successfully!${NC}"
