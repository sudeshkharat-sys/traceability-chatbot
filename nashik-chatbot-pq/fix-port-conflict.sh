#!/bin/bash

echo "=== Port 80 and 443 Conflict Resolution ==="
echo ""

echo "Step 1: Checking what's using port 80..."
echo "---"
sudo lsof -i :80 || sudo netstat -tulpn | grep :80 || sudo ss -tulpn | grep :80
echo ""

echo "Step 2: Checking what's using port 443..."
echo "---"
sudo lsof -i :443 || sudo netstat -tulpn | grep :443 || sudo ss -tulpn | grep :443
echo ""

echo "Step 3: Checking if Apache is running..."
echo "---"
sudo systemctl status apache2 2>/dev/null || sudo systemctl status httpd 2>/dev/null || echo "Apache not found or not running"
echo ""

echo "Step 4: Checking if other nginx is running..."
echo "---"
sudo systemctl status nginx 2>/dev/null || echo "System nginx not found or not running"
echo ""

echo "=== Common Solutions ==="
echo ""
echo "If Apache is running:"
echo "  sudo systemctl stop apache2    # or httpd"
echo "  sudo systemctl disable apache2"
echo ""
echo "If system nginx is running:"
echo "  sudo systemctl stop nginx"
echo "  sudo systemctl disable nginx"
echo ""
echo "If unknown process is using the port, kill it:"
echo "  sudo kill -9 <PID>  # Replace <PID> with the process ID shown above"
echo ""
echo "After stopping the conflicting service, restart Docker:"
echo "  cd /home/maiuser/nashik-chatbot-pq"
echo "  sudo docker compose down"
echo "  sudo docker compose up -d"
echo ""
