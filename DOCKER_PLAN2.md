# 🐳 Docker Mastery - Advanced Learning Chapters

## 📖 How to Use This Document

This document serves as **Chapter 2** of your Docker learning journey. It builds upon the foundation established in `DOCKER_PLAN.md` and provides advanced concepts, practical exercises, and real-world scenarios.

### 📚 Learning Path Integration
```
DOCKER_PLAN.md (Chapters 1-3)
    ↓
🎯 YOU ARE HERE → DOCKER_PLAN2.md (Chapters 4-8)
    ↓
Production Deployment & Orchestration
```

### 🎯 Prerequisites
Before starting these chapters, ensure you've completed:
- ✅ Basic Docker concepts from DOCKER_PLAN.md
- ✅ Built your first Video Compressor container
- ✅ Experimented with the Docker Learning Companion notebook
- ✅ Comfortable with `docker build`, `docker run`, and volume mounting

---

## 📊 Chapter 4: Performance Monitoring & Optimization

### 🎯 Learning Objectives
By the end of this chapter, you'll be able to:
- Monitor container resource usage in real-time
- Identify performance bottlenecks in containerized applications
- Optimize container startup times and resource consumption
- Implement effective logging strategies

### 🔍 4.1: Advanced Container Monitoring

#### Real-Time Performance Tracking
```bash
# Monitor multiple containers simultaneously
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# Export metrics to CSV for analysis
docker stats --no-stream --format "{{.Container}},{{.CPUPerc}},{{.MemUsage}}" > container_metrics.csv

# Monitor specific container with timestamps
while true; do
  echo "$(date): $(docker stats video-compressor --no-stream --format '{{.CPUPerc}} {{.MemUsage}}')"
  sleep 5
done
```

#### Performance Analysis Scripts
```bash
#!/bin/bash
# scripts/monitor-performance.sh
# LEARNING: Automated performance monitoring

CONTAINER_NAME=${1:-video-compressor}
DURATION=${2:-60}
OUTPUT_FILE="performance_$(date +%Y%m%d_%H%M%S).log"

echo "📊 Monitoring $CONTAINER_NAME for ${DURATION}s..."
echo "📝 Output will be saved to $OUTPUT_FILE"

# Header
echo "timestamp,cpu_percent,memory_usage,memory_limit,network_io" > $OUTPUT_FILE

# Monitor loop
for i in $(seq 1 $DURATION); do
  STATS=$(docker stats $CONTAINER_NAME --no-stream --format "{{.CPUPerc}},{{.MemUsage}},{{.NetIO}}")
  echo "$(date +%Y-%m-%d_%H:%M:%S),$STATS" >> $OUTPUT_FILE
  sleep 1
done

echo "✅ Monitoring complete. Check $OUTPUT_FILE for results."
```

### 🚀 4.2: Container Startup Optimization

#### Dockerfile Optimization Techniques
```dockerfile
# Dockerfile.optimized
# LEARNING: Multi-stage builds with optimization focus

# Build stage
FROM python:3.11-alpine AS builder
WORKDIR /app

# Install build dependencies in single layer
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    linux-headers \
    && apk add --no-cache ffmpeg

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-alpine AS production

# Install only runtime dependencies
RUN apk add --no-cache ffmpeg \
    && addgroup -S appgroup \
    && adduser -S appuser -G appgroup

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application with correct ownership
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

# Update PATH for user-installed packages
ENV PATH=/home/appuser/.local/bin:$PATH

# Health check for container readiness
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:7869 || exit 1

EXPOSE 7869
CMD ["python", "GradioVideoCompression.py"]
```

#### Build Time Comparison Script
```bash
#!/bin/bash
# scripts/compare-builds.sh
# LEARNING: Measure optimization impact

echo "🏗️ Docker Build Time Comparison"
echo "================================"

# Build baseline
echo "📦 Building baseline (no optimization)..."
time docker build -f Dockerfile -t video-compressor:baseline . 2>&1 | grep "real\|user\|sys"

# Build optimized
echo "📦 Building optimized version..."
time docker build -f Dockerfile.optimized -t video-compressor:optimized . 2>&1 | grep "real\|user\|sys"

# Compare sizes
echo -e "\n📏 Size Comparison:"
docker images | grep video-compressor | head -2

# Layer analysis
echo -e "\n🔍 Layer Analysis:"
echo "Baseline layers:"
docker history video-compressor:baseline --format "table {{.CreatedBy}}\t{{.Size}}" | head -10

echo -e "\nOptimized layers:"
docker history video-compressor:optimized --format "table {{.CreatedBy}}\t{{.Size}}" | head -10
```

### 📊 4.3: Resource Management & Limits

#### Container Resource Controls
```yaml
# docker-compose.production.yml
# LEARNING: Production-ready resource management

version: '3.8'

services:
  video-compressor:
    build:
      context: .
      dockerfile: Dockerfile.optimized

    # Resource limits and reservations
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
          pids: 100  # Limit number of processes
        reservations:
          cpus: '0.5'
          memory: 512M

    # Restart policy
    restart: unless-stopped

    # Security options
    security_opt:
      - no-new-privileges:true

    # Read-only root filesystem (security)
    read_only: true
    tmpfs:
      - /tmp
      - /var/run

    # Logging configuration
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

    # Environment optimizations
    environment:
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
      - WORKERS=2  # Limit Gradio workers

    volumes:
      - type: bind
        source: ${VIDEO_INPUT_DIR:-./input}
        target: /videos/input
        read_only: true
      - type: bind
        source: ${VIDEO_OUTPUT_DIR:-./output}
        target: /videos/output
      - logs:/app/logs

volumes:
  logs:
    driver: local
```

