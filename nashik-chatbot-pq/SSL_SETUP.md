# SSL/HTTPS Setup Guide

## Overview

Your nginx configuration now supports both HTTP (port 80) and HTTPS (port 443) with SSL certificates.

## Architecture

```
Internet
    ↓
Load Balancer OR Direct Access
    ↓
Nginx Container
    ├── Port 80 (HTTP)
    └── Port 443 (HTTPS with SSL)
         ↓
    App Container (Port 5000)
```

## Quick Start

### Step 1: Create SSL Directory

```bash
cd ~/nashik-chatbot-pq
mkdir -p ssl
chmod 700 ssl
```

### Step 2: Add Your SSL Certificates

Place your SSL certificate files in the `ssl/` directory:

```bash
ssl/
├── cert.pem       # Your SSL certificate
└── key.pem        # Your private key
```

### Step 3: Set Proper Permissions

```bash
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem
```

### Step 4: Start Docker Services

```bash
sudo docker compose down
sudo docker compose up -d
```

### Step 5: Test HTTPS

```bash
# Test HTTPS
curl https://localhost --insecure

# Or from browser
https://your-domain.com
```

## Option 1: Using Let's Encrypt (Free SSL - Recommended)

### Manual Certificate Generation

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot

# Generate certificate (HTTP-01 challenge)
# Requires port 80 to be accessible from internet
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# Certificates will be in:
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem

# Copy to ssl directory
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ~/nashik-chatbot-pq/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ~/nashik-chatbot-pq/ssl/key.pem

