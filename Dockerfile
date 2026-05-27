FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright chromium for JS-rendered menus
RUN python -m playwright install --with-deps chromium

COPY . .

EXPOSE 8080
CMD ["uvicorn", "remote_dispensary_scraper:app", "--host", "0.0.0.0", "--port", "8080"]