---

## 🔒 Chapter 5: Security Best Practices

### 🎯 Learning Objectives
- Implement container security hardening
- Understand Linux capabilities and user namespaces
- Scan for vulnerabilities in Docker images
- Secure secrets management in containers

### 🛡️ 5.1: Container Security Hardening

#### Security-First Dockerfile
```dockerfile
# Dockerfile.secure
# LEARNING: Security-focused container design

FROM python:3.11-alpine AS scanner

# Install security scanning tools
RUN apk add --no-cache \
    trivy \
    && rm -rf /var/cache/apk/*

# Scan base image
RUN trivy image --exit-code 1 --severity HIGH,CRITICAL python:3.11-alpine

# Build stage
FROM python:3.11-alpine AS builder

# Create non-root user early
RUN addgroup -S buildgroup && adduser -S builduser -G buildgroup

# Install dependencies as root, then switch
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    linux-headers \
    && apk add --no-cache ffmpeg

USER builduser
WORKDIR /home/builduser/app

# Install Python packages to user directory
COPY --chown=builduser:buildgroup requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-alpine AS production

# Install runtime dependencies only
RUN apk add --no-cache \
    ffmpeg \
    dumb-init \
    && rm -rf /var/cache/apk/*

# Create application user with minimal privileges
RUN addgroup -S appgroup \
    && adduser -S appuser -G appgroup -h /app \
    && mkdir -p /app/logs /app/config \
    && chown -R appuser:appgroup /app

# Copy Python packages from builder
COPY --from=builder /home/builduser/.local /home/appuser/.local

# Copy application files with correct ownership
WORKDIR /app
COPY --chown=appuser:appgroup . .

# Remove any setuid/setgid binaries (security)
RUN find / -type f \( -perm -4000 -o -perm -2000 \) -delete 2>/dev/null || true

# Switch to non-root user
USER appuser

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]

# Drop unnecessary capabilities
# Note: This would be handled by runtime flags in production

EXPOSE 7869
CMD ["python", "GradioVideoCompression.py"]
```

#### Security Scanning Integration
```bash
#!/bin/bash
# scripts/security-scan.sh
# LEARNING: Automated security scanning pipeline

IMAGE_NAME=${1:-video-compressor:latest}

echo "🔒 Security Scanning Pipeline for $IMAGE_NAME"
echo "============================================="

# 1. Scan for known vulnerabilities
echo "📍 Step 1: Vulnerability scanning..."
if command -v trivy &> /dev/null; then
    trivy image --severity HIGH,CRITICAL $IMAGE_NAME
else
    echo "⚠️ Trivy not installed. Install with: brew install aquasecurity/trivy/trivy"
fi

# 2. Check Dockerfile best practices
echo -e "\n📍 Step 2: Dockerfile linting..."
if command -v hadolint &> /dev/null; then
    hadolint Dockerfile.secure
else
    echo "⚠️ Hadolint not installed. Install with: brew install hadolint"
fi

# 3. Analyze image layers for secrets
echo -e "\n📍 Step 3: Secret scanning..."
docker history $IMAGE_NAME --no-trunc | grep -i -E "(password|secret|key|token)" || echo "✅ No obvious secrets found in layers"

# 4. Check running processes
echo -e "\n📍 Step 4: Process analysis..."
CONTAINER_ID=$(docker run -d $IMAGE_NAME sleep 10)
echo "Running processes in container:"
docker exec $CONTAINER_ID ps aux
docker stop $CONTAINER_ID > /dev/null

# 5. File permissions audit
echo -e "\n📍 Step 5: Permission audit..."
docker run --rm $IMAGE_NAME find /app -type f -perm -002 -exec ls -l {} \; | head -10

echo -e "\n✅ Security scan complete!"
```

### 🔐 5.2: Secrets Management

#### Secure Configuration Loading
```python
# config/secure_config.py
# LEARNING: Container-aware secrets management

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any

class SecureConfigLoader:
    """Secure configuration loader for containerized applications."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = {}

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from multiple secure sources."""

        # 1. Load from Docker secrets (production)
        self._load_docker_secrets()

        # 2. Load from environment variables
        self._load_environment()

        # 3. Load from config files (development)
        self._load_config_files()

        # 4. Validate required configuration
        self._validate_config()

        return self.config

    def _load_docker_secrets(self):
        """Load secrets from Docker secrets mount point."""
        secrets_dir = Path("/run/secrets")

        if secrets_dir.exists():
            self.logger.info("Loading Docker secrets...")

            for secret_file in secrets_dir.iterdir():
                if secret_file.is_file():
                    try:
                        secret_value = secret_file.read_text().strip()
                        self.config[secret_file.name] = secret_value
                        self.logger.info(f"Loaded secret: {secret_file.name}")
                    except Exception as e:
                        self.logger.error(f"Failed to load secret {secret_file.name}: {e}")

    def _load_environment(self):
        """Load configuration from environment variables."""
        env_mappings = {
            "FFMPEG_PATH": "ffmpeg_path",
            "VIDEO_BASE_PATH": "video_base_path",
            "LOG_LEVEL": "log_level",
            "MAX_FILE_SIZE": "max_file_size",
            "ALLOWED_EXTENSIONS": "allowed_extensions"
        }

        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                self.config[config_key] = value
                self.logger.info(f"Loaded from env: {config_key}")

    def _load_config_files(self):
        """Load configuration from files (development only)."""
        config_files = [
            "/app/config/app.json",
            "/app/secrets.json",  # Development fallback
            "./config.json"
        ]

        for config_file in config_files:
            path = Path(config_file)
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        file_config = json.load(f)
                        self.config.update(file_config)
                        self.logger.info(f"Loaded config from: {config_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to load {config_file}: {e}")

    def _validate_config(self):
        """Validate that required configuration is present."""
        required_keys = ["ffmpeg_path", "video_base_path"]

        missing_keys = [key for key in required_keys if key not in self.config]

        if missing_keys:
            raise ValueError(f"Missing required configuration: {missing_keys}")

        self.logger.info("Configuration validation passed")

    def get_safe_config(self) -> Dict[str, Any]:
        """Return config with sensitive values masked."""
        safe_config = {}
        sensitive_keys = ["api_key", "password", "secret", "token"]

        for key, value in self.config.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                safe_config[key] = "***REDACTED***"
            else:
                safe_config[key] = value

        return safe_config

# Usage in your application
if __name__ == "__main__":
    loader = SecureConfigLoader()
    config = loader.load_config()

    # Log safe configuration
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info(f"Application config: {loader.get_safe_config()}")
```

