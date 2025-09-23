# 🐳 Docker Containerization Plan for Video Compressor

## 📚 Educational Overview: Understanding Docker

### What is Docker?
Docker is a platform for developing, shipping, and running applications in **containers**. Think of a container as a lightweight, standalone package that includes everything needed to run your application: code, runtime, system tools, libraries, and settings.

### Key Docker Concepts You'll Learn
1. **Images**: Read-only templates containing instructions for creating containers (like a class in OOP)
2. **Containers**: Running instances of images (like objects/instances in OOP)
3. **Dockerfile**: A text file with instructions to build your image (like a recipe)
4. **Volumes**: Persistent data storage that exists outside containers
5. **Port Mapping**: Connecting container ports to host machine ports
6. **Multi-stage Builds**: Building efficient images by separating build and runtime stages

### Why Containerize?
- **Consistency**: "Works on my machine" becomes "works everywhere"
- **Isolation**: Dependencies don't conflict with host system
- **Scalability**: Easy to deploy multiple instances
- **Portability**: Run on any system that supports Docker

---

## 🎯 Project-Specific Architecture

### Application Overview
The Video Compressor is a Python-based video processing application with:
- **Core Engine**: FFmpeg for video processing
- **Web Interface**: Gradio for user interaction
- **Parallel Processing**: Multi-threaded compression for large files
- **File System Access**: Needs to read/write video files from host system

### Containerization Challenges & Solutions

| Challenge | Solution | Learning Point |
|-----------|----------|----------------|
| Large video files | Volume mounting | Containers shouldn't store large data internally |
| FFmpeg dependency | Alpine packages | Base images can include system packages |
| File path access | Bind mounts | Containers can access host filesystem selectively |
| Configuration management | Config volumes | Separate config from code for flexibility |
| Logging persistence | Log volumes | Logs should survive container restarts |

---

## 🏗️ Implementation Plan

### Phase 1: Basic Containerization
**Goal**: Create a working Docker image with all dependencies

#### Step 1.1: Create Dockerfile
```dockerfile
# Dockerfile
# LEARNING: Multi-stage builds reduce image size
FROM python:3.11-alpine AS builder

# LEARNING: Alpine uses 'apk' package manager, not 'apt'
RUN apk add --no-cache \
    ffmpeg \
    gcc \
    musl-dev \
    linux-headers

# LEARNING: WORKDIR sets the working directory for subsequent commands
WORKDIR /app

# LEARNING: Copy dependency files first for better cache utilization
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-alpine
RUN apk add --no-cache ffmpeg

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .

# LEARNING: EXPOSE documents which ports the container listens on
EXPOSE 7869

# LEARNING: CMD specifies default command to run
CMD ["python", "GradioVideoCompression.py"]
```

#### Step 1.2: Create requirements.txt
```text
# requirements.txt
gradio==4.44.0
psutil==5.9.8
# Note: pathlib is part of Python standard library
```

#### Step 1.3: Create .dockerignore
```text
# .dockerignore
# LEARNING: Like .gitignore but for Docker build context
__pycache__/
*.pyc
*.pyo
*.pyd
.git/
.gitignore
logs/
*.mp4
*.mov
*.avi
tests/
.pytest_cache/
```

---

### Phase 2: Volume Management
**Goal**: Enable file processing without copying videos into container

#### Step 2.1: Docker Compose Configuration
```yaml
# docker-compose.yml
version: '3.8'

services:
  video-compressor:
    build: .
    ports:
      - "7869:7869"  # LEARNING: host:container port mapping
    volumes:
      # LEARNING: Bind mounts for file access
      - type: bind
        source: ${VIDEO_INPUT_DIR:-./input}
        target: /videos/input
      - type: bind
        source: ${VIDEO_OUTPUT_DIR:-./output}
        target: /videos/output
      # LEARNING: Named volumes for persistence
      - logs:/app/logs
      - config:/app/config
    environment:
      # LEARNING: Environment variables for configuration
      - PYTHONUNBUFFERED=1
      - VIDEO_BASE_PATH=/videos
    # LEARNING: Resource limits
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G

volumes:
  logs:
  config:
```

