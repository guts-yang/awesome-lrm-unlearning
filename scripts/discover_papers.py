#!/usr/bin/env python3
"""Discover new LRM and CoT unlearning papers and optionally open a review set.

The script searches arXiv and Semantic Scholar, deduplicates results against
each other and against data/papers.json, then writes a candidate report.
Structured inclusion requires DEEPSEEK_API_KEY. Without that key, or with
--report-only, it leaves the curated data unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_readme import PAPERS_PATH, README_PATH, ROOT, render_readme  # noqa: E402

SEEN_PATH = ROOT / "data" / "seen_candidates.json"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_API = "https://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-flash"
USER_AGENT = "awesome-lrm-unlearning-discovery/1.0"
S2_FIELDS = ",".join(
    [
        "title",
        "abstract",
        "authors",
        "year",
        "venue",
        "url",
        "externalIds",
        "publicationDate",
        "openAccessPdf",
    ]
)
ANCHORS = [
    {"name": "R-TOFU", "arxiv": "2505.15214"},
    {"name": "R2MU", "arxiv": "2506.12963"},
    {"name": "FUR", "arxiv": "2502.14829"},
    {"name": "RMLLMU-Bench", "arxiv": "2512.17911"},
]
UNLEARNING_TERMS = (
    "unlearning",
    "selective forgetting",
    "knowledge erasure",
    "machine unlearning",
    "forget-set",
    "forgetting",
)
REASONING_TERMS = (
    "reasoning model",
    "large reasoning",
    "chain-of-thought",
    "chain of thought",
    "reasoning trace",
    "thinking trajectory",
    "rlvr",
    "r-tofu",
    "deepseek-r1",
    "<think>",
)
VALID_CATEGORIES = {
    "parameter_update",
    "inference_time",
    "benchmarks",
    "attacks_auditing",
    "faithfulness",
}
ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})")
DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", re.I)
URL_RE = re.compile(r"https://[^\s)>\]]+")
CODE_HOST_RE = re.compile(r"https://(?:github\.com|gitlab\.com|huggingface\.co)/[^\s)>\]]+", re.I)
DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def urlopen_retry(request: urllib.request.Request):
    delay = 3.0
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            return urllib.request.urlopen(request, timeout=45)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 503} or attempt == 3:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else delay)
            delay *= 2
    if last_error:
        raise last_error
    raise RuntimeError("request failed")


def http_json(url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    data = None
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=req_headers)
    with urlopen_retry(request) as response:
        return json.loads(response.read().decode("utf-8"))


def http_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen_retry(request) as response:
        return response.read().decode("utf-8")


def normalize_title(title: str) -> str:
    text = title.lower().replace("\n", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_arxiv(value: str | None) -> str | None:
    if not value:
        return None
    match = ARXIV_RE.search(value)
    return match.group(1) if match else None


def extract_doi(value: str | None) -> str | None:
    if not value:
        return None
    match = DOI_RE.search(value)
    return match.group(1).rstrip(".").lower() if match else None


def extract_code_url(text: str | None) -> str | None:
    if not text:
        return None
    match = CODE_HOST_RE.search(text)
    return match.group(0).rstrip(".,;") if match else None


def surname(name: str) -> str:
    parts = [part for part in re.split(r"\s+", name.strip()) if part]
    return normalize_title(parts[-1]) if parts else ""


def parse_day(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19] if "T" in value else value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def candidate_key(item: dict[str, Any]) -> tuple[str, str]:
    if item.get("arxiv_id"):
        return ("arxiv", item["arxiv_id"])
    if item.get("doi"):
        return ("doi", item["doi"])
    return ("title", item.get("normalized_title") or normalize_title(item.get("title", "")))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_repo_index(papers: list[dict[str, Any]]) -> dict[str, Any]:
    index: dict[str, Any] = {"arxiv": {}, "doi": {}, "title": {}, "records": []}
    for paper in papers:
        record = {
            "title": paper["title"],
            "url": paper["paper_url"],
            "year": paper.get("year"),
            "surname": surname(paper["authors"][0]) if paper.get("authors") else "",
            "normalized_title": normalize_title(paper["title"]),
        }
        arxiv_id = extract_arxiv(paper.get("paper_url"))
        doi = extract_doi(paper.get("paper_url"))
        if arxiv_id:
            index["arxiv"][arxiv_id] = record
        if doi:
            index["doi"][doi] = record
        index["title"][record["normalized_title"]] = record
        index["records"].append(record)
    return index


def build_seen_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in payload.get("candidates", []):
        for key in (
            ("arxiv", item.get("arxiv_id")),
            ("doi", item.get("doi")),
            ("title", item.get("normalized_title")),
        ):
            if key[1]:
                index[f"{key[0]}:{key[1]}"] = item
    return index


def match_repo(item: dict[str, Any], index: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    if item.get("arxiv_id") and item["arxiv_id"] in index["arxiv"]:
        return index["arxiv"][item["arxiv_id"]], "arXiv id"
    if item.get("doi") and item["doi"] in index["doi"]:
        return index["doi"][item["doi"]], "DOI"
    normalized = item.get("normalized_title") or ""
    if normalized and normalized in index["title"]:
        return index["title"][normalized], "normalized title"
    first = surname(item["authors"][0]) if item.get("authors") else ""
    year = item.get("year")
    for record in index["records"]:
        if not first or not year or first != record["surname"] or year != record["year"]:
            continue
        if SequenceMatcher(None, normalized, record["normalized_title"]).ratio() >= 0.92:
            return record, "similar title, author, and year"
    return None


def matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term in lowered]


def passes_lexical_gate(item: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    text = f"{item.get('title', '')}\n{item.get('abstract', '')}"
    unlearning = matched_terms(text, UNLEARNING_TERMS)
    reasoning = matched_terms(text, REASONING_TERMS)
    return bool(unlearning and reasoning), unlearning, reasoning


def blank_candidate() -> dict[str, Any]:
    return {
        "title": "",
        "authors": [],
        "abstract": "",
        "venue": "",
        "published": None,
        "year": None,
        "paper_url": "",
        "arxiv_id": None,
        "doi": None,
        "code_url": None,
        "sources": [],
        "normalized_title": "",
    }


def from_arxiv_entry(entry: ET.Element, source: str) -> dict[str, Any]:
    item = blank_candidate()
    item["title"] = " ".join((entry.findtext(f"{ATOM}title") or "").split())
    item["abstract"] = " ".join((entry.findtext(f"{ATOM}summary") or "").split())
    item["authors"] = [
        " ".join((author.findtext(f"{ATOM}name") or "").split())
        for author in entry.findall(f"{ATOM}author")
        if author.findtext(f"{ATOM}name")
    ]
    published = entry.findtext(f"{ATOM}published")
    item["published"] = published
    parsed = parse_day(published)
    item["year"] = parsed.year if parsed else None
    raw_id = entry.findtext(f"{ATOM}id") or ""
    item["arxiv_id"] = extract_arxiv(raw_id)
    item["paper_url"] = f"https://arxiv.org/abs/{item['arxiv_id']}" if item["arxiv_id"] else raw_id
    item["venue"] = "arXiv"
    for link in entry.findall(f"{ATOM}link"):
        href = link.attrib.get("href", "")
        if "doi.org/" in href:
            item["doi"] = extract_doi(href)
    item["code_url"] = extract_code_url(f"{item['title']}\n{item['abstract']}")
    item["normalized_title"] = normalize_title(item["title"])
    item["sources"] = [source]
    return item


def from_s2_paper(paper: dict[str, Any], source: str) -> dict[str, Any] | None:
    if not paper or not paper.get("title"):
        return None
    item = blank_candidate()
    item["title"] = " ".join(str(paper.get("title", "")).split())
    item["abstract"] = " ".join(str(paper.get("abstract") or "").split())
    item["authors"] = [
        author.get("name", "")
        for author in paper.get("authors") or []
        if author.get("name")
    ]
    item["venue"] = paper.get("venue") or "Unknown"
    item["published"] = paper.get("publicationDate")
    parsed = parse_day(item["published"])
    item["year"] = parsed.year if parsed else paper.get("year")
    external = paper.get("externalIds") or {}
    item["arxiv_id"] = extract_arxiv(str(external.get("ArXiv") or ""))
    item["doi"] = extract_doi(str(external.get("DOI") or "")) or extract_doi(paper.get("url"))
    if item["arxiv_id"]:
        item["paper_url"] = f"https://arxiv.org/abs/{item['arxiv_id']}"
    elif item["doi"]:
        item["paper_url"] = f"https://doi.org/{item['doi']}"
    else:
        item["paper_url"] = paper.get("url") or ""
    item["code_url"] = extract_code_url(f"{item['title']}\n{item['abstract']}")
    pdf = (paper.get("openAccessPdf") or {}).get("url")
    if not item["code_url"] and pdf and extract_code_url(pdf):
        item["code_url"] = extract_code_url(pdf)
    item["normalized_title"] = normalize_title(item["title"])
    item["sources"] = [source]
    return item


def merge_candidate(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    for source in new.get("sources", []):
        if source not in existing["sources"]:
            existing["sources"].append(source)
    for key in ("abstract", "venue", "published", "paper_url", "arxiv_id", "doi", "code_url"):
        if not existing.get(key) and new.get(key):
            existing[key] = new[key]
    if len(new.get("authors") or []) > len(existing.get("authors") or []):
        existing["authors"] = new["authors"]
    if not existing.get("year") and new.get("year"):
        existing["year"] = new["year"]
    return existing


def search_arxiv(cutoff: datetime, failures: list[str]) -> list[dict[str, Any]]:
    query = (
        "(cat:cs.CL OR cat:cs.LG OR cat:cs.AI OR cat:cs.CV) AND "
        '(all:unlearning OR all:"selective forgetting" OR all:"knowledge erasure") AND '
        '(all:"chain-of-thought" OR all:"chain of thought" OR all:"reasoning model" '
        'OR all:"reasoning trace" OR all:"thinking trajectory" OR all:"large reasoning" '
        'OR all:RLVR OR all:"R-TOFU" OR all:"DeepSeek-R1")'
    )
    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "start": 0,
            "max_results": 50,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    try:
        root = ET.fromstring(http_text(f"{ARXIV_API}?{params}"))
    except (urllib.error.URLError, ET.ParseError, TimeoutError) as exc:
        failures.append(f"arXiv search failed: {exc}")
        return []
    found = []
    for entry in root.findall(f"{ATOM}entry"):
        item = from_arxiv_entry(entry, "arXiv search")
        published = parse_day(item.get("published"))
        if published and published >= cutoff:
            found.append(item)
    return found


def search_semantic_scholar(cutoff: datetime, failures: list[str]) -> list[dict[str, Any]]:
    query = "machine unlearning chain-of-thought large reasoning model"
    url = f"{S2_API}/paper/search?{urllib.parse.urlencode({'query': query, 'limit': 50, 'fields': S2_FIELDS})}"
    try:
        payload = http_json(url)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        failures.append(f"Semantic Scholar search failed: {exc}")
        return []
    found = []
    for paper in payload.get("data") or []:
        item = from_s2_paper(paper, "Semantic Scholar search")
        if not item:
            continue
        published = parse_day(item.get("published"))
        if published and published >= cutoff:
            found.append(item)
        elif not published:
            failures.append(f"Skipped Semantic Scholar result without a publication date: {item['title']}")
    return found


def search_forward_citations(cutoff: datetime, failures: list[str]) -> list[dict[str, Any]]:
    found = []
    for anchor in ANCHORS:
        fields = ",".join(f"citingPaper.{field}" for field in S2_FIELDS.split(","))
        url = f"{S2_API}/paper/ARXIV:{anchor['arxiv']}/citations?{urllib.parse.urlencode({'limit': 50, 'fields': fields})}"
        try:
            payload = http_json(url)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            failures.append(f"Semantic Scholar citations for {anchor['name']} failed: {exc}")
            time.sleep(3)
            continue
        for row in payload.get("data") or []:
            item = from_s2_paper(row.get("citingPaper") or {}, f"Semantic Scholar forward citation of {anchor['name']}")
            if not item:
                continue
            published = parse_day(item.get("published"))
            if published and published >= cutoff:
                found.append(item)
            elif not published:
                failures.append(
                    f"Skipped undated citation of {anchor['name']}: {item['title']}"
                )
        time.sleep(3)
    return found


def deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []
    for item in items:
        if not item.get("normalized_title"):
            item["normalized_title"] = normalize_title(item.get("title", ""))
        key = candidate_key(item)
        if key in merged:
            merge_candidate(merged[key], item)
        else:
            merged[key] = item
            order.append(key)
    return [merged[key] for key in order]


def source_text(item: dict[str, Any]) -> str:
    return "\n".join(
        [
            item.get("title") or "",
            item.get("abstract") or "",
            item.get("paper_url") or "",
            item.get("code_url") or "",
        ]
    )


def sanitize_url(url: str | None, text: str) -> str | None:
    if not url or not url.startswith("https://") or url not in text:
        return None
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if response.status == 404:
                return None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
    except (urllib.error.URLError, TimeoutError):
        return url
    return url


def llm_adjudicate(item: dict[str, Any], api_key: str) -> dict[str, Any]:
    system = (
        "You screen papers for a curated LRM and Chain-of-Thought machine-unlearning list. "
        "Include a paper only when multi-step CoT traces, thinking trajectories, LRMs, "
        "reasoning MLLMs, or RLVR reasoning are central to the unlearning method, benchmark, attack, audit, or faithfulness test. "
        "Exclude generic answer-only LLM unlearning, prompt-PII redaction that is not machine unlearning, "
        "hallucination-span editing that is not CoT, and broad surveys that merely mention reasoning models. "
        "If a paper evaluates an LRM or R-TOFU but reports only answer-level MU/FE, say that explicitly in target_scope and summary. "
        "Return JSON only with keys decision (in_scope, borderline, out_of_scope), confidence (high or borderline), "
        "inclusion_rationale, and paper. paper is null when out_of_scope; otherwise it contains id, title, method_name, "
        "authors, date, year, venue, paper_url, code_url, project_url, category, also_categories, subcategory, stage, "
        "target_scope, models, and summary. category must be one of parameter_update, inference_time, benchmarks, "
        "attacks_auditing, faithfulness. Use null for unknown code or project URLs. Do not invent URLs."
    )
    user = json.dumps(
        {
            "title": item.get("title"),
            "authors": item.get("authors"),
            "date": (item.get("published") or "")[:7],
            "venue": item.get("venue"),
            "paper_url": item.get("paper_url"),
            "abstract": item.get("abstract"),
            "sources": item.get("sources"),
        },
        ensure_ascii=False,
    )
    payload = http_json(
        DEEPSEEK_URL,
        {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "stream": False,
        },
        {"Authorization": f"Bearer {api_key}"},
    )
    content = payload["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
    return json.loads(content)


def validate_extracted_paper(paper: dict[str, Any], text: str) -> list[str]:
    errors = []
    required = [
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
    ]
    missing = [key for key in required if key not in paper]
    if missing:
        return [f"missing fields: {', '.join(missing)}"]
    if paper["category"] not in VALID_CATEGORIES:
        errors.append("invalid category")
    if not isinstance(paper["authors"], list) or not paper["authors"]:
        errors.append("authors must be a non-empty list")
    if not isinstance(paper["models"], list) or not paper["models"]:
        errors.append("models must be a non-empty list")
    if not isinstance(paper["also_categories"], list):
        errors.append("also_categories must be a list")
    if not DATE_RE.match(str(paper["date"])) or int(str(paper["date"])[:4]) != paper["year"]:
        errors.append("date and year do not match YYYY-MM")
    if not str(paper["paper_url"]).startswith("https://"):
        errors.append("paper_url must be https")
    for key in ("code_url", "project_url"):
        if paper[key] is not None and sanitize_url(str(paper[key]), text) is None:
            paper[key] = None
    return errors


def slug_id(paper: dict[str, Any]) -> str:
    author = surname(paper["authors"][0]) if paper.get("authors") else "paper"
    year = str(paper.get("year") or "0000")
    method = normalize_title(str(paper.get("method_name") or paper.get("title") or "paper")).split(" ")
    token = next((part for part in method if part not in {"a", "an", "the", "for", "of"}), "paper")
    return f"{author}{year}{token}"[:48]


def insert_paper(papers: list[dict[str, Any]], paper: dict[str, Any]) -> None:
    existing_ids = {item["id"] for item in papers}
    if paper["id"] in existing_ids:
        suffix = 2
        while f"{paper['id']}-{suffix}" in existing_ids:
            suffix += 1
        paper["id"] = f"{paper['id']}-{suffix}"
    position = next((idx for idx, item in enumerate(papers) if item["date"] < paper["date"]), len(papers))
    papers.insert(position, paper)


def upsert_seen(payload: dict[str, Any], item: dict[str, Any], status: str, today: str) -> None:
    candidates = payload.setdefault("candidates", [])
    for current in candidates:
        same = (
            (item.get("arxiv_id") and current.get("arxiv_id") == item.get("arxiv_id"))
            or (item.get("doi") and current.get("doi") == item.get("doi"))
            or current.get("normalized_title") == item.get("normalized_title")
        )
        if same:
            current["status"] = status
            current["last_seen"] = today
            current["paper_url"] = item.get("paper_url")
            return
    candidates.append(
        {
            "title": item.get("title"),
            "normalized_title": item.get("normalized_title"),
            "arxiv_id": item.get("arxiv_id"),
            "doi": item.get("doi"),
            "paper_url": item.get("paper_url"),
            "status": status,
            "first_seen": today,
            "last_seen": today,
        }
    )


def render_report(meta: dict[str, Any], groups: dict[str, list[dict[str, Any]]], failures: list[str]) -> str:
    lines = [
        "# Paper Discovery Report",
        "",
        f"- Run time: {meta['run_time']}",
        f"- Window: {meta['window_start']} to {meta['window_end']}",
        "- Sources: arXiv, Semantic Scholar",
        f"- Mode: {meta['mode']}",
        "",
        "## Summary",
        "",
        f"- Retrieved: {meta['retrieved']}",
        f"- Unique after search deduplication: {meta['unique']}",
        f"- Already in repository: {len(groups['already'])}",
        f"- Previously reported: {len(groups['seen'])}",
        f"- New candidates: {len(groups['possible']) + len(groups['out']) + len(groups['accepted'])}",
        "",
        "## Already in repository",
        "",
    ]
    if groups["already"]:
        for item in groups["already"]:
            lines.append(
                f"- {item['title']} — matched by {item['match_reason']} — {item['match_url']}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Accepted for review", ""])
    if groups["accepted"]:
        for item in groups["accepted"]:
            lines.extend(render_candidate(item, "accepted"))
    else:
        lines.append("- None")
    lines.extend(["", "## Candidate: possible_in_scope", ""])
    if groups["possible"]:
        for item in groups["possible"]:
            lines.extend(render_candidate(item, "possible"))
    else:
        lines.append("- None")
    lines.extend(["", "## Candidate: likely_out_of_scope", ""])
    if groups["out"]:
        for item in groups["out"]:
            lines.extend(render_candidate(item, "out"))
    else:
        lines.append("- None")
    if failures:
        lines.extend(["", "## Retrieval failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    lines.append("")
    return "\n".join(lines)


def render_candidate(item: dict[str, Any], kind: str) -> list[str]:
    lines = [
        f"### {item['title']}",
        "",
        f"- Date: {(item.get('published') or 'unknown')[:10]}",
        f"- Authors: {', '.join(item.get('authors') or []) or '-'}",
        f"- Venue: {item.get('venue') or '-'}",
        f"- Paper: {item.get('paper_url') or '-'}",
        f"- Code: {item.get('code_url') or '-'}",
        f"- Source: {'; '.join(item.get('sources') or [])}",
        f"- Matched unlearning terms: {', '.join(f'`{term}`' for term in item.get('unlearning_terms') or []) or '-'}",
        f"- Matched reasoning terms: {', '.join(f'`{term}`' for term in item.get('reasoning_terms') or []) or '-'}",
    ]
    if kind == "possible":
        lines.append(f"- Rule-based suggestion: `{item.get('suggestion') or 'unclassified'}`")
        lines.append("- Manual decision needed: Does the paper treat the reasoning trace or LRM as a first-class unlearning target?")
    elif kind == "out":
        lines.append(f"- Rule reason: {item.get('rule_reason') or 'Outside the lexical LRM/CoT unlearning gate.'}")
    elif kind == "accepted":
        lines.append(f"- Decision: `{item.get('decision')}` / `{item.get('confidence')}`")
        lines.append(f"- Rationale: {item.get('inclusion_rationale') or '-'}")
    if item.get("abstract"):
        lines.extend(["", item["abstract"], ""])
    else:
        lines.append("")
    return lines


def suggestion_for(item: dict[str, Any]) -> str:
    text = f"{item.get('title', '')} {item.get('abstract', '')}".lower()
    if "benchmark" in text or "dataset" in text:
        return "benchmarks"
    if "attack" in text or "audit" in text or "vulnerab" in text:
        return "attacks_auditing"
    if "faithfulness" in text:
        return "faithfulness"
    if "inference" in text or "training-free" in text or "test-time" in text:
        return "inference_time"
    return "parameter_update"


def render_pr_body(groups: dict[str, list[dict[str, Any]]]) -> str:
    lines = ["## Proposed additions", ""]
    for item in groups["accepted"]:
        paper = item.get("paper") or {}
        authors = ", ".join(paper.get("authors") or item.get("authors") or []) or "-"
        code = paper.get("code_url") or "-"
        title = paper.get("title") or item.get("title")
        lines.append(
            f"- **{title}** — {authors} — `{paper.get('category') or '-'}` — code: {code} — confidence `{item.get('confidence') or '-'}`"
        )
        lines.append(f"  - Why: {item.get('inclusion_rationale') or '-'}")
    lines.extend(["", "<details>", "<summary>Excluded this round</summary>", ""])
    if groups["out"]:
        lines.extend(f"- {item['title']}: {item.get('rule_reason') or '-'}" for item in groups["out"])
    else:
        lines.append("- None")
    lines.extend(["", "</details>", ""])
    return "\n".join(lines)


def write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def set_github_output(key: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"{key}={value}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and key == "report_path":
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(Path(value).read_text(encoding="utf-8"))


def discover(args: argparse.Namespace) -> int:
    papers_data = load_json(PAPERS_PATH)
    seen_data = load_json(SEEN_PATH)
    repo_index = build_repo_index(papers_data["papers"])
    seen_index = build_seen_index(seen_data)
    now = utc_now()
    cutoff = now - timedelta(days=args.lookback_days)
    failures: list[str] = []
    retrieved = search_arxiv(cutoff, failures)
    time.sleep(3)
    retrieved.extend(search_semantic_scholar(cutoff, failures))
    time.sleep(3)
    retrieved.extend(search_forward_citations(cutoff, failures))
    unique = deduplicate(retrieved)
    groups: dict[str, list[dict[str, Any]]] = {
        "already": [],
        "seen": [],
        "possible": [],
        "out": [],
        "accepted": [],
    }
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    report_only = args.report_only or not api_key
    today = now.date().isoformat()
    changed = False

    for item in unique:
        repo_match = match_repo(item, repo_index)
        if repo_match:
            record, reason = repo_match
            item["match_reason"] = reason
            item["match_url"] = record["url"]
            groups["already"].append(item)
            continue
        identity = candidate_key(item)
        seen_hit = seen_index.get(f"{identity[0]}:{identity[1]}")
        if seen_hit:
            groups["seen"].append(item)
            continue
        passed, unlearning, reasoning = passes_lexical_gate(item)
        item["unlearning_terms"] = unlearning
        item["reasoning_terms"] = reasoning
        if not passed:
            item["rule_reason"] = "Title and abstract do not jointly show unlearning and CoT/LRM reasoning."
            groups["out"].append(item)
            if not report_only:
                upsert_seen(seen_data, item, "rejected", today)
            continue
        item["suggestion"] = suggestion_for(item)
        if report_only:
            groups["possible"].append(item)
            continue
        try:
            decision = llm_adjudicate(item, api_key)
        except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
            failures.append(f"LLM adjudication failed for {item['title']}: {exc}")
            groups["possible"].append(item)
            continue
        verdict = decision.get("decision")
        item["decision"] = verdict
        item["confidence"] = decision.get("confidence")
        item["inclusion_rationale"] = decision.get("inclusion_rationale")
        paper = decision.get("paper")
        if verdict in {"in_scope", "borderline"} and isinstance(paper, dict):
            paper.setdefault("id", slug_id(paper if paper.get("authors") else item))
            paper.setdefault("paper_url", item.get("paper_url"))
            errors = validate_extracted_paper(paper, source_text(item))
            if errors:
                failures.append(f"Rejected extracted metadata for {item['title']}: {'; '.join(errors)}")
                groups["possible"].append(item)
            elif match_repo(
                {
                    "title": paper["title"],
                    "arxiv_id": extract_arxiv(paper["paper_url"]),
                    "doi": extract_doi(paper["paper_url"]),
                    "normalized_title": normalize_title(paper["title"]),
                    "authors": paper["authors"],
                    "year": paper["year"],
                },
                repo_index,
            ):
                groups["already"].append(item)
            else:
                insert_paper(papers_data["papers"], paper)
                repo_index = build_repo_index(papers_data["papers"])
                item["paper"] = paper
                groups["accepted"].append(item)
                upsert_seen(seen_data, item, "accepted", today)
                changed = True
        else:
            item["rule_reason"] = item.get("inclusion_rationale") or "LLM marked the paper out of scope."
            groups["out"].append(item)
            upsert_seen(seen_data, item, "rejected", today)

    if changed and not report_only:
        PAPERS_PATH.write_text(json.dumps(papers_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        SEEN_PATH.write_text(json.dumps(seen_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        README_PATH.write_text(render_readme(), encoding="utf-8")
        import subprocess

        validation = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_data.py"), "--check-readme"],
            cwd=ROOT,
            check=False,
        )
        if validation.returncode != 0:
            failures.append("Validation failed after inserting papers; no pull request should be opened.")
            changed = False
            report_status = 1
        else:
            report_status = 0
    else:
        report_status = 0
    mode = "report_only (LLM disabled)" if report_only else "llm_review"
    report = render_report(
        {
            "run_time": now.strftime("%Y-%m-%d %H:%M UTC"),
            "window_start": cutoff.date().isoformat(),
            "window_end": now.date().isoformat(),
            "mode": mode,
            "retrieved": len(retrieved),
            "unique": len(unique),
        },
        groups,
        failures,
    )
    report_path = Path(args.report)
    candidates_path = Path(args.candidates)
    write_output(report_path, report)
    write_output(candidates_path, json.dumps({"candidates": unique, "failures": failures}, indent=2, ensure_ascii=False) + "\n")
    if groups["accepted"]:
        write_output(ROOT / "artifacts" / "pr-body.md", render_pr_body(groups))
    set_github_output("changed", "true" if changed else "false")
    set_github_output("report_path", str(report_path))
    print(report)
    return report_status


def self_test() -> int:
    papers = load_json(PAPERS_PATH)["papers"]
    index = build_repo_index(papers)
    known = papers[0]
    matched = match_repo(
        {
            "title": known["title"],
            "authors": known["authors"],
            "year": known["year"],
            "arxiv_id": extract_arxiv(known["paper_url"]),
            "doi": extract_doi(known["paper_url"]),
            "normalized_title": normalize_title(known["title"]),
        },
        index,
    )
    if not matched:
        print("Self-test failed: existing paper was not recognized.", file=sys.stderr)
        return 1
    novel = match_repo(
        {
            "title": "A Completely Different Hypothetical Paper About Cooking",
            "authors": ["Nobody Example"],
            "year": 1900,
            "arxiv_id": None,
            "doi": None,
            "normalized_title": normalize_title("A Completely Different Hypothetical Paper About Cooking"),
        },
        index,
    )
    if novel:
        print("Self-test failed: unrelated title matched the repository.", file=sys.stderr)
        return 1
    merged = deduplicate(
        [
            {"title": "Same Paper", "arxiv_id": "2601.00001", "normalized_title": "same paper", "sources": ["arXiv search"], "authors": ["A"]},
            {"title": "Same Paper", "arxiv_id": "2601.00001", "normalized_title": "same paper", "sources": ["Semantic Scholar search"], "authors": ["A"]},
        ]
    )
    if len(merged) != 1 or len(merged[0]["sources"]) != 2:
        print("Self-test failed: search results were not merged.", file=sys.stderr)
        return 1
    print("Self-test passed (repository deduplication and search deduplication).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover LRM and CoT unlearning papers.")
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--report", default=str(ROOT / "artifacts" / "paper-discovery-report.md"))
    parser.add_argument("--candidates", default=str(ROOT / "artifacts" / "paper-discovery-candidates.json"))
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    return discover(args)


if __name__ == "__main__":
    raise SystemExit(main())
