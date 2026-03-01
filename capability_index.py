#!/usr/bin/env python3
"""Local capability-card ingestion and search experiment.

This script ingests open-source repositories, extracts structured metadata plus
evidence-backed capability cards, and supports query-time structured filters
with semantic fallback.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from fastembed import TextEmbedding

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    TextEmbedding = None
    EMBEDDINGS_AVAILABLE = False


TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".xml",
    ".html",
    ".css",
    ".sh",
}

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".sh",
}

MAX_FILES_TO_SCAN = 2500
MAX_FILE_SIZE_BYTES = 250_000
MAX_CHARS_PER_FILE = 12_000


CAPABILITIES = [
    {
        "name": "document_ingestion_pipeline",
        "title": "Document ingestion pipeline",
        "keywords": [
            "ingest",
            "upload",
            "document",
            "pdf",
            "parser",
            "extract text",
        ],
        "strong_keywords": ["upload", "ingest", "pdf", "document parser"],
        "default_pipeline": "upload -> parse -> normalize -> persist",
    },
    {
        "name": "ocr_processing",
        "title": "OCR processing",
        "keywords": ["ocr", "tesseract", "image to text", "hocr", "scan", "recognition"],
        "strong_keywords": ["ocr", "tesseract", "hocr"],
        "default_pipeline": "image/pdf -> ocr -> text artifacts",
    },
    {
        "name": "async_processing_engine",
        "title": "Asynchronous processing engine",
        "keywords": [
            "queue",
            "worker",
            "celery",
            "rq",
            "background",
            "job",
            "async",
            "pipeline",
        ],
        "strong_keywords": ["celery", "rq", "queue", "worker"],
        "default_pipeline": "enqueue -> worker -> stage handlers -> persist",
    },
    {
        "name": "api_service",
        "title": "API service",
        "keywords": ["api", "endpoint", "rest", "fastapi", "flask", "django", "router"],
        "strong_keywords": ["fastapi", "flask", "django", "router", "endpoint"],
        "default_pipeline": "request -> validate -> business logic -> response",
    },
    {
        "name": "database_persistence",
        "title": "Database persistence",
        "keywords": ["database", "sql", "postgres", "sqlite", "orm", "model", "migration"],
        "strong_keywords": ["sqlalchemy", "sqlite", "postgres", "migration", "orm"],
        "default_pipeline": "domain object -> persistence model -> db",
    },
    {
        "name": "cli_tooling",
        "title": "CLI tooling",
        "keywords": ["cli", "command", "argparse", "click", "typer", "terminal"],
        "strong_keywords": ["argparse", "click", "typer", "cli"],
        "default_pipeline": "cli args -> command handler -> action",
    },
]


FRAMEWORK_PATTERNS = {
    "fastapi": re.compile(r"\bfastapi\b", re.IGNORECASE),
    "flask": re.compile(r"\bflask\b", re.IGNORECASE),
    "django": re.compile(r"\bdjango\b", re.IGNORECASE),
    "celery": re.compile(r"\bcelery\b", re.IGNORECASE),
    "rq": re.compile(r"\brq\b", re.IGNORECASE),
    "sqlalchemy": re.compile(r"\bsqlalchemy\b", re.IGNORECASE),
    "pydantic": re.compile(r"\bpydantic\b", re.IGNORECASE),
    "click": re.compile(r"\bclick\b", re.IGNORECASE),
    "typer": re.compile(r"\btyper\b", re.IGNORECASE),
    "react": re.compile(r"\breact\b", re.IGNORECASE),
}


LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
}


QUERY_FILTERS = {
    "languages": {
        "python": "Python",
        "typescript": "TypeScript",
        "javascript": "JavaScript",
        "java": "Java",
        "go": "Go",
        "rust": "Rust",
        "ruby": "Ruby",
    },
    "licenses": {
        "mit": "MIT",
        "apache": "Apache-2.0",
        "gpl": "GPL",
        "bsd": "BSD",
    },
}


SEMANTIC_SYNONYMS = {
    "ocr": ["recognition", "scan", "image text", "tesseract"],
    "pipeline": ["workflow", "processing", "stages", "orchestration"],
    "upload": ["ingest", "ingestion", "file input"],
    "extract": ["parse", "pull", "derive"],
    "async": ["background", "queue", "worker", "job"],
    "api": ["endpoint", "service", "http"],
    "database": ["sql", "persistence", "storage"],
    "invoice": ["receipt", "billing", "accounting"],
    "document": ["pdf", "file", "contract"],
}


EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_EMBEDDER: Any = None


DEFAULT_CAPABILITY_STRUCTURAL_RULES = {
    "document_ingestion_pipeline": {
        "required_groups": [
            [
                re.compile(r"\bpdf(plumber|miner|ium)?\b", re.IGNORECASE),
                re.compile(r"\bpypdf\b", re.IGNORECASE),
                re.compile(r"\bpikepdf\b", re.IGNORECASE),
                re.compile(r"\bfitz\b", re.IGNORECASE),
                re.compile(r"\btesseract\b", re.IGNORECASE),
            ],
            [
                re.compile(r"\bupload\b", re.IGNORECASE),
                re.compile(r"\bingest\b", re.IGNORECASE),
                re.compile(r"\bmultipart\b", re.IGNORECASE),
                re.compile(r"\bdocument\b", re.IGNORECASE),
            ],
        ],
        "support_patterns": [
            re.compile(r"\bparse\b", re.IGNORECASE),
            re.compile(r"\bextract\b", re.IGNORECASE),
            re.compile(r"\bnormalize\b", re.IGNORECASE),
        ],
        "min_support": 1,
    },
    "ocr_processing": {
        "required_groups": [
            [
                re.compile(r"\bocr\b", re.IGNORECASE),
                re.compile(r"\btesseract\b", re.IGNORECASE),
                re.compile(r"\bhocr\b", re.IGNORECASE),
                re.compile(r"\bimage_to_string\b", re.IGNORECASE),
            ]
        ],
        "support_patterns": [
            re.compile(r"\bimage\b", re.IGNORECASE),
            re.compile(r"\bpdf\b", re.IGNORECASE),
            re.compile(r"\btext\b", re.IGNORECASE),
        ],
        "min_support": 1,
    },
    "async_processing_engine": {
        "required_groups": [
            [
                re.compile(r"\bcelery\b", re.IGNORECASE),
                re.compile(r"\bshared_task\b", re.IGNORECASE),
                re.compile(r"\brq\b", re.IGNORECASE),
                re.compile(r"\basyncio\b", re.IGNORECASE),
                re.compile(r"\bThreadPoolExecutor\b", re.IGNORECASE),
                re.compile(r"\bProcessPoolExecutor\b", re.IGNORECASE),
            ],
            [
                re.compile(r"\bworker\b", re.IGNORECASE),
                re.compile(r"\bqueue\b", re.IGNORECASE),
                re.compile(r"\btask\b", re.IGNORECASE),
                re.compile(r"\bjob\b", re.IGNORECASE),
            ],
        ],
        "support_patterns": [
            re.compile(r"\bpipeline\b", re.IGNORECASE),
            re.compile(r"\benqueue\b", re.IGNORECASE),
        ],
        "min_support": 1,
    },
    "api_service": {
        "required_groups": [
            [
                re.compile(r"@app\.route\(", re.IGNORECASE),
                re.compile(r"\bFastAPI\(", re.IGNORECASE),
                re.compile(r"\bAPIRouter\(", re.IGNORECASE),
                re.compile(r"\bBlueprint\(", re.IGNORECASE),
                re.compile(r"router\.(get|post|put|delete|patch)\(", re.IGNORECASE),
                re.compile(r"@bp\.route\(", re.IGNORECASE),
            ],
            [
                re.compile(r"\brequest\b", re.IGNORECASE),
                re.compile(r"\bresponse\b", re.IGNORECASE),
                re.compile(r"\bjsonify\b", re.IGNORECASE),
                re.compile(r"\bHTTP\b", re.IGNORECASE),
            ],
        ],
        "support_patterns": [
            re.compile(r"\bendpoint\b", re.IGNORECASE),
            re.compile(r"\bstatus_code\b", re.IGNORECASE),
        ],
        "min_support": 0,
    },
    "database_persistence": {
        "required_groups": [
            [
                re.compile(r"\bsqlalchemy\b", re.IGNORECASE),
                re.compile(r"\bsqlite3\.connect\b", re.IGNORECASE),
                re.compile(r"\bcreate_engine\b", re.IGNORECASE),
                re.compile(r"\bsessionmaker\b", re.IGNORECASE),
                re.compile(r"\bpsycopg\b", re.IGNORECASE),
                re.compile(r"\bdjango\.db\b", re.IGNORECASE),
            ],
            [
                re.compile(r"\bSELECT\b", re.IGNORECASE),
                re.compile(r"\bINSERT\b", re.IGNORECASE),
                re.compile(r"\bUPDATE\b", re.IGNORECASE),
                re.compile(r"\bDELETE\b", re.IGNORECASE),
                re.compile(r"\bmigration\b", re.IGNORECASE),
            ],
        ],
        "support_patterns": [
            re.compile(r"\bmodel\b", re.IGNORECASE),
            re.compile(r"\bschema\b", re.IGNORECASE),
        ],
        "min_support": 0,
    },
    "cli_tooling": {
        "required_groups": [
            [
                re.compile(r"\bargparse\.ArgumentParser\b", re.IGNORECASE),
                re.compile(r"@click\.(command|group|option)\(", re.IGNORECASE),
                re.compile(r"\bTyper\(", re.IGNORECASE),
                re.compile(r"\bclick\.command\(", re.IGNORECASE),
            ]
        ],
        "support_patterns": [
            re.compile(r"__main__", re.IGNORECASE),
            re.compile(r"\bsys\.argv\b", re.IGNORECASE),
            re.compile(r"\bmain\(", re.IGNORECASE),
        ],
        "min_support": 0,
    },
}


ACTIVE_CAPABILITY_STRUCTURAL_RULES = DEFAULT_CAPABILITY_STRUCTURAL_RULES


def _compile_patterns(patterns: list[Any]) -> list[re.Pattern]:
    compiled = []
    for pattern in patterns:
        if isinstance(pattern, re.Pattern):
            compiled.append(pattern)
        else:
            compiled.append(re.compile(str(pattern), re.IGNORECASE))
    return compiled


def _compile_rule_definition(raw_rule: dict[str, Any], base_rule: dict[str, Any] | None = None) -> dict[str, Any]:
    base_rule = base_rule or {}

    required_groups_src = raw_rule.get("required_groups")
    if required_groups_src is None:
        required_groups = base_rule.get("required_groups", [])
    else:
        required_groups = [_compile_patterns(group) for group in required_groups_src]

    support_patterns_src = raw_rule.get("support_patterns")
    if support_patterns_src is None:
        support_patterns = base_rule.get("support_patterns", [])
    else:
        support_patterns = _compile_patterns(support_patterns_src)

    min_support = int(raw_rule.get("min_support", base_rule.get("min_support", 0)))
    return {
        "required_groups": required_groups,
        "support_patterns": support_patterns,
        "min_support": min_support,
    }


def get_default_validator_pack() -> dict[str, dict[str, Any]]:
    return {
        name: _compile_rule_definition(rule, None)
        for name, rule in DEFAULT_CAPABILITY_STRUCTURAL_RULES.items()
    }


def set_active_validator_pack(validator_pack_path: Path | None = None) -> None:
    global ACTIVE_CAPABILITY_STRUCTURAL_RULES
    base_pack = get_default_validator_pack()
    if not validator_pack_path:
        ACTIVE_CAPABILITY_STRUCTURAL_RULES = base_pack
        return

    path = Path(validator_pack_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_caps = payload.get("capabilities", {})

    merged_pack: dict[str, dict[str, Any]] = {}
    cap_names = set(base_pack.keys()) | set(raw_caps.keys())
    for cap_name in cap_names:
        base_rule = base_pack.get(cap_name, {})
        raw_rule = raw_caps.get(cap_name, {})
        merged_pack[cap_name] = _compile_rule_definition(raw_rule, base_rule)

    ACTIVE_CAPABILITY_STRUCTURAL_RULES = merged_pack


@dataclass
class CapabilityCard:
    repo_name: str
    card_type: str
    capability_name: str
    title: str
    summary: str
    pipeline_shape: str
    inputs: str
    outputs: str
    frameworks: list[str]
    license_name: str
    quality_signals: dict
    evidence_paths: list[str]
    confidence: float

    def search_text(self) -> str:
        payload = {
            "title": self.title,
            "summary": self.summary,
            "pipeline_shape": self.pipeline_shape,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "frameworks": self.frameworks,
            "capability": self.capability_name,
            "quality_signals": self.quality_signals,
        }
        return json.dumps(payload, ensure_ascii=True)


def init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS repos (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            path TEXT NOT NULL,
            license TEXT,
            primary_language TEXT,
            frameworks_json TEXT,
            has_tests INTEGER,
            summary TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY,
            repo_name TEXT NOT NULL,
            card_type TEXT NOT NULL,
            capability_name TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            pipeline_shape TEXT,
            inputs TEXT,
            outputs TEXT,
            frameworks_json TEXT,
            license TEXT,
            quality_signals_json TEXT,
            evidence_json TEXT,
            confidence REAL,
            search_text TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5(
            title,
            summary,
            search_text,
            content='cards',
            content_rowid='id'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS card_embeddings (
            card_id INTEGER PRIMARY KEY,
            model_name TEXT NOT NULL,
            vector_json TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES cards(id)
        )
        """
    )
    conn.commit()
    conn.close()


