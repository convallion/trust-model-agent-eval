FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including tools for terminal)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    vim \
    less \
    procps \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application code
COPY . .

# Create non-root user with home directory for terminal
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app && \
    echo "export PS1='\\[\\033[01;32m\\]trustmodel\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ '" >> /home/appuser/.bashrc && \
    echo "alias ll='ls -la'" >> /home/appuser/.bashrc

# Switch to non-root user
USER appuser

# Keep working directory as /app for the application
WORKDIR /app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
