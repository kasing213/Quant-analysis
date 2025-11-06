# Docker Setup for Quantitative Trading System

## Prerequisites

### For WSL2 Users (Windows)

1. **Install Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop/
   - Install and enable WSL2 backend

2. **Enable WSL Integration**
   - Open Docker Desktop
   - Go to Settings → Resources → WSL Integration
   - Enable integration with your WSL2 distro
   - Apply & Restart

3. **Verify Docker in WSL2**
   ```bash
   docker --version
   docker-compose --version
   ```

### For Linux Users

1. **Install Docker**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   newgrp docker
   ```

2. **Install Docker Compose**
   ```bash
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

## Quick Start

### 1. Start PostgreSQL Database Only
```bash
# Start only the PostgreSQL container
docker-compose up postgres -d

# Check if it's running
docker-compose ps

# View logs
docker-compose logs postgres
```

### 2. Test Database Connection
```bash
# Run the database connection test
python3 test_db_connection.py

# Or test with environment variables
POSTGRES_HOST=localhost POSTGRES_PASSWORD=trading_secure_password_2024 python3 test_db_connection.py
```

### 3. Start Full Stack (PostgreSQL + FastAPI)
```bash
# Build and start all services
docker-compose up --build

# Or start in background
docker-compose up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
docker-compose logs -f postgres
```

### 4. Test FastAPI Application
```bash
# Health check
curl http://localhost:8000/health

# Database health
curl http://localhost:8000/health/database

# Detailed health check
curl http://localhost:8000/health/detailed

# API documentation
# Open browser: http://localhost:8000/docs
```

## Environment Configuration

The system uses these environment variables (configured in docker-compose.yml):

```bash
# Database Connection
DATABASE_URL=postgresql+asyncpg://trader:trading_secure_password_2024@postgres:5432/trading_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=trading_db
POSTGRES_USER=trader
POSTGRES_PASSWORD=trading_secure_password_2024

# Connection Pool
POSTGRES_MIN_CONN=5
POSTGRES_MAX_CONN=25
POSTGRES_TIMEOUT=30

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
SQL_ECHO=false
```

## Development Workflow

### Local Development with Docker Database
```bash
# 1. Start only PostgreSQL
docker-compose up postgres -d

# 2. Run FastAPI locally (with hot reload)
cd src
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 3. Test connection
python3 ../test_db_connection.py
```

### Full Docker Development
```bash
# 1. Start all services with build
docker-compose up --build

# 2. Make changes to code (auto-reloaded via volume mounts)

# 3. Rebuild if requirements change
docker-compose build api
docker-compose up api
```

## Troubleshooting

### Common Issues

1. **Docker not found in WSL2**
   ```bash
   # Check if Docker Desktop is running
   # Enable WSL integration in Docker Desktop settings
   ```

2. **PostgreSQL connection refused**
   ```bash
   # Check if container is running
   docker-compose ps

   # Check logs
   docker-compose logs postgres

   # Restart PostgreSQL
   docker-compose restart postgres
   ```

3. **Port already in use**
   ```bash
   # Check what's using the port
   sudo netstat -tlnp | grep :5432
   sudo netstat -tlnp | grep :8000

   # Stop conflicting services or change ports in docker-compose.yml
   ```

4. **Permission denied errors**
   ```bash
   # Fix file permissions
   sudo chown -R $USER:$USER .
   ```

### Database Debugging

1. **Connect to PostgreSQL directly**
   ```bash
   # Using docker exec
   docker-compose exec postgres psql -U trader -d trading_db

   # Using local psql (if installed)
   psql -h localhost -p 5432 -U trader -d trading_db
   ```

2. **View database tables**
   ```sql
   -- List all schemas
   \\dn

   -- List tables in trading schema
   \\dt trading.*

   -- Describe a table
   \\d trading.positions
   ```

3. **Check connection stats**
   ```sql
   -- Active connections
   SELECT * FROM pg_stat_activity WHERE datname = 'trading_db';

   -- Database size
   SELECT pg_size_pretty(pg_database_size('trading_db'));
   ```

### Performance Tuning

1. **PostgreSQL Configuration**
   - Edit `config/postgresql.conf` for custom settings
   - Adjust memory settings in docker-compose.yml
   - Monitor with `docker stats`

2. **Connection Pool Tuning**
   - Adjust `POSTGRES_MIN_CONN` and `POSTGRES_MAX_CONN`
   - Monitor pool usage via health endpoints

## Production Deployment

### Using Docker Compose Profiles
```bash
# Production with Nginx reverse proxy
docker-compose --profile production up -d

# This includes:
# - PostgreSQL with optimized settings
# - FastAPI with multiple workers
# - Redis for caching
# - Nginx reverse proxy
```

### Health Monitoring
```bash
# Check all container health
docker-compose ps

# Monitor logs
docker-compose logs -f --tail=100

# Health check endpoints
curl http://localhost/health
curl http://localhost/health/detailed
```

## Backup and Restore

### Database Backup
```bash
# Create backup
docker-compose exec postgres pg_dump -U trader trading_db > backup.sql

# Or with compression
docker-compose exec postgres pg_dump -U trader trading_db | gzip > backup.sql.gz
```

### Database Restore
```bash
# Restore from backup
docker-compose exec -T postgres psql -U trader trading_db < backup.sql

# Or from compressed backup
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U trader trading_db
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `docker-compose up -d` | Start all services in background |
| `docker-compose down` | Stop all services |
| `docker-compose build` | Rebuild containers |
| `docker-compose ps` | List running containers |
| `docker-compose logs -f` | Follow logs |
| `docker-compose restart postgres` | Restart PostgreSQL |
| `docker-compose exec api bash` | Shell into API container |
| `docker-compose exec postgres psql -U trader trading_db` | PostgreSQL shell |

## Security Notes

- Change default passwords in production
- Use environment files (.env) for secrets
- Enable SSL for database connections
- Configure firewall rules appropriately
- Regular security updates for base images