def iter_repo_files(repo_path: Path) -> Iterable[Path]:
    count = 0
    for path in repo_path.rglob("*"):
        if count >= MAX_FILES_TO_SCAN:
            break
        if not path.is_file():
            continue
        if "/.git/" in path.as_posix():
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS:
            try:
                if path.stat().st_size <= MAX_FILE_SIZE_BYTES:
                    count += 1
                    yield path
            except OSError:
                continue


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:MAX_CHARS_PER_FILE]
    except OSError:
        return ""


def infer_license(repo_path: Path) -> str:
    candidates = [
        repo_path / "LICENSE",
        repo_path / "LICENSE.txt",
        repo_path / "LICENSE.md",
        repo_path / "COPYING",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        text = read_text(candidate).lower()
        if "mit license" in text:
            return "MIT"
        if "apache license" in text and "2.0" in text:
            return "Apache-2.0"
        if "gnu general public license" in text:
            return "GPL"
        if "bsd" in text and "redistribution" in text:
            return "BSD"
        return "Other"
    return "Unknown"


def infer_primary_language(ext_counter: Counter) -> str:
    language_counter = Counter()
    for ext, count in ext_counter.items():
        language = LANGUAGE_BY_EXTENSION.get(ext)
        if language:
            language_counter[language] += count
    if not language_counter:
        return "Unknown"
    return language_counter.most_common(1)[0][0]


def get_embedder() -> Any:
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER
    if not EMBEDDINGS_AVAILABLE:
        return None
    _EMBEDDER = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    return _EMBEDDER


def embed_texts(texts: list[str]) -> list[list[float]]:
    embedder = get_embedder()
    if embedder is None:
        return []
    vectors = list(embedder.embed(texts))
    return [vector.tolist() for vector in vectors]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a_val, b_val in zip(vec_a, vec_b):
        dot += a_val * b_val
        norm_a += a_val * a_val
        norm_b += b_val * b_val
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def normalize_score_map(score_map: dict[int, float]) -> dict[int, float]:
    if not score_map:
        return {}
    values = list(score_map.values())
    min_value = min(values)
    max_value = max(values)
    if math.isclose(min_value, max_value):
        return {key: 1.0 for key in score_map}
    return {key: (value - min_value) / (max_value - min_value) for key, value in score_map.items()}


def build_repo_profile(repo_path: Path) -> dict:
    ext_counter: Counter = Counter()
    framework_hits: Counter = Counter()
    capability_hits: dict[str, float] = defaultdict(float)
    capability_strong_hits: dict[str, int] = defaultdict(int)
    capability_evidence: dict[str, list[str]] = defaultdict(list)
    validator_group_hits: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    validator_support_hits: dict[str, set[str]] = defaultdict(set)

    has_tests = False
    readme_text = ""
    readme_path = next(iter(repo_path.glob("README*")), None)
    if readme_path and readme_path.is_file():
        readme_text = read_text(readme_path)

    files_scanned = 0
    for file_path in iter_repo_files(repo_path):
        files_scanned += 1
        rel = file_path.relative_to(repo_path).as_posix()
        ext_counter[file_path.suffix.lower()] += 1
        lower_rel = rel.lower()
        if "test" in lower_rel:
            has_tests = True

        text = read_text(file_path)
        combined = f"{lower_rel}\n{text[:2000]}".lower()
        is_code_file = file_path.suffix.lower() in CODE_EXTENSIONS
        path_parts = set(part.lower() for part in file_path.parts)
        is_docs_or_tests = bool(path_parts.intersection({"test", "tests", "doc", "docs", "example", "examples"}))
        score_weight = 1.0 if is_code_file else 0.35
        if is_docs_or_tests:
            score_weight *= 0.15

        for fw_name, pattern in FRAMEWORK_PATTERNS.items():
            if pattern.search(combined):
                framework_hits[fw_name] += 1

        for capability in CAPABILITIES:
            matches = 0
            for keyword in capability["keywords"]:
                if keyword in combined:
                    matches += 1
            if matches > 0:
                capability_hits[capability["name"]] += matches * score_weight
                strong_matches = 0
                for keyword in capability.get("strong_keywords", []):
                    if keyword in combined:
                        strong_matches += 1
                if not is_docs_or_tests:
                    capability_strong_hits[capability["name"]] += strong_matches

                if is_code_file and not is_docs_or_tests and len(capability_evidence[capability["name"]]) < 12:
                    capability_evidence[capability["name"]].append(rel)

        if is_code_file and not is_docs_or_tests:
            for cap_name, rule in ACTIVE_CAPABILITY_STRUCTURAL_RULES.items():
                required_groups = rule.get("required_groups", [])
                for group_idx, patterns in enumerate(required_groups):
                    if any(pattern.search(combined) for pattern in patterns):
                        validator_group_hits[cap_name][group_idx].add(rel)
                support_patterns = rule.get("support_patterns", [])
                if any(pattern.search(combined) for pattern in support_patterns):
                    validator_support_hits[cap_name].add(rel)

    license_name = infer_license(repo_path)
    primary_language = infer_primary_language(ext_counter)
    frameworks = [name for name, _ in framework_hits.most_common(6)]

    summary_parts = [
        f"Scanned {files_scanned} text files.",
        f"Primary language appears to be {primary_language}.",
    ]
    if frameworks:
        summary_parts.append("Detected frameworks/libraries: " + ", ".join(frameworks) + ".")
    if readme_text:
        first_lines = " ".join(line.strip() for line in readme_text.splitlines()[:3]).strip()
        if first_lines:
            summary_parts.append("README signal: " + first_lines[:220])

    validator_group_counts: dict[str, list[int]] = {}
    validator_support_counts: dict[str, int] = {}
    validator_evidence: dict[str, list[str]] = {}
    for cap_name, rule in ACTIVE_CAPABILITY_STRUCTURAL_RULES.items():
        required_groups = rule.get("required_groups", [])
        group_counts = [len(validator_group_hits[cap_name].get(idx, set())) for idx in range(len(required_groups))]
        validator_group_counts[cap_name] = group_counts
        validator_support_counts[cap_name] = len(validator_support_hits[cap_name])

        evidence_paths = set()
        for idx in range(len(required_groups)):
            evidence_paths.update(validator_group_hits[cap_name].get(idx, set()))
        evidence_paths.update(validator_support_hits[cap_name])
        validator_evidence[cap_name] = sorted(evidence_paths)[:12]

    return {
        "license": license_name,
        "primary_language": primary_language,
        "frameworks": frameworks,
        "has_tests": has_tests,
        "capability_hits": dict(capability_hits),
        "capability_strong_hits": dict(capability_strong_hits),
        "capability_evidence": dict(capability_evidence),
        "validator_group_counts": validator_group_counts,
        "validator_support_counts": validator_support_counts,
        "validator_evidence": validator_evidence,
        "summary": " ".join(summary_parts),
    }


def build_cards(repo_name: str, profile: dict) -> list[CapabilityCard]:
    cards: list[CapabilityCard] = []
    quality_signals = {
        "has_tests": profile["has_tests"],
        "framework_count": len(profile["frameworks"]),
        "primary_language": profile["primary_language"],
        "embeddings_available": EMBEDDINGS_AVAILABLE,
    }

    overview = CapabilityCard(
        repo_name=repo_name,
        card_type="repo_overview",
        capability_name="repository_summary",
        title=f"{repo_name}: repository overview",
        summary=profile["summary"],
        pipeline_shape="n/a",
        inputs="n/a",
        outputs="n/a",
        frameworks=profile["frameworks"],
        license_name=profile["license"],
        quality_signals=quality_signals,
        evidence_paths=[],
        confidence=0.55,
    )
    cards.append(overview)

    hits = profile["capability_hits"]
    strong_hits = profile["capability_strong_hits"]
    evidence = profile["capability_evidence"]
    validator_group_counts = profile.get("validator_group_counts", {})
    validator_support_counts = profile.get("validator_support_counts", {})
    validator_evidence = profile.get("validator_evidence", {})

    for capability in CAPABILITIES:
        cap_name = capability["name"]
        score = float(hits.get(cap_name, 0))
        strong_score = int(strong_hits.get(cap_name, 0))
        lexical_evidence = evidence.get(cap_name, [])

        rule = ACTIVE_CAPABILITY_STRUCTURAL_RULES.get(cap_name, {})
        group_counts = validator_group_counts.get(cap_name, [])
        support_count = int(validator_support_counts.get(cap_name, 0))
        min_support = int(rule.get("min_support", 0))
        required_ok = all(count > 0 for count in group_counts) if group_counts else True
        support_ok = support_count >= min_support

        if score < 4.0 or strong_score < 1:
            continue
        if not required_ok or not support_ok:
            continue

        structural_evidence = validator_evidence.get(cap_name, [])
        merged_evidence = []
        for path in [*structural_evidence, *lexical_evidence]:
            if path not in merged_evidence:
                merged_evidence.append(path)
            if len(merged_evidence) >= 12:
                break

        if not merged_evidence:
            continue

        validated_groups = sum(1 for count in group_counts if count > 0)
        total_groups = len(group_counts) if group_counts else 1
        validation_score = min(1.0, (validated_groups / total_groups) * 0.8 + (0.2 if support_ok else 0.0))

        normalized_confidence = min(
            0.95,
            0.2 + (score / 20.0) + (0.04 * strong_score) + (0.28 * validation_score),
        )
        summary = (
            f"Detected {capability['title'].lower()} signals with structural validation score "
            f"{validation_score:.2f}. Evidence includes: {', '.join(merged_evidence[:4])}."
        )

        inputs = "Likely files/documents plus configuration"
        outputs = "Likely transformed data artifacts and/or persisted records"
        if cap_name == "ocr_processing":
            inputs = "Images or PDFs"
            outputs = "OCR text artifacts (text/hOCR/json)"
        elif cap_name == "api_service":
            inputs = "HTTP requests"
            outputs = "JSON or HTTP responses"
        elif cap_name == "database_persistence":
            inputs = "Domain entities"
            outputs = "Stored relational or document records"

        cards.append(
            CapabilityCard(
                repo_name=repo_name,
                card_type="capability",
                capability_name=cap_name,
                title=f"{repo_name}: {capability['title']}",
                summary=summary,
                pipeline_shape=capability["default_pipeline"],
                inputs=inputs,
                outputs=outputs,
                frameworks=profile["frameworks"],
                license_name=profile["license"],
                quality_signals={
                    **quality_signals,
                    "validation_score": round(validation_score, 3),
                    "validated_groups": validated_groups,
                    "required_groups": total_groups,
                    "support_hits": support_count,
                },
                evidence_paths=merged_evidence,
                confidence=normalized_confidence,
            )
        )

    return cards


def upsert_repo_and_cards(
    db_path: Path,
    repo_path: Path,
    repo_name: str,
    validator_pack_path: Path | None = None,
) -> int:
    if validator_pack_path:
        set_active_validator_pack(validator_pack_path)
    profile = build_repo_profile(repo_path)
    cards = build_cards(repo_name, profile)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.execute("DELETE FROM card_embeddings WHERE card_id IN (SELECT id FROM cards WHERE repo_name = ?)", (repo_name,))
    conn.execute("DELETE FROM cards_fts WHERE rowid IN (SELECT id FROM cards WHERE repo_name = ?)", (repo_name,))
    conn.execute("DELETE FROM cards WHERE repo_name = ?", (repo_name,))
    conn.execute("DELETE FROM repos WHERE name = ?", (repo_name,))

    conn.execute(
        """
        INSERT INTO repos (name, path, license, primary_language, frameworks_json, has_tests, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            repo_name,
            str(repo_path),
            profile["license"],
            profile["primary_language"],
            json.dumps(profile["frameworks"], ensure_ascii=True),
            int(profile["has_tests"]),
            profile["summary"],
        ),
    )

    card_rows_for_embeddings: list[tuple[int, str]] = []
    for card in cards:
        cur = conn.execute(
            """
            INSERT INTO cards (
                repo_name, card_type, capability_name, title, summary,
                pipeline_shape, inputs, outputs, frameworks_json, license,
                quality_signals_json, evidence_json, confidence, search_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card.repo_name,
                card.card_type,
                card.capability_name,
                card.title,
                card.summary,
                card.pipeline_shape,
                card.inputs,
                card.outputs,
                json.dumps(card.frameworks, ensure_ascii=True),
                card.license_name,
                json.dumps(card.quality_signals, ensure_ascii=True),
                json.dumps(card.evidence_paths, ensure_ascii=True),
                card.confidence,
                card.search_text(),
            ),
        )
        rowid = cur.lastrowid
        conn.execute(
            "INSERT INTO cards_fts (rowid, title, summary, search_text) VALUES (?, ?, ?, ?)",
            (rowid, card.title, card.summary, card.search_text()),
        )
        card_rows_for_embeddings.append((rowid, card.search_text()))

    if EMBEDDINGS_AVAILABLE and card_rows_for_embeddings:
        texts = [item[1] for item in card_rows_for_embeddings]
        vectors = embed_texts(texts)
        if len(vectors) == len(card_rows_for_embeddings):
            for (card_id, _), vector in zip(card_rows_for_embeddings, vectors):
                conn.execute(
                    "INSERT OR REPLACE INTO card_embeddings (card_id, model_name, vector_json) VALUES (?, ?, ?)",
                    (card_id, EMBEDDING_MODEL_NAME, json.dumps(vector, ensure_ascii=True)),
                )

    conn.commit()
    conn.close()
    return len(cards)


def tokenize(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(tok) > 1]


def extract_query_filters(query: str) -> dict:
    tokens = tokenize(query)
    language = None
    license_name = None
    capability_terms = []

    for token in tokens:
        if token in QUERY_FILTERS["languages"] and not language:
            language = QUERY_FILTERS["languages"][token]
        if token in QUERY_FILTERS["licenses"] and not license_name:
            license_name = QUERY_FILTERS["licenses"][token]

    token_str = " ".join(expand_tokens(tokens))
    for capability in CAPABILITIES:
        cap_name = capability["name"]
        for kw in capability["keywords"]:
            if kw in token_str:
                capability_terms.append(cap_name)
                break

    return {
        "language": language,
        "license": license_name,
        "capabilities": sorted(set(capability_terms)),
        "tokens": tokens,
    }


def build_fts_query(tokens: list[str]) -> str:
    cleaned = [tok for tok in tokens if len(tok) > 1]
    if not cleaned:
        return ""
    return " OR ".join(cleaned)


def expand_tokens(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    token_set = set(tokens)
    for token in tokens:
        for root, synonyms in SEMANTIC_SYNONYMS.items():
            if token == root or token in synonyms:
                if root not in token_set:
                    expanded.append(root)
                    token_set.add(root)
                for synonym in synonyms:
                    syn_tokens = tokenize(synonym)
                    for syn_tok in syn_tokens:
                        if syn_tok not in token_set:
                            expanded.append(syn_tok)
                            token_set.add(syn_tok)
    return expanded


def build_filter_sql(filters: dict) -> tuple[str, list[Any]]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    if filters["language"]:
        where_clauses.append("r.primary_language = ?")
        params.append(filters["language"])
    if filters["license"]:
        where_clauses.append("c.license LIKE ?")
        params.append(f"%{filters['license']}%")
    if filters["capabilities"]:
        placeholders = ", ".join(["?"] * len(filters["capabilities"]))
        where_clauses.append(f"c.capability_name IN ({placeholders})")
        params.extend(filters["capabilities"])
    return " AND ".join(where_clauses), params


def run_lexical_search(conn: sqlite3.Connection, where_sql: str, params: list[Any], tokens: list[str], k: int) -> list[sqlite3.Row]:
    fts_query = build_fts_query(tokens)
    rows: list[sqlite3.Row] = []
    candidate_k = max(k * 6, 20)

    if fts_query:
        sql = (
            "SELECT c.*, r.primary_language, bm25(cards_fts) AS rank "
            "FROM cards_fts "
            "JOIN cards c ON c.id = cards_fts.rowid "
            "JOIN repos r ON r.name = c.repo_name "
            f"WHERE cards_fts MATCH ? AND {where_sql} "
            "ORDER BY rank LIMIT ?"
        )
        rows = conn.execute(sql, [fts_query, *params, candidate_k]).fetchall()

    expanded = expand_tokens(tokens)
    fts_fallback = build_fts_query(expanded)
    if fts_fallback:
        sql = (
            "SELECT c.*, r.primary_language, bm25(cards_fts) AS rank "
            "FROM cards_fts "
            "JOIN cards c ON c.id = cards_fts.rowid "
            "JOIN repos r ON r.name = c.repo_name "
            f"WHERE cards_fts MATCH ? AND {where_sql} "
            "ORDER BY rank LIMIT ?"
        )
        fallback_rows = conn.execute(sql, [fts_fallback, *params, candidate_k]).fetchall()
        dedup = {row["id"]: row for row in rows}
        for row in fallback_rows:
            existing = dedup.get(row["id"])
            if existing is None or row["rank"] < existing["rank"]:
                dedup[row["id"]] = row
        rows = list(dedup.values())
        rows.sort(key=lambda row: row["rank"])
    return rows[:candidate_k]


def run_semantic_search(
    conn: sqlite3.Connection,
    where_sql: str,
    params: list[Any],
    query: str,
    k: int,
) -> tuple[list[sqlite3.Row], dict[int, float]]:
    if not EMBEDDINGS_AVAILABLE:
        return [], {}

    vectors = embed_texts([query])
    if not vectors:
        return [], {}
    query_vector = vectors[0]

    candidate_k = max(k * 10, 40)
    sql = (
        "SELECT c.*, r.primary_language, e.vector_json "
        "FROM cards c "
        "JOIN repos r ON r.name = c.repo_name "
        "JOIN card_embeddings e ON e.card_id = c.id "
        f"WHERE {where_sql} "
        "ORDER BY c.confidence DESC LIMIT ?"
    )
    rows = conn.execute(sql, [*params, candidate_k]).fetchall()

    scored_rows: list[tuple[sqlite3.Row, float]] = []
    semantic_scores: dict[int, float] = {}
    for row in rows:
        vector = json.loads(row["vector_json"])
        score = cosine_similarity(query_vector, vector)
        semantic_scores[row["id"]] = score
        scored_rows.append((row, score))

    scored_rows.sort(key=lambda item: item[1], reverse=True)
    ordered_rows = [item[0] for item in scored_rows[:candidate_k]]
    return ordered_rows, semantic_scores


def get_validation_score(row: sqlite3.Row) -> float:
    try:
        payload = json.loads(row["quality_signals_json"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    return float(payload.get("validation_score", 0.0))


def search_cards(db_path: Path, query: str, k: int, mode: str = "hybrid") -> list[sqlite3.Row]:
    filters = extract_query_filters(query)
    tokens = filters["tokens"]
    where_sql, params = build_filter_sql(filters)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    lexical_rows: list[sqlite3.Row] = []
    semantic_rows: list[sqlite3.Row] = []
    semantic_scores: dict[int, float] = {}

    if mode in {"lexical", "hybrid"}:
        lexical_rows = run_lexical_search(conn, where_sql, params, tokens, k)
    if mode in {"semantic", "hybrid"}:
        semantic_rows, semantic_scores = run_semantic_search(conn, where_sql, params, query, k)

    if mode == "semantic" and not EMBEDDINGS_AVAILABLE:
        lexical_rows = run_lexical_search(conn, where_sql, params, tokens, k)

    if mode == "semantic" and not semantic_rows and EMBEDDINGS_AVAILABLE:
        conn.close()
        return []

    candidate_rows: dict[int, sqlite3.Row] = {}
    lexical_rank_scores: dict[int, float] = {}
    semantic_rank_scores: dict[int, float] = {}

    for idx, row in enumerate(lexical_rows):
        candidate_rows[row["id"]] = row
        lexical_rank_scores[row["id"]] = 1.0 / (1.0 + idx)

    for row in semantic_rows:
        candidate_rows[row["id"]] = row
    semantic_rank_scores.update(semantic_scores)

    lexical_norm = normalize_score_map(lexical_rank_scores)
    semantic_norm = normalize_score_map(semantic_rank_scores)

    ranked = []
    for card_id, row in candidate_rows.items():
        lex_score = lexical_norm.get(card_id, 0.0)
        sem_score = semantic_norm.get(card_id, 0.0)
        conf_score = float(row["confidence"])
        val_score = get_validation_score(row)

        if mode == "lexical":
            final_score = (0.65 * lex_score) + (0.25 * conf_score) + (0.10 * val_score)
        elif mode == "semantic":
            final_score = (0.70 * sem_score) + (0.20 * conf_score) + (0.10 * val_score)
        else:
            final_score = (0.50 * sem_score) + (0.25 * lex_score) + (0.15 * conf_score) + (0.10 * val_score)
        ranked.append((row, final_score))

    ranked.sort(key=lambda item: item[1], reverse=True)
    rows = [item[0] for item in ranked[:k]]

    if not rows:
        sql = (
            "SELECT c.*, r.primary_language, 0.0 AS rank "
            "FROM cards c "
            "JOIN repos r ON r.name = c.repo_name "
            f"WHERE {where_sql} "
            "ORDER BY c.confidence DESC LIMIT ?"
        )
        rows = conn.execute(sql, [*params, k]).fetchall()

    conn.close()
    return rows


def print_search_results(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("No results.")
        return

    for idx, row in enumerate(rows, start=1):
        evidence = json.loads(row["evidence_json"] or "[]")
        evidence_preview = ", ".join(evidence[:3]) if evidence else "none"
        print(f"[{idx}] {row['title']}")
        print(f"    repo={row['repo_name']} language={row['primary_language']} license={row['license']}")
        print(f"    capability={row['capability_name']} confidence={row['confidence']:.2f}")
        print(f"    pipeline={row['pipeline_shape']}")
        print(f"    evidence={evidence_preview}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capability-card indexing experiment")
    parser.add_argument("--db", default="./data/capabilities.db", help="Path to sqlite database")
    parser.add_argument(
        "--validator-pack",
        default=None,
        help="Optional JSON validator pack path to override structural rules",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    init_cmd = sub.add_parser("init", help="Initialize sqlite schema")
    init_cmd.set_defaults(func=cmd_init)

    ingest_cmd = sub.add_parser("ingest", help="Ingest one repository")
    ingest_cmd.add_argument("--repo-path", required=True, help="Path to local repository")
    ingest_cmd.add_argument("--repo-name", help="Optional logical repo name")
    ingest_cmd.set_defaults(func=cmd_ingest)

    search_cmd = sub.add_parser("search", help="Search capability cards")
    search_cmd.add_argument("--query", required=True, help="Natural language query")
    search_cmd.add_argument("--k", type=int, default=5, help="Top-K results")
    search_cmd.add_argument(
        "--mode",
        choices=["lexical", "semantic", "hybrid"],
        default="hybrid",
        help="Retrieval mode",
    )
    search_cmd.set_defaults(func=cmd_search)

    list_cmd = sub.add_parser("list", help="List ingested cards")
    list_cmd.set_defaults(func=cmd_list)

    return parser.parse_args()


def cmd_init(args: argparse.Namespace) -> None:
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)
    print(f"Initialized database at {db_path}")


def cmd_ingest(args: argparse.Namespace) -> None:
    db_path = Path(args.db)
    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise SystemExit(f"Repository path does not exist: {repo_path}")
    repo_name = args.repo_name or repo_path.name
    validator_pack_path = Path(args.validator_pack) if args.validator_pack else None
    card_count = upsert_repo_and_cards(
        db_path=db_path,
        repo_path=repo_path,
        repo_name=repo_name,
        validator_pack_path=validator_pack_path,
    )
    print(f"Ingested {repo_name} with {card_count} cards")


def cmd_search(args: argparse.Namespace) -> None:
    rows = search_cards(Path(args.db), args.query, args.k, mode=args.mode)
    print_search_results(rows)


def cmd_list(args: argparse.Namespace) -> None:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT repo_name, card_type, capability_name, title, confidence FROM cards ORDER BY repo_name, confidence DESC"
    ).fetchall()
    conn.close()
    for row in rows:
        print(
            f"repo={row['repo_name']} type={row['card_type']} capability={row['capability_name']} "
            f"confidence={row['confidence']:.2f} title={row['title']}"
        )


def main() -> None:
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
