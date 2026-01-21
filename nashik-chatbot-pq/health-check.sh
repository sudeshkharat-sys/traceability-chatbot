#!/bin/bash

# Docker Container Health Check Script
# This script verifies all containers and services are running correctly

echo "========================================"
echo "  Docker Container Health Check"
echo "  $(date)"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Change to project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo -e "${BLUE}Working Directory:${NC} $(pwd)"
echo ""

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed or not in PATH${NC}"
    exit 1
fi

echo "1. Container Status"
echo "═══════════════════"
sudo docker compose ps
echo ""

# Count running containers
RUNNING=$(sudo docker compose ps --status running --format json 2>/dev/null | wc -l)
echo -e "Running containers: ${GREEN}${RUNNING}/4${NC}"
echo ""

echo "2. Basic Health Endpoint"
echo "════════════════════════"
BASIC_HEALTH=$(curl -s -w "\nHTTP_CODE:%{http_code}" http://localhost/health 2>/dev/null)
HTTP_CODE=$(echo "$BASIC_HEALTH" | grep "HTTP_CODE" | cut -d: -f2)
RESPONSE=$(echo "$BASIC_HEALTH" | grep -v "HTTP_CODE")

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ HTTP 200 OK${NC}"
    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
else
    echo -e "${RED}✗ HTTP $HTTP_CODE${NC}"
    echo "$RESPONSE"
fi
echo ""

echo "3. Detailed Health Endpoint"
echo "═══════════════════════════"
DETAILED_HEALTH=$(curl -s -w "\nHTTP_CODE:%{http_code}" http://localhost/health/detailed 2>/dev/null)
HTTP_CODE=$(echo "$DETAILED_HEALTH" | grep "HTTP_CODE" | cut -d: -f2)
RESPONSE=$(echo "$DETAILED_HEALTH" | grep -v "HTTP_CODE")

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ HTTP 200 OK${NC}"
    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"

    # Check if healthy
    if echo "$RESPONSE" | grep -q '"status".*:.*"healthy"'; then
        echo -e "${GREEN}✓ All components healthy${NC}"
    elif echo "$RESPONSE" | grep -q '"status".*:.*"degraded"'; then
        echo -e "${YELLOW}⚠ Some components degraded${NC}"
    fi
else
    echo -e "${RED}✗ HTTP $HTTP_CODE${NC}"
    echo "$RESPONSE"
fi
echo ""

echo "4. System Statistics"
echo "════════════════════"
STATS=$(curl -s http://localhost/stats 2>/dev/null)
echo "$STATS" | jq '.' 2>/dev/null || echo "$STATS"
echo ""

echo "5. PostgreSQL Connection"
echo "════════════════════════"
PG_STATUS=$(sudo docker compose exec -T postgres pg_isready -U postgres 2>&1)
echo "$PG_STATUS"
if echo "$PG_STATUS" | grep -q "accepting connections"; then
    echo -e "${GREEN}✓ PostgreSQL is healthy${NC}"
else
    echo -e "${RED}✗ PostgreSQL has issues${NC}"
fi
echo ""

echo "6. Neo4j Connection"
echo "═══════════════════"
# Get Neo4j password from .env
NEO4J_PASSWORD=$(grep "^NEO4J_PASSWORD=" .env 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'")
NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}

NEO4J_STATUS=$(sudo docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1 as test;" 2>&1)
if echo "$NEO4J_STATUS" | grep -q "test"; then
    echo -e "${GREEN}✓ Neo4j is healthy${NC}"
    echo "Query executed successfully"
else
    echo -e "${RED}✗ Neo4j has issues${NC}"
    echo "$NEO4J_STATUS" | head -5
fi
echo ""

echo "7. Listening Ports"
echo "══════════════════"
echo "Expected ports: 80, 443, 5000, 7474, 7687"
sudo netstat -tulpn 2>/dev/null | grep -E ':80|:443|:5000|:7474|:7687' | grep LISTEN | awk '{print $4}' | sort -u || echo "netstat not available, trying ss..."
if [ $? -ne 0 ]; then
    sudo ss -tulpn 2>/dev/null | grep -E ':80|:443|:5000|:7474|:7687' | grep LISTEN || echo "No ports found"
fi
echo ""

echo "8. Recent Application Logs"
echo "══════════════════════════"
sudo docker compose logs app --tail=15 2>&1 | tail -15
echo ""

echo "9. Recent Nginx Logs"
echo "════════════════════"
sudo docker compose logs nginx --tail=10 2>&1 | tail -10
echo ""

echo "10. Resource Usage"
echo "══════════════════"
sudo docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null || echo "Could not get stats"
echo ""

echo "11. Disk Usage"
echo "══════════════"
echo "Docker system:"
sudo docker system df 2>/dev/null || echo "Could not get disk usage"
echo ""
echo "Volumes:"
sudo docker volume ls --format "table {{.Name}}\t{{.Driver}}" | grep nashik || echo "No volumes found"
echo ""

echo "========================================"
echo "  Summary"
echo "========================================"
echo ""

# Overall health determination
OVERALL_HEALTHY=true

# Check containers
if [ "$RUNNING" -lt 4 ]; then
    echo -e "${RED}✗ Not all containers are running ($RUNNING/4)${NC}"
    OVERALL_HEALTHY=false
else
    echo -e "${GREEN}✓ All containers are running (4/4)${NC}"
fi

# Check health endpoint
if echo "$RESPONSE" | grep -q '"status".*:.*"healthy"'; then
    echo -e "${GREEN}✓ Application reports healthy status${NC}"
elif echo "$RESPONSE" | grep -q '"status".*:.*"degraded"'; then
    echo -e "${YELLOW}⚠ Application reports degraded status${NC}"
    OVERALL_HEALTHY=false
else
    echo -e "${RED}✗ Cannot determine application health${NC}"
    OVERALL_HEALTHY=false
fi

# Check PostgreSQL
if echo "$PG_STATUS" | grep -q "accepting connections"; then
    echo -e "${GREEN}✓ PostgreSQL is accepting connections${NC}"
else
    echo -e "${RED}✗ PostgreSQL is not accessible${NC}"
    OVERALL_HEALTHY=false
fi

# Check Neo4j
if echo "$NEO4J_STATUS" | grep -q "test"; then
    echo -e "${GREEN}✓ Neo4j is responding to queries${NC}"
else
    echo -e "${RED}✗ Neo4j is not accessible${NC}"
    OVERALL_HEALTHY=false
fi

echo ""
if [ "$OVERALL_HEALTHY" = true ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}   ✓ ALL SYSTEMS OPERATIONAL ✓${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}   ✗ ISSUES DETECTED ✗${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Run 'sudo docker compose logs' to see detailed logs"
    exit 1
fi
