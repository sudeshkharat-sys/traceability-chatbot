#!/bin/bash

#==============================================================================

# Nginx Setup Script for SupportEaze

# This script sets up Nginx as a reverse proxy with SSL support

#==============================================================================

set -e  # Exit on error

# Color codes for output

RED='\033[0;31m'

GREEN='\033[0;32m'

YELLOW='\033[1;33m'

BLUE='\033[0;34m'

NC='\033[0m' # No Color

# Function to print colored messages

print_message() {

    echo -e "${2}${1}${NC}"

}

print_header() {

    echo ""

    print_message "========================================" "$BLUE"

    print_message "$1" "$BLUE"

    print_message "========================================" "$BLUE"

    echo ""

}

print_error() {

    print_message "ERROR: $1" "$RED"

}

print_success() {

    print_message "✓ $1" "$GREEN"

}

print_warning() {

    print_message "⚠ $1" "$YELLOW"

}

# Check if running as root

if [ "$EUID" -eq 0 ]; then

    print_error "Please do not run this script as root"

    exit 1

fi

print_header "SupportEaze Nginx Setup Script"

# Get configuration from user

print_message "Please provide the following information:" "$BLUE"

echo ""

read -p "Enter your domain name (e.g., supporteaze.com): " DOMAIN_NAME

if [ -z "$DOMAIN_NAME" ]; then

    print_error "Domain name is required"

    exit 1

fi

read -p "Enter application directory path [/var/www/supporteaze]: " APP_DIR

APP_DIR=${APP_DIR:-/var/www/supporteaze}

read -p "Enter backend port [5000]: " BACKEND_PORT

BACKEND_PORT=${BACKEND_PORT:-5000}

echo ""

print_message "SSL Certificate Setup:" "$BLUE"

echo "1) Let's Encrypt (free, auto-renewal)"

echo "2) Corporate/Custom certificates (manual)"

read -p "Choose SSL option (1 or 2): " SSL_OPTION

if [ "$SSL_OPTION" != "1" ] && [ "$SSL_OPTION" != "2" ]; then

    print_error "Invalid option"

    exit 1

fi

if [ "$SSL_OPTION" = "1" ]; then

    read -p "Enter your email for Let's Encrypt: " EMAIL

    if [ -z "$EMAIL" ]; then

        print_error "Email is required for Let's Encrypt"

        exit 1

    fi

fi

print_header "Configuration Summary"

echo "Domain Name: $DOMAIN_NAME"

echo "App Directory: $APP_DIR"

echo "Backend Port: $BACKEND_PORT"

echo "SSL Option: $([ "$SSL_OPTION" = "1" ] && echo "Let's Encrypt" || echo "Corporate/Custom")"

echo ""

read -p "Continue with this configuration? (y/n): " CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then

    print_warning "Setup cancelled"

    exit 0

fi

# Install Nginx

print_header "Installing Nginx"

if ! command -v nginx &> /dev/null; then

    sudo apt update

    sudo apt install -y nginx

    print_success "Nginx installed"

else

    print_success "Nginx already installed"

fi

# Setup SSL certificates

print_header "Setting up SSL Certificates"

if [ "$SSL_OPTION" = "1" ]; then

    # Let's Encrypt

    if ! command -v certbot &> /dev/null; then

        print_message "Installing Certbot..." "$YELLOW"

        sudo apt install -y certbot

    fi

    # Stop nginx temporarily

    sudo systemctl stop nginx 2>/dev/null || true

    print_message "Generating Let's Encrypt certificates..." "$YELLOW"

    sudo certbot certonly --standalone \

        -d $DOMAIN_NAME \

        -d www.$DOMAIN_NAME \

        --agree-tos \

        --email $EMAIL \

        --non-interactive \

        --keep-until-expiring

    # Create symbolic links

    sudo mkdir -p /etc/nginx/ssl

    sudo ln -sf /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem /etc/nginx/ssl/fullchain.pem

    sudo ln -sf /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem /etc/nginx/ssl/server.key

    sudo ln -sf /etc/letsencrypt/live/$DOMAIN_NAME/chain.pem /etc/nginx/ssl/ca-chain.crt

    # Setup auto-renewal

    print_message "Setting up auto-renewal..." "$YELLOW"

    sudo tee /etc/cron.d/certbot-renew > /dev/null << EOF

0 0,12 * * * root certbot renew --quiet --post-hook "systemctl reload nginx"

EOF

    print_success "Let's Encrypt certificates installed"

