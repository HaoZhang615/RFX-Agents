# Use Python 3.10 slim as the base image for better efficiency
FROM python:3.10-slim

# Label for maintainability
LABEL maintainer="RFX-Agents Team"
LABEL description="Multi-agent system for Microsoft RFX situations"

# Environment variables to control Python behavior
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Prevents Python from buffering stdout and stderr
    PYTHONFAULTHANDLER=1 \
    # Installs pip packages to the local user directory
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Set working directory
WORKDIR /app

# Copy requirements file first for better layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables for Streamlit
ENV STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Expose port for Streamlit
EXPOSE 8501

# Set non-root user for better security
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Health check to verify the service is running properly
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Command to run the application
CMD ["streamlit", "run", "rfx_multiagent_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]