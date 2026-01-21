# Docker Installation Guide for Ubuntu

This guide will help you install Docker and Docker Compose on your Ubuntu VM.

## Quick Installation

Run this single script to install everything:

```bash
# Update package index
sudo apt-get update

# Install prerequisites
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
sudo docker --version
sudo docker compose version
```

## Step-by-Step Installation

### Step 1: Update System

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### Step 2: Install Prerequisites

```bash
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release
```

### Step 3: Add Docker Repository

```bash
# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

### Step 4: Install Docker

```bash
# Update package index
sudo apt-get update

# Install Docker Engine, CLI, and Docker Compose V2
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Step 5: Verify Installation

```bash
# Check Docker version
sudo docker --version
# Output: Docker version 24.0.x, build...

# Check Docker Compose version
sudo docker compose version
# Output: Docker Compose version v2.x.x
```

### Step 6: Start and Enable Docker

```bash
# Start Docker service
sudo systemctl start docker

# Enable Docker to start on boot
sudo systemctl enable docker

# Check status
sudo systemctl status docker
```

### Step 7: Add Your User to Docker Group (Optional but Recommended)

This allows you to run Docker commands without `sudo`:

```bash
# Add current user to docker group
sudo usermod -aG docker $USER

# Apply changes (or logout and login again)
newgrp docker

# Test without sudo
docker --version
docker compose version
```

**IMPORTANT:** After adding yourself to the docker group, you need to:
- Either run `newgrp docker` in your current terminal
- OR logout and login again
- OR restart your SSH session

## Docker Compose V2 vs V1

**You have Docker Compose V2** (installed with Docker Engine)

| Version | Command | Status |
|---------|---------|--------|
| V1 (Standalone) | `docker-compose` | ❌ Legacy (being deprecated) |
| V2 (Plugin) | `docker compose` | ✅ **Use this** (no hyphen) |

**Use `docker compose` (without hyphen) for all commands:**

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f

# Check status
docker compose ps
```

## Verify Complete Installation

Run these commands to ensure everything is working:

```bash
# 1. Docker daemon is running
sudo systemctl status docker

# 2. Docker version
docker --version

# 3. Docker Compose version
docker compose version

# 4. Test Docker
docker run hello-world

# 5. Test Docker Compose
cd /path/to/nashik-chatbot-pq
docker compose config
```

## Start Your Application

Once Docker is installed:

```bash
# Navigate to project directory
cd /home/user/Traceability/nashik-chatbot-pq

# Create .env file
cp .env.example .env
nano .env  # Add your credentials

# Start all services (NO HYPHEN!)
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

## Troubleshooting

### Permission Denied Error

If you get "permission denied" when running docker commands:

```bash
# Either use sudo
sudo docker compose up -d

# Or add user to docker group (recommended)
sudo usermod -aG docker $USER
newgrp docker
```

### Docker Daemon Not Running

```bash
# Start Docker service
sudo systemctl start docker

# Enable on boot
sudo systemctl enable docker

# Check status
sudo systemctl status docker
```

### Cannot Connect to Docker Daemon

```bash
# Check if Docker is running
sudo systemctl status docker

# If not running, start it
sudo systemctl start docker

# Check if your user is in docker group
groups $USER

# If not in docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Port Already in Use

```bash
# Check what's using the port
sudo lsof -i :5432  # PostgreSQL
sudo lsof -i :7687  # Neo4j
sudo lsof -i :5000  # App
sudo lsof -i :7434  # Nginx

# Stop the service using that port
sudo systemctl stop <service-name>
```

## Uninstall Docker (if needed)

```bash
# Stop all containers
docker stop $(docker ps -aq)

# Remove all containers
docker rm $(docker ps -aq)

# Remove all images
docker rmi $(docker images -q)

# Uninstall Docker packages
sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Remove Docker files
sudo rm -rf /var/lib/docker
sudo rm -rf /var/lib/containerd

# Remove Docker group
sudo groupdel docker
```

## Docker Compose Command Reference

Remember: Use `docker compose` (NO HYPHEN) for V2

| Task | Command |
|------|---------|
| Start services | `docker compose up -d` |
| Stop services | `docker compose down` |
| Restart services | `docker compose restart` |
| View logs | `docker compose logs -f` |
| Check status | `docker compose ps` |
| Build images | `docker compose build` |
| Pull images | `docker compose pull` |
| Execute command | `docker compose exec <service> <command>` |
| View config | `docker compose config` |

## System Requirements

- **OS**: Ubuntu 20.04+ (64-bit)
- **RAM**: 4GB minimum, 32GB recommended for your setup
- **Disk**: 20GB free space minimum
- **CPU**: 2 cores minimum

## Post-Installation Checklist

- [ ] Docker installed: `docker --version`
- [ ] Docker Compose V2 installed: `docker compose version`
- [ ] Docker service running: `sudo systemctl status docker`
- [ ] Docker enabled on boot: `sudo systemctl is-enabled docker`
- [ ] User added to docker group (optional): `groups $USER | grep docker`
- [ ] Test Docker: `docker run hello-world`
- [ ] Project .env file created: `test -f .env && echo "exists"`
- [ ] Services started: `docker compose up -d`

## Quick Reference

```bash
# After installation, use these commands:
cd /home/user/Traceability/nashik-chatbot-pq

# Start (NO HYPHEN!)
docker compose up -d

# Stop
docker compose down

# Status
docker compose ps

# Logs
docker compose logs -f app
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/engine/install/ubuntu/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/)
