FROM python:3.11-slim

# Set environment variables to prevent hanging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies that might be needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN pip install --upgrade pip

# Install dependencies one by one to identify issues
RUN pip install --no-cache-dir nextcord==2.6.0
RUN pip install --no-cache-dir openai==1.12.0  
RUN pip install --no-cache-dir aiohttp==3.9.1
RUN pip install --no-cache-dir typing-extensions==4.8.0
RUN pip install --no-cache-dir fastapi==0.104.1
RUN pip install --no-cache-dir uvicorn==0.24.0

# Copy application files
COPY main.py .
COPY web_main_simple.py .

EXPOSE 8000

# Run the simplified web server
CMD ["python", "web_main_simple.py"] 