---

## 🌐 Chapter 6: Advanced Networking & Multi-Container Applications

### 🎯 Learning Objectives
- Design multi-container application architectures
- Implement custom Docker networks
- Set up service discovery and load balancing
- Create production-ready Docker Compose configurations

### 🔗 6.1: Custom Networks and Service Discovery

#### Advanced Docker Compose Configuration
```yaml
# docker-compose.advanced.yml
# LEARNING: Multi-container production architecture

version: '3.8'

# Custom networks for service isolation
networks:
  frontend:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
  backend:
    driver: bridge
    internal: true  # No external access
    ipam:
      config:
        - subnet: 172.21.0.0/16

services:
  # Reverse proxy and load balancer
  nginx-proxy:
    image: nginx:alpine
    container_name: video-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - logs:/var/log/nginx
    networks:
      - frontend
    depends_on:
      - video-compressor-1
      - video-compressor-2
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "nginx", "-t"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Primary video compression service
  video-compressor-1:
    build:
      context: .
      dockerfile: Dockerfile.secure
    container_name: video-compressor-1
    networks:
      - frontend
      - backend
    volumes:
      - type: bind
        source: ${VIDEO_INPUT_DIR:-./input}
        target: /videos/input
        read_only: true
      - type: bind
        source: ${VIDEO_OUTPUT_DIR:-./output}
        target: /videos/output
      - logs:/app/logs
    environment:
      - INSTANCE_ID=compressor-1
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:pass@postgres:5432/videoapp
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G

  # Secondary video compression service (scaling)
  video-compressor-2:
    build:
      context: .
      dockerfile: Dockerfile.secure
    container_name: video-compressor-2
    networks:
      - frontend
      - backend
    volumes:
      - type: bind
        source: ${VIDEO_INPUT_DIR:-./input}
        target: /videos/input
        read_only: true
      - type: bind
        source: ${VIDEO_OUTPUT_DIR:-./output}
        target: /videos/output
      - logs:/app/logs
    environment:
      - INSTANCE_ID=compressor-2
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:pass@postgres:5432/videoapp
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G

  # Redis for caching and job queues
  redis:
    image: redis:7-alpine
    container_name: video-redis
    networks:
      - backend
    volumes:
      - redis_data:/data
      - ./redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
    command: redis-server /usr/local/etc/redis/redis.conf
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  # PostgreSQL for metadata and job tracking
  postgres:
    image: postgres:15-alpine
    container_name: video-postgres
    networks:
      - backend
    environment:
      - POSTGRES_DB=videoapp
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
    secrets:
      - postgres_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d videoapp"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Monitoring and metrics
  prometheus:
    image: prom/prometheus:latest
    container_name: video-prometheus
    networks:
      - backend
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: video-grafana
    networks:
      - frontend
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana-datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml:ro
    environment:
      - GF_SECURITY_ADMIN_PASSWORD_FILE=/run/secrets/grafana_password
    secrets:
      - grafana_password
    restart: unless-stopped

# Secrets management
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  grafana_password:
    file: ./secrets/grafana_password.txt

# Persistent volumes
volumes:
  logs:
    driver: local
  redis_data:
    driver: local
  postgres_data:
    driver: local
  prometheus_data:
    driver: local
  grafana_data:
    driver: local
```

#### Nginx Load Balancer Configuration
```nginx
# nginx/nginx.conf
# LEARNING: Container-aware load balancing

upstream video_compressor {
    least_conn;  # Load balancing method
    server video-compressor-1:7869 max_fails=3 fail_timeout=30s;
    server video-compressor-2:7869 max_fails=3 fail_timeout=30s;

    # Health check endpoint
    keepalive 32;
}

server {
    listen 80;
    server_name localhost;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    # Main application
    location / {
        limit_req zone=api burst=20 nodelay;

        proxy_pass http://video_compressor;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support for Gradio
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts for large file uploads
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;

        # Large file upload support
        client_max_body_size 100M;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://video_compressor/health;
        access_log off;
    }

    # Monitoring endpoint (internal only)
    location /metrics {
        allow 172.20.0.0/16;  # Only from frontend network
        deny all;
        proxy_pass http://video_compressor/metrics;
    }
}

# Logging
error_log /var/log/nginx/error.log warn;
access_log /var/log/nginx/access.log combined;
```

