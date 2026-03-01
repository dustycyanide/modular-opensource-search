# Generated Challenge Cards

Mode: `hybrid`

## AUTO-Q-DATA-001

- query: `python orm migration database`
- family: `data`
- mode: `hybrid`
- failure_type: `ranking_fp`
- severity: `medium`
- expected_repos: ['django', 'sqlalchemy']
- expected_capabilities: ['database_persistence']
- observed_top_k: ['sqlalchemy:database_persistence', 'celery:database_persistence', 'django:database_persistence', 'fastapi:database_persistence']
- error_samples:
  - ranking_fp: unexpected repo celery
  - ranking_fp: unexpected repo fastapi

## AUTO-Q-FILTER-001

- query: `gpl python ocr pipeline`
- family: `filters`
- mode: `hybrid`
- failure_type: `extraction_fp`
- severity: `medium`
- expected_repos: ['OCRmyPDF']
- expected_capabilities: ['document_ingestion_pipeline', 'ocr_processing']
- observed_top_k: ['OCRmyPDF:ocr_processing', 'OCRmyPDF:async_processing_engine']
- error_samples:
  - extraction_fn: missing expected capability: document_ingestion_pipeline
  - extraction_fp: unexpected capability async_processing_engine

## AUTO-Q-FILTER-002

- query: `apache python cli`
- family: `filters`
- mode: `hybrid`
- failure_type: `extraction_fn`
- severity: `medium`
- expected_repos: ['typer']
- expected_capabilities: ['cli_tooling']
- observed_top_k: []
- error_samples:
  - ranking_fn: missing expected repo: typer
  - extraction_fn: missing expected capability: cli_tooling

## AUTO-Q-OCR-001

- query: `python ocr document pipeline async`
- family: `document`
- mode: `hybrid`
- failure_type: `ranking_fp`
- severity: `low`
- expected_repos: ['OCRmyPDF', 'pytesseract']
- expected_capabilities: ['async_processing_engine', 'document_ingestion_pipeline', 'ocr_processing']
- observed_top_k: ['OCRmyPDF:ocr_processing', 'pytesseract:ocr_processing', 'OCRmyPDF:async_processing_engine', 'OCRmyPDF:document_ingestion_pipeline', 'rq:async_processing_engine']
- error_samples:
  - ranking_fp: unexpected repo rq

## AUTO-Q-API-002

- query: `python fastapi router endpoint`
- family: `api`
- mode: `hybrid`
- failure_type: `ranking_fp`
- severity: `low`
- expected_repos: ['fastapi']
- expected_capabilities: ['api_service']
- observed_top_k: ['fastapi:api_service', 'flask:api_service']
- error_samples:
  - ranking_fp: unexpected repo flask

## AUTO-Q-ASYNC-001

- query: `python async queue worker`
- family: `async`
- mode: `hybrid`
- failure_type: `ranking_fp`
- severity: `low`
- expected_repos: ['OCRmyPDF', 'celery', 'rq']
- expected_capabilities: ['async_processing_engine']
- observed_top_k: ['rq:async_processing_engine', 'celery:async_processing_engine', 'OCRmyPDF:async_processing_engine', 'django:async_processing_engine']
- error_samples:
  - ranking_fp: unexpected repo django

## AUTO-Q-NEG-001

- query: `python http client library`
- family: `negative`
- mode: `hybrid`
- failure_type: `ranking_fp`
- severity: `high`
- expected_repos: ['requests']
- expected_capabilities: []
- observed_top_k: ['flask:api_service', 'fastapi:api_service', 'fastapi:cli_tooling', 'typer:cli_tooling', 'rq:cli_tooling']
- error_samples:
  - ranking_fn: missing expected repo: requests
  - ranking_fp: off-target result flask:api_service
  - ranking_fp: off-target result fastapi:api_service
  - ranking_fp: off-target result fastapi:cli_tooling
  - ranking_fp: off-target result typer:cli_tooling

## AUTO-Q-CLI-001

- query: `python cli command tooling`
- family: `cli`
- mode: `hybrid`
- failure_type: `ranking_fp`
- severity: `high`
- expected_repos: ['OCRmyPDF', 'click', 'typer']
- expected_capabilities: ['cli_tooling']
- observed_top_k: ['rq:cli_tooling', 'typer:cli_tooling', 'fastapi:cli_tooling', 'OCRmyPDF:cli_tooling', 'celery:cli_tooling']
- error_samples:
  - ranking_fn: missing expected repo: click
  - ranking_fp: unexpected repo rq
  - ranking_fp: unexpected repo fastapi
  - ranking_fp: unexpected repo celery
