#!/usr/bin/env bash
set -euo pipefail

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q \
  tests/test_chunking.py \
  tests/test_ingestion.py \
  tests/test_github_api.py

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q \
  tests/test_lexical.py \
  tests/test_semantic.py \
  tests/test_ranking.py \
  tests/test_packaging.py \
  tests/test_pipeline_local.py

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q \
  tests/test_codesearchnet_adapters.py \
  tests/test_codesearchnet_evaluator.py \
  tests/test_provenance.py
