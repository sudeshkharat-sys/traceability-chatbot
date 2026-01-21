# Load Balancer Setup Guide

## Architecture

```
Internet (HTTPS)
       ↓
Load Balancer (Port 443)
       ↓
VM Public IP (Port 80)
       ↓
Docker Nginx (Port 80 → forwards to → Port 5000)
       ↓
FastAPI App (Port 5000)
       ↓
PostgreSQL (5432) & Neo4j (7687)
```

## Current Setup

Your load balancer forwards HTTPS traffic (port 443) to your VM's port 80.

## Configuration Steps

### Step 1: Free Port 80 on VM

Port 80 must be available for Docker Nginx to bind to.

```bash
# Check what's using port 80
sudo lsof -i :80

# Common services to stop:

# Apache2
sudo systemctl stop apache2
sudo systemctl disable apache2

# System Nginx (not Docker)
sudo systemctl stop nginx
sudo systemctl disable nginx

# Verify port 80 is free
sudo lsof -i :80
# Should return nothing
```

### Step 2: Update Docker Configuration

The `docker-compose.yml` is now configured for port 80:

```yaml
nginx:
  ports:
    - "80:80"  # VM port 80 → Container port 80
```

### Step 3: Update CORS Configuration

Edit your `.env` file to include your load balancer URL:

```bash
nano .env
```

Update CORS_ORIGINS to include your load balancer URL:

```env
CORS_ORIGINS=http://localhost,https://your-load-balancer-domain,http://your-vm-ip
```

**Example:**
```env
CORS_ORIGINS=http://localhost,https://app.example.com,http://10.20.30.40
```

### Step 4: Start Docker Services

```bash
cd ~/nashik-chatbot-pq

# Pull latest configuration
git pull origin claude/docker-setup-postgres-neo4j-GJI8n

# Stop existing containers
sudo docker compose down

# Start with port 80 (requires sudo)
sudo docker compose up -d --build

# Verify services are running
sudo docker compose ps
```

### Step 5: Verify Port 80 is Listening

```bash
# Check if Docker Nginx is listening on port 80
sudo netstat -tulpn | grep :80

# Should show something like:
# tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN      12345/docker-proxy

# Test from VM itself
curl http://localhost

# Should return HTML from your app
```

### Step 6: Configure Load Balancer

Your load balancer should be configured as:

**Frontend (Internet-facing):**
- Protocol: HTTPS
- Port: 443
- SSL Certificate: Your domain certificate

**Backend (VM):**
- Protocol: HTTP
- Port: 80
- Target: Your VM's IP address
- Health Check: HTTP GET on `/health`

**Example (AWS ALB/NLB):**
```
Listener: HTTPS:443
Target Group: HTTP:80
Health Check: HTTP:80/health
```

**Example (Nginx Load Balancer):**
```nginx
upstream backend {
    server your-vm-ip:80;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Firewall Configuration

Ensure your VM firewall allows traffic on port 80:

### Ubuntu (UFW)

```bash
# Allow port 80
sudo ufw allow 80/tcp

# Verify
sudo ufw status

# Should show:
# 80/tcp                     ALLOW       Anywhere
```

### CentOS/RHEL (firewalld)

```bash
# Allow port 80
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

### Cloud Provider Security Groups

**AWS:**
- Add inbound rule: HTTP (80) from Load Balancer Security Group

**Azure:**
- Add inbound rule: Port 80, Protocol TCP, Source: Load Balancer IP

**GCP:**
- Add firewall rule: tcp:80 from load balancer subnet

## Testing

### Test 1: Local VM Test

```bash
# From the VM itself
curl http://localhost

# Should return HTML
```

### Test 2: Direct VM IP Test

```bash
# From another machine
curl http://your-vm-ip

# Should return HTML
```

### Test 3: Load Balancer Test

```bash
# From any machine
curl https://your-load-balancer-url

# Should return HTML (via HTTPS through load balancer)
```

### Test 4: Health Check

```bash
# Test health endpoint
curl http://your-vm-ip/health

# Should return:
# {"status": "healthy"} or similar
```

## Troubleshooting

### Issue 1: "Connection Refused" on Port 80

```bash
# Check if Docker Nginx is running
sudo docker compose ps

# Check if port 80 is listening
sudo netstat -tulpn | grep :80

# Check Docker logs
sudo docker compose logs nginx
```

**Fix:**
- Ensure no other service is using port 80
- Restart Docker: `sudo docker compose restart nginx`