#### Step 2.2: Configuration Adaptation
```python
# config_docker.py
# LEARNING: Container-aware configuration
import os
import json

def get_docker_config():
    """Adapt configuration for Docker environment."""
    base_config = {
        "ffmpeg_path": "/usr/bin/ffmpeg",  # Alpine Linux path
        "temp_dir": "/tmp/video_compression",
        "log_dir": "/app/logs",
        "video_base_path": os.getenv("VIDEO_BASE_PATH", "/videos")
    }
    return base_config
```

---

### Phase 3: Development Workflow
**Goal**: Streamline development with Docker

#### Step 3.1: Development Scripts

```bash
#!/bin/bash
# scripts/docker-dev.sh
# LEARNING: Shell scripts automate Docker workflows

# Build the image
echo "🔨 Building Docker image..."
docker build -t video-compressor:dev .

# Run with live code mounting for development
echo "🚀 Starting container with live reload..."
docker run -it --rm \
  -p 7869:7869 \
  -v $(pwd):/app \
  -v ~/Videos:/videos/input \
  -v ~/Videos/Compressed:/videos/output \
  video-compressor:dev
```

#### Step 3.2: Production Build Script
```bash
#!/bin/bash
# scripts/docker-prod.sh
# LEARNING: Production builds optimize for size and security

# Build with BuildKit for better caching
DOCKER_BUILDKIT=1 docker build \
  --target production \
  -t video-compressor:latest \
  -t video-compressor:$(git rev-parse --short HEAD) \
  .

echo "✅ Production image built"
docker images video-compressor
```

---

## 🎓 Docker Commands Cheat Sheet

### Essential Commands for Your Learning Journey

```bash
# Building Images
docker build -t video-compressor .          # Build image with tag
docker build --no-cache -t app .           # Rebuild without cache

# Running Containers
docker run -p 7869:7869 video-compressor   # Run with port mapping
docker run -d --name vc video-compressor   # Run detached with name
docker run -v /local:/container app        # Run with volume mount

# Container Management
docker ps                                   # List running containers
docker ps -a                               # List all containers
docker logs container-name                 # View container logs
docker exec -it container-name sh          # Shell into container
docker stop container-name                 # Stop container
docker rm container-name                   # Remove container

# Image Management
docker images                              # List images
docker rmi image-name                      # Remove image
docker tag old-tag new-tag                 # Retag image

# Docker Compose
docker-compose up                          # Start services
docker-compose down                        # Stop and remove
docker-compose logs -f                     # Follow logs
docker-compose build --no-cache           # Rebuild services
```

---

## 📋 Implementation Checklist

### For Claude Code to Help You Build:

- [ ] **Create Dockerfile**
  - Base image selection (Alpine Linux)
  - FFmpeg installation
  - Python dependencies
  - Application code copy
  - Port exposure
  - Entry point configuration

- [ ] **Create docker-compose.yml**
  - Service definition
  - Volume mappings for videos
  - Port mappings
  - Environment variables
  - Resource limits

- [ ] **Adapt Application Code**
  - Path handling for container environment
  - Configuration loading from environment
  - Graceful shutdown handling
  - Health check endpoint

- [ ] **Create Helper Scripts**
  - Build script with versioning
  - Development run script
  - Production deployment script
  - Container cleanup script

- [ ] **Documentation**
  - README update with Docker instructions
  - Environment variable documentation
  - Volume mounting guide
  - Troubleshooting section

---

## 🚀 Deployment Progression

### Local Development → Docker Hub → Cloud

#### Stage 1: Local Development (Current Focus)
```bash
# Build locally
docker build -t video-compressor .

# Test locally
docker run -p 7869:7869 -v ~/Videos:/videos video-compressor

# Verify functionality
curl http://localhost:7869
```

