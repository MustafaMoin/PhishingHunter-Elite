# PhishingHunter Elite - Production Deployment Guide

Complete guide for deploying PhishingHunter Elite in production with Docker, PostgreSQL, Redis, and Nginx.

---

## 🚀 Quick Start (5 Minutes)

```bash
# 1. Clone and navigate
cd PhishingHunter_v2

# 2. Copy environment file
cp .env.example .env

# 3. Edit .env and change passwords/secrets
nano .env  # or your preferred editor

# 4. Build and start
docker-compose up -d

# 5. Check status
docker-compose ps

# 6. View logs
docker-compose logs -f app

# 7. Open browser
http://localhost
```

---

## 📋 Prerequisites

### Required:
- Docker 20.10+ and Docker Compose 2.0+
- 2GB RAM minimum, 4GB recommended
- 10GB disk space
- Linux server (Ubuntu 20.04+ recommended) or Windows with WSL2

### Optional (for production):
- Domain name
- SSL certificate (or Let's Encrypt)
- Google Safe Browsing API key
- VirusTotal API key

---

## 🏗️ Architecture

```
Internet
    ↓
Nginx (Port 80/443)
    ↓ (reverse proxy)
Gunicorn (4 workers) → Flask App
    ↓                      ↓
PostgreSQL             Redis
(persistent data)   (cache + rate limit)
```

### Services:

1. **nginx** - Reverse proxy, SSL termination, static files
2. **app** - PhishingHunter Flask app (4 Gunicorn workers)
3. **postgres** - PostgreSQL 16 database
4. **redis** - Redis 7 cache

### Volumes:

- `postgres_data` - PostgreSQL data (persistent)
- `redis_data` - Redis data (persistent)
- `./data` - App data (logs, cache)
- `./ml` - ML models (read-only)

---

## 🔧 Configuration

### Step 1: Environment Variables

```bash
# Copy example file
cp .env.example .env

# Edit with your values
nano .env
```

**Critical variables to change:**

```bash
# Database password
POSTGRES_PASSWORD=use_strong_password_here

# Flask secret keys (generate with: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your_random_secret_key_here
PHISHINGHUNTER_SECRET=another_random_secret_here

# Optional API keys (improves detection)
GOOGLE_SAFE_BROWSING_API_KEY=your_key_here
VIRUSTOTAL_API_KEY=your_key_here
```

### Step 2: Database Initialization

Database schema is auto-created on first run. No manual SQL needed.

### Step 3: ML Model (Optional)

If you have a trained ML model:

```bash
# Copy model files
cp /path/to/model.joblib ml/
cp /path/to/features.json ml/
```

If no model exists, app works fine with rule-based detection only.

---

## 🐳 Docker Deployment

### Build and Start

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Check Status

```bash
# Service status
docker-compose ps

# View logs for specific service
docker-compose logs -f app
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f nginx

# Health checks
curl http://localhost/health
```

### Scaling Workers

```bash
# Edit docker-compose.yml
# Change: WORKERS: 4  →  WORKERS: 8

# Restart app
docker-compose restart app
```

---

## 🔐 SSL/HTTPS Setup

### Option 1: Let's Encrypt (Free, Automatic)

```bash
# 1. Install certbot
sudo apt-get install certbot python3-certbot-nginx

# 2. Get certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# 3. Certificates saved to /etc/letsencrypt/live/yourdomain.com/

# 4. Mount in docker-compose.yml
volumes:
  - /etc/letsencrypt:/etc/nginx/ssl:ro

# 5. Uncomment HTTPS server block in nginx.conf

# 6. Restart nginx
docker-compose restart nginx
```

### Option 2: Self-Signed (Development Only)

```bash
# Generate certificate
mkdir ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem -out ssl/cert.pem

# Update nginx.conf with paths
ssl_certificate /etc/nginx/ssl/cert.pem;
ssl_certificate_key /etc/nginx/ssl/key.pem;

# Restart
docker-compose restart nginx
```

### Option 3: Bring Your Own Certificate

```bash
# Copy certificates
mkdir ssl
cp your-cert.crt ssl/cert.pem
cp your-key.key ssl/key.pem

# Update nginx.conf and restart
docker-compose restart nginx
```

---

## 📊 Database Management

### PostgreSQL Access

```bash
# Connect to database
docker-compose exec postgres psql -U phishuser -d phishinghunter

# Backup database
docker-compose exec postgres pg_dump -U phishuser phishinghunter > backup.sql

# Restore database
cat backup.sql | docker-compose exec -T postgres psql -U phishuser -d phishinghunter
```

### Database Queries

```sql
-- Check scan count
SELECT COUNT(*) FROM scans;

-- Recent high-risk scans
SELECT url, score, risk, created_at 
FROM scans 
WHERE risk IN ('HIGH RISK', 'PHISHING') 
ORDER BY created_at DESC 
LIMIT 10;

-- Blocklist size
SELECT COUNT(*) FROM blocklist;

-- Feedback summary
SELECT feedback_type, COUNT(*) 
FROM feedback 
GROUP BY feedback_type;
```

---

## 🔄 Updates and Maintenance

### Update Application

```bash
# 1. Pull latest code
git pull origin main

# 2. Rebuild containers
docker-compose build

# 3. Restart services (zero-downtime)
docker-compose up -d

# 4. Check logs
docker-compose logs -f app
```

### Update ML Model

```bash
# 1. Copy new model
cp /path/to/new_model.joblib ml/model.joblib

# 2. Restart app (model loaded on startup)
docker-compose restart app
```

### Database Migrations

If schema changes:

```bash
# 1. Backup database first!
docker-compose exec postgres pg_dump -U phishuser phishinghunter > backup.sql

# 2. Run migrations (if any)
docker-compose exec app python migrate.py

# 3. Restart app
docker-compose restart app
```

---

## 📈 Monitoring

### Health Checks

```bash
# App health
curl http://localhost/health

# Expected response:
# {"status": "ok", "blocklist_entries": 12345}
```

### Resource Usage

```bash
# CPU and memory
docker stats

# Disk usage
docker system df

# Container logs size
docker-compose exec app du -sh /app/logs/
```

### Prometheus Metrics (Future Enhancement)

```python
# Add to app.py:
from prometheus_flask_exporter import PrometheusMetrics
metrics = PrometheusMetrics(app)
```

---

## 🔥 Performance Tuning

### Gunicorn Workers

```bash
# Formula: (2 x CPU cores) + 1
# For 4-core server: 9 workers

# Edit .env:
WORKERS=9

# Restart:
docker-compose restart app
```

### PostgreSQL Tuning

Edit `docker-compose.yml` → postgres → command:

```yaml
command: >
  postgres
  -c shared_buffers=256MB
  -c effective_cache_size=1GB
  -c maintenance_work_mem=64MB
  -c checkpoint_completion_target=0.9
```

### Redis Memory

```yaml
redis:
  command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### Nginx Cache

Add to nginx.conf:

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=100m inactive=60m;

location /stats {
    proxy_cache api_cache;
    proxy_cache_valid 200 1m;
    # ... other proxy settings
}
```

---

## 🐛 Troubleshooting

### App Won't Start

```bash
# Check logs
docker-compose logs app

# Common issues:
# 1. Database not ready → Wait 30 seconds and retry
# 2. Port 8000 in use → Change in docker-compose.yml
# 3. Missing dependencies → docker-compose build --no-cache
```

### Database Connection Errors

```bash
# Check postgres is running
docker-compose ps postgres

# Test connection
docker-compose exec app python -c "import database_postgres; database_postgres.init_db()"

# Check environment variables
docker-compose exec app env | grep DATABASE_URL
```

### High Memory Usage

```bash
# Check which service
docker stats

# If app:
# - Reduce WORKERS in .env
# - Increase server RAM

# If postgres:
# - Tune shared_buffers
# - Add connection pooling

# If redis:
# - Reduce maxmemory
# - Check for memory leaks
```

### Slow Scans

```bash
# Check API keys are set
docker-compose exec app env | grep API_KEY

# Check network latency
docker-compose exec app ping -c 3 google.com

# Check logs for timeouts
docker-compose logs app | grep -i timeout

# Increase timeouts in detector.py if needed
```

---

## 🔒 Security Hardening

### 1. Use Strong Passwords

```bash
# Generate secure passwords
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Enable Firewall

```bash
# Ubuntu UFW
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Restrict Database Access

Edit `docker-compose.yml`:

```yaml
postgres:
  # Remove or comment out:
  # ports:
  #   - "5432:5432"
  
  # Database only accessible within Docker network
```

### 4. Enable HTTPS Only

In nginx.conf:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    return 301 https://$host$request_uri;
}
```

### 5. Set Security Headers

Already in nginx.conf (uncomment HTTPS section):

```nginx
add_header Strict-Transport-Security "max-age=31536000";
add_header X-Frame-Options "SAMEORIGIN";
add_header X-Content-Type-Options "nosniff";
```

### 6. Rate Limiting

Already configured in nginx.conf:

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/m;
```

