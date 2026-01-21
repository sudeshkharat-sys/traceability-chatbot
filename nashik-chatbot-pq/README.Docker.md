# Docker Setup Guide for Thar Roxx Quality Intelligence API

This guide explains how to run the Thar Roxx Quality Intelligence API using Docker and Docker Compose.

## Architecture

The Docker setup includes the following services:

1. **PostgreSQL** (Alpine 17) - Relational database for chat history and checkpoints
2. **Neo4j** (Community Edition) - Graph database for knowledge graphs
3. **Application** - FastAPI backend with React frontend
4. **Nginx** - Reverse proxy forwarding traffic from port 7434 to the application

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 4GB of available RAM
- Azure OpenAI API credentials

> **Don't have Docker installed?** See [DOCKER_INSTALLATION.md](DOCKER_INSTALLATION.md) for complete installation instructions for Ubuntu.

## Data Persistence & Auto-Start

✅ **Your data is safe!** This setup uses Docker volumes for persistent storage.
✅ **Auto-starts on VM reboot!** All containers configured with `restart: unless-stopped`.

Perfect for VMs that shutdown daily:
- **8 PM VM shutdown** → Data persists on disk
- **Morning VM startup** → Containers auto-start with all data intact

**See [VM_RESTART_GUIDE.md](VM_RESTART_GUIDE.md) for complete details on:**
- How data persistence works
- Auto-start configuration
- Testing VM restart scenarios
- One-time VM setup (enable Docker on boot)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd nashik-chatbot-pq
```

### 2. Configure Environment Variables

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env
```

Edit the `.env` file and update the following:

**Required - Azure OpenAI credentials:**
```env
AZURE_API_KEY=your_actual_azure_api_key
AZURE_CHAT_ENDPOINT=https://your-resource.openai.azure.com/...
AZURE_EMBEDDING_ENDPOINT=https://your-resource.openai.azure.com/...
```

**IMPORTANT - Change default passwords:**
```env
POSTGRES_PASSWORD=your_secure_postgres_password
NEO4J_PASSWORD=your_secure_neo4j_password
SESSION_SECRET=your_random_session_secret
```

