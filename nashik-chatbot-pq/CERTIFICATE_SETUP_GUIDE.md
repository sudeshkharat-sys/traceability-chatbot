# SSL Certificate Setup Guide for m-devsecops.com

## Current Situation

You have SSL certificates for `m-devsecops.com` that need to be configured for Docker Nginx to enable HTTPS on port 443.

## Certificate Files You Have

Based on your description, you have:
- `m-devsecops.com.cer` or `m-devsecops.cer` - SSL certificate
- `m-devsecops.com.key` or `m-devsecops.key` - Private key
- `m-devsecops.com.pfx` or `m-devsecops.pfx` - PKCS#12 bundle (contains both cert and key)
- `CloudflareCA.cer` - Cloudflare CA certificate (for certificate chain)

## Option 1: Automatic Setup (Recommended)

Use the provided setup script:

```bash
cd ~/Traceability/nashik-chatbot-pq

# If certificates are in /home/maiuser/certificate/
sudo ./setup-ssl.sh /home/maiuser/certificate

# Or if certificates are in a different location
sudo ./setup-ssl.sh /path/to/certificate/directory
```

The script will:
1. Detect certificate files automatically
2. Convert from DER to PEM format if needed
3. Extract certificate and key from PFX if needed
4. Combine with CA certificate for full chain
5. Set proper permissions
6. Verify certificate and key match

Then restart Docker:
```bash
sudo docker compose down
sudo docker compose up -d
```

## Option 2: Manual Setup (If you know exact file locations)

### Step 1: Create SSL Directory

```bash
cd ~/Traceability/nashik-chatbot-pq
mkdir -p ssl
chmod 700 ssl
```

### Step 2a: If Using PFX File (Easiest)

```bash
# Extract certificate from PFX
sudo openssl pkcs12 -in /home/maiuser/certificate/m-devsecops.pfx \
  -clcerts -nokeys -out ssl/cert.pem

# Extract private key from PFX
sudo openssl pkcs12 -in /home/maiuser/certificate/m-devsecops.pfx \
  -nocerts -nodes -out ssl/key.pem

# If password protected, you'll be prompted
```

### Step 2b: If Using Separate .cer and .key Files

```bash
# Copy and convert certificate (if needed)
# First, try as PEM
sudo cp /home/maiuser/certificate/m-devsecops.cer ssl/cert.pem

# If that doesn't work, convert from DER to PEM
sudo openssl x509 -inform DER \
  -in /home/maiuser/certificate/m-devsecops.cer \
  -out ssl/cert.pem

# Copy private key
sudo cp /home/maiuser/certificate/m-devsecops.key ssl/key.pem
```

### Step 3: Add CA Certificate to Chain

```bash
# Add Cloudflare CA to certificate chain
# First check if it's PEM format
sudo cat /home/maiuser/certificate/CloudflareCA.cer >> ssl/cert.pem

# If DER format, convert first
sudo openssl x509 -inform DER \
  -in /home/maiuser/certificate/CloudflareCA.cer >> ssl/cert.pem
```

### Step 4: Set Permissions

```bash
sudo chmod 600 ssl/key.pem    # Private key - owner only
sudo chmod 644 ssl/cert.pem   # Certificate - readable by all
sudo chown $USER:$USER ssl/*.pem
```

### Step 5: Verify Certificate

```bash
# View certificate details
openssl x509 -in ssl/cert.pem -noout -text

# Check certificate dates
openssl x509 -in ssl/cert.pem -noout -dates

# Verify certificate and key match
openssl x509 -noout -modulus -in ssl/cert.pem | openssl md5
openssl rsa -noout -modulus -in ssl/key.pem | openssl md5
# The two MD5 hashes should be identical
```

### Step 6: Restart Docker

```bash
sudo docker compose down
sudo docker compose up -d
```

## Option 3: If Certificates Are Not Accessible

If the certificates are on a different machine or need to be transferred:

### Transfer from Windows to Linux VM

**Using SCP:**
```bash
# From Windows (in PowerShell)
scp C:\path\to\certificate\* user@your-vm-ip:/home/user/temp-certs/

# Then on Linux VM
sudo ./setup-ssl.sh /home/user/temp-certs
```

**Using WinSCP:**
1. Connect to your VM using WinSCP
2. Upload certificate files to `/home/user/Traceability/nashik-chatbot-pq/ssl/`
3. Follow manual setup steps above

### Transfer from Local Machine to VM

```bash
# From your local machine
scp /path/to/certificates/* user@vm-ip:/home/user/Traceability/nashik-chatbot-pq/ssl/
```

## Testing HTTPS

### Test 1: Local Test (Self-Signed Warning Expected)

```bash
# Test HTTPS connection
curl https://localhost --insecure

# Test specific port
curl https://localhost:443 --insecure

# View SSL certificate details
echo | openssl s_client -connect localhost:443 -showcerts
```

### Test 2: Check Nginx Logs

```bash
# View nginx logs for errors
sudo docker compose logs nginx

# Common errors to look for:
# - "cannot load certificate" - File path or permission issue
# - "SSL certificate verify failed" - Certificate chain issue
# - "no such file or directory" - Certificate not mounted correctly
```