else

    # Corporate/Custom certificates

    print_message "Please provide the paths to your certificate files:" "$YELLOW"

    echo ""

    read -p "Full path to certificate file (.crt or .pem): " CERT_FILE

    read -p "Full path to private key file (.key): " KEY_FILE

    read -p "Full path to CA chain file (optional, press Enter to skip): " CHAIN_FILE

    if [ ! -f "$CERT_FILE" ]; then

        print_error "Certificate file not found: $CERT_FILE"

        exit 1

    fi

    if [ ! -f "$KEY_FILE" ]; then

        print_error "Private key file not found: $KEY_FILE"

        exit 1

    fi

    sudo mkdir -p /etc/nginx/ssl /etc/ssl/certs /etc/ssl/private

    # Copy and combine certificates

    if [ -n "$CHAIN_FILE" ] && [ -f "$CHAIN_FILE" ]; then

        print_message "Creating full certificate chain..." "$YELLOW"

        cat "$CERT_FILE" "$CHAIN_FILE" | sudo tee /etc/nginx/ssl/fullchain.pem > /dev/null

        sudo cp "$CHAIN_FILE" /etc/nginx/ssl/ca-chain.crt

    else

        sudo cp "$CERT_FILE" /etc/nginx/ssl/fullchain.pem

        echo "" | sudo tee /etc/nginx/ssl/ca-chain.crt > /dev/null

    fi

    sudo cp "$KEY_FILE" /etc/nginx/ssl/server.key

    # Set permissions

    sudo chmod 600 /etc/nginx/ssl/server.key

    sudo chmod 644 /etc/nginx/ssl/fullchain.pem

    sudo chmod 644 /etc/nginx/ssl/ca-chain.crt

    print_success "Custom certificates installed"

fi

# Verify certificates

print_message "Verifying SSL certificates..." "$YELLOW"

if sudo openssl x509 -in /etc/nginx/ssl/fullchain.pem -text -noout > /dev/null 2>&1; then

    print_success "SSL certificates verified"

else

    print_error "SSL certificate verification failed"

    exit 1

fi

# Create Nginx configuration

print_header "Creating Nginx Configuration"

NGINX_CONFIG="/etc/nginx/sites-available/$DOMAIN_NAME"

sudo tee $NGINX_CONFIG > /dev/null << EOF

# SupportEaze Nginx Configuration

# Domain: $DOMAIN_NAME

# Generated: $(date)

# Rate limiting zones

limit_req_zone \$binary_remote_addr zone=api_limit:10m rate=10r/s;

limit_req_zone \$binary_remote_addr zone=general_limit:10m rate=50r/s;

# Upstream definition for FastAPI backend

upstream fastapi_backend {

    server 127.0.0.1:$BACKEND_PORT max_fails=3 fail_timeout=30s;

    keepalive 32;

}

# HTTP to HTTPS Redirect

server {

    listen 80;

    listen [::]:80;

    server_name $DOMAIN_NAME www.$DOMAIN_NAME;

    location / {

        return 301 https://\$server_name\$request_uri;

    }

}

# Main HTTPS Server

