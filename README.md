# Job Scraper Microservice

A production-ready FastAPI microservice for web scraping job postings with advanced features including service-to-service authentication, event-driven architecture, intelligent caching, and comprehensive monitoring.

## =€ Features

- **Fast & Scalable**: Built with FastAPI for high-performance async operations
- **Production Ready**: Comprehensive logging, monitoring, and error handling
- **Service Authentication**: JWT-based inter-service communication with scoped access
- **Event-Driven Architecture**: RabbitMQ integration for real-time event processing
- **Intelligent Caching**: Redis-based multi-layer caching with automatic invalidation
- **Advanced Rate Limiting**: Multiple algorithms (sliding window, token bucket, adaptive)
- **Request Tracing**: Correlation IDs for distributed request tracking
- **Health Monitoring**: Comprehensive health checks and system metrics
- **Data Retention**: Configurable policies for automatic data cleanup
- **Docker Ready**: Complete containerization with development and production configs

## =Ë Prerequisites

Before setting up the job scraper microservice, ensure you have the following installed:

### Required Software
- **Python 3.11+**: Main application runtime
- **PostgreSQL 13+**: Primary database for job data storage
- **Redis 6+**: Caching and session storage
- **RabbitMQ 3.8+**: Message broker for event-driven architecture
- **Docker & Docker Compose**: For containerized deployment (recommended)

### Optional Tools
- **Git**: For version control
- **Make**: For simplified command execution (if using Makefiles)
- **Nginx**: For production reverse proxy (included in Docker setup)

## =à Installation & Setup

### Method 1: Docker Compose (Recommended)

This is the easiest way to get started with all dependencies included.

#### 1. Clone and Navigate
```bash
git clone <your-repository-url>
cd job_scraper/backend
```

#### 2. Environment Configuration
```bash
# Copy environment template
cp env.example .env

# Edit configuration (see Configuration section below)
nano .env  # or your preferred editor
```

#### 3. Build and Start Services
```bash
# Build and start all services
docker-compose -f docker-compose.dev.yml up --build

# Or run in background
docker-compose -f docker-compose.dev.yml up -d --build
```

#### 4. Initialize Database
```bash
# Run database migrations
docker-compose -f docker-compose.dev.yml exec app alembic upgrade head

# Create initial admin user (optional)
docker-compose -f docker-compose.dev.yml exec app python -c "
from app.db.session import SessionLocal
from app.services.user_service import UserService
from app.schemas.user import UserCreate
db = SessionLocal()
user_service = UserService()
admin_user = UserCreate(
    email='admin@example.com',
    password='admin123',
    full_name='Admin User'
)
user_service.create_user(db, admin_user, is_admin=True)
db.close()
print('Admin user created successfully')
"
```

### Method 2: Manual Installation

If you prefer to set up services manually:

#### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
# Update package list
sudo apt update

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Install Redis
sudo apt install redis-server

# Install RabbitMQ
sudo apt install rabbitmq-server

# Start services
sudo systemctl start postgresql redis-server rabbitmq-server
sudo systemctl enable postgresql redis-server rabbitmq-server
```

**macOS (using Homebrew):**
```bash
# Install dependencies
brew install postgresql redis rabbitmq

# Start services
brew services start postgresql
brew services start redis
brew services start rabbitmq
```

**Windows:**
- Download and install PostgreSQL from https://www.postgresql.org/download/windows/
- Download and install Redis from https://redis.io/download
- Download and install RabbitMQ from https://www.rabbitmq.com/download.html

#### 2. Setup Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Database Setup
```bash
# Create database user and database
sudo -u postgres psql
postgres=# CREATE USER jobscraper WITH PASSWORD 'your_password';
postgres=# CREATE DATABASE jobscraper_db OWNER jobscraper;
postgres=# GRANT ALL PRIVILEGES ON DATABASE jobscraper_db TO jobscraper;
postgres=# \q

# Run migrations
alembic upgrade head
```

#### 4. Configure Services
```bash
# Copy and edit environment configuration
cp env.example .env
# Edit .env with your database and service configurations
```

#### 5. Start the Application
```bash
# Development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production server
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## ™ Configuration

### Environment Variables

Create a `.env` file based on `env.example`:

#### Database Configuration
```env
DATABASE_URL=postgresql://jobscraper:password@localhost:5432/jobscraper_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=jobscraper_db
DB_USER=jobscraper
DB_PASSWORD=your_secure_password
```

#### Redis Configuration
```env
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

#### RabbitMQ Configuration
```env
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
```

#### Security Settings
```env
# Generate a secure secret key
SECRET_KEY=your-super-secret-key-here-change-this-in-production
JWT_SECRET_KEY=another-secret-key-for-jwt-tokens
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