### 7. Regular Updates

```bash
# Update Docker images
docker-compose pull
docker-compose up -d

# Update system packages
sudo apt-get update && sudo apt-get upgrade
```

---

## 📦 Backup Strategy

### Automated Daily Backups

Create `/root/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backups/phishinghunter"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Database backup
docker-compose exec -T postgres pg_dump -U phishuser phishinghunter | \
  gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

Add to crontab:

```bash
# Daily at 2 AM
0 2 * * * /root/backup.sh >> /var/log/phishing_backup.log 2>&1
```

---

## 🌐 Multi-Server Deployment

For high availability:

```
Load Balancer
    ↓
Server 1     Server 2     Server 3
(App + Nginx) (App + Nginx) (App + Nginx)
    ↓            ↓            ↓
Shared PostgreSQL + Shared Redis
```

**Changes needed:**
1. External PostgreSQL and Redis
2. Update DATABASE_URL and REDIS_URL
3. Remove postgres and redis from docker-compose.yml
4. Add load balancer (HAProxy, AWS ELB, etc.)

---

## 📞 Support

### Logs

```bash
# All services
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100 app

# Follow specific service
docker-compose logs -f postgres
```

### Common Commands

```bash
# Restart single service
docker-compose restart app

# Rebuild single service
docker-compose build app
docker-compose up -d app

# Shell access
docker-compose exec app /bin/bash

# Python shell
docker-compose exec app python

# Database shell
docker-compose exec postgres psql -U phishuser -d phishinghunter
```

---

## ✅ Production Checklist

Before going live:

- [ ] Changed all default passwords
- [ ] Set strong SECRET_KEY values
- [ ] Configured HTTPS/SSL
- [ ] Added API keys (optional but recommended)
- [ ] Set up automated backups
- [ ] Configured firewall rules
- [ ] Tested health checks
- [ ] Monitored logs for errors
- [ ] Load tested the application
- [ ] Documented custom configuration
- [ ] Set up monitoring/alerts

---

**Last Updated:** Phase 8 complete  
**Docker Compose Version:** 3.8  
**Production-Ready:** Yes ✅