server {

    listen 443 ssl http2;

    listen [::]:443 ssl http2;

    server_name $DOMAIN_NAME www.$DOMAIN_NAME;

    # SSL Certificate Configuration

    ssl_certificate /etc/nginx/ssl/fullchain.pem;

    ssl_certificate_key /etc/nginx/ssl/server.key;

    # SSL Security Settings

    ssl_protocols TLSv1.2 TLSv1.3;

    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;

    ssl_prefer_server_ciphers off;

    ssl_session_cache shared:SSL:10m;

    ssl_session_timeout 10m;

    ssl_session_tickets off;

    # OCSP Stapling (comment out if using corporate certificates)

    # ssl_stapling on;

    # ssl_stapling_verify on;

    ssl_trusted_certificate /etc/nginx/ssl/ca-chain.crt;

    resolver 8.8.8.8 8.8.4.4 valid=300s;

    resolver_timeout 5s;

    # Security Headers

    add_header X-Frame-Options "SAMEORIGIN" always;

    add_header X-XSS-Protection "1; mode=block" always;

    add_header X-Content-Type-Options "nosniff" always;

    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline' 'unsafe-eval'" always;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # Compression

    gzip on;

    gzip_vary on;

    gzip_min_length 1024;

    gzip_proxied any;

    gzip_comp_level 6;

    gzip_types

        text/plain

        text/css

        text/xml

        text/javascript

        application/json

        application/javascript

        application/xml+rss

        application/atom+xml

        image/svg+xml;

    # Client Settings

    client_max_body_size 50M;

    client_body_timeout 60s;

    client_header_timeout 60s;

    # Proxy Settings

    proxy_connect_timeout 60s;

    proxy_send_timeout 60s;

    proxy_read_timeout 60s;

    proxy_buffering off;

    # Static Files (React Build)

    location /static/ {

        alias $APP_DIR/chatbot-interface/build/static/;

        expires 1y;

        add_header Cache-Control "public, immutable";

        try_files \$uri \$uri/ =404;

        gzip_static on;

    }

    # PDF.js Worker File

    location = /pdf.worker.min.js {

        alias $APP_DIR/chatbot-interface/build/pdf.worker.min.js;

        expires 1y;

        add_header Cache-Control "public, immutable";

        add_header Content-Type "application/javascript";

    }

    # Document Directory

    location /documents/ {

        alias /var/www/pdf_docs/;

        autoindex on;

        autoindex_exact_size off;

        autoindex_localtime on;

        # PDF files - display inline in browser

        location ~* \.(pdf)\$ {

            add_header Content-Type application/pdf;

            add_header Content-Disposition "inline";

        }

        # Images

        location ~* \.(png|jpg|jpeg|gif|svg)\$ {

            expires 1M;

            add_header Cache-Control "public";

        }

        # Office documents - force download

        location ~* \.(doc|docx|xls|xlsx|ppt|pptx)\$ {

            add_header Content-Disposition "attachment";

        }

        gzip on;

        gzip_types application/pdf image/png image/jpeg;

    }

    # Backward compatibility for /pdfs/

    location /pdfs/ {

        alias /var/www/pdf_docs/;

        location ~* \.(pdf)\$ {

            add_header Content-Type application/pdf;

            add_header Content-Disposition "inline";

        }

        gzip on;

        gzip_types application/pdf;

    }

    # API Routes with Rate Limiting

    location /api/ {

        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://fastapi_backend;

        proxy_http_version 1.1;

        # WebSocket support

        proxy_set_header Upgrade \$http_upgrade;

        proxy_set_header Connection 'upgrade';

        # Standard proxy headers

        proxy_set_header Host \$host;

        proxy_set_header X-Real-IP \$remote_addr;

        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_set_header X-Forwarded-Host \$server_name;

        proxy_cache_bypass \$http_upgrade;

        proxy_buffering off;

    }

    # API Documentation

    location = /docs {

        limit_req zone=general_limit burst=10 nodelay;

        proxy_pass http://fastapi_backend/docs;

        proxy_set_header Host \$host;

        proxy_set_header X-Real-IP \$remote_addr;

        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

        proxy_set_header X-Forwarded-Proto \$scheme;

    }

    # OpenAPI JSON

    location /openapi.json {

        limit_req zone=general_limit burst=5 nodelay;

        proxy_pass http://fastapi_backend/openapi.json;

        proxy_set_header Host \$host;

        proxy_set_header X-Real-IP \$remote_addr;

        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

        proxy_set_header X-Forwarded-Proto \$scheme;

    }

    # Health Check Endpoint

    location /health {

        proxy_pass http://fastapi_backend/health;

        proxy_set_header Host \$host;

        proxy_set_header X-Real-IP \$remote_addr;

        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

        proxy_set_header X-Forwarded-Proto \$scheme;

        access_log off;

    }

    # Frontend React App (Catch-all for React Router)

    location / {

        limit_req zone=general_limit burst=30 nodelay;

        root $APP_DIR/chatbot-interface/build;

        index index.html;

        try_files \$uri \$uri/ /index.html;

    }

    # Security: Block Access to Sensitive Files

    location ~ /\.(ht|git|svn|env) {

        deny all;

        access_log off;

        log_not_found off;

    }

    # Block access to backup files

    location ~ \.(bak|backup|old|orig|save|swp|tmp)\$ {

        deny all;

        access_log off;

        log_not_found off;

    }

    # Custom Error Pages

    error_page 404 /404.html;

    error_page 500 502 503 504 /50x.html;

    location = /50x.html {

        root $APP_DIR/chatbot-interface/build;

    }

}

EOF

print_success "Nginx configuration created: $NGINX_CONFIG"

# Enable site

print_message "Enabling site..." "$YELLOW"

sudo ln -sf $NGINX_CONFIG /etc/nginx/sites-enabled/

sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration

print_message "Testing Nginx configuration..." "$YELLOW"

if sudo nginx -t; then

    print_success "Nginx configuration test passed"

else

    print_error "Nginx configuration test failed"

    exit 1

fi

# Restart Nginx

print_message "Restarting Nginx..." "$YELLOW"

sudo systemctl restart nginx

sudo systemctl enable nginx

print_success "Nginx started and enabled"

print_header "Setup Complete!"

print_success "Nginx is now configured for $DOMAIN_NAME"

echo ""

print_message "Next Steps:" "$BLUE"

echo "1. Ensure your DNS A record points to this server's IP"

echo "2. Build your frontend: cd $APP_DIR/chatbot-interface && npm run build"

echo "3. Start your backend: cd $APP_DIR/ai_chat_bot && python main.py"

echo "4. Access your application at: https://$DOMAIN_NAME"

echo ""

print_message "Useful Commands:" "$BLUE"

echo "  Check Nginx status:  sudo systemctl status nginx"

echo "  View Nginx logs:     sudo tail -f /var/log/nginx/error.log"

echo "  Test config:         sudo nginx -t"

echo "  Reload config:       sudo systemctl reload nginx"

echo ""

if [ "$SSL_OPTION" = "1" ]; then

    print_message "SSL Auto-Renewal:" "$BLUE"

    echo "  Your Let's Encrypt certificates will auto-renew via cron"

    echo "  Test renewal:        sudo certbot renew --dry-run"

fi
 