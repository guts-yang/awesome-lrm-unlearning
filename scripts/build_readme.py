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


def paper_anchor(paper_id: str) -> str:
    """Stable fragment id for one chronological paper entry.

    Those entries are list items, so GitHub does not assign a heading
    anchor, and a title slug can collide. The paper id survives regeneration.
    """
    return f"paper-{paper_id}"


_EXPLICIT_ANCHOR_RE = re.compile(
    r"""<a\b[^>]*\bid\s*=\s*["']([^"']+)["']""",
    flags=re.IGNORECASE,
)


def collect_readme_anchors(markdown: str) -> set[str]:
    """Heading slugs plus explicit HTML ids that in-page links can target."""
    headings = {
        slugify_heading(match.group(1).strip())
        for match in re.finditer(r"^#{1,6}\s+(.+)$", markdown, flags=re.MULTILINE)
    }
    return headings | set(_EXPLICIT_ANCHOR_RE.findall(markdown))


def apply_highlight_links(
    content: str,
    links: list[dict[str, Any]] | None,
    paper_ids: set[str],
) -> str:
    """Wrap highlight phrases in links to a paper entry or a section anchor."""
    if not links:
        raise ValueError(f"Highlight has no jump target: {content[:80]}")

    # Longer phrases first so a short label cannot consume part of a longer one.
    ordered = sorted(links, key=lambda item: len(item.get("text", "")), reverse=True)
    for item in ordered:
        text = item.get("text", "")
        has_paper = "paper_id" in item
        has_anchor = "anchor" in item
        if not text or has_paper == has_anchor:
            raise ValueError(
                "Each highlight link needs text and exactly one of paper_id or anchor."
            )
        if has_paper:
            paper_id = item["paper_id"]
            if paper_id not in paper_ids:
                raise ValueError(f"Highlight links unknown paper id: {paper_id}")
            anchor = paper_anchor(paper_id)
        else:
            anchor = item["anchor"]
            if not isinstance(anchor, str) or not anchor or anchor.startswith("#"):
                raise ValueError(f"Highlight section anchor must be a bare id: {anchor!r}")
        if content.count(text) != 1:
            raise ValueError(f"Highlight link text must appear exactly once: {text}")
        content = content.replace(text, f"[{text}](#{anchor})", 1)
    return content


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
        f'  <a href="#papers-by-chronological-order"><img src="https://img.shields.io/badge/Papers-{total_papers}-0F172A?style=for-the-badge&labelColor=000000" alt="{total_papers} registered papers"></a>'
    )
    lines.append(
        f'  <a href="https://github.com/{owner}/{repo_name}/commits"><img src="https://img.shields.io/github/last-commit/{owner}/{repo_name}?style=for-the-badge&logo=github&logoColor=white&label=Last%20Commit&labelColor=000000&color=0F172A" alt="Last Commit"></a>'
    )
    lines.append(
        f'  <a href="https://github.com/{owner}/{repo_name}/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-0F172A?style=for-the-badge&labelColor=000000" alt="License"></a>'
    )
    lines.append("</p>")
    lines.append("")
    # Opening prose is maintained here. The JSON subtitle is repository metadata and is not printed.
    lines.append(
        "This repository lists papers, benchmarks, evaluation metrics, and code for machine unlearning "
        "in large reasoning models (LRMs) and chain-of-thought (CoT) reasoning. "
        "It is a reading list for work on the reasoning trace: "
        "the steps a model writes before the final answer, often inside `<think>...</think>`."
    )
    lines.append("")
    lines.append(
        f"The list currently contains **{total_papers}** papers, "
        f"**{total_benchmarks}** benchmarks and evaluation suites, **{total_metrics}** LRM-specific evaluation metrics, "
        f"and **{total_frameworks}** codebases and project pages."
    )
    lines.append("")
    lines.append(
        "> **Scope.** An entry belongs here when multi-step chain-of-thought traces, "
        "thinking trajectories (`<think>...</think>`), or large reasoning models are central "
        "to the method or the evaluation. To add a paper, benchmark, or codebase, open an "
        "[Issue](../../issues) or send a [Pull Request](CONTRIBUTING.md)."
    )
    lines.append("")
    lines.append(
        "> **Survey.** For a field overview, research timeline, and beginner-friendly "
        "reading guide, see the [LRM Unlearning Survey (rendered)]"
        "(https://guts-yang.github.io/awesome-lrm-unlearning/). "
        "Opens in English by default; use the **EN / 中文** switcher at the "
        "top-right for the Chinese version."
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
        "Standard LLM unlearning scores a map from a question $q$ to an answer $a$. "
        "The forget loss and the retain loss are computed on that final answer."
    )
    lines.append("")
    lines.append(
        "A large reasoning model writes a chain-of-thought before the answer. "
        "Models in this setting include OpenAI o1/o3-style systems, DeepSeek-R1 and its distilled variants, "
        "QwQ, RLVR-trained checkpoints, and reasoning multimodal LLMs. "
        "The trace $c = [c_1, \\dots, c_T]$ is usually wrapped in `<think>...</think>`, and the answer $a$ follows it. "
        "The prompting setup is the one in [Chain-of-Thought Prompting](https://arxiv.org/abs/2201.11903) "
        "([GitHub](https://github.com/jasonwei20/chain-of-thought-prompting)). "
        "Generation then factors as"
    )
    lines.append("")
    lines.append("$$\\pi_{\\theta}(c, a \\mid q) = \\pi_{\\theta}(c \\mid q)\\,\\pi_{\\theta}(a \\mid q, c)$$")
    lines.append("")
    lines.append('<table align="center"><tr>')
    lines.append("  <td align=\"center\" valign=\"top\" width=\"50%\">")
    lines.append(
        '    <a href="https://arxiv.org/abs/2201.11903"><img src="figs/cot-prompting-figure-1.png" alt="Comparison of Standard Prompting and Chain-of-Thought Prompting" width="100%"></a>'
    )
    lines.append("    <br>")
    lines.append(
        '    <em>Figure 1 from <a href="https://arxiv.org/abs/2201.11903">Wei et al., Chain-of-Thought Prompting Elicits Reasoning in Large Language Models</a>.</em>'
    )
    lines.append("  </td>")
    lines.append("  <td align=\"center\" valign=\"top\" width=\"50%\">")
    lines.append(
        '    <a href="https://arxiv.org/abs/2505.15214"><img src="figs/rtofu-figure-1.png" alt="R-TOFU benchmark for unlearning in large reasoning models" width="100%"></a>'
    )
    lines.append("    <br>")
    lines.append(
        '    <em>Figure 1 from <a href="https://arxiv.org/abs/2505.15214">R-TOFU: Unlearning in Large Reasoning Models</a>.</em>'
    )
    lines.append("  </td>")
    lines.append("</tr></table>")
    lines.append("")
    lines.append("Methods that edit only the final answer meet three failure modes on these models.")
    lines.append("")
    lines.append(
        "1. **Residual CoT leakage.** Deleting or refusing the answer $a$ can leave sensitive, private, or hazardous content inside the trace $c$. The steps themselves are enough to reconstruct it."
    )
    lines.append(
        "2. **Reasoning collapse.** Large edits to weights or hidden states along a long trace break multi-step deduction. The usual signs are repeated tokens, a missing closing `</think>` tag, and lower accuracy on general STEM sets (`AIME`, `MATH-500`, `GPQA`)."
    )
    lines.append(
        "3. **Decoding and reasoning-path bypass.** Constrained decoding (`ZeroThink`, `LessThink`), multi-hop logical paths, and step-by-step prompts can surface knowledge that no longer appears in a normal answer."
    )
    lines.append("")
    lines.append('<p align="center">')
    lines.append('  <img src="figs/taxonomy.png" alt="LRM and CoT Machine Unlearning Framework and Taxonomy" width="100%">')
    lines.append("</p>")
    lines.append("")
    lines.append(
        "Read the figure in two passes. The top row is the problem setting. "
        "A forget query $q$ enters a target model $\\pi_{\\theta}$. "
        "The model writes a reasoning trace $c$, then an answer $a$. Unlearning has to cover both. "
        "The outcome boxes are residual CoT leakage, reasoning collapse, and collapse-free unlearning, "
        "where the sensitive content is gone and the trace still ends coherently."
    )
    lines.append("")
    lines.append(
        "The bottom row matches the five tables below, from left to right: parameter updates, inference-time control, "
        "benchmarks, attacks and audits, and CoT faithfulness. Keywords in each box are examples from that track."
    )
    lines.append("")

    # 4. News. Named papers jump to their chronological entry; named
    # sections jump to that heading. Link text is the original phrase.
    lines.append("## News & Highlights")
    lines.append("")
    paper_ids = {p["id"] for p in papers}
    for item in papers_data["news"]:
        body = apply_highlight_links(item["content"], item.get("links"), paper_ids)
        lines.append(f"- **`[{item['date']}]`** {body}")
    lines.append("")

    # 5. View 1: Taxonomy-Structured Paper Catalog (tamlhp style)
    lines.append("---")
    lines.append("")
    lines.append("## Papers by Research Taxonomy")
    lines.append("")
    lines.append(
        "Papers are grouped by the question they study. Each paper has one primary track. "
        "A second row, marked `†`, appears when the same paper also belongs elsewhere, "
        "for example when it releases both a benchmark and an unlearning algorithm."
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
        "Full entries in reverse chronological order (`YYYY-MM`). "
        "Each entry gives the authors, venue, category, evaluated models, a one-line summary, and a code link when one is public."
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
            lines.append(
                f'- <a id="{paper_anchor(p["id"])}"></a>[{p["title"]}]({p["paper_url"]})'
            )
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
        "Datasets and suites for trace leakage, answer erasure, multi-hop consistency, multimodal retention, and decoding variants."
    )
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
        "These metrics record four things: leakage inside the reasoning trace, erasure of the final answer, "
        "whether multi-step reasoning still finishes cleanly, and whether a change in decoding brings the forgotten content back."
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
    lines.append("Public code and project pages for methods and benchmarks in this list.")
    lines.append("")
    for fw in frameworks:
        is_gh = "github.com" in fw["url"]
        badge = (
            f"[![GitHub]({GITHUB_BADGE})]({fw['url']})"
            if is_gh
            else f"[![Project]({PROJECT_BADGE})]({fw['url']})"
        )
        lines.append(f"- **[{fw['name']}]({fw['url']})** ({fw['venue']}) {badge}")
        lines.append(f"  - {fw['description']}")
    lines.append("")

    # 10. Contributing and citation. This list is a collection, so it has no paper citation.
    lines.append("---")
    lines.append("")
    lines.append("## Contributing")
    lines.append("")
    lines.append(
        "To add an entry, follow [CONTRIBUTING.md](CONTRIBUTING.md), or open a submission with the "
        "[issue template](../../issues/new/choose)."
    )
    lines.append("")
    lines.append("- **Inclusion criteria:**")
    lines.append(
        "  1. The work studies machine unlearning, selective forgetting, an unlearning attack or audit, or an unlearning benchmark, "
        "and the chain-of-thought trace, the `<think>...</think>` trajectory, or a large reasoning model "
        "(including reasoning multimodal LLMs and RLVR models) is part of the method or the evaluation."
    )
    lines.append(
        "  2. Papers that unlearn only the final answer, with no intervention on the reasoning trace, no leakage analysis of that trace, "
        "and no LRM evaluation, belong in the general lists "
        "[chrisliu298/awesome-llm-unlearning](https://github.com/chrisliu298/awesome-llm-unlearning) and "
        "[tamlhp/awesome-machine-unlearning](https://github.com/tamlhp/awesome-machine-unlearning)."
    )
    lines.append("- **Update steps:**")
    lines.append("  ```bash")
    lines.append("  # 1. Add or update entries in data/papers.json or data/benchmarks_metrics.json")
    lines.append("  # 2. Rebuild README.md and check that it matches the data")
    lines.append("  python3 scripts/build_readme.py")
    lines.append("  python3 scripts/validate_data.py --check-readme")
    lines.append("  ```")
    lines.append("")

    lines.append("## Citation")
    lines.append("")
    lines.append(
        "This repository is a curated reading list for machine unlearning in large reasoning models "
        "and chain-of-thought reasoning. There is no paper to cite for the list itself. "
        f"If the list helps, [star the repository](https://github.com/{owner}/{repo_name}). "
        "If your work uses a listed result, cite that paper, benchmark, or codebase on its own."
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    content = render_readme()
    README_PATH.write_text(content, encoding="utf-8")
    print(f"Generated {README_PATH} ({len(content.splitlines())} lines).")


if __name__ == "__main__":
    main()