# Service-to-service authentication
SERVICE_SECRET_KEY=service-communication-secret-key
```

#### Application Settings
```env
APP_NAME="Job Scraper API"
DEBUG=false
ENVIRONMENT=production
API_V1_STR=/api/v1
```

#### Data Retention Configuration
```env
# Data retention periods (in days)
DATA_RETENTION_JOBS=90
DATA_RETENTION_LOGS=30
DATA_RETENTION_METRICS=7
DATA_RETENTION_CACHE=1
```

#### Monitoring & Logging
```env
LOG_LEVEL=INFO
ENABLE_METRICS=true
METRICS_EXPORT_INTERVAL=60
```

### Service Configuration

#### Internal Service URLs
Update these if your ML/LLM services are on different hosts:
```env
ML_SERVICE_URL=http://ml-service:8001
LLM_SERVICE_URL=http://llm-service:8002
ANALYTICS_SERVICE_URL=http://analytics-service:8003
```

## =3 Docker Configuration

### Development Environment
```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up

# View logs
docker-compose -f docker-compose.dev.yml logs -f app

# Execute commands in container
docker-compose -f docker-compose.dev.yml exec app bash
```

### Production Environment
```bash
# Start production environment
docker-compose -f docker-compose.prod.yml up -d

# Scale the application
docker-compose -f docker-compose.prod.yml up -d --scale app=3
```

### Docker Commands
```bash
# Build specific service
docker-compose build app

# Restart services
docker-compose restart

# Stop and remove containers
docker-compose down

# View container status
docker-compose ps

# Access container shell
docker-compose exec app bash
docker-compose exec db psql -U jobscraper -d jobscraper_db
docker-compose exec redis redis-cli
```

## =á API Documentation

### Core Endpoints

#### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - User logout

#### Job Management
- `GET /api/v1/jobs` - List jobs with filtering and pagination
- `GET /api/v1/jobs/{job_id}` - Get specific job details
- `GET /api/v1/jobs/recent` - Get recent jobs
- `POST /api/v1/jobs/scrape` - Trigger job scraping (admin only)

#### User Management
- `GET /api/v1/users/profile` - Get user profile
- `PUT /api/v1/users/profile` - Update user profile
- `POST /api/v1/users/upload-resume` - Upload resume

#### Statistics & Analytics
- `GET /api/v1/stats/dashboard-stats` - Dashboard statistics
- `GET /api/v1/stats/job-stats` - Job-related statistics

### Internal Service Endpoints

These endpoints are used for service-to-service communication:

#### Data Serving for ML/LLM Services
- `GET /api/v1/internal/jobs/bulk` - Bulk job data with pagination
- `GET /api/v1/internal/users/data` - User data for ML analysis
- `GET /api/v1/internal/jobs/categories` - Available job categories
- `GET /api/v1/internal/jobs/locations` - Available job locations

#### Authentication for Internal Services
Internal services must include a service token in the Authorization header:
```
Authorization: Bearer <service_token>
```

### Monitoring Endpoints
- `GET /health` - Basic health check
- `GET /readiness` - Readiness probe (Kubernetes compatible)
- `GET /liveness` - Liveness probe (Kubernetes compatible)
- `GET /api/v1/monitoring/metrics` - Prometheus-compatible metrics
- `GET /api/v1/monitoring/dashboard` - Monitoring dashboard data

### Interactive API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## =' Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_jobs.py

# Run tests in verbose mode
pytest -v
```

### Code Quality
```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Downgrade migration
alembic downgrade -1

# View migration history
alembic history
```

### Adding New Features

1. **Create feature branch**: `git checkout -b feature/new-feature`
2. **Implement changes**: Follow existing code patterns and conventions
3. **Add tests**: Ensure adequate test coverage
4. **Update documentation**: Update API docs and README if needed
5. **Test thoroughly**: Run full test suite and manual testing
6. **Create pull request**: Include description of changes and test results

## =Ê Monitoring & Observability

### Application Metrics

The service exposes comprehensive metrics for monitoring:

#### Request Metrics
- Request count by endpoint and status code
- Request duration percentiles (50th, 95th, 99th)
- Error rates and status code distributions
- Concurrent request counts

#### System Metrics
- CPU and memory usage
- Disk space utilization
- Database connection pool status
- Cache hit/miss rates

#### Business Metrics
- Jobs scraped per hour/day
- User registration rates
- API usage by service
- Data retention statistics

### Monitoring Stack Integration

#### Prometheus
```yaml
# prometheus.yml configuration
scrape_configs:
  - job_name: 'job-scraper'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/monitoring/metrics'
    scrape_interval: 30s
```

#### Grafana Dashboards
Import the provided Grafana dashboard (`monitoring/grafana-dashboard.json`) for visualization.

#### Alert Rules
Example Prometheus alert rules:
```yaml
groups:
  - name: job-scraper
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: High error rate detected
```

### Log Analysis