### 📊 6.2: Service Discovery and Health Checks

#### Health Check Implementation
```python
# health_check.py
# LEARNING: Container health monitoring

from flask import Flask, jsonify
import psutil
import os
import subprocess
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/health')
def health_check():
    """Comprehensive health check endpoint."""

    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "instance_id": os.getenv("INSTANCE_ID", "unknown"),
        "checks": {}
    }

    # Check 1: System resources
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        health_status["checks"]["resources"] = {
            "status": "healthy",
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "disk_percent": (disk.used / disk.total) * 100
        }

        # Mark as unhealthy if resources are too high
        if cpu_percent > 90 or memory.percent > 90:
            health_status["checks"]["resources"]["status"] = "unhealthy"
            health_status["status"] = "unhealthy"

    except Exception as e:
        health_status["checks"]["resources"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"

    # Check 2: FFmpeg availability
    try:
        result = subprocess.run(['ffmpeg', '-version'],
                              capture_output=True, text=True, timeout=5)
        health_status["checks"]["ffmpeg"] = {
            "status": "healthy" if result.returncode == 0 else "unhealthy",
            "version": result.stdout.split('\n')[0] if result.returncode == 0 else None
        }

        if result.returncode != 0:
            health_status["status"] = "unhealthy"

    except Exception as e:
        health_status["checks"]["ffmpeg"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"

    # Check 3: Database connectivity (if configured)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            # Simple connection test
            import psycopg2
            conn = psycopg2.connect(db_url)
            conn.close()
            health_status["checks"]["database"] = {"status": "healthy"}
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"

    # Check 4: Redis connectivity (if configured)
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis
            r = redis.from_url(redis_url)
            r.ping()
            health_status["checks"]["redis"] = {"status": "healthy"}
        except Exception as e:
            health_status["checks"]["redis"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"

    # Return appropriate HTTP status code
    status_code = 200 if health_status["status"] == "healthy" else 503
    return jsonify(health_status), status_code

@app.route('/metrics')
def metrics():
    """Prometheus-compatible metrics endpoint."""

    metrics_data = []

    # System metrics
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()

    metrics_data.extend([
        f"# HELP cpu_usage_percent Current CPU usage percentage",
        f"# TYPE cpu_usage_percent gauge",
        f"cpu_usage_percent {cpu_percent}",
        f"",
        f"# HELP memory_usage_percent Current memory usage percentage",
        f"# TYPE memory_usage_percent gauge",
        f"memory_usage_percent {memory.percent}",
        f"",
        f"# HELP memory_usage_bytes Current memory usage in bytes",
        f"# TYPE memory_usage_bytes gauge",
        f"memory_usage_bytes {memory.used}",
    ])

    return '\n'.join(metrics_data), 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

---

## 🚀 Chapter 7: CI/CD Integration & Automated Deployments

### 🎯 Learning Objectives
- Set up automated Docker builds with GitHub Actions
- Implement multi-stage deployment pipelines
- Create automated testing in containerized environments
- Deploy containers to cloud platforms

### ⚙️ 7.1: GitHub Actions CI/CD Pipeline

#### Complete CI/CD Workflow
```yaml
# .github/workflows/docker-ci-cd.yml
# LEARNING: Production Docker CI/CD pipeline

name: Docker CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov flake8

    - name: Lint code
      run: flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

    - name: Run tests
      run: pytest --cov=. --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  security-scan:
    runs-on: ubuntu-latest
    needs: test

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'
        format: 'sarif'
        output: 'trivy-results.sarif'

    - name: Upload Trivy scan results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'

  build:
    runs-on: ubuntu-latest
    needs: [test, security-scan]

    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
      image-digest: ${{ steps.build.outputs.digest }}

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}
          type=sha,prefix={{branch}}-

    - name: Build and push Docker image
      id: build
      uses: docker/build-push-action@v5
      with:
        context: .
        file: ./Dockerfile.secure
        platforms: linux/amd64,linux/arm64
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

    - name: Generate SBOM
      uses: anchore/sbom-action@v0
      with:
        image: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
        format: spdx-json
        output-file: sbom.spdx.json

    - name: Upload SBOM
      uses: actions/upload-artifact@v3
      with:
        name: sbom
        path: sbom.spdx.json

  integration-test:
    runs-on: ubuntu-latest
    needs: build

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Pull built image
      run: docker pull ${{ needs.build.outputs.image-tag }}

    - name: Run integration tests
      run: |
        # Start the application stack
        docker-compose -f docker-compose.test.yml up -d

        # Wait for services to be ready
        sleep 30

        # Run integration tests
        docker-compose -f docker-compose.test.yml exec -T video-compressor python -m pytest tests/integration/

        # Cleanup
        docker-compose -f docker-compose.test.yml down -v

  deploy-staging:
    runs-on: ubuntu-latest
    needs: [build, integration-test]
    if: github.ref == 'refs/heads/develop'
    environment: staging

    steps:
    - name: Deploy to staging
      run: |
        echo "Deploying ${{ needs.build.outputs.image-tag }} to staging..."
        # Add your staging deployment logic here
        # Examples: kubectl, docker-compose, cloud provider CLI

    - name: Run smoke tests
      run: |
        echo "Running smoke tests against staging..."
        # Add smoke test logic here

  deploy-production:
    runs-on: ubuntu-latest
    needs: [build, integration-test]
    if: startsWith(github.ref, 'refs/tags/v')
    environment: production

    steps:
    - name: Deploy to production
      run: |
        echo "Deploying ${{ needs.build.outputs.image-tag }} to production..."
        # Add your production deployment logic here

    - name: Notify deployment
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        text: "🚀 Video Compressor deployed to production: ${{ needs.build.outputs.image-tag }}"
      env:
        SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

