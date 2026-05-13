FROM python:3.11-slim

WORKDIR /app
RUN mkdir -p /app/data

# Dépendances système :
#  - LibreOffice : conversion docx/pptx/xlsx/html/... → PDF avant ingestion
#  - Tesseract + packs FR/EN : OCR multilingue de qualité sur les PDF scannés
#    (Tesseract est nettement plus précis que RapidOCR sur le français accentué)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-core libreoffice-writer libreoffice-calc libreoffice-impress \
        tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng \
        fonts-dejavu fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ENV LIBREOFFICE_BIN=/usr/bin/soffice \
    TESSERACT_BIN=/usr/bin/tesseract \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata/

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
