FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./etl/

# Run as non-root
RUN useradd -m etluser
USER etluser

ENV PYTHONPATH=/app
CMD ["python", "-m", "etl.main"]
