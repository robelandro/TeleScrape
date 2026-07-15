FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if any are needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy english model
RUN python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8000

# Run database migrations and seed before starting uvicorn
CMD ["sh", "-c", "alembic upgrade head && python app/seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
