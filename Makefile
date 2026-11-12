.DEFAULT_GOAL := help
PY ?= python
MUESTRAS ?= 500
SEMILLA ?= 2026

help: ## Lista los comandos disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Instala el paquete con motores livianos (ddddocr, Tesseract) y herramientas de desarrollo
	$(PY) -m pip install -e ".[ocr,dev]"
	pre-commit install || true

install-completo: ## Agrega EasyOCR (PyTorch CPU, ~1 GB)
	$(PY) -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
	$(PY) -m pip install -e ".[ocr,easyocr,sqlserver,dev]"

lint: ## Ruff (lint + formato) y mypy estricto
	ruff check .
	ruff format --check .
	mypy src

format: ## Formatea el código
	ruff check --fix .
	ruff format .

test: ## Pruebas unitarias con cobertura (sin servicios ni motores reales)
	pytest --cov

test-ocr: ## Motores OCR reales (requiere .[ocr] y el binario de Tesseract)
	pytest -m ocr -v

e2e: ## Bot real con Selenium + Chrome contra el portal ficticio
	pytest -m e2e -v

test-sqlserver: ## Repositorio contra SQL Server (requiere `make sqlserver` y VIGIA_PRUEBAS_SQLSERVER_URL)
	pytest -m sqlserver -v

evaluar: ## Banco de evaluación con los motores instalados → docs/evaluacion.md
	vigia evaluar --cantidad $(MUESTRAS) --semilla $(SEMILLA)

evaluar-docker: ## Banco de evaluación con los tres motores, dentro de Docker
	docker build -t vigia-ocr:completo --build-arg CON_EASYOCR=1 .
	docker run --rm -v vigia-easyocr:/home/vigia/.EasyOCR -v "$(CURDIR)/docs:/app/docs" \
		vigia-ocr:completo evaluar --cantidad $(MUESTRAS) --semilla $(SEMILLA)

portal: ## Levanta el portal ficticio en http://127.0.0.1:8000
	vigia portal

demo: ## Consulta el lote de ejemplo contra el portal (en otra terminal: make portal)
	vigia consultar datos/radicados_demo.csv

demo-web: ## Construye la demo estática en site/
	vigia demo-web --salida site

up: ## Portal + bot en Docker Compose
	docker compose up --build portal bot

sqlserver: ## Levanta SQL Server en Docker (requiere aceptar la EULA: MSSQL_ACEPTO_EULA=Y)
	docker compose --profile sqlserver up -d sqlserver

down: ## Detiene los contenedores
	docker compose --profile sqlserver down

limpiar: ## Borra artefactos locales
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov site muestras vigia.db

.PHONY: help install install-completo lint format test test-ocr e2e test-sqlserver evaluar \
	evaluar-docker portal demo demo-web up sqlserver down limpiar
