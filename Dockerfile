# Use official Python base image
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir flask pytest

# Copy all app files
COPY . .

# Expose Flask port
EXPOSE 5000

# Command to run the app
CMD ["python3", "app.py"]