Logs are structured in JSON format for easy parsing:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Job scraping completed",
  "correlation_id": "req-123abc",
  "user_id": "user-456",
  "duration_ms": 1250,
  "jobs_found": 45
}
```

## =' Troubleshooting

### Common Issues

#### Database Connection Issues
**Problem**: `FATAL: password authentication failed`
**Solution**:
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Reset password
sudo -u postgres psql
postgres=# ALTER USER jobscraper PASSWORD 'new_password';

# Update .env file with new password
```

#### Redis Connection Issues
**Problem**: `ConnectionError: Error connecting to Redis`
**Solution**:
```bash
# Check Redis status
redis-cli ping

# Restart Redis if needed
sudo systemctl restart redis-server

# Check Redis configuration
redis-cli config get "*"
```

#### RabbitMQ Connection Issues
**Problem**: `AMQPConnectionError: Connection refused`
**Solution**:
```bash
# Check RabbitMQ status
sudo systemctl status rabbitmq-server

# Enable management plugin
sudo rabbitmq-plugins enable rabbitmq_management

# Access management UI at http://localhost:15672
# Default credentials: guest/guest
```

#### High Memory Usage
**Problem**: Application consuming too much memory
**Solution**:
```bash
# Check cache usage
curl http://localhost:8000/api/v1/monitoring/dashboard

# Clear cache if needed
redis-cli FLUSHDB

# Adjust cache TTL in configuration
```

#### Slow API Responses
**Problem**: API endpoints responding slowly
**Solution**:
1. Check database query performance:
   ```sql
   -- Enable query logging in PostgreSQL
   ALTER SYSTEM SET log_statement = 'all';
   SELECT pg_reload_conf();
   ```

2. Monitor cache hit rates:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/metrics | grep cache
   ```

3. Check rate limiting configuration
4. Review database indexes

### Performance Optimization

#### Database Optimization
```sql
-- Add indexes for common queries
CREATE INDEX CONCURRENTLY idx_jobs_created_at ON jobs(created_at);
CREATE INDEX CONCURRENTLY idx_jobs_location ON jobs(location);
CREATE INDEX CONCURRENTLY idx_jobs_job_type ON jobs(job_type);

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM jobs WHERE location = 'Remote';
```

#### Cache Optimization
```python
# Adjust cache TTL based on data volatility
CACHE_SETTINGS = {
    'job_search': 300,    # 5 minutes
    'job_details': 3600,  # 1 hour
    'categories': 86400,  # 24 hours
}
```

#### Rate Limiting Tuning
```python
# Adjust rate limits based on usage patterns
RATE_LIMITS = {
    'auth_endpoints': 10,      # requests per minute
    'api_endpoints': 100,      # requests per minute
    'internal_endpoints': 1000, # requests per minute
}
```

### Debugging

#### Enable Debug Mode
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

#### View Detailed Logs
```bash
# Docker logs
docker-compose logs -f app

# Application logs
tail -f logs/app.log

# Filter logs by correlation ID
grep "req-123abc" logs/app.log
```

#### Database Debugging
```bash
# Connect to database
docker-compose exec db psql -U jobscraper -d jobscraper_db

# View active connections
SELECT * FROM pg_stat_activity;

# Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Getting Help

1. **Check Logs**: Always start by examining application and system logs
2. **Review Configuration**: Verify all environment variables are set correctly
3. **Test Components**: Use health check endpoints to identify failing components
4. **Monitor Resources**: Check CPU, memory, and disk usage
5. **Database Status**: Verify database connectivity and performance

For additional support:
- Check the issues section in the repository
- Review the API documentation at `/docs`
- Monitor system health at `/health`

## =€ Deployment

### Production Checklist

Before deploying to production:

- [ ] Update all secret keys and passwords
- [ ] Set `DEBUG=false` and `ENVIRONMENT=production`
- [ ] Configure proper database backup strategy
- [ ] Set up monitoring and alerting
- [ ] Configure log rotation and retention
- [ ] Test all health check endpoints
- [ ] Verify SSL/TLS certificates
- [ ] Set up proper firewall rules
- [ ] Configure rate limiting for production load
- [ ] Test disaster recovery procedures

### Scaling Considerations

- **Horizontal Scaling**: Multiple application instances behind a load balancer
- **Database Scaling**: Read replicas for improved read performance
- **Cache Scaling**: Redis cluster for high availability
- **Message Queue Scaling**: RabbitMQ cluster for event processing
- **Resource Monitoring**: Implement auto-scaling based on metrics

## =Ä License

This project is licensed under the MIT License - see the LICENSE file for details.

## > Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## =Þ Support

For support and questions:
- Create an issue in the GitHub repository
- Check the troubleshooting section above
- Review the API documentation at `/docs`

---

**Note**: This microservice is designed for production use with comprehensive monitoring, security, and scalability features. Ensure all security configurations are properly set before deploying to production environments.