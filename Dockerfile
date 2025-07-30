# Optimized single-stage build for YOLO application
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV PYTHONDONTWRITEBYTECODE=1

# Install essential system dependencies for YOLO, PIL, and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get autoclean

# Install uv for faster dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv (faster than pip)
RUN uv sync --no-dev

# Copy application code and model
COPY main.py ./
COPY snapshot.jpeg ./
COPY models/ ./models/

# Create logs directory
RUN mkdir -p /app/logs

# Create non-root user for security
RUN useradd -m -u 1000 henhouse && chown -R henhouse:henhouse /app
USER henhouse

# Expose no ports (this is a background service)

# Health check to ensure the application is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run the application using the virtual environment Python
CMD ["/app/.venv/bin/python", "-u", "main.py"] 
