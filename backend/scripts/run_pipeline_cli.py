#!/usr/bin/env python
"""
CLI proof of the end-to-end pipeline: ingest -> extract -> simplify ->
verify (with retry gate). Run against any PDF in the Dataset corpus.

Usage:
  python scripts/run_pipeline_cli.py ../Dataset/data/gov_myscheme/text_data/oap(1).pdf
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chains.pipeline import run_pipeline  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main():
    if len(sys.argv) < 2:
        print("usage: run_pipeline_cli.py <path-to-pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    t0 = time.time()
    result = run_pipeline(pdf_path)
    elapsed = time.time() - t0

    print("\n" + "=" * 70)
    print(f"TITLE:            {result.title}")
    print(f"STATUS:           {result.status.upper()}")
    print(f"FIDELITY SCORE:   {result.verification.fidelity_score:.1f}%")
    print(f"READING GRADE:    {result.reading_grade:.1f}")
    print(f"RETRIES USED:     {result.retries_used}")
    print(f"TOTAL TIME:       {elapsed:.1f}s")
    print(f"INGEST WARNINGS:  {result.ingest_warnings}")
    print("=" * 70)

    print("\n--- FACT LEDGER ---")
    print(result.ledger.model_dump_json(indent=2))

    print("\n--- SIMPLIFIED TEXT ---")
    print(result.simplified_text)

    print("\n--- VERIFICATION CHECKS ---")
    for c in result.verification.checks:
        mark = "PASS" if c.preserved else "FAIL"
        print(f"[{mark}] ({c.tier}) {c.fact_description} -> {c.raw_value!r} :: {c.reason}")

    if result.verification.missing_facts:
        print("\n--- MISSING FACTS (would block publish) ---")
        for m in result.verification.missing_facts:
            print(f" - {m}")


if __name__ == "__main__":
    main()