#### Integration Test Configuration
```yaml
# docker-compose.test.yml
# LEARNING: Automated testing environment

version: '3.8'

services:
  video-compressor:
    image: ${DOCKER_IMAGE:-video-compressor:latest}
    environment:
      - TESTING=true
      - DATABASE_URL=postgresql://test:test@postgres:5432/testdb
      - REDIS_URL=redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./tests/fixtures:/videos/input
      - test_output:/videos/output
    networks:
      - test_network

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=testdb
      - POSTGRES_USER=test
      - POSTGRES_PASSWORD=test
    networks:
      - test_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test -d testdb"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    networks:
      - test_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

networks:
  test_network:
    driver: bridge

volumes:
  test_output:
```

### 🔄 7.2: Automated Testing Strategies

#### Container Testing Framework
```python
# tests/integration/test_docker_integration.py
# LEARNING: Testing containerized applications

import pytest
import requests
import docker
import time
import subprocess
import os
from pathlib import Path

class TestDockerIntegration:
    """Integration tests for the containerized Video Compressor."""

    @classmethod
    def setup_class(cls):
        """Set up test environment."""
        cls.client = docker.from_env()
        cls.base_url = "http://localhost:7869"
        cls.container = None

    @classmethod
    def teardown_class(cls):
        """Clean up test environment."""
        if cls.container:
            cls.container.stop()
            cls.container.remove()

    def test_container_startup(self):
        """Test that container starts successfully."""
        # Start container
        self.container = self.client.containers.run(
            "video-compressor:latest",
            ports={'7869/tcp': 7869},
            detach=True,
            environment={
                'TESTING': 'true'
            }
        )

        # Wait for startup
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                time.sleep(2)
        else:
            pytest.fail("Container failed to start within timeout")

    def test_health_check_endpoint(self):
        """Test health check endpoint."""
        response = requests.get(f"{self.base_url}/health")
        assert response.status_code == 200

        health_data = response.json()
        assert health_data['status'] == 'healthy'
        assert 'checks' in health_data
        assert 'ffmpeg' in health_data['checks']

    def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        response = requests.get(f"{self.base_url}/metrics")
        assert response.status_code == 200
        assert 'cpu_usage_percent' in response.text
        assert 'memory_usage_percent' in response.text

    def test_file_upload_processing(self):
        """Test video file upload and processing."""
        # Create a test video file
        test_video = self.create_test_video()

        try:
            # Upload test video
            with open(test_video, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    f"{self.base_url}/upload",
                    files=files,
                    timeout=60
                )

            assert response.status_code == 200

            # Check processing result
            result = response.json()
            assert 'output_file' in result
            assert result['status'] == 'success'

        finally:
            # Clean up test file
            if test_video.exists():
                test_video.unlink()

    def test_container_resource_limits(self):
        """Test that container respects resource limits."""
        # Get container stats
        stats = self.container.stats(stream=False)

        # Check memory usage
        memory_usage = stats['memory_stats']['usage']
        memory_limit = stats['memory_stats']['limit']
        memory_percent = (memory_usage / memory_limit) * 100

        # Should not exceed 90% of limit
        assert memory_percent < 90, f"Memory usage too high: {memory_percent}%"

    def test_container_security(self):
        """Test security configuration."""
        # Check that container is not running as root
        exec_result = self.container.exec_run("whoami")
        assert exec_result.output.decode().strip() != "root"

        # Check that sensitive files are not accessible
        exec_result = self.container.exec_run("ls -la /etc/shadow")
        assert exec_result.exit_code != 0  # Should fail

    def create_test_video(self) -> Path:
        """Create a small test video file."""
        test_file = Path("/tmp/test_video.mp4")

        # Create a 5-second test video using FFmpeg
        cmd = [
            "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=5:size=320x240:rate=1",
            "-c:v", "libx264", "-t", "5", "-pix_fmt", "yuv420p", "-y", str(test_file)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        return test_file

class TestDockerCompose:
    """Test Docker Compose multi-container setup."""

    def test_compose_startup(self):
        """Test that all services start correctly."""
        # Start compose stack
        result = subprocess.run(
            ["docker-compose", "-f", "docker-compose.test.yml", "up", "-d"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

        try:
            # Wait for services
            time.sleep(30)

            # Check all services are healthy
            result = subprocess.run(
                ["docker-compose", "-f", "docker-compose.test.yml", "ps"],
                capture_output=True,
                text=True
            )

            # All services should be up
            assert "Up" in result.stdout
            assert "Exit" not in result.stdout

        finally:
            # Clean up
            subprocess.run(
                ["docker-compose", "-f", "docker-compose.test.yml", "down", "-v"],
                capture_output=True
            )

    def test_service_communication(self):
        """Test that services can communicate with each other."""
        # Start compose stack
        subprocess.run(
            ["docker-compose", "-f", "docker-compose.test.yml", "up", "-d"],
            check=True,
            capture_output=True
        )

        try:
            time.sleep(30)

            # Test database connection from app
            result = subprocess.run([
                "docker-compose", "-f", "docker-compose.test.yml", "exec", "-T",
                "video-compressor", "python", "-c",
                "import psycopg2; conn = psycopg2.connect('postgresql://test:test@postgres:5432/testdb'); print('DB OK')"
            ], capture_output=True, text=True)

            assert result.returncode == 0
            assert "DB OK" in result.stdout

        finally:
            subprocess.run(
                ["docker-compose", "-f", "docker-compose.test.yml", "down", "-v"],
                capture_output=True
            )

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## 📊 Chapter 8: Troubleshooting & Production Operations

### 🎯 Learning Objectives
- Master Docker debugging techniques
- Implement effective logging and monitoring
- Handle production incidents efficiently
- Optimize container performance in production

### 🔧 8.1: Advanced Debugging Techniques

#### Comprehensive Debugging Toolkit
```bash
#!/bin/bash
# scripts/docker-debug.sh
# LEARNING: Production Docker debugging toolkit

