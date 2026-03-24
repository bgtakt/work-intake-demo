FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl
# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py db.py jira.py viz.py feedback.py README.md ./

# Copy static files (documentation)
COPY static/ static/

# Copy Streamlit config (theme + headless settings)
COPY .streamlit/config.toml .streamlit/config.toml

# Create an empty secrets.toml so Streamlit doesn't crash when no secrets are mounted
RUN touch .streamlit/secrets.toml

# Create data directory for SQLite (will be overridden by volume mount)
RUN mkdir -p /app/data

# Expose Streamlit default port
EXPOSE 8501

# Health check: Streamlit exposes /_stcore/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true"]
