#!/bin/bash

# OCTA Graph Extraction - Automated Command Runner
# Handles automatic container lifecycle and path configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values from .env file
DEFAULT_HOST_TMP_DIR=$(grep "HOST_TMP_DIR=" .env 2>/dev/null | cut -d'=' -f2 || echo "/tmp/voreen")
DEFAULT_HOST_SRC_DIR=$(grep "HOST_SRC_DIR=" .env 2>/dev/null | cut -d'=' -f2 || echo "")
DEFAULT_HOST_OUTPUT_DIR=$(grep "HOST_OUTPUT_DIR=" .env 2>/dev/null | cut -d'=' -f2 || echo "")

# Parse command line arguments
COMMAND=""
HOST_TMP_DIR="$DEFAULT_HOST_TMP_DIR"
HOST_SRC_DIR="$DEFAULT_HOST_SRC_DIR"
HOST_OUTPUT_DIR="$DEFAULT_HOST_OUTPUT_DIR"
EXTRA_ARGS=()

show_help() {
    echo -e "${BLUE}OCTA Graph Extraction - Command Runner${NC}"
    echo ""
    echo "Usage: $0 <command> [options] [-- command_args...]"
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo "  faz_seg                Run FAZ segmentation"
    echo "  graph                  Run graph extraction"
    echo "  etdrs_pipeline         Run complete ETDRS pipeline"
    echo "  summary                Generate analysis summary"
    echo "  pipeline               Run complete pipeline"
    echo ""
    echo -e "${CYAN}Options:${NC}"
    echo "  --source_dir DIR          Source directory (override HOST_SRC_DIR)"
    echo "  --output_dir DIR       Output directory (override HOST_OUTPUT_DIR)"
    echo "  --tmp_dir DIR          Temporary directory (override HOST_TMP_DIR)"
    echo "  --help                 Show this help"
    echo ""
    echo -e "${CYAN}Examples:${NC}"
    echo "  $0 faz_seg --source_dir /path/to/images --output_dir /path/to/output"
    echo "  $0 etdrs_pipeline --source_dir /data/segmentations --output_dir /results"
    echo "  $0 graph -- --verbose --threads 8"
    echo ""
    echo -e "${YELLOW}Note: Arguments after '--' are passed directly to the command${NC}"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --source_dir)
            HOST_SRC_DIR="$2"
            shift 2
            ;;
        --output_dir)
            HOST_OUTPUT_DIR="$2"
            shift 2
            ;;
        --tmp_dir)
            HOST_TMP_DIR="$2"
            shift 2
            ;;
        --)
            shift
            EXTRA_ARGS=("$@")
            break
            ;;
        faz_seg|graph|summary|pipeline|etdrs_pipeline)
            if [ -z "$COMMAND" ]; then
                COMMAND="$1"
                shift
            else
                echo -e "${RED}Error: Multiple commands specified${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "${RED}Error: Unknown argument '$1'${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Validate command
if [ -z "$COMMAND" ]; then
    echo -e "${RED}Error: No command specified${NC}"
    show_help
    exit 1
fi

# Validate paths
if [ -z "$HOST_SRC_DIR" ] || [ "$HOST_SRC_DIR" = "TODO" ]; then
    echo -e "${RED}Error: Source directory not specified. Use --source_dir or configure HOST_SRC_DIR in .env${NC}"
    exit 1
fi

if [ -z "$HOST_OUTPUT_DIR" ] || [ "$HOST_OUTPUT_DIR" = "TODO" ]; then
    echo -e "${RED}Error: Output directory not specified. Use --output_dir or configure HOST_OUTPUT_DIR in .env${NC}"
    exit 1
fi

# Create directories if they don't exist
mkdir -p "$HOST_TMP_DIR" "$HOST_OUTPUT_DIR"

# Check if source directory exists (unless it's a glob pattern)
if [[ "$HOST_SRC_DIR" != *"*"* ]] && [ ! -d "$HOST_SRC_DIR" ]; then
    echo -e "${YELLOW}Warning: Source directory '$HOST_SRC_DIR' does not exist${NC}"
fi

echo -e "${BLUE}🚀 Running OCTA Graph Extraction${NC}"
echo -e "${CYAN}Command:${NC} $COMMAND"
echo -e "${CYAN}Source:${NC} $HOST_SRC_DIR"
echo -e "${CYAN}Output:${NC} $HOST_OUTPUT_DIR"
echo -e "${CYAN}Temp:${NC} $HOST_TMP_DIR"
if [ ${#EXTRA_ARGS[@]} -gt 0 ]; then
    echo -e "${CYAN}Extra args:${NC} ${EXTRA_ARGS[*]}"
fi
echo ""

# Function to cleanup containers on exit
cleanup() {
    echo -e "\n${YELLOW}Cleaning up containers...${NC}"
    docker compose down --remove-orphans 2>/dev/null || true
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Create temporary .env file with current paths
ENV_FILE=".env.tmp"
cp .env "$ENV_FILE"

# Update paths in temporary .env file
sed -i "s|^HOST_TMP_DIR=.*|HOST_TMP_DIR=$HOST_TMP_DIR|" "$ENV_FILE"
sed -i "s|^HOST_SRC_DIR=.*|HOST_SRC_DIR=$HOST_SRC_DIR|" "$ENV_FILE"
sed -i "s|^HOST_OUTPUT_DIR=.*|HOST_OUTPUT_DIR=$HOST_OUTPUT_DIR|" "$ENV_FILE"

# Determine which containers to start based on command
case "$COMMAND" in
    faz_seg|summary)
        echo -e "${BLUE}Starting octa-graph-extraction container only...${NC}"
        # Use --no-deps to avoid starting dependency containers
        docker compose --env-file "$ENV_FILE" up -d --no-deps octa-graph-extraction
        ;;
    graph|etdrs_pipeline|pipeline)
        echo -e "${BLUE}Starting all containers...${NC}"
        docker compose --env-file "$ENV_FILE" up -d
        ;;
    *)
        echo -e "${BLUE}Starting all containers...${NC}"
        docker compose --env-file "$ENV_FILE" up -d
        ;;
esac

# Wait for containers to be ready
echo -e "${BLUE}Waiting for containers to be ready...${NC}"
sleep 3

# Run the command
echo -e "${GREEN}Executing command...${NC}"
docker compose --env-file "$ENV_FILE" exec -T octa-graph-extraction \
    /home/OCTA-graph-extraction/docker/dockershell.sh \
    "$COMMAND" "${EXTRA_ARGS[@]}"

echo -e "${GREEN}✅ Command completed successfully!${NC}"

# Cleanup temporary .env file
rm -f "$ENV_FILE"