# Fix permissions
sudo chown $USER:$USER ~/nashik-chatbot-pq/ssl/*.pem
chmod 600 ~/nashik-chatbot-pq/ssl/key.pem
chmod 644 ~/nashik-chatbot-pq/ssl/cert.pem
```

### Auto-Renewal Setup

```bash
# Test renewal
sudo certbot renew --dry-run

# Create renewal script
cat > ~/renew-ssl.sh << 'EOF'
#!/bin/bash
certbot renew --quiet
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ~/nashik-chatbot-pq/ssl/cert.pem
cp /etc/letsencrypt/live/your-domain.com/privkey.pem ~/nashik-chatbot-pq/ssl/key.pem
docker compose -f ~/nashik-chatbot-pq/docker-compose.yml restart nginx
EOF

chmod +x ~/renew-ssl.sh

# Add to crontab (runs daily at 3am)
(crontab -l 2>/dev/null; echo "0 3 * * * /home/$USER/renew-ssl.sh") | crontab -
```

## Option 2: Using Self-Signed Certificate (Testing Only)

**Warning:** Self-signed certificates will show security warnings in browsers. Only use for testing!

```bash
cd ~/nashik-chatbot-pq
mkdir -p ssl

# Generate self-signed certificate (valid for 365 days)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem \
  -out ssl/cert.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=your-domain.com"

# Set permissions
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem
```

## Option 3: Using Existing SSL Certificate

If you already have SSL certificates from your provider:

```bash
cd ~/nashik-chatbot-pq
mkdir -p ssl

# Copy your certificate files
cp /path/to/your/certificate.crt ssl/cert.pem
cp /path/to/your/private.key ssl/key.pem

# If you have a certificate chain, combine them:
cat certificate.crt intermediate.crt root.crt > ssl/cert.pem

# Set permissions
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem
```

## Option 4: Load Balancer Handles SSL (Current Setup)

If your load balancer terminates SSL:
- Load balancer handles HTTPS (port 443)
- Load balancer forwards HTTP to VM (port 80)
- You **don't need SSL certificates** in Docker

**In this case:**
1. Load balancer configured with SSL certificate
2. Backend (VM) receives HTTP on port 80
3. No need to expose port 443 in docker-compose.yml

**Update docker-compose.yml:**
```yaml
nginx:
  ports:
    - "80:80"  # Only HTTP needed
  # Remove port 443
  # Remove SSL volume mount
```

## Configuration Files

### .gitignore Entry

Make sure SSL certificates are not committed to git:

```bash
echo "ssl/" >> .gitignore
echo "*.pem" >> .gitignore
```

### docker-compose.yml

Already configured:
```yaml
nginx:
  ports:
    - "80:80"    # HTTP
    - "443:443"  # HTTPS
  volumes:
    - ./ssl:/etc/nginx/ssl:ro  # SSL certificates
```

### nginx.conf

Already configured with two server blocks:
- **Port 80:** HTTP server
- **Port 443:** HTTPS server with SSL

## Testing

### Test HTTP (Port 80)

```bash
curl http://localhost
curl http://your-vm-ip
```

### Test HTTPS (Port 443)

```bash
# With valid certificate
curl https://localhost
curl https://your-domain.com

# With self-signed (bypass verification)
curl https://localhost --insecure
curl https://your-vm-ip --insecure
```

### Test SSL Certificate

```bash
# Check certificate details
openssl s_client -connect localhost:443 -showcerts

# Check certificate expiration
echo | openssl s_client -connect your-domain.com:443 2>/dev/null | openssl x509 -noout -dates
```

### Browser Test

1. Open browser
2. Navigate to `https://your-domain.com`
3. Check for padlock icon (valid SSL)
4. Click padlock to view certificate details

## Firewall Configuration

Open port 443 for HTTPS:

```bash
# Ubuntu UFW
sudo ufw allow 443/tcp
sudo ufw status

# CentOS/Firewalld
sudo firewall-cmd --add-port=443/tcp --permanent
sudo firewall-cmd --reload
```

## Troubleshooting

### Error: "certificate verify failed"

**Cause:** Self-signed certificate or certificate not trusted.

**Solutions:**
- Use Let's Encrypt for valid certificate
- Add `--insecure` flag for testing: `curl https://localhost --insecure`
- Import certificate to browser/system trust store

### Error: "SSL certificate problem: unable to get local issuer certificate"

**Cause:** Certificate chain incomplete.

**Fix:** Include full certificate chain:
```bash
cat your-cert.crt intermediate.crt root.crt > ssl/cert.pem
```

### Error: "nginx: [emerg] cannot load certificate"

**Causes:**
1. Certificate files not found
2. Incorrect file paths
3. Permission issues

**Fixes:**
```bash
# Check files exist
ls -la ssl/

# Verify permissions
chmod 644 ssl/cert.pem
chmod 600 ssl/key.pem

# Check nginx logs
sudo docker compose logs nginx
```

### Error: "Connection refused" on port 443

**Causes:**
1. Port 443 not exposed in docker-compose.yml
2. Firewall blocking port 443
3. Nginx not listening on 443

**Fixes:**
```bash
# Check if port is exposed
sudo docker compose ps

# Check if nginx is listening
sudo docker exec traceability-nginx netstat -tulpn | grep 443

# Check firewall
sudo ufw status | grep 443
```

### Browser Shows "Not Secure"

**For Self-Signed Certificates:**
- Expected behavior
- Click "Advanced" → "Proceed to site"
- Only use for testing!

**For Valid Certificates:**
- Check certificate is not expired
- Verify domain name matches certificate
- Ensure full certificate chain is included

## HTTP to HTTPS Redirect (Optional)

To force all traffic to HTTPS, uncomment this in `nginx.conf`:

```nginx
# HTTP Server Block (Port 80) - Redirect to HTTPS
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}
```

Then comment out the full HTTP server block that serves content.

Restart nginx:
```bash
sudo docker compose restart nginx
```

## Certificate Renewal

### Let's Encrypt Certificates (90 days validity)

```bash
# Manual renewal
sudo certbot renew

# Copy renewed certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ~/nashik-chatbot-pq/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ~/nashik-chatbot-pq/ssl/key.pem

# Restart nginx
sudo docker compose restart nginx
```

### Check Certificate Expiration

```bash
# Check expiration date
openssl x509 -in ssl/cert.pem -noout -enddate

# Or online
echo | openssl s_client -connect your-domain.com:443 2>/dev/null | openssl x509 -noout -dates
```

### Set Expiration Alert

```bash
# Create monitoring script
cat > ~/check-ssl-expiry.sh << 'EOF'
#!/bin/bash
CERT="/home/$USER/nashik-chatbot-pq/ssl/cert.pem"
DAYS_UNTIL_EXPIRY=$(( ($(date -d "$(openssl x509 -in $CERT -noout -enddate | cut -d= -f2)" +%s) - $(date +%s)) / 86400 ))

if [ $DAYS_UNTIL_EXPIRY -lt 30 ]; then
    echo "WARNING: SSL certificate expires in $DAYS_UNTIL_EXPIRY days!"
    # Add notification here (email, slack, etc.)
fi
EOF

chmod +x ~/check-ssl-expiry.sh

# Run weekly
(crontab -l 2>/dev/null; echo "0 9 * * 1 /home/$USER/check-ssl-expiry.sh") | crontab -
```

## Security Best Practices

### 1. Strong SSL Configuration

Already configured in `nginx.conf`:
```nginx
ssl_protocols TLSv1.2 TLSv1.3;  # Only modern protocols
ssl_ciphers HIGH:!aNULL:!MD5;   # Strong ciphers only
```

### 2. HSTS Header

Already configured:
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

This tells browsers to always use HTTPS for your site.

### 3. Protect Private Key

```bash
# Private key should be readable only by owner
chmod 600 ssl/key.pem

# Never commit to git
echo "ssl/" >> .gitignore
```

### 4. Regular Updates

```bash
# Check for security updates
sudo apt-get update
sudo apt-get upgrade

# Update Docker images
sudo docker compose pull
sudo docker compose up -d
```

## Different Deployment Scenarios

### Scenario 1: Direct SSL Termination (Docker Nginx)

```
Internet → Port 443 → Docker Nginx (SSL) → App
```

**Setup:**
- Use Let's Encrypt or commercial SSL certificate
- Expose ports 80 and 443 in docker-compose.yml
- Mount SSL certificates to nginx container

### Scenario 2: Load Balancer SSL Termination (Recommended)

```
Internet → LB:443 (SSL) → VM:80 (HTTP) → Docker Nginx → App
```

**Setup:**
- SSL certificate on load balancer
- Only expose port 80 in docker-compose.yml
- No SSL certificates needed in Docker
- Comment out HTTPS server block in nginx.conf

### Scenario 3: Both (Defense in Depth)

```
Internet → LB:443 (SSL) → VM:443 (SSL) → Docker Nginx → App
```

**Setup:**
- SSL on both load balancer and Docker
- Expose port 443 in docker-compose.yml
- Mount SSL certificates
- Double encryption (more secure, slight overhead)

## Summary

### Files Created/Modified

- ✅ `nginx.conf` - Two server blocks (80 and 443)
- ✅ `docker-compose.yml` - Exposes ports 80 and 443
- ✅ `ssl/` directory - Contains SSL certificates

### Access URLs

- HTTP: `http://your-domain.com` (port 80)
- HTTPS: `https://your-domain.com` (port 443)

### Next Steps

1. **Choose deployment scenario** (direct SSL, LB SSL, or both)
2. **Obtain SSL certificate** (Let's Encrypt recommended)
3. **Place certificates in `ssl/` directory**
4. **Restart Docker:** `sudo docker compose down && sudo docker compose up -d`
5. **Test HTTPS:** `curl https://your-domain.com`
6. **Set up auto-renewal** (for Let's Encrypt)

For most setups with a load balancer, **Scenario 2** is recommended (SSL termination at load balancer only).
