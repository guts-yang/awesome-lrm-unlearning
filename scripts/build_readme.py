#!/usr/bin/env python3
"""Deterministic README.md generator for Awesome LRM Unlearning."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PAPERS_PATH = ROOT / "data" / "papers.json"
BENCH_METRICS_PATH = ROOT / "data" / "benchmarks_metrics.json"
README_PATH = ROOT / "README.md"

GITHUB_BADGE = (
    "https://img.shields.io/badge/GitHub-181717?style=flat&logo=github&logoColor=white"
)
PROJECT_BADGE = "https://img.shields.io/badge/Project-2563EB?style=flat"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def short_authors(authors: list[str]) -> str:
    if len(authors) == 1:
        return authors[0].split()[-1]
    if len(authors) == 2:
        return f"{authors[0].split()[-1]} & {authors[1].split()[-1]}"
    return f"{authors[0].split()[-1]} et al."


def format_code_cell(paper: dict[str, Any], compact: bool = False) -> str:
    links: list[str] = []
    if paper.get("code_url"):
        if compact:
            links.append(f"[![GitHub]({GITHUB_BADGE})]({paper['code_url']})")
        else:
            links.append(f"[![GitHub]({GITHUB_BADGE})]({paper['code_url']})")
    if paper.get("project_url"):
        links.append(f"[![Project]({PROJECT_BADGE})]({paper['project_url']})")
    return " ".join(links) if links else "-"


def slugify_heading(heading: str) -> str:
    """Match GitHub Flavored Markdown (GFM) heading anchor generation."""
    cleaned = re.sub(r"[^\w\- ]", "", heading.lower())
    return cleaned.replace(" ", "-")


def render_readme() -> str:
    papers_data = load_json(PAPERS_PATH)
    bm_data = load_json(BENCH_METRICS_PATH)

    repo = papers_data["repository"]
    owner = repo["owner"]
    repo_name = repo["name"]
    categories = papers_data["categories"]
    cat_map = {c["id"]: c for c in categories}

    papers: list[dict[str, Any]] = sorted(
        papers_data["papers"],
        key=lambda p: (p["date"], p["id"]),
        reverse=True,
    )
    benchmarks = bm_data["benchmarks"]
    metric_groups = bm_data["metric_groups"]
    frameworks = bm_data["frameworks"]

    total_papers = len(papers)
    total_benchmarks = len(benchmarks)
    total_metrics = sum(len(g["metrics"]) for g in metric_groups)
    total_frameworks = len(frameworks)

    years = sorted({p["year"] for p in papers}, reverse=True)

    lines: list[str] = []

    # 1. Header & Badges (chrisliu298 + tamlhp style)
    lines.append(f"# {repo['title']}")
    lines.append("")
    lines.append('<p align="center">')
    lines.append(
        '  <a href="https://awesome.re"><img src="https://img.shields.io/badge/Awesome-LRM_Unlearning-0F172A?style=for-the-badge&labelColor=000000" alt="Awesome LRM Unlearning"></a>'
    )
    lines.append(
        f'  <a href="https://github.com/{owner}/{repo_name}/commits"><img src="https://img.shields.io/github/last-commit/{owner}/{repo_name}?style=for-the-badge&logo=github&logoColor=white&label=Last%20Commit&labelColor=000000&color=0F172A" alt="Last Commit"></a>'
    )
    lines.append(
        f'  <a href="https://github.com/{owner}/{repo_name}/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-0F172A?style=for-the-badge&labelColor=000000" alt="License"></a>'
    )
    lines.append("</p>")
    lines.append("")
    lines.append(repo["subtitle"])
    lines.append("")
    lines.append(
        f"As of the latest update, this repository curates **{total_papers}** core papers, "
        f"**{total_benchmarks}** benchmarks and evaluation suites, **{total_metrics}** LRM-specific evaluation metrics, "
        f"and **{total_frameworks}** open-source codebases and project portals."
    )
    lines.append("")
    lines.append(
        "> **Scope & Contributions:** This list strictly focuses on machine unlearning where **multi-step Chain-of-Thought (CoT) reasoning traces**, **thinking trajectories (`<think>...</think>`)**, or **Large Reasoning Models (LRMs)** are first-class objects of study. If your paper, benchmark, or codebase fits this scope, please open an [Issue](../../issues) or submit a [Pull Request](CONTRIBUTING.md)!"
    )
    lines.append("")

    # 2. Table of Contents
    lines.append("## Contents")
    lines.append("")
    lines.append("- [Overview: Why LRM & CoT Unlearning?](#overview-why-lrm--cot-unlearning)")
    lines.append("- [News & Highlights](#news--highlights)")
    lines.append("- [Papers by Research Taxonomy](#papers-by-research-taxonomy)")
    for c in categories:
        lines.append(f"  - [{c['title']}](#{slugify_heading(c['title'])})")
    lines.append("- [Papers by Chronological Order](#papers-by-chronological-order)")
    for yr in years:
        lines.append(f"  - [{yr}](#{yr})")
    lines.append("- [Benchmarks & Evaluation Suites](#benchmarks--evaluation-suites)")
    lines.append("- [Evaluation Metrics for LRM & CoT Unlearning](#evaluation-metrics-for-lrm--cot-unlearning)")
    lines.append("- [Open-Source Frameworks & Portals](#open-source-frameworks--portals)")
    lines.append("- [Contributing](#contributing)")
    lines.append("- [Citation](#citation)")
    lines.append("")

    # 3. Overview & Taxonomy Figure
    lines.append("## Overview: Why LRM & CoT Unlearning?")
    lines.append("")
    lines.append(
        "Conventional LLM unlearning operates on direct input-output mappings $q \\to a$, optimizing forget and retain losses solely over final answers. "
        "In contrast, **Large Reasoning Models (LRMs)**—such as OpenAI o1/o3-style models, DeepSeek-R1 and its distilled variants, QwQ, RLVR-trained checkpoints, and Reasoning MLLMs—explicitly generate an intermediate **Chain-of-Thought (CoT)** [Chain-of-Thought Prompting](https://arxiv.org/abs/2201.11903) ([GitHub](https://github.com/jasonwei20/chain-of-thought-prompting)) trajectory $c = [c_1, \\dots, c_T]$ (typically enclosed in `<think>...</think>`) before emitting a final answer $a$:"
    )
    lines.append("")
    lines.append("$$\\pi_{\\theta}(c, a \\mid q) = \\pi_{\\theta}(c \\mid q)\\,\\pi_{\\theta}(a \\mid q, c)$$")
    lines.append("")
    lines.append('<p align="center">')
    lines.append(
        '  <img src="figs/cot_prompting_comparison.png" alt="Comparison of Standard Prompting and Chain-of-Thought Prompting" width="90%">'
    )
    lines.append("  <br>")
    lines.append(
        '  <em>Figure 1 from <a href="https://arxiv.org/abs/2201.11903">Wei et al., Chain-of-Thought Prompting Elicits Reasoning in Large Language Models</a>.</em>'
    )
    lines.append("</p>")
    lines.append("")
    lines.append("Applying answer-centric unlearning to LRMs exposes a fundamental **forgetting–reasoning dilemma**:")
    lines.append("")
    lines.append(
        "1. **Residual CoT Leakage:** Erasing or refusing only at the final answer $a$ leaves sensitive, private, or hazardous knowledge intact within intermediate reasoning steps $c$, allowing trivial extraction or answer reconstruction."
    )
    lines.append(
        "2. **Reasoning Collapse:** Aggressively perturbing weights or hidden representations over long reasoning chains destabilizes multi-step deduction, causes repetitive token loops, suppresses closing `</think>` delimiters, or degrades general STEM reasoning (`AIME`, `MATH-500`, `GPQA`)."
    )
    lines.append(
        "3. **Decoding & Reasoning-Path Bypass:** Constrained decoding modes (`ZeroThink`, `LessThink`), multi-hop logical paths, and step-by-step reasoning attacks can resurface superficially suppressed knowledge."
    )
    lines.append("")
    lines.append('<p align="center">')
    lines.append('  <img src="figs/taxonomy.png" alt="LRM and CoT Machine Unlearning Framework and Taxonomy" width="100%">')
    lines.append("</p>")
    lines.append("")

    # 4. News
    lines.append("## News & Highlights")
    lines.append("")
    for item in papers_data["news"]:
        lines.append(f"- **`[{item['date']}]`** {item['content']}")
    lines.append("")

    # 5. View 1: Taxonomy-Structured Paper Catalog (tamlhp style)
    lines.append("---")
    lines.append("")
    lines.append("## Papers by Research Taxonomy")
    lines.append("")
    lines.append(
        "A taxonomy-organized comparison of LRM and CoT machine unlearning literature. "
        "Works spanning multiple pillars (e.g., introducing both a benchmark and an unlearning algorithm) are cross-referenced with `†`."
    )
    lines.append("")

    for cat in categories:
        cid = cat["id"]
        cat_papers = [
            p
            for p in papers
            if p["category"] == cid or cid in p.get("also_categories", [])
        ]
        lines.append(f"### {cat['title']}")
        lines.append("")
        lines.append(cat["description"])
        lines.append("")
        lines.append(
            "| **Paper Title** | **Date** | **Author(s)** | **Venue** | **Method** | **Stage** | **Target Scope** | **Code / Portal** |"
        )
        lines.append("| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |")
        for p in cat_papers:
            cross_mark = " †" if p["category"] != cid else ""
            venue_disp = f"*{p['venue']}*" if p["venue"] != "Preprint" else "*arXiv*"
            lines.append(
                f"| [{p['title']}]({p['paper_url']}){cross_mark} | {p['date']} | {short_authors(p['authors'])} | "
                f"{venue_disp} | `{p['method_name']}` | {p['stage']} | {p['target_scope']} | {format_code_cell(p, compact=True)} |"
            )
        lines.append("")

    # 6. View 2: Chronological Paper Feed (chrisliu298 style)
    lines.append("---")
    lines.append("")
    lines.append("## Papers by Chronological Order")
    lines.append("")
    lines.append(
        "Complete bibliographic entries sorted in reverse chronological order (`YYYY-MM`)."
    )
    lines.append("")

    for yr in years:
        lines.append(f"### {yr}")
        lines.append("")
        yr_papers = [p for p in papers if p["year"] == yr]
        for p in yr_papers:
            venue_str = "-" if p["venue"] == "Preprint" else p["venue"]
            cat_tags = [cat_map[p["category"]]["short_tag"]] + [
                cat_map[ac]["short_tag"] for ac in p.get("also_categories", [])
            ]
            cat_str = " / ".join(cat_tags)
            models_str = ", ".join(p["models"])
            lines.append(f"- [{p['title']}]({p['paper_url']})")
            lines.append(f"  - Author(s): {', '.join(p['authors'])}")
            lines.append(f"  - Date: {p['date']}")
            lines.append(f"  - Venue: {venue_str}")
            lines.append(f"  - Category: {cat_str} (`{p['target_scope']}`)")
            lines.append(f"  - Evaluated Backbones: {models_str}")
            lines.append(f"  - Summary: {p['summary']}")
            lines.append(f"  - Code: {format_code_cell(p)}")
        lines.append("")

    # 7. Benchmarks & Datasets (tamlhp style)
    lines.append("---")
    lines.append("")
    lines.append("## Benchmarks & Evaluation Suites")
    lines.append("")
    lines.append(
        "| **Benchmark / Dataset** | **Category** | **Scale & Splits** | **Modality** | **Evaluation Focus** | **Links** |"
    )
    lines.append("| :--- | :--- | :--- | :---: | :--- | :---: |")
    for b in benchmarks:
        link_parts = [f"[[Paper]]({b['paper_url']})"]
        if b["url"] != b["paper_url"]:
            link_parts.insert(0, f"[[Resource]]({b['url']})")
        lines.append(
            f"| **{b['name']}** | {b['type']} | {b['scale']} | {b['modality']} | {b['focus']} | {' '.join(link_parts)} |"
        )
    lines.append("")

    # 8. Evaluation Metrics (tamlhp style)
    lines.append("---")
    lines.append("")
    lines.append("## Evaluation Metrics for LRM & CoT Unlearning")
    lines.append("")
    lines.append(
        "Unlike standard LLM unlearning, evaluating LRMs requires disentangling **intermediate trace leakage**, **final answer erasure**, **reasoning utility & structural termination**, and **decoding-time robustness**."
    )
    lines.append("")

    for group in metric_groups:
        lines.append(f"### {group['group']}")
        lines.append("")
        lines.append(
            "| **Metric** | **Target Granularity** | **Mechanism / Definition** | **Primary Reference** |"
        )
        lines.append("| :--- | :---: | :--- | :--- |")
        for m in group["metrics"]:
            lines.append(
                f"| **{m['name']}** | {m['granularity']} | {m['description']} | {m['reference']} |"
            )
        lines.append("")

    # 9. Open-Source Frameworks & Portals (chrisliu298 style)
    lines.append("---")
    lines.append("")
    lines.append("## Open-Source Frameworks & Portals")
    lines.append("")
    for fw in frameworks:
        is_gh = "github.com" in fw["url"]
        badge = (
            f"[![GitHub]({GITHUB_BADGE})]({fw['url']})"
            if is_gh
            else f"[![Project]({PROJECT_BADGE})]({fw['url']})"
        )
        lines.append(f"- **[{fw['name']}]({fw['url']})** ({fw['venue']}) — {badge}")
        lines.append(f"  - {fw['description']}")
    lines.append("")

    # 10. Contributing, Citation & Star History
    lines.append("---")
    lines.append("")
    lines.append("## Contributing")
    lines.append("")
    lines.append(
        "Contributions are warmly welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed instructions or open a paper submission via our [GitHub Issue Template](../../issues/new/choose)."
    )
    lines.append("")
    lines.append("- **Strict Inclusion Criteria:**")
    lines.append(
        "  1. The work must explicitly investigate machine unlearning, selective forgetting, unlearning attacks/audits, or unlearning benchmarks where **intermediate Chain-of-Thought (CoT) reasoning traces**, **thinking trajectories (`<think>...</think>`)**, or **Large Reasoning Models (LRMs / Reasoning MLLMs / RLVR models)** are central to the problem formulation or evaluation."
    )
    lines.append(
        "  2. General LLM unlearning papers that only target final answers without reasoning-trace intervention, reasoning-level leakage analysis, or LRM evaluation are out of scope (for general LLM unlearning, see [chrisliu298/awesome-llm-unlearning](https://github.com/chrisliu298/awesome-llm-unlearning) and [tamlhp/awesome-machine-unlearning](https://github.com/tamlhp/awesome-machine-unlearning))."
    )
    lines.append("- **Quick Update Workflow:**")
    lines.append("  ```bash")
    lines.append("  # 1. Add or update entries in data/papers.json or data/benchmarks_metrics.json")
    lines.append("  # 2. Rebuild README.md and run schema & freshness checks")
    lines.append("  python3 scripts/build_readme.py")
    lines.append("  python3 scripts/validate_data.py --check-readme")
    lines.append("  ```")
    lines.append("")

    lines.append("## Citation")
    lines.append("")
    lines.append(
        "If you find this repository helpful in your research on LRM or CoT unlearning, please consider citing it:"
    )
    lines.append("")
    lines.append("```bibtex")
    lines.append("@misc{awesome-lrm-unlearning,")
    lines.append("  title        = {{Awesome LRM Unlearning: A Curated List of Chain-of-Thought and Large Reasoning Model Machine Unlearning}},")
    lines.append(f"  author       = {{{owner}}},")
    lines.append("  year         = {2026},")
    lines.append(f"  howpublished = {{\\url{{https://github.com/{owner}/{repo_name}}}}}")
    lines.append("}")
    lines.append("```")
    lines.append("")

    lines.append("## Star History")
    lines.append("")
    lines.append(
        f"[![Star History Chart](https://api.star-history.com/svg?repos={owner}/{repo_name}&type=Date)](https://star-history.com/#{owner}/{repo_name}&Date)"
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    content = render_readme()
    README_PATH.write_text(content, encoding="utf-8")
    print(f"Generated {README_PATH} ({len(content.splitlines())} lines).")


if __name__ == "__main__":
    main()
