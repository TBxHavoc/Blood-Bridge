#!/usr/bin/env bash
# ==============================================================================
# Blood Bridge - Server Deployment & Migration Script
# Targets: Linux (Ubuntu/Debian/RHEL/CentOS/SLES) & IBM LinuxONE (s390x)
# ==============================================================================

set -euo pipefail

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}          Blood Bridge Server Deployment & Migration Tool       ${NC}"
echo -e "${CYAN}================================================================${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Check prerequisites
echo -e "\n${BLUE}[1/5] Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed or not in PATH.${NC}"
    echo "Please install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi

DOCKER_COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Error: Docker Compose (v2 or v1) is not installed.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker engine & compose found: $($DOCKER_COMPOSE_CMD version --short)${NC}"

# 2. Check environment configuration
echo -e "\n${BLUE}[2/5] Checking environment configuration...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo -e "${YELLOW}! No .env file found. Creating one from .env.example...${NC}"
        cp .env.example .env
        
        # Generate a random 32-byte JWT Secret Key if not set
        if command -v openssl &> /dev/null; then
            RAND_SECRET=$(openssl rand -hex 32)
            sed -i.bak "s/JWT_SECRET_KEY=/JWT_SECRET_KEY=${RAND_SECRET}/" .env && rm -f .env.bak
            echo -e "${GREEN}✓ Generated secure random JWT_SECRET_KEY.${NC}"
        fi
        echo -e "${YELLOW}! Please review .env to customize credentials if needed.${NC}"
    else
        echo -e "${RED}Error: Neither .env nor .env.example exists.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ .env configuration present.${NC}"
fi

# Load variables safely
set -a
# shellcheck disable=SC1091
source .env
set +a

WEB_PORT="${WEB_PORT:-8080}"
API_PORT="${API_PORT:-8000}"

# Handle action flags
ACTION="up"
RUN_SEED=false
BUILD_FLAG="--build"

for arg in "$@"; do
    case "$arg" in
        --down)
            ACTION="down"
            ;;
        --status)
            ACTION="status"
            ;;
        --logs)
            ACTION="logs"
            ;;
        --no-build)
            BUILD_FLAG=""
            ;;
        --seed)
            RUN_SEED=true
            ;;
        --help|-h)
            echo "Usage: ./deploy.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  (default)     Build and start all services in background"
            echo "  --seed        Automatically seed database after services are healthy"
            echo "  --no-build    Start without rebuilding images"
            echo "  --down        Stop all running containers"
            echo "  --status      Show container status"
            echo "  --logs        Tail container logs"
            echo "  --help, -h    Show this help message"
            exit 0
            ;;
    esac
done

if [ "$ACTION" = "down" ]; then
    echo -e "\n${YELLOW}Stopping Blood Bridge services...${NC}"
    $DOCKER_COMPOSE_CMD down
    echo -e "${GREEN}✓ Services stopped.${NC}"
    exit 0
fi

if [ "$ACTION" = "status" ]; then
    echo -e "\n${CYAN}Current Service Status:${NC}"
    $DOCKER_COMPOSE_CMD ps
    exit 0
fi

if [ "$ACTION" = "logs" ]; then
    $DOCKER_COMPOSE_CMD logs -f
    exit 0
fi

# 3. Build & start containers
echo -e "\n${BLUE}[3/5] Starting Blood Bridge stack with Docker Compose...${NC}"
$DOCKER_COMPOSE_CMD up -d $BUILD_FLAG

# 4. Await service health
echo -e "\n${BLUE}[4/5] Waiting for services to become healthy...${NC}"
MAX_WAIT=90
ELAPSED=0
API_READY=false

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -fsS "http://127.0.0.1:${API_PORT}/api/v1/health" &> /dev/null; then
        API_READY=true
        break
    fi
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    echo -ne "  Waiting for backend API... (${ELAPSED}s / ${MAX_WAIT}s)\r"
done
echo ""

if [ "$API_READY" = true ]; then
    echo -e "${GREEN}✓ Backend API is healthy and answering on port ${API_PORT}!${NC}"
else
    echo -e "${YELLOW}! Backend API is taking longer than expected. Check logs with: ./deploy.sh --logs${NC}"
fi

# 5. Optional demo data seed
if [ "$RUN_SEED" = true ]; then
    echo -e "\n${BLUE}[5/5] Seeding database with synthetic demonstration data...${NC}"
    $DOCKER_COMPOSE_CMD run --rm seed
    echo -e "${GREEN}✓ Database seeded successfully.${NC}"
else
    echo -e "\n${BLUE}[5/5] Skipping demo seed (run with '--seed' or: $DOCKER_COMPOSE_CMD run --rm seed)${NC}"
fi

echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}  Blood Bridge is successfully deployed and running!            ${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e "  Web Application (Frontend + Reverse Proxy): ${CYAN}http://localhost:${WEB_PORT}${NC}"
echo -e "  Direct API Documentation:                   ${CYAN}http://localhost:${API_PORT}/docs${NC}"
echo -e "  API Health Check:                           ${CYAN}http://localhost:${API_PORT}/api/v1/health${NC}"
echo -e "================================================================"
echo -e "Management shortcuts:"
echo -e "  View container status: ${YELLOW}./deploy.sh --status${NC}"
echo -e "  View live logs:        ${YELLOW}./deploy.sh --logs${NC}"
echo -e "  Seed demo accounts:    ${YELLOW}./deploy.sh --seed${NC}"
echo -e "  Stop all services:     ${YELLOW}./deploy.sh --down${NC}"
echo -e "================================================================\n"
