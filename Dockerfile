# Imagen de Vigía OCR con Tesseract y Chromium incluidos.
#
#   docker build -t vigia-ocr .                              # ddddocr + Tesseract
#   docker build -t vigia-ocr:completo --build-arg CON_EASYOCR=1 .   # + EasyOCR (PyTorch CPU)
#
# Ejemplos:
#   docker run --rm vigia-ocr --help
#   docker run --rm -v "$PWD/docs:/app/docs" vigia-ocr:completo evaluar --cantidad 300

FROM python:3.15-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# tesseract-ocr: motor OCR. chromium + chromium-driver: navegador del bot.
# libgl1 y libglib2.0-0: dependencias nativas de OpenCV (que ddddocr instala).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr chromium chromium-driver libgl1 libglib2.0-0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

ARG CON_EASYOCR=0
RUN pip install ".[ocr,sqlserver]" \
    && if [ "$CON_EASYOCR" = "1" ]; then \
        pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
        && pip install ".[easyocr]"; \
    fi

COPY datos ./datos

# ~/.EasyOCR guarda los pesos del modelo; móntalo como volumen para no descargarlos cada vez.
RUN useradd --create-home --uid 10001 vigia \
    && mkdir -p /app/docs /home/vigia/.EasyOCR \
    && chown -R vigia /app /home/vigia/.EasyOCR
USER vigia

ENV VIGIA_NAVEGADOR_BINARIO=/usr/bin/chromium \
    VIGIA_CHROMEDRIVER=/usr/bin/chromedriver \
    VIGIA_LOG_FORMATO=json

ENTRYPOINT ["vigia"]
CMD ["--help"]