CONTAINER_NAME=${1:-video-compressor}
DEBUG_MODE=${2:-basic}

echo "🔍 Docker Debugging Toolkit"
echo "=========================="
echo "Container: $CONTAINER_NAME"
echo "Mode: $DEBUG_MODE"
echo ""

# Function to get container ID
get_container_id() {
    docker ps -q -f "name=$CONTAINER_NAME" | head -1
}

# Function for basic debugging
basic_debug() {
    local container_id=$(get_container_id)

    if [ -z "$container_id" ]; then
        echo "❌ Container '$CONTAINER_NAME' not found or not running"
        echo "📋 Available containers:"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
        return 1
    fi

    echo "📊 Container Status:"
    docker ps -f "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    echo -e "\n💾 Resource Usage:"
    docker stats $CONTAINER_NAME --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

    echo -e "\n📋 Recent Logs (last 50 lines):"
    docker logs $CONTAINER_NAME --tail 50 --timestamps

    echo -e "\n🔍 Container Inspection:"
    docker inspect $CONTAINER_NAME --format '{{json .State}}' | jq '.'
}

# Function for advanced debugging
advanced_debug() {
    basic_debug

    local container_id=$(get_container_id)
    [ -z "$container_id" ] && return 1

    echo -e "\n🌐 Network Information:"
    docker inspect $CONTAINER_NAME --format '{{json .NetworkSettings}}' | jq '.Networks'

    echo -e "\n📁 Volume Mounts:"
    docker inspect $CONTAINER_NAME --format '{{json .Mounts}}' | jq '.[]'

    echo -e "\n⚙️ Environment Variables:"
    docker inspect $CONTAINER_NAME --format '{{json .Config.Env}}' | jq '.[]'

    echo -e "\n🔒 Security Information:"
    docker inspect $CONTAINER_NAME --format '{{json .HostConfig}}' | jq '{SecurityOpt, ReadonlyRootfs, User}'

    echo -e "\n📊 Image Layers:"
    IMAGE=$(docker inspect $CONTAINER_NAME --format '{{.Config.Image}}')
    docker history $IMAGE --no-trunc
}

# Function for deep debugging (performance analysis)
deep_debug() {
    advanced_debug

    local container_id=$(get_container_id)
    [ -z "$container_id" ] && return 1

    echo -e "\n🔬 Deep System Analysis:"

    echo "Process tree inside container:"
    docker exec $CONTAINER_NAME ps auxf

    echo -e "\nFile descriptor usage:"
    docker exec $CONTAINER_NAME sh -c 'ls /proc/*/fd | wc -l'

    echo -e "\nNetwork connections:"
    docker exec $CONTAINER_NAME netstat -tuln

    echo -e "\nDisk usage in container:"
    docker exec $CONTAINER_NAME df -h

    echo -e "\n📈 Performance Monitoring (10 seconds):"
    docker exec $CONTAINER_NAME top -b -n 2 -d 5
}

# Function to analyze container logs
analyze_logs() {
    local container_id=$(get_container_id)
    [ -z "$container_id" ] && return 1

    echo "📊 Log Analysis for $CONTAINER_NAME"
    echo "=================================="

    # Error analysis
    echo "🚨 Error Count:"
    docker logs $CONTAINER_NAME 2>&1 | grep -i error | wc -l

    echo -e "\n🚨 Recent Errors:"
    docker logs $CONTAINER_NAME 2>&1 | grep -i error | tail -10

    # Warning analysis
    echo -e "\n⚠️ Warning Count:"
    docker logs $CONTAINER_NAME 2>&1 | grep -i warning | wc -l

    # Memory-related issues
    echo -e "\n💾 Memory-related logs:"
    docker logs $CONTAINER_NAME 2>&1 | grep -i -E "memory|oom|killed" | tail -10

    # Network-related issues
    echo -e "\n🌐 Network-related logs:"
    docker logs $CONTAINER_NAME 2>&1 | grep -i -E "connection|timeout|refused" | tail -10

    # Log size analysis
    echo -e "\n📏 Log Size Analysis:"
    LOG_SIZE=$(docker inspect $CONTAINER_NAME --format='{{.LogPath}}' | xargs ls -lh | awk '{print $5}')
    echo "Log file size: $LOG_SIZE"
}

