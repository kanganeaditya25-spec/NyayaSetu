FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Set environment variables for headless cloud execution
ENV PYTHONUNBUFFERED=1 \
    PORT=7860 \
    HEADLESS=true

WORKDIR /app

# Copy dependencies manifest and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application codebase
COPY . .

# Expose default cloud container port
EXPOSE 7860

# Run FastAPI app with dynamic port resolution for cloud platforms (Render, HuggingFace, Railway, Cloud Run)
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
