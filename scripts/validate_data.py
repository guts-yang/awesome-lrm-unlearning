#!/usr/bin/env python3
"""Schema, ordering, figure, and README-sync validator for Awesome LRM Unlearning."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from build_readme import (
    BENCH_METRICS_PATH,
    PAPERS_PATH,
    README_PATH,
    ROOT,
    collect_readme_anchors,
    render_readme,
)

DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DAY_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
URL_RE = re.compile(r"^https://\S+$")
SEEN_PATH = ROOT / "data" / "seen_candidates.json"
SEEN_STATUSES = {"reported", "accepted", "rejected"}

REQUIRED_PAPER_FIELDS = {
    "id",
    "title",
    "method_name",
    "authors",
    "date",
    "year",
    "venue",
    "paper_url",
    "code_url",
    "project_url",
    "category",
    "also_categories",
    "subcategory",
    "stage",
    "target_scope",
    "models",
    "summary",
}


def validate_seen_candidates(errors: list[str]) -> None:
    if not SEEN_PATH.exists():
        errors.append(f"Missing file: {SEEN_PATH}")
        return
    try:
        payload = json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"[seen_candidates] Invalid JSON: {exc}")
        return
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list):
        errors.append("[seen_candidates] Expected an object with a candidates list.")
        return

    seen_arxiv: set[str] = set()
    seen_doi: set[str] = set()
    seen_titles: set[str] = set()
    for idx, item in enumerate(candidates):
        label = f"[seen_candidates:{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{label} Candidate must be an object.")
            continue
        title = item.get("normalized_title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{label} normalized_title must be a non-empty string.")
        elif title in seen_titles:
            errors.append(f"{label} Duplicate normalized_title: {title}")
        else:
            seen_titles.add(title)
        status = item.get("status")
        if status not in SEEN_STATUSES:
            errors.append(f"{label} Invalid status: {status}")
        for day_key in ("first_seen", "last_seen"):
            day = item.get(day_key)
            if not isinstance(day, str) or not DAY_RE.match(day):
                errors.append(f"{label} Invalid {day_key}: {day}")
        arxiv_id = item.get("arxiv_id")
        if arxiv_id is not None:
            if not isinstance(arxiv_id, str) or not arxiv_id.strip():
                errors.append(f"{label} arxiv_id must be a non-empty string or null.")
            elif arxiv_id in seen_arxiv:
                errors.append(f"{label} Duplicate arxiv_id: {arxiv_id}")
            else:
                seen_arxiv.add(arxiv_id)
        doi = item.get("doi")
        if doi is not None:
            if not isinstance(doi, str) or not doi.strip():
                errors.append(f"{label} doi must be a non-empty string or null.")
            elif doi.lower() in seen_doi:
                errors.append(f"{label} Duplicate doi: {doi}")
            else:
                seen_doi.add(doi.lower())
        paper_url = item.get("paper_url")
        if paper_url is not None and (not isinstance(paper_url, str) or not URL_RE.match(paper_url)):
            errors.append(f"{label} Invalid paper_url: {paper_url}")


def validate_all(check_readme: bool = False) -> list[str]:
    errors: list[str] = []

    if not PAPERS_PATH.exists():
        return [f"Missing file: {PAPERS_PATH}"]
    if not BENCH_METRICS_PATH.exists():
        return [f"Missing file: {BENCH_METRICS_PATH}"]

    papers_data = json.loads(PAPERS_PATH.read_text(encoding="utf-8"))
    bm_data = json.loads(BENCH_METRICS_PATH.read_text(encoding="utf-8"))

    categories = {c["id"] for c in papers_data.get("categories", [])}
    if len(categories) < 3:
        errors.append("Expected at least 3 taxonomy categories in data/papers.json.")

    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    prev_date: str | None = None

    for idx, paper in enumerate(papers_data.get("papers", [])):
        pid = paper.get("id", f"<index-{idx}>")
        missing = REQUIRED_PAPER_FIELDS - set(paper.keys())
        if missing:
            errors.append(f"[{pid}] Missing required fields: {sorted(missing)}")
            continue

        if pid in seen_ids:
            errors.append(f"[{pid}] Duplicate paper id.")
        seen_ids.add(pid)

        if paper["paper_url"] in seen_urls:
            errors.append(f"[{pid}] Duplicate paper_url: {paper['paper_url']}")
        seen_urls.add(paper["paper_url"])

        if not DATE_RE.match(paper["date"]):
            errors.append(f"[{pid}] Invalid date '{paper['date']}' (expected YYYY-MM).")
        elif int(paper["date"][:4]) != paper["year"]:
            errors.append(
                f"[{pid}] Year {paper['year']} does not match date '{paper['date']}'."
            )

        if prev_date is not None and paper["date"] > prev_date:
            errors.append(
                f"[{pid}] data/papers.json is not sorted in non-increasing date order "
                f"('{paper['date']}' appears after '{prev_date}')."
            )
        prev_date = paper["date"]

        if not URL_RE.match(paper["paper_url"]):
            errors.append(f"[{pid}] Invalid paper_url: {paper['paper_url']}")

        for optional_url_key in ("code_url", "project_url"):
            val = paper.get(optional_url_key)
            if val is not None and not URL_RE.match(val):
                errors.append(f"[{pid}] Invalid {optional_url_key}: {val}")

        if paper["category"] not in categories:
            errors.append(f"[{pid}] Unknown primary category: {paper['category']}")
        for extra_cat in paper["also_categories"]:
            if extra_cat not in categories or extra_cat == paper["category"]:
                errors.append(f"[{pid}] Invalid also_categories entry: {extra_cat}")

        if not isinstance(paper["authors"], list) or not paper["authors"]:
            errors.append(f"[{pid}] Authors must be a non-empty list.")
        else:
            for author in paper["authors"]:
                if not author or author != author.strip():
                    errors.append(f"[{pid}] Untrimmed or empty author name: '{author}'")

        if not isinstance(paper["models"], list) or not paper["models"]:
            errors.append(f"[{pid}] Models must be a non-empty list.")

    # Validate benchmarks, metrics, frameworks
    for b in bm_data.get("benchmarks", []):
        for key in ("name", "type", "scale", "modality", "focus", "url", "paper_url"):
            if not b.get(key):
                errors.append(f"[Benchmark:{b.get('name')}] Missing '{key}'.")
        if not URL_RE.match(b.get("url", "")):
            errors.append(f"[Benchmark:{b.get('name')}] Invalid url: {b.get('url')}")
        if not URL_RE.match(b.get("paper_url", "")):
            errors.append(
                f"[Benchmark:{b.get('name')}] Invalid paper_url: {b.get('paper_url')}"
            )

    for grp in bm_data.get("metric_groups", []):
        if not grp.get("metrics"):
            errors.append(f"[MetricGroup:{grp.get('group')}] Empty metrics list.")
        for m in grp.get("metrics", []):
            for key in ("name", "granularity", "description", "reference"):
                if not m.get(key):
                    errors.append(f"[Metric:{m.get('name')}] Missing '{key}'.")

    for fw in bm_data.get("frameworks", []):
        if fw.get("paper_id") not in seen_ids:
            errors.append(
                f"[Framework:{fw.get('name')}] Unknown paper_id '{fw.get('paper_id')}'."
            )
        if not URL_RE.match(fw.get("url", "")):
            errors.append(f"[Framework:{fw.get('name')}] Invalid url: {fw.get('url')}")

    validate_seen_candidates(errors)

    # Validate the README taxonomy figure
    figure_path = ROOT / "figs" / "taxonomy.png"
    if not figure_path.exists():
        errors.append(f"Missing taxonomy figure: {figure_path}")
    elif not figure_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        errors.append(f"Taxonomy figure is not a PNG: {figure_path}")

    # Optionally check README sync
    if check_readme:
        if not README_PATH.exists():
            errors.append("README.md does not exist. Run python3 scripts/build_readme.py.")
        else:
            expected = render_readme()
            actual = README_PATH.read_text(encoding="utf-8")
            if actual != expected:
                errors.append(
                    "README.md is out of sync with data/*.json. "
                    "Run `python3 scripts/build_readme.py` to regenerate."
                )

            # Heading slugs and explicit HTML ids are both valid jump targets.
            readme_anchors = collect_readme_anchors(actual)
            for link_match in re.finditer(r"\]\(#([^)]+)\)", actual):
                anchor = link_match.group(1)
                if anchor not in readme_anchors:
                    errors.append(f"Broken internal README anchor link: #{anchor}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Awesome LRM Unlearning data.")
    parser.add_argument(
        "--check-readme",
        "--check",
        dest="check_readme",
        action="store_true",
        help="Also verify that README.md matches the generated output.",
    )
    args = parser.parse_args()

    errors = validate_all(check_readme=args.check_readme)
    if errors:
        print("Validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    papers_count = len(json.loads(PAPERS_PATH.read_text(encoding="utf-8"))["papers"])
    print(f"Validation passed ({papers_count} papers verified, taxonomy figure valid, README in sync={args.check_readme}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
