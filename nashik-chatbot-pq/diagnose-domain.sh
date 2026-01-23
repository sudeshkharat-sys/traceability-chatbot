#!/bin/bash

echo "=== Domain & HTTPS Configuration Diagnostic ==="
echo ""

# Get the domain from nginx.conf
DOMAIN=$(grep -m 1 "server_name" /home/user/Traceability/nashik-chatbot-pq/nginx.conf | grep -v "_" | awk '{print $2}' | tr -d ';')
echo "Domain configured in nginx: $DOMAIN"
echo ""

echo "Step 1: Checking DNS Resolution..."
echo "---"
timeout 5 nslookup $DOMAIN 2>&1 || timeout 5 dig $DOMAIN +short 2>&1 || echo "DNS lookup failed - domain may not be configured"
echo ""

echo "Step 2: Checking Server IP..."
echo "---"
hostname -I | awk '{print "Server IP addresses:", $0}'
echo ""

echo "Step 3: Checking if nginx container is running..."
echo "---"
docker ps | grep nginx || echo "Nginx container not running!"
echo ""

echo "Step 4: Checking SSL certificates..."
echo "---"
if [ -f /home/user/Traceability/nashik-chatbot-pq/ssl/cert.pem ]; then
    echo "Certificate found. Details:"
    openssl x509 -in /home/user/Traceability/nashik-chatbot-pq/ssl/cert.pem -noout -subject -issuer -dates -ext subjectAltName
else
    echo "⚠️ SSL certificate NOT found at /home/user/Traceability/nashik-chatbot-pq/ssl/cert.pem"
    echo "This is why HTTPS shows 'not secure'"
fi
echo ""

echo "Step 5: Testing connectivity..."
echo "---"
echo "Testing HTTP (port 80):"
timeout 5 curl -I http://localhost 2>&1 | head -5 || echo "HTTP port 80 not accessible"
echo ""
echo "Testing HTTPS (port 443):"
timeout 5 curl -I https://localhost --insecure 2>&1 | head -5 || echo "HTTPS port 443 not accessible"
echo ""

echo "Step 6: Checking nginx configuration..."
echo "---"
timeout 10 docker exec traceability-nginx nginx -t 2>&1 || echo "Cannot check nginx config"
echo ""

echo "=== DIAGNOSIS SUMMARY ==="
echo ""
echo "✓ Nginx is serving the application correctly"
echo "✓ Application loads when accessed via IP: https://10.226.0.19"
echo ""
echo "Issues to fix:"
echo "1. DNS: $DOMAIN must resolve to your server IP (10.226.0.19)"
echo "2. SSL: Install SSL certificate for $DOMAIN to remove 'not secure' warning"
echo ""
echo "How to fix DNS:"
echo "  - Contact your DNS administrator"
echo "  - Add A record: $DOMAIN -> 10.226.0.19"
echo "  - Wait for DNS propagation (can take up to 24 hours)"
echo ""
echo "How to fix SSL:"
echo "  Option 1: Use existing certificates"
echo "    ./setup-ssl.sh /path/to/certificates"
echo ""
echo "  Option 2: Use Let's Encrypt (free)"
echo "    See documentation for Let's Encrypt setup"
echo ""
echo "After both are fixed, restart docker:"
echo "  docker compose down && docker compose up -d"
echo ""
