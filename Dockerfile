FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY backend ./backend
COPY frontend ./frontend
COPY fixtures ./fixtures
COPY .env.example .env.example

# Set environment defaults
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Start command reads dynamic $PORT if provided by cloud platforms (Render, Railway, Fly.io)
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
