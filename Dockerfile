# Video Compressor Docker Image
FROM python:3.11-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    ffmpeg

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-alpine

# Install runtime dependencies
RUN apk add --no-cache ffmpeg

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code
COPY . .

# Expose Gradio port
EXPOSE 7869

# Run the application
CMD ["python", "GradioVideoCompression.py"]
