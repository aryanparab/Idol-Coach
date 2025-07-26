FROM python:3.11-slim

WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (excluding files in .dockerignore)
COPY . .

EXPOSE 8000

# Use uvicorn for FastAPI production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]