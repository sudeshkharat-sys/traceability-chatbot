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

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd nashik-chatbot-pq
```

### 2. Configure Environment Variables

Copy the example environment file and configure your Azure OpenAI credentials:

```bash
cp .env.docker.example .env
```

Edit the `.env` file and add your Azure OpenAI credentials:

```env
AZURE_API_KEY=your_actual_azure_api_key
AZURE_CHAT_ENDPOINT=https://your-resource.openai.azure.com/...
AZURE_EMBEDDING_ENDPOINT=https://your-resource.openai.azure.com/...
```

Also copy the environment file to the app config directory:

```bash
cp .env app/config/.env
```

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

- **Image**: neo4j:5.15-community
- **HTTP Port**: 7474
- **Bolt Port**: 7687
- **Username**: neo4j
- **Password**: password
- **Data Volumes**: neo4j_data, neo4j_logs, neo4j_import, neo4j_plugins

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

| Variable | Description | Default |
|----------|-------------|---------|
| AZURE_API_KEY | Azure OpenAI API Key | Required |
| AZURE_CHAT_ENDPOINT | Azure Chat Model Endpoint | Required |
| AZURE_EMBEDDING_ENDPOINT | Azure Embedding Endpoint | Required |
| NEO4J_URI | Neo4j Connection URI | neo4j://neo4j:7687 |
| NEO4J_USERNAME | Neo4j Username | neo4j |
| NEO4J_PASSWORD | Neo4j Password | password |
| POSTGRES_HOST | PostgreSQL Host | postgres |
| POSTGRES_PORT | PostgreSQL Port | 5432 |
| POSTGRES_USER | PostgreSQL User | postgres |
| POSTGRES_PASSWORD | PostgreSQL Password | password |
| POSTGRES_DB | PostgreSQL Database | chatbot |

## Support

For issues and questions:
- Check the logs: `docker-compose logs -f`
- Verify service health: `docker-compose ps`
- Review this documentation
- Check application README.md for general information