# Function to test container connectivity
test_connectivity() {
    local container_id=$(get_container_id)
    [ -z "$container_id" ] && return 1

    echo "🌐 Connectivity Tests for $CONTAINER_NAME"
    echo "======================================="

    # Test internal connectivity
    echo "📡 Internal network test:"
    docker exec $CONTAINER_NAME ping -c 3 google.com || echo "❌ External connectivity failed"

    # Test service ports
    echo -e "\n🔌 Port connectivity:"
    EXPOSED_PORTS=$(docker inspect $CONTAINER_NAME --format='{{json .Config.ExposedPorts}}' | jq -r 'keys[]' 2>/dev/null)

    for port in $EXPOSED_PORTS; do
        PORT_NUM=$(echo $port | cut -d'/' -f1)
        echo -n "Testing port $PORT_NUM: "
        if docker exec $CONTAINER_NAME netstat -tln | grep ":$PORT_NUM " > /dev/null; then
            echo "✅ Listening"
        else
            echo "❌ Not listening"
        fi
    done

    # Test database connectivity (if applicable)
    if docker exec $CONTAINER_NAME printenv | grep -q DATABASE_URL; then
        echo -e "\n🗃️ Database connectivity test:"
        docker exec $CONTAINER_NAME python -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
" 2>/dev/null || echo "❌ Database test failed"
    fi
}

# Function to create debugging snapshot
create_snapshot() {
    local container_id=$(get_container_id)
    [ -z "$container_id" ] && return 1

    local snapshot_dir="debug_snapshot_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$snapshot_dir"

    echo "📸 Creating debugging snapshot in $snapshot_dir/"

    # Container information
    docker inspect $CONTAINER_NAME > "$snapshot_dir/container_inspect.json"
    docker logs $CONTAINER_NAME > "$snapshot_dir/container_logs.txt" 2>&1
    docker stats $CONTAINER_NAME --no-stream > "$snapshot_dir/container_stats.txt"

    # System information inside container
    docker exec $CONTAINER_NAME ps auxf > "$snapshot_dir/processes.txt" 2>/dev/null
    docker exec $CONTAINER_NAME df -h > "$snapshot_dir/disk_usage.txt" 2>/dev/null
    docker exec $CONTAINER_NAME netstat -tuln > "$snapshot_dir/network_connections.txt" 2>/dev/null
    docker exec $CONTAINER_NAME env > "$snapshot_dir/environment.txt" 2>/dev/null

    # Image information
    IMAGE=$(docker inspect $CONTAINER_NAME --format '{{.Config.Image}}')
    docker history $IMAGE > "$snapshot_dir/image_history.txt"
    docker inspect $IMAGE > "$snapshot_dir/image_inspect.json"

    # System resources
    docker system df > "$snapshot_dir/system_usage.txt"
    docker system events --since '1h' > "$snapshot_dir/system_events.txt" &
    sleep 2
    pkill -f "docker system events"

    echo "✅ Snapshot saved to $snapshot_dir/"
    echo "📋 Files created:"
    ls -la "$snapshot_dir/"
}

# Main execution
case $DEBUG_MODE in
    "basic")
        basic_debug
        ;;
    "advanced")
        advanced_debug
        ;;
    "deep")
        deep_debug
        ;;
    "logs")
        analyze_logs
        ;;
    "connectivity")
        test_connectivity
        ;;
    "snapshot")
        create_snapshot
        ;;
    "all")
        echo "🚀 Running comprehensive debugging..."
        deep_debug
        echo -e "\n" && analyze_logs
        echo -e "\n" && test_connectivity
        echo -e "\n" && create_snapshot
        ;;
    *)
        echo "Usage: $0 <container_name> [basic|advanced|deep|logs|connectivity|snapshot|all]"
        echo ""
        echo "Modes:"
        echo "  basic        - Basic container status and logs"
        echo "  advanced     - Detailed configuration and network info"
        echo "  deep         - Performance analysis and system details"
        echo "  logs         - Comprehensive log analysis"
        echo "  connectivity - Network and service connectivity tests"
        echo "  snapshot     - Create complete debugging snapshot"
        echo "  all          - Run all debugging modes"
        exit 1
        ;;
esac
```

### 📈 8.2: Production Monitoring and Alerting

#### Monitoring Stack Configuration
```yaml
# monitoring/docker-compose.monitoring.yml
# LEARNING: Production monitoring stack

version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus/rules/:/etc/prometheus/rules/:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
      - '--web.enable-lifecycle'
      - '--web.enable-admin-api'
    networks:
      - monitoring
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/datasources/:/etc/grafana/provisioning/datasources/:ro
      - ./grafana/dashboards/:/etc/grafana/provisioning/dashboards/:ro
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_INSTALL_PLUGINS=grafana-clock-panel,grafana-simple-json-datasource
    networks:
      - monitoring
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
      - '--web.external-url=http://localhost:9093'
    networks:
      - monitoring
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    networks:
      - monitoring
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:rw
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    privileged: true
    devices:
      - /dev/kmsg
    networks:
      - monitoring
    restart: unless-stopped

networks:
  monitoring:
    driver: bridge

volumes:
  prometheus_data:
  grafana_data:
  alertmanager_data:
```

#### Alert Rules Configuration
```yaml
# prometheus/rules/docker_alerts.yml
# LEARNING: Production alerting rules

