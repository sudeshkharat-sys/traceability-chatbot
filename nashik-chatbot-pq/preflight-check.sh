#!/bin/bash
# ============================================================================
# Pre-flight check before starting embedding creation
# Run this to verify system is ready
# ============================================================================

echo "🚀 PRE-FLIGHT CHECK - Embedding Creation"
echo "========================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check counter
CHECKS_PASSED=0
CHECKS_FAILED=0

# Function to check
check() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}❌ $2${NC}"
        ((CHECKS_FAILED++))
    fi
}

# 1. Check if containers are running
echo "📦 Container Status:"
docker ps --filter "name=traceability-" --format "table {{.Names}}\t{{.Status}}" | grep -q "Up"
check $? "All containers running"
echo ""

# 2. Check VM memory
echo "💾 Memory Check:"
TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
AVAILABLE_MEM=$(free -g | awk '/^Mem:/{print $7}')

echo "  Total RAM: ${TOTAL_MEM}GB"
echo "  Available: ${AVAILABLE_MEM}GB"

if [ "$AVAILABLE_MEM" -gt 20 ]; then
    echo -e "${GREEN}✅ Sufficient memory available (>20GB)${NC}"
    ((CHECKS_PASSED++))
elif [ "$AVAILABLE_MEM" -gt 15 ]; then
    echo -e "${YELLOW}⚠️  Memory is lower than ideal (15-20GB available)${NC}"
    echo "  Consider stopping other services or reducing batch size"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}❌ Low memory (<15GB available) - May cause OOM!${NC}"
    echo "  Recommendation: Free up memory or reduce BATCH_SIZE to 5"
    ((CHECKS_FAILED++))
fi
echo ""

# 3. Check CPU load
echo "🖥️  CPU Load:"
LOAD=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
echo "  Current load average: $LOAD"

if (( $(echo "$LOAD < 2.0" | bc -l) )); then
    echo -e "${GREEN}✅ CPU load is low${NC}"
    ((CHECKS_PASSED++))
elif (( $(echo "$LOAD < 4.0" | bc -l) )); then
    echo -e "${YELLOW}⚠️  CPU load is moderate${NC}"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}❌ CPU load is high - wait before starting${NC}"
    ((CHECKS_FAILED++))
fi
echo ""

# 4. Check disk space
echo "💿 Disk Space:"
DISK_AVAIL=$(df -h /var/lib/docker | awk 'NR==2 {print $4}')
DISK_PCT=$(df -h /var/lib/docker | awk 'NR==2 {print $5}' | sed 's/%//')

echo "  Available: $DISK_AVAIL"
echo "  Usage: ${DISK_PCT}%"

if [ "$DISK_PCT" -lt 70 ]; then
    echo -e "${GREEN}✅ Disk space OK (<70% used)${NC}"
    ((CHECKS_PASSED++))
elif [ "$DISK_PCT" -lt 85 ]; then
    echo -e "${YELLOW}⚠️  Disk space getting full (70-85%)${NC}"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}❌ Disk space critical (>85%) - cleanup needed${NC}"
    ((CHECKS_FAILED++))
fi
echo ""

# 5. Check Docker volumes
echo "📁 Docker Volumes:"
docker volume ls | grep -q opensearch_data
check $? "OpenSearch volume exists"

docker volume ls | grep -q neo4j_data
check $? "Neo4j volume exists"

docker volume ls | grep -q postgres_data
check $? "Postgres volume exists"
echo ""

# 6. Check environment variables
echo "⚙️  Environment Configuration:"
docker exec traceability-app bash -c 'echo $BATCH_SIZE' &>/dev/null
check $? "Environment variables loaded"

BATCH_SIZE=$(docker exec traceability-app bash -c 'echo ${BATCH_SIZE:-10}')
echo "  BATCH_SIZE: $BATCH_SIZE"

THREADS=$(docker exec traceability-app bash -c 'echo ${DOCLING_NUM_THREADS:-8}')
echo "  DOCLING_NUM_THREADS: $THREADS"
echo ""

# 7. Check OpenSearch health
echo "🔍 OpenSearch Health:"
OS_STATUS=$(curl -s http://localhost:9200/_cluster/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
if [ "$OS_STATUS" = "green" ] || [ "$OS_STATUS" = "yellow" ]; then
    echo -e "${GREEN}✅ OpenSearch is healthy (status: $OS_STATUS)${NC}"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}❌ OpenSearch is not healthy (status: $OS_STATUS)${NC}"
    ((CHECKS_FAILED++))
fi
echo ""

# 8. Check Neo4j health
echo "📊 Neo4j Health:"
NEO4J_STATUS=$(curl -s http://localhost:7474 | grep -q "neo4j" && echo "UP" || echo "DOWN")
if [ "$NEO4J_STATUS" = "UP" ]; then
    echo -e "${GREEN}✅ Neo4j is responding${NC}"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}❌ Neo4j is not responding${NC}"
    ((CHECKS_FAILED++))
fi
echo ""

# 9. Check for existing OOM errors
echo "🔎 Recent OOM Check:"
OOM_COUNT=$(docker logs --since 1h traceability-app 2>&1 | grep -i "oom\|killed" | wc -l)
if [ "$OOM_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ No recent OOM errors${NC}"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}❌ Found $OOM_COUNT OOM errors in last hour${NC}"
    echo "  Run: docker logs traceability-app 2>&1 | grep -i oom"
    ((CHECKS_FAILED++))
fi
echo ""

# Summary
echo "========================================"
echo "📋 SUMMARY:"
echo -e "  ${GREEN}Passed: $CHECKS_PASSED${NC}"
echo -e "  ${RED}Failed: $CHECKS_FAILED${NC}"
echo ""

if [ "$CHECKS_FAILED" -eq 0 ]; then
    echo -e "${GREEN}🎉 All checks passed! System is ready for embedding creation.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start monitoring: ./monitoring-during-embeddings.sh"
    echo "  2. In another terminal, start embeddings: docker exec -it traceability-app invoke create-embeddings"
    echo ""
    exit 0
elif [ "$CHECKS_FAILED" -lt 3 ]; then
    echo -e "${YELLOW}⚠️  Some checks failed but you can proceed with caution.${NC}"
    echo "  Review the warnings above and consider reducing BATCH_SIZE"
    echo ""
    exit 1
else
    echo -e "${RED}❌ Critical issues detected! Fix these before proceeding.${NC}"
    echo ""
    exit 2
fi