### Test 3: Browser Test

1. Open browser
2. Navigate to `https://your-vm-ip` or `https://your-domain.com`
3. You should see your app (might show certificate warning if using IP)
4. Click padlock icon to view certificate details

### Test 4: Through Load Balancer

```bash
# Test through your load balancer
curl https://your-load-balancer-url

# Should return your app content with valid SSL
```

## Troubleshooting

### Error: "Could not read certificate"

**Cause:** Certificate might be in DER format instead of PEM

**Solution:**
```bash
# Check format
file ssl/cert.pem

# If it says "data", it's DER format - convert it
openssl x509 -inform DER -in ssl/cert.pem -out ssl/cert-converted.pem
mv ssl/cert-converted.pem ssl/cert.pem
```

### Error: "Permission denied"

**Cause:** Docker container can't read certificate files

**Solution:**
```bash
sudo chown $USER:$USER ssl/*.pem
chmod 644 ssl/cert.pem
chmod 600 ssl/key.pem
```

### Error: "Certificate and private key do not match"

**Cause:** Wrong key file for the certificate

**Solution:**
- Ensure you're using the correct key file
- If using PFX, extract both from the same file
- Verify match: `openssl x509 -noout -modulus -in ssl/cert.pem | openssl md5`

### Error: "SSL certificate problem: unable to get local issuer certificate"

**Cause:** Certificate chain incomplete

**Solution:**
```bash
# Combine certificate with CA certificate
cat ssl/cert.pem /home/maiuser/certificate/CloudflareCA.cer > ssl/fullchain.pem
mv ssl/fullchain.pem ssl/cert.pem
```

### Nginx Container Won't Start

```bash
# Check nginx configuration
sudo docker compose config

# Test nginx syntax
sudo docker compose exec nginx nginx -t

# View detailed logs
sudo docker compose logs nginx --tail=100
```

## Verification Checklist

- [ ] SSL directory created: `ls -la ssl/`
- [ ] Certificate file exists: `ls -la ssl/cert.pem`
- [ ] Private key exists: `ls -la ssl/key.pem`
- [ ] Permissions correct: `ls -la ssl/`
  - cert.pem: `-rw-r--r--` (644)
  - key.pem: `-rw-------` (600)
- [ ] Certificate is valid PEM: `openssl x509 -in ssl/cert.pem -noout -text`
- [ ] Certificate and key match (same MD5 hash)
- [ ] Certificate not expired: `openssl x509 -in ssl/cert.pem -noout -dates`
- [ ] Docker containers running: `sudo docker compose ps`
- [ ] Port 443 listening: `sudo netstat -tulpn | grep 443`
- [ ] HTTPS responds: `curl https://localhost --insecure`
- [ ] Nginx logs clean: `sudo docker compose logs nginx | grep -i error`

## Current Configuration

Your nginx.conf is already configured with:
- HTTP server on port 80
- HTTPS server on port 443
- SSL certificate path: `/etc/nginx/ssl/cert.pem`
- SSL key path: `/etc/nginx/ssl/key.pem`

Your docker-compose.yml already:
- Exposes ports 80 and 443
- Mounts `./ssl` to `/etc/nginx/ssl` in the container

**You just need to provide the certificate files in the `ssl/` directory!**

## Quick Start Commands

```bash
# 1. Navigate to project
cd ~/Traceability/nashik-chatbot-pq

# 2. Run setup script (easiest way)
sudo ./setup-ssl.sh /home/maiuser/certificate

# 3. Restart Docker
sudo docker compose down && sudo docker compose up -d

# 4. Test HTTPS
curl https://localhost --insecure

# 5. Check logs
sudo docker compose logs nginx

# 6. Test through load balancer
curl https://your-load-balancer-url
```

## Load Balancer Configuration

Since you mentioned having a load balancer on port 443, you have two options:

### Option A: SSL Termination at Load Balancer Only (Simpler)

Load Balancer handles HTTPS, forwards HTTP to VM:
```
Internet (HTTPS:443) → Load Balancer (SSL) → VM (HTTP:80) → Docker
```

In this case:
- Configure SSL certificate on load balancer
- VM only needs port 80 (HTTP)
- Comment out HTTPS server block in nginx.conf
- No need for SSL certificates in Docker

### Option B: End-to-End SSL (More Secure)

Both load balancer and VM handle HTTPS:
```
Internet (HTTPS:443) → Load Balancer (SSL) → VM (HTTPS:443) → Docker (SSL)
```

In this case:
- Configure SSL on load balancer
- Configure SSL on Docker (follow this guide)
- Load balancer forwards HTTPS to HTTPS
- Double encryption (more secure, slight overhead)

**Current setup supports Option B (end-to-end SSL).**

If you want Option A instead, let me know and I'll update the nginx.conf.

## Summary

1. **Your certificates are ready** - just need to copy them to the `ssl/` directory
2. **Use the setup script** - it handles format conversion automatically
3. **Restart Docker** - containers will pick up the new certificates
4. **Test thoroughly** - use the verification checklist above

If you encounter any issues, check the troubleshooting section or share the error message!