> **Note:** The `.env` file is automatically loaded by Docker Compose and mounted into containers. No need to create separate config files. See [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for detailed configuration guide.

### 3. Start All Services

Build and start all containers:

```bash
docker-compose up -d
```

This will:
- Pull required Docker images
- Build the application image
- Start PostgreSQL, Neo4j, the application, and Nginx
- Create necessary volumes for data persistence

### 4. Verify Services

Check that all services are running:

```bash
docker-compose ps
```

All services should show "healthy" status after a minute.

### 5. Access the Application

- **Main Application**: http://localhost:7434
- **Neo4j Browser**: http://localhost:7474 (Username: `neo4j`, Password: `password`)
- **Direct App Access**: http://localhost:5000

## Service Configuration

### PostgreSQL

- **Image**: postgres:17-alpine
- **Port**: 5432
- **Database**: chatbot
- **Username**: postgres
- **Password**: password
- **Data Volume**: postgres_data

### Neo4j

- **Image**: neo4j:2025.12.1
- **HTTP Port**: 7474
- **Bolt Port**: 7687
- **Username**: neo4j
- **Password**: password
- **Data Volumes**: neo4j_data, neo4j_logs, neo4j_import, neo4j_plugins

#### Memory Configuration (Optimized for 32GB RAM Ubuntu VM)

The Neo4j configuration is optimized for a dedicated Ubuntu VM with 32GB RAM:

- **Page Cache**: 18GB - Used for caching graph data and indexes from disk into memory for optimal read performance
- **Heap Initial Size**: 10GB - Initial JVM heap allocation for transaction processing
- **Heap Max Size**: 12GB - Maximum JVM heap for query execution and intermediate results
- **OS Reserve**: ~2GB - Reserved for operating system and other processes

This configuration follows Neo4j's best practices, allocating approximately:
- **56% to Page Cache** (18GB) - Primary performance driver for graph traversals
- **31-38% to Heap** (10-12GB) - Handles transaction states and query processing
- **6% to OS** (2GB) - System overhead and process management

**Note**: For different RAM sizes, you can adjust these values proportionally or use Neo4j's memory recommendation tool:
```bash
docker-compose exec neo4j neo4j-admin server memory-recommendation --memory=32g
```

**For detailed memory configuration guidance**, see [NEO4J_MEMORY_GUIDE.md](NEO4J_MEMORY_GUIDE.md) which includes:
- Memory component explanations
- Recommendations for different RAM sizes (8GB, 16GB, 32GB, 64GB)
- Performance tuning tips
- Troubleshooting common memory issues

### Application

- **Internal Port**: 5000
- **Build**: Multi-stage (Node.js for frontend, Python for backend)
- **Health Check**: /health endpoint

### Nginx

- **External Port**: 7434
- **Internal Port**: 80
- **Purpose**: Reverse proxy to application on port 5000

## Database Initialization

After the first start, initialize the databases:

```bash
# Enter the app container
docker-compose exec app bash

# Run database setup
python -m invoke setup-database

# Or run individual setup commands
python -m invoke create-tables
python -m invoke seed-prompts

# Exit container
exit
```

## Docker Commands

### Start Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d app

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f app
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v
```

### Rebuild Application

```bash
# Rebuild after code changes
docker-compose up -d --build app

# Force rebuild without cache
docker-compose build --no-cache app
docker-compose up -d app
```

### View Service Status

```bash
# Check service status
docker-compose ps

# Check health status
docker-compose ps --format json | jq '.[] | {name: .Name, health: .Health}'
```

### Access Container Shell

```bash
# Application container
docker-compose exec app bash

# PostgreSQL container
docker-compose exec postgres psql -U postgres -d chatbot

# Neo4j container (cypher-shell)
docker-compose exec neo4j cypher-shell -u neo4j -p password
```

## Volume Management

### List Volumes

```bash
docker volume ls | grep nashik
```

### Backup Data

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U postgres chatbot > backup_postgres.sql

# Backup Neo4j (create dump)
docker-compose exec neo4j neo4j-admin database dump neo4j --to-path=/data
```

### Restore Data

```bash
# Restore PostgreSQL
cat backup_postgres.sql | docker-compose exec -T postgres psql -U postgres chatbot

# Restore Neo4j
docker-compose exec neo4j neo4j-admin database load neo4j --from-path=/data
```

## Troubleshooting

### Services Won't Start

Check logs for errors:

```bash
docker-compose logs app
docker-compose logs postgres
docker-compose logs neo4j
```

### Port Conflicts

If ports are already in use, modify them in `docker-compose.yml`:

```yaml
ports:
  - "17434:80"  # Change 7434 to another port
```

### Database Connection Issues

Ensure services are healthy:

```bash
docker-compose ps
```

Test database connections:

```bash
# Test PostgreSQL
docker-compose exec postgres pg_isready -U postgres

# Test Neo4j
docker-compose exec neo4j cypher-shell -u neo4j -p password "RETURN 1"
```

### Application Errors

View application logs:

```bash
docker-compose logs -f app
```

Check environment variables:

```bash
docker-compose exec app env | grep -E 'NEO4J|POSTGRES|AZURE'
```

### Clear Everything and Start Fresh

```bash
# Stop and remove all containers, networks, and volumes
docker-compose down -v

# Remove built images
docker-compose down --rmi all

# Rebuild and start
docker-compose up -d --build
```

## Development Mode

For development with hot-reload:

1. Modify `docker-compose.yml` to add volume mounts:

```yaml
app:
  volumes:
    - ./app:/app/app
    - ./backend:/app/backend
    - ./main.py:/app/main.py
```

2. Restart the service:

```bash
docker-compose restart app
```

## Production Considerations

For production deployment:

1. **Change Default Passwords**: Update all passwords in `docker-compose.yml` and `.env`
2. **Use Secrets**: Consider using Docker secrets for sensitive data
3. **Enable HTTPS**: Configure SSL/TLS in Nginx
4. **Resource Limits**: Add resource constraints in `docker-compose.yml`
5. **Monitoring**: Add health monitoring and alerting
6. **Backups**: Set up automated backup schedules
7. **Logging**: Configure centralized logging

Example resource limits:

```yaml
app:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G
```

## Network Architecture

```
Internet (Port 7434)
        ↓
    [Nginx Container]
        ↓ (Port 80)
    [App Container] (Port 5000)
        ↓               ↓
[PostgreSQL:5432]  [Neo4j:7687]
```

## Environment Variables Reference

**Required Variables (Must be set in .env):**

| Variable | Description | Example |
|----------|-------------|---------|
| AZURE_API_KEY | Azure OpenAI API Key | `abc123...` |
| AZURE_CHAT_ENDPOINT | Azure Chat Model Endpoint | `https://your-resource.openai.azure.com/...` |
| AZURE_EMBEDDING_ENDPOINT | Azure Embedding Endpoint | `https://your-resource.openai.azure.com/...` |
| POSTGRES_PASSWORD | PostgreSQL Password | **Change from default!** |
| NEO4J_PASSWORD | Neo4j Password | **Change from default!** |

**Optional Variables (with defaults):**

| Variable | Default | Description |
|----------|---------|-------------|
| NEO4J_URL | `neo4j://neo4j:7687` | Neo4j Connection URI |
| NEO4J_USERNAME | `neo4j` | Neo4j Username |
| POSTGRES_HOST | `postgres` | PostgreSQL Host |
| POSTGRES_PORT | `5432` | PostgreSQL Port |
| POSTGRES_USER | `postgres` | PostgreSQL User |
| POSTGRES_DB | `chatbot` | PostgreSQL Database |
| SERVER_HOST | `0.0.0.0` | Application Host |
| SERVER_PORT | `5000` | Application Port |
| SESSION_SECRET | `change-me-in-production` | **Change for security!** |

> **For complete environment configuration documentation**, see [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)

## Support

For issues and questions:
- Check the logs: `docker-compose logs -f`
- Verify service health: `docker-compose ps`
- Review this documentation
- Check application README.md for general information
