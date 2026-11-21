# Contributing to Awesome LRM Unlearning

Thank you for your interest in contributing to **Awesome LRM Unlearning**! We welcome community Pull Requests and Issues for new papers, benchmarks, datasets, evaluation metrics, and open-source frameworks.

## 1. Strict Inclusion Criteria

To keep this repository focused as a high-signal resource for the **LRM & CoT Machine Unlearning** sub-field, every submitted entry must satisfy **at least one** of the following criteria:

1. **LRM / CoT Unlearning Algorithms:** Proposes a training-time or inference-time machine unlearning method that explicitly intervenes on, suppresses, replaces, distills, or steers **intermediate Chain-of-Thought (CoT) reasoning traces** (`<think>...</think>`), **RLVR reasoning trajectories**, or **Multimodal CoT processes**.
2. **LRM Unlearning Benchmarks & Metrics:** Introduces a benchmark, dataset, or evaluation metric tailored to reasoning-trace leakage, step-wise forgetting, reasoning collapse, or post-unlearning reasoning retention in LRMs.
3. **Attacks, Vulnerabilities & Audits on Reasoning Unlearning:** Investigates step-by-step reasoning extraction attacks, malicious unlearning requests manipulating CoT rationales, decoding-mode bypasses (`ZeroThink` / `LessThink`), or memorization audit validity on reasoning traces.
4. **CoT Faithfulness via Step Unlearning:** Uses machine unlearning on individual reasoning steps to evaluate or interpret parametric CoT faithfulness.

> **Out of Scope:** Generic LLM unlearning works that evaluate or optimize solely on final answers without reasoning-trace formulation, CoT leakage analysis, or LRM evaluation belong in general repositories such as [chrisliu298/awesome-llm-unlearning](https://github.com/chrisliu298/awesome-llm-unlearning) or [tamlhp/awesome-machine-unlearning](https://github.com/tamlhp/awesome-machine-unlearning).

---

## 2. How to Add a Paper via Pull Request

`README.md` is deterministically generated from [`data/papers.json`](data/papers.json) and [`data/benchmarks_metrics.json`](data/benchmarks_metrics.json). **Do not edit `README.md` manually.**

### Step 1: Add Your Entry to `data/papers.json`

Insert your paper in **reverse chronological order** (`YYYY-MM`, newest at the top) inside the `"papers"` array of [`data/papers.json`](data/papers.json):

```json
{
  "id": "firstauthor2026shortkey",
  "title": "Full Paper Title",
  "method_name": "ShortMethodName",
  "authors": [
    "First Author",
    "Second Author"
  ],
  "date": "2026-11",
  "year": 2026,
  "venue": "Preprint",
  "paper_url": "https://arxiv.org/abs/XXXX.XXXXX",
  "code_url": "https://github.com/org/repo",
  "project_url": null,
  "category": "parameter_update",
  "also_categories": [],
  "subcategory": "Constructive Trace Replacement & Distillation",
  "stage": "Training-Time",
  "target_scope": "CoT + Answer",
  "models": [
    "DeepSeek-R1-Distill-Llama-8B"
  ],
  "summary": "One-sentence technical summary highlighting how CoT/LRM unlearning is formulated or evaluated."
}
```

Valid `"category"` IDs:
- `"parameter_update"` — Parameter-Update LRM & CoT Unlearning
- `"inference_time"` — Inference-Time & Training-Free Trajectory Regulation
- `"benchmarks"` — Benchmarks & Holistic Evaluation Suites
- `"attacks_auditing"` — Attacks, Vulnerabilities & Memorization Auditing
- `"faithfulness"` — CoT Faithfulness via Reasoning-Step Unlearning

*(Optional)* If your paper also releases a new public benchmark, evaluation metric, or open-source framework, add it to [`data/benchmarks_metrics.json`](data/benchmarks_metrics.json).

### Step 2: Regenerate `README.md` and Validate

Run the zero-dependency Python 3 scripts from the repository root:

```bash
python3 scripts/build_readme.py
python3 scripts/validate_data.py --check-readme
```

### Step 3: Open a Pull Request

Commit both your `data/*.json` changes and the regenerated `README.md`, then submit a Pull Request. Our GitHub Actions workflow will automatically verify schema integrity and `README.md` synchronization.

---

## 3. Submitting via GitHub Issue

Prefer not to open a PR? Open a [New Paper / Resource Issue](../../issues/new?template=add_paper.yml) with the paper link and metadata, and maintainers will add it.
