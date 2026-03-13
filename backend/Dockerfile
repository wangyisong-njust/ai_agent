FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc libffi-dev libssl-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python packages — ignore failures for heavy/optional packages
RUN pip install --no-cache-dir -r requirements.txt 2>&1 || true

# Ensure core packages always installed
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" sqlalchemy aiosqlite \
    httpx "pydantic-settings>=2.0" python-multipart aiofiles \
    "icalendar>=5.0" aiosmtplib chromadb \
    "sentence-transformers" rank-bm25 pymupdf \
    canvasapi beautifulsoup4 lxml

COPY . .

RUN mkdir -p data/uploads

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
