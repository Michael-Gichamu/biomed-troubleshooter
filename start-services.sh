#!/bin/bash
# =============================================================================
# Biomedical Troubleshooting Agent - Linux/macOS Startup Script
# =============================================================================
# Usage:
#   ./start-services.sh           # Start all services
#   ./start-services.sh stop      # Stop all services
#   ./start-services.sh status    # Check service status
#   ./start-services.sh logs     # View logs
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${YELLOW}BIOMEDICAL TROUBLESHOOTING AGENT${NC}"
    echo -e "${YELLOW}Docker Services Management${NC}"
    echo -e "${CYAN}============================================================${NC}"
    echo ""
}

test_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}[ERROR] Docker is not installed${NC}"
        echo -e "${YELLOW}Please install Docker: https://docs.docker.com/get-docker/${NC}"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}[ERROR] Docker Compose is not installed${NC}"
        exit 1
    fi
}

start_services() {
    print_header
    echo -e "[1/3] ${GREEN}Starting ChromaDB...${NC}"

    if docker ps -a --format '{{.Names}}' | grep -q 'biomed-chromadb'; then
        if ! docker ps --format '{{.Names}}' | grep -q 'biomed-chromadb'; then
            docker start biomed-chromadb 2>/dev/null || true
            echo -e "       ChromaDB started"
        else
            echo -e "       ChromaDB already running"
        fi
    else
        docker run -d -p 8000:8000 --name biomed-chromadb chromadb/chroma 2>/dev/null || true
        echo -e "       ChromaDB started on port 8000"
    fi

    echo -e "[2/3] ${GREEN}Starting Mosquitto MQTT...${NC}"

    if docker ps -a --format '{{.Names}}' | grep -q 'biomed-mosquitto'; then
        if ! docker ps --format '{{.Names}}' | grep -q 'biomed-mosquitto'; then
            docker start biomed-mosquitto 2>/dev/null || true
            echo -e "       Mosquitto started"
        else
            echo -e "       Mosquitto already running"
        fi
    else
        docker run -d -p 1883:1883 -p 9001:9001 --name biomed-mosquitto eclipse-mosquitto 2>/dev/null || true
        echo -e "       Mosquitto started on ports 1883, 9001"
    fi

    echo -e "[3/3] ${GREEN}Verifying services...${NC}"
    sleep 3

    if curl -s http://localhost:8000/api/v1/heartbeat > /dev/null 2>&1; then
        echo -e "       ChromaDB: ${GREEN}✓ Running${NC}"
    else
        echo -e "       ChromaDB: ${RED}✗ Not responding${NC}"
    fi

    echo ""
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${GREEN}SERVICES STARTED${NC}"
    echo -e "${CYAN}============================================================${NC}"
    echo ""
    echo "  ChromaDB:  http://localhost:8000"
    echo "  MQTT:       localhost:1883"
    echo ""
    echo "Run agent in mock mode:"
    echo -e "  ${CYAN}python -m src.interfaces.cli --mock${NC}"
    echo ""
}

stop_services() {
    print_header
    echo -e "${YELLOW}Stopping services...${NC}"
    docker stop biomed-chromadb biomed-mosquitto 2>/dev/null || true
    docker rm biomed-chromadb biomed-mosquitto 2>/dev/null || true
    echo -e "${GREEN}All services stopped${NC}"
}

show_status() {
    print_header
    echo -e "${YELLOW}Service Status:${NC}"
    echo ""

    if docker ps --format '{{.Names}}' | grep -q 'biomed-chromadb'; then
        echo -e "  ChromaDB:  ${GREEN}✓ Running${NC}"
    else
        echo -e "  ChromaDB:  ${RED}✗ Stopped${NC}"
    fi

    if docker ps --format '{{.Names}}' | grep -q 'biomed-mosquitto'; then
        echo -e "  Mosquitto: ${GREEN}✓ Running${NC}"
    else
        echo -e "  Mosquitto: ${RED}✗ Stopped${NC}"
    fi

    echo ""
    echo "Active containers:"
    docker ps --format "  {{.Names}} - {{.Status}} - {{.Ports}}" | grep biomed || echo "  (none)"
}

show_logs() {
    echo -e "${YELLOW}ChromaDB logs:${NC}"
    docker logs biomed-chromadb --tail 20

    echo ""
    echo -e "${YELLOW}Mosquitto logs:${NC}"
    docker logs biomed-mosquitto --tail 20
}

# Main
test_docker

case "${1:-}" in
    up)
        start_services
        ;;
    stop)
        stop_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    restart)
        stop_services
        start_services
        ;;
    *)
        echo -e "${CYAN}Usage: $0 [up|stop|status|logs|restart]${NC}"
        echo ""
        echo "  up      Start all services (default)"
        echo "  stop    Stop all services"
        echo "  status  Show service status"
        echo "  logs    View service logs"
        echo "  restart Restart all services"
        ;;
esac