#### Stage 2: Docker Hub Publication (Future)
```bash
# Tag for Docker Hub
docker tag video-compressor username/video-compressor:latest

# Push to registry
docker push username/video-compressor:latest

# Pull and run anywhere
docker pull username/video-compressor
docker run -p 7869:7869 username/video-compressor
```

#### Stage 3: Cloud Deployment (Future)
```yaml
# kubernetes-deployment.yml example
apiVersion: apps/v1
kind: Deployment
metadata:
  name: video-compressor
spec:
  replicas: 3
  selector:
    matchLabels:
      app: video-compressor
  template:
    metadata:
      labels:
        app: video-compressor
    spec:
      containers:
      - name: video-compressor
        image: username/video-compressor:latest
        ports:
        - containerPort: 7869
```

---

## 🎯 Learning Objectives Achieved

By implementing this plan, you will learn:

1. **Dockerfile Best Practices**
   - Multi-stage builds for optimization
   - Layer caching strategies
   - Security considerations

2. **Volume Management**
   - Bind mounts vs named volumes
   - Data persistence patterns
   - File system permissions

3. **Networking**
   - Port mapping concepts
   - Container networking
   - Service discovery basics

4. **Orchestration Basics**
   - Docker Compose for multi-container apps
   - Environment configuration
   - Resource management

5. **DevOps Workflows**
   - CI/CD pipeline integration
   - Version tagging strategies
   - Registry management

---

## 🔧 Common Issues & Solutions

### Issue 1: FFmpeg Not Found
**Problem**: FFmpeg path differs in container
**Solution**: Use `/usr/bin/ffmpeg` in Alpine
**Learning**: Container filesystems are isolated

### Issue 2: Permission Denied on Videos
**Problem**: Container user can't access host files
**Solution**: Set proper user/group in Dockerfile
**Learning**: Linux permissions apply to containers

### Issue 3: Large Image Size
**Problem**: Image over 1GB
**Solution**: Use Alpine base and multi-stage builds
**Learning**: Smaller images deploy faster

### Issue 4: Lost Processed Videos
**Problem**: Videos disappear when container stops
**Solution**: Use volume mounts for output
**Learning**: Container filesystems are ephemeral

---

## 🎓 Advanced Topics for Future Learning

Once you master the basics, explore:

1. **Container Security**
   - Non-root users
   - Secret management
   - Image scanning

2. **Performance Optimization**
   - Build cache strategies
   - Layer optimization
   - Resource allocation

3. **Orchestration**
   - Kubernetes deployment
   - Docker Swarm
   - Service mesh

4. **CI/CD Integration**
   - GitHub Actions
   - GitLab CI
   - Jenkins pipelines

5. **Monitoring & Logging**
   - Prometheus metrics
   - ELK stack integration
   - Distributed tracing

---

## 📚 Recommended Learning Resources

### Documentation
- [Docker Official Docs](https://docs.docker.com/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Alpine Linux Package Management](https://wiki.alpinelinux.org/wiki/Alpine_Linux_package_management)

### Tutorials
- Docker's official getting started tutorial
- Play with Docker (online playground)
- Docker Mastery course by Bret Fisher

### Books
- "Docker Deep Dive" by Nigel Poulton
- "Docker in Action" by Jeff Nickoloff
- "The Docker Book" by James Turnbull

---

## 🎯 Next Steps

1. **Review this plan** to understand the architecture
2. **Ask Claude Code** to implement Phase 1 (basic Dockerfile)
3. **Test locally** with a small video file
4. **Iterate** based on learnings
5. **Progress** through phases as comfort grows

Remember: Docker is a journey, not a destination. Each container you build teaches you something new about isolation, dependencies, and deployment. This video compressor project is your stepping stone into the world of containerization!

---

*This plan is designed to be both a technical blueprint and an educational guide. Feel free to ask Claude Code to explain any concept in more detail or to help implement specific sections.*