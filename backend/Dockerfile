FROM python:3.11-slim

WORKDIR /app
RUN mkdir -p /app/data

# LibreOffice pour convertir docx/pptx/xlsx/html/... en PDF avant ingestion
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-core libreoffice-writer libreoffice-calc libreoffice-impress \
        fonts-dejavu fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ENV LIBREOFFICE_BIN=/usr/bin/soffice

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
