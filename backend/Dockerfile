FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for rasterio, shapely, psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libgdal-dev \
    gdal-bin \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev

# Copy source
COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
