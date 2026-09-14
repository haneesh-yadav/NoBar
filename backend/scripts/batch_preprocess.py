#!/usr/bin/env python
"""
Batch preprocess script for NoBar.

Scans Dataset/data/gov_myscheme/text_data/, selects a representative subset of PDFs
across key categories (pensions, disability, women/child welfare, agriculture, labour),
runs the full end-to-end pipeline (ingest -> extract -> simplify -> verify -> WCAG/TTS/translate),
and populates the SQLite database repository so the pre-built library page and review queue are seeded.

Usage:
  python scripts/batch_preprocess.py [--limit 25] [--category pension]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.storage import audio_dir_for_document  # noqa: E402
from chains.pipeline import run_pipeline  # noqa: E402
from db.models import init_db  # noqa: E402
from db.repository import create_document, get_session, save_pipeline_result  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nobar.batch")

DATASET_DIR = BACKEND_DIR.parent / "Dataset" / "data" / "gov_myscheme" / "text_data"


def classify_category(filename: str) -> str:
    fn = filename.lower()
    if any(k in fn for k in ("oap", "pension", "vaya", "ignoap", "vradha", "elder")):
        return "pension"
    if any(k in fn for k in ("disab", "divyang", "handicap", "blind", "disabled")):
        return "disability"
    if any(k in fn for k in ("mahila", "kanya", "sukanya", "poshan", "matru", "widow", "girl")):
        return "women_child"
    if any(k in fn for k in ("kisan", "pmkisan", "crop", "agri", "fasal", "krishi")):
        return "agriculture"
    if any(k in fn for k in ("bocw", "shram", "labour", "labor", "dattopant", "worker")):
        return "labour"
    return "general_welfare"


def select_curated_subset(limit: int = 25, category_filter: str | None = None) -> list[Path]:
    if not DATASET_DIR.exists():
        logger.error("Dataset directory %s not found", DATASET_DIR)
        return []

    # Get non-duplicate PDFs (skip " copy.pdf")
    pdf_files = [p for p in DATASET_DIR.glob("*.pdf") if " copy.pdf" not in p.name]

    if category_filter:
        pdf_files = [p for p in pdf_files if classify_category(p.name) == category_filter]

    # Select representative samples per category
    categories: dict[str, list[Path]] = {}
    for p in pdf_files:
        cat = classify_category(p.name)
        categories.setdefault(cat, []).append(p)

    selected: list[Path] = []
    # Interleave categories to ensure balanced representation
    max_len = max((len(v) for v in categories.values()), default=0)
    for i in range(max_len):
        for cat in sorted(categories.keys()):
            if i < len(categories[cat]):
                selected.append(categories[cat][i])
                if len(selected) >= limit:
                    break
        if len(selected) >= limit:
            break

    return selected


def main():
    parser = argparse.ArgumentParser(description="Batch preprocess NoBar dataset scheme PDFs")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of PDFs to process")
    parser.add_argument("--category", type=str, default=None, help="Filter by specific category")
    args = parser.parse_args()

    init_db()
    selected_files = select_curated_subset(limit=args.limit, category_filter=args.category)
    logger.info("Selected %d PDFs for batch preprocessing from %s", len(selected_files), DATASET_DIR)

    stats = {
        "total": len(selected_files),
        "published": 0,
        "needs_review": 0,
        "failed": 0,
        "total_time_sec": 0.0,
        "fidelity_scores": [],
    }

    t0_all = time.time()
    for idx, pdf_path in enumerate(selected_files, start=1):
        cat = classify_category(pdf_path.name)
        logger.info("[%d/%d] Processing %s (Category: %s)", idx, len(selected_files), pdf_path.name, cat)

        with get_session() as session:
            doc = create_document(session, source_pdf_path=str(pdf_path), category=cat)
            doc_id = doc.id

        t0 = time.time()
        try:
            result = run_pipeline(
                str(pdf_path),
                session_id=doc_id,
                languages=("en", "hi", "ta"),
                audio_dir=audio_dir_for_document(),
            )
            with get_session() as session:
                save_pipeline_result(session, doc_id, result)

            elapsed = time.time() - t0
            stats["fidelity_scores"].append(result.verification.fidelity_score)
            if result.status == "published":
                stats["published"] += 1
            else:
                stats["needs_review"] += 1

            logger.info(
                "[%d/%d] Finished %s in %.1fs -> Status: %s | Fidelity: %.1f%%",
                idx, len(selected_files), pdf_path.name, elapsed, result.status.upper(), result.verification.fidelity_score,
            )
        except Exception as exc:
            logger.exception("[%d/%d] Failed to process %s", idx, len(selected_files), pdf_path.name)
            stats["failed"] += 1
            with get_session() as session:
                from db.models import Document
                d = session.get(Document, doc_id)
                if d:
                    d.status = "failed"

    stats["total_time_sec"] = time.time() - t0_all
    avg_fidelity = (sum(stats["fidelity_scores"]) / len(stats["fidelity_scores"])) if stats["fidelity_scores"] else 0.0

    print("\n" + "=" * 60)
    print("BATCH PREPROCESSING COMPLETE")
    print(f"Total PDFs Processed:  {stats['total']}")
    print(f"Published:             {stats['published']}")
    print(f"Needs Review:          {stats['needs_review']}")
    print(f"Failed:                {stats['failed']}")
    print(f"Average Fidelity Score: {avg_fidelity:.1f}%")
    print(f"Total Elapsed Time:    {stats['total_time_sec']:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