groups:
- name: docker_alerts
  rules:

  # Container down alert
  - alert: ContainerDown
    expr: up{job="docker"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Container {{ $labels.instance }} is down"
      description: "Container {{ $labels.instance }} has been down for more than 1 minute."

  # High CPU usage
  - alert: HighCPUUsage
    expr: rate(container_cpu_usage_seconds_total[5m]) * 100 > 80
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU usage on {{ $labels.name }}"
      description: "Container {{ $labels.name }} CPU usage is above 80% for more than 5 minutes."

  # High memory usage
  - alert: HighMemoryUsage
    expr: (container_memory_usage_bytes / container_spec_memory_limit_bytes) * 100 > 90
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "High memory usage on {{ $labels.name }}"
      description: "Container {{ $labels.name }} memory usage is above 90% for more than 2 minutes."

  # Container restart alert
  - alert: ContainerRestarts
    expr: increase(container_restart_count[1h]) > 3
    for: 0m
    labels:
      severity: warning
    annotations:
      summary: "Container {{ $labels.name }} restarting frequently"
      description: "Container {{ $labels.name }} has restarted {{ $value }} times in the last hour."

  # Disk usage alert
  - alert: HighDiskUsage
    expr: (node_filesystem_size_bytes - node_filesystem_avail_bytes) / node_filesystem_size_bytes * 100 > 85
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High disk usage on {{ $labels.instance }}"
      description: "Disk usage is above 85% on {{ $labels.instance }}."

  # Application-specific alerts
  - alert: VideoProcessingBacklog
    expr: video_processing_queue_size > 10
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Video processing backlog building up"
      description: "There are {{ $value }} videos in the processing queue for more than 5 minutes."

  - alert: FFmpegProcessFailures
    expr: rate(ffmpeg_process_failures_total[5m]) > 0.1
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "High FFmpeg failure rate"
      description: "FFmpeg processes are failing at a rate of {{ $value }} per second."
```

---

## 🎯 Next Steps and Mastery Path

### 🚀 Congratulations on Completing Advanced Docker Learning!

By working through both DOCKER_PLAN.md and DOCKER_PLAN2.md, you've gained comprehensive knowledge of:

✅ **Foundation Skills** (Plan 1):
- Docker basics and containerization concepts
- Building and optimizing Docker images
- Volume management and networking
- Basic orchestration with Docker Compose

✅ **Advanced Skills** (Plan 2):
- Performance monitoring and optimization
- Security hardening and best practices
- Multi-container architectures
- CI/CD integration and automation
- Production troubleshooting and operations

### 🎓 Your Docker Mastery Roadmap

#### Level 1: Container Specialist (Completed)
- ✅ Can containerize any application
- ✅ Understands Docker networking and volumes
- ✅ Implements security best practices
- ✅ Monitors and debugs containers effectively

#### Level 2: Orchestration Expert (Next Steps)
- 🎯 **Kubernetes Fundamentals**
  - Pods, Services, and Deployments
  - ConfigMaps and Secrets
  - Ingress and LoadBalancing

- 🎯 **Advanced Orchestration**
  - Helm charts and package management
  - Custom Resource Definitions (CRDs)
  - Operators and automation

#### Level 3: Platform Engineer (Advanced)
- 🎯 **Service Mesh** (Istio, Linkerd)
- 🎯 **GitOps** (ArgoCD, Flux)
- 🎯 **Observability** (Jaeger, OpenTelemetry)
- 🎯 **Security** (Falco, OPA/Gatekeeper)

### 📚 Recommended Learning Resources

#### Books
- "Kubernetes in Action" by Marko Lukša
- "Docker Deep Dive" by Nigel Poulton
- "Site Reliability Engineering" by Google

#### Hands-On Platforms
- [Katacoda Docker Scenarios](https://www.katacoda.com/courses/docker)
- [Play with Kubernetes](https://labs.play-with-k8s.com/)
- [KodeKloud](https://kodekloud.com/) - Hands-on DevOps training

#### Projects to Build
1. 🎯 **Multi-tier Web Application**
   - Frontend (React/Vue)
   - Backend API (FastAPI/Express)
   - Database (PostgreSQL)
   - Redis cache
   - Nginx reverse proxy

2. 🎯 **Microservices E-commerce Platform**
   - User service
   - Product catalog
   - Order management
   - Payment processing
   - API Gateway

3. 🎯 **CI/CD Pipeline**
   - Automated testing
   - Security scanning
   - Multi-environment deployment
   - Rollback capabilities

### 🏆 Certification Paths

Consider pursuing these industry certifications:
- **Docker Certified Associate (DCA)**
- **Certified Kubernetes Administrator (CKA)**
- **Certified Kubernetes Application Developer (CKAD)**
- **AWS/GCP/Azure Container certifications**

---

## 🎊 Final Thoughts

You've now completed a comprehensive journey through Docker containerization, from basic concepts to production-ready implementations. The combination of theoretical knowledge, hands-on practice, and real-world scenarios has prepared you for professional Docker usage.

### Key Takeaways:
1. **Start Simple**: Every complex system begins with simple containers
2. **Security First**: Always implement security from the beginning
3. **Monitor Everything**: Observability is crucial for production success
4. **Automate Relentlessly**: CI/CD pipelines save time and reduce errors
5. **Practice Continuously**: Technology evolves rapidly - keep learning

### Community Resources:
- [Docker Community](https://www.docker.com/community)
- [Stack Overflow Docker Tag](https://stackoverflow.com/questions/tagged/docker)
- [Reddit r/docker](https://www.reddit.com/r/docker/)
- [CNCF Community](https://www.cncf.io/community/)

Remember: The best way to master Docker is by containerizing real applications and solving actual problems. Take what you've learned and apply it to your own projects!

🐳 **Happy Dockerizing!** 🐳

---

*This document represents the culmination of your Docker learning journey. Keep it as a reference guide and continue building upon these foundations as you advance in your containerization expertise.*