# Use an official Python runtime as the base image
FROM python:3.11-slim


# Set environment variables
# - Prevents Python from writing pyc files to disk
# - Ensures stdout and stderr are unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose the port that the app runs on
EXPOSE 8000

# Specify the entrypoint. Using Uvicorn to run the FastAPI app
# It assumes that your FastAPI app is located in app/m3u_filter.py and the FastAPI instance is named 'app'
CMD ["uvicorn", "app.m3u_filter:app", "--host", "0.0.0.0", "--port", "8000"]
