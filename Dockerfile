FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .
COPY web_main.py .

EXPOSE 8000

# Run the bot
CMD ["python", "web_main.py"] 