### Issue 2: Load Balancer Shows "Unhealthy"

```bash
# Test health check endpoint
curl http://your-vm-ip/health

# Check app logs
sudo docker compose logs app
```

**Fix:**
- Ensure app is fully started (check logs)
- Verify health check path in load balancer config
- Check firewall allows traffic from load balancer

### Issue 3: "502 Bad Gateway"

This means Nginx can't reach the app on port 5000.

```bash
# Check if app is running
sudo docker compose ps

# Check if app is healthy
sudo docker compose exec app curl http://localhost:5000/health

# Check app logs
sudo docker compose logs app
```

**Fix:**
- Wait for app to fully start (40 seconds startup time)
- Check database connections are working
- Restart app: `sudo docker compose restart app`

### Issue 4: CORS Errors in Browser

```
Access-Control-Allow-Origin error
```

**Fix:**
Update `.env` file to include your load balancer URL:

```bash
nano .env

# Add your load balancer URL
CORS_ORIGINS=https://your-load-balancer-domain,http://your-vm-ip,http://localhost
```

Restart app:
```bash
sudo docker compose restart app
```

## Security Considerations

### 1. SSL/TLS Termination

- ✅ **At Load Balancer** (Recommended): Load balancer handles HTTPS, VM receives HTTP
- ⚠️ **At Application**: More complex, but end-to-end encryption

Current setup uses SSL termination at load balancer.

### 2. Restrict Port 80 Access

If you want to accept traffic ONLY from load balancer:

```bash
# Ubuntu UFW
sudo ufw delete allow 80/tcp
sudo ufw allow from LOAD_BALANCER_IP to any port 80

# Or use security groups (AWS/Azure/GCP)
```

### 3. Use Private Network

For better security, use a private network between load balancer and VM:
- Load balancer on public subnet
- VM on private subnet
- Only load balancer can reach VM:80

## Monitoring

### Check Docker Container Status

```bash
# All containers status
sudo docker compose ps

# Container logs
sudo docker compose logs -f nginx
sudo docker compose logs -f app

# Resource usage
sudo docker stats
```

### Check Port Connectivity

```bash
# Check from VM
curl -v http://localhost:80

# Check from external
curl -v http://your-vm-ip:80
```

### Health Checks

```bash
# App health
curl http://localhost:5000/health

# Through Nginx
curl http://localhost:80/health

# Through Load Balancer
curl https://your-load-balancer/health
```

## Port Summary

| Component | Port | Protocol | Access |
|-----------|------|----------|--------|
| Load Balancer | 443 | HTTPS | Internet |
| VM Nginx (Docker) | 80 | HTTP | Load Balancer |
| FastAPI App | 5000 | HTTP | Docker Network |
| PostgreSQL | 5432 | TCP | Docker Network |
| Neo4j HTTP | 7474 | HTTP | Docker Network |
| Neo4j Bolt | 7687 | TCP | Docker Network |

## Quick Commands Reference

```bash
# Stop service using port 80
sudo systemctl stop apache2
sudo systemctl stop nginx

# Start Docker services
sudo docker compose up -d

# Check port 80
sudo lsof -i :80

# Test local access
curl http://localhost

# View logs
sudo docker compose logs -f

# Restart specific service
sudo docker compose restart nginx

# Full restart
sudo docker compose down && sudo docker compose up -d
```

## Success Checklist

- [ ] Port 80 is free: `sudo lsof -i :80` (before Docker)
- [ ] Docker started: `sudo docker compose up -d`
- [ ] Port 80 is listening: `sudo lsof -i :80` (shows docker-proxy)
- [ ] All containers healthy: `sudo docker compose ps`
- [ ] Local test works: `curl http://localhost`
- [ ] VM IP test works: `curl http://vm-ip`
- [ ] Load balancer configured: Backend HTTP:80
- [ ] Firewall allows port 80
- [ ] CORS includes load balancer URL
- [ ] Load balancer health check passes
- [ ] Load balancer test works: `curl https://lb-url`

## Final Architecture

```
User Browser
    ↓ HTTPS (443)
Load Balancer (SSL termination)
    ↓ HTTP (80)
VM Firewall (allow 80 from LB)
    ↓
Docker Nginx (80 → 5000)
    ↓
FastAPI + React App (5000)
    ↓                    ↓
PostgreSQL (5432)    Neo4j (7687)
```

All traffic flows through HTTPS to load balancer, then HTTP to VM port 80! 🚀
