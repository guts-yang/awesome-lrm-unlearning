#!/usr/bin/env python3
"""Build a SINGLE bilingual (EN + ZH) HTML view for the LRM unlearning formula
cheat sheet, with a top-right language switcher (default English).

This is a generated view. The Markdown files are the canonical source of truth:
  - docs/tutorials/lrm_unlearning_formulas.md     (English)
  - docs/tutorials/lrm_unlearning_formulas_CN.md  (Chinese)

It reuses the /render-html skill's own renderer (parse_blocks / _render_blocks /
render_toc / load_template / CDN blocks) so the Markdown subset, math, callouts,
tables, <details> and CSS stay identical to the skill's academic template. The
two rendered bodies are then embedded into ONE self-contained HTML file, wrapped
in two <div lang-pane> containers; a small inline script toggles between them.

Output: survey/index.html  (GitHub Pages renders this on click by default).

Usage:
    python3 scripts/build_bilingual_survey.py
"""
from __future__ import annotations

import html as html_lib
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve the /render-html helper through the canonical chain.
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent
CANDIDATES = [
    REPO / ".agent/skills/render-html/scripts/render_html.py",
    REPO / ".aris/skills/render-html/scripts/render_html.py",
    REPO / "skills/render-html/scripts/render_html.py",
]
HELPER = next((p for p in CANDIDATES if p.exists()), None)
if HELPER is None:
    sys.exit("ERROR: /render-html helper render_html.py not found; cannot build bilingual view.")

spec = importlib.util.spec_from_file_location("aris_render_html", HELPER)
rh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rh)  # type: ignore

EN_MD = REPO / "docs/tutorials/lrm_unlearning_formulas.md"
CN_MD = REPO / "docs/tutorials/lrm_unlearning_formulas_CN.md"
OUT = REPO / "survey/index.html"


def render_pane(md_path: Path, pane_id: str) -> dict:
    """Render one language's Markdown into a body + TOC, using skill functions.

    Heading IDs are prefixed with the pane id so EN/CN never collide (they share
    the same document structure). The leading H1 is dropped — the hero supplies
    the single visible title.
    """
    raw = md_path.read_text(encoding="utf-8")
    source_hash = rh.sha256_of(raw)
    md_source = rh.strip_frontmatter(raw)
    blocks = rh.parse_blocks(md_source.split("\n"))

    # Drop the first H1 block (hero owns the title); keep everything else.
    blocks = [b for i, b in enumerate(blocks) if not (i == 0 and b.get("type") == "heading" and b.get("level") == 1)]

    body_html, toc = rh._render_blocks(blocks, collect_toc=True)

    # Namespace all ids + TOC hrefs to this pane.
    import re as _re
    body_html = _re.sub(r'id="([^"]+)"', lambda m: f'id="{pane_id}-{m.group(1)}"', body_html)
    for e in toc:
        e["id"] = f"{pane_id}-{e['id']}"
    toc_html = rh.render_toc(toc)
    return {
        "body": body_html,
        "toc": toc_html,
        "source": rh._repo_relative(md_path),
        "sha": source_hash,
        "sha_short": source_hash[:12],
    }


def hero_meta(pane: dict) -> str:
    return (
        f'<div class="meta">'
        f'<span><strong>Source:</strong> <code>{html_lib.escape(pane["source"])}</code></span>'
        f'<span><strong>SHA256:</strong> <code>{html_lib.escape(pane["sha_short"])}</code></span>'
        f'<span><strong>Rendered:</strong> {GENERATED_AT}</span>'
        f'</div>'
    )


GENERATED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

en = render_pane(EN_MD, "en")
cn = render_pane(CN_MD, "cn")

template = rh.load_template("academic")

# Shared vars for the outer shell. Per-pane BODY_HTML/TOC_HTML are injected via
# markers so each pane keeps its own TOC, hero meta and lang attribute.
base_vars = {
    "LANG": "en",
    "TITLE": "Large Reasoning Model Machine Unlearning — Formula Deep-Dive Cheat Sheet",
    "SUBTITLE_BLOCK": "",
    "EYEBROW_BLOCK": '<div class="eyebrow">Interview Prep · LRM / CoT Unlearning · Verbatim Formulas</div>',
    "BYLINE_BLOCK": "",
    "SOURCE_PATH": f"{en['source']} + {cn['source']}",
    "SOURCE_SHA256": en["sha"],
    "SOURCE_SHA256_SHORT": en["sha_short"],
    "GENERATED_AT": GENERATED_AT,
    "HEAD_CDN": rh.CDN_BLOCK_FULL,
    "TOC_HTML": "{{PANE_TOC}}",
    "TOC_LABEL": "Contents",
    "BODY_HTML": "{{PANE_BODY}}",
    "EXTRA_META": "",
    "PAPER_REGISTRY_JSON": "{}",
    "COLLAPSE_CODE_MIN": "30",
    "BODY_CLASS": "aris-blog bilingual",
}

shell = rh.substitute(template, base_vars)

# --- Build the two panes' inner markup -------------------------------------
def pane_markup(pane: dict, lang: str, label_long: str) -> str:
    toc = (
        f'<nav class="toc" data-lang="{lang}">'
        f'<h3>Contents</h3>{pane["toc"]}</nav>'
    )
    hero = (
        f'<header class="hero" data-lang="{lang}">'
        f'<div class="eyebrow">Interview Prep · LRM / CoT Unlearning · Verbatim Formulas</div>'
        f'<h1>{html_lib.escape(TITLES[lang])}</h1>'
        f'<p class="subtitle">{html_lib.escape(SUBTITLES[lang])}</p>'
        f'{hero_meta(pane)}'
        f'</header>'
    )
    return (
        f'<div class="lang-pane" id="pane-{lang}" lang="{lang}" data-lang="{lang}">'
        f'{toc}'
        f'<main>{hero}{pane["body"]}'
        f'<footer class="aris-footer">'
        f'Generated by <a href="https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/main/skills/render-html/SKILL.md">ARIS <code>/render-html</code></a> · '
        f'source <code>{html_lib.escape(pane["source"])}</code> · SHA256 <code>{html_lib.escape(pane["sha_short"])}</code> · '
        f'{GENERATED_AT}. This is a generated view — edit the source Markdown, then re-render.'
        f'</footer></main></div>'
    )


TITLES = {
    "en": "Large Reasoning Model Machine Unlearning — Formula Deep-Dive Cheat Sheet",
    "cn": "大推理模型机器遗忘 公式拆解 Cheat Sheet",
}
SUBTITLES = {
    "en": "34 papers, core mathematical formulas verbatim — with mathematical principle & physical intuition",
    "cn": "34 篇论文核心数学公式逐篇逻辑拆解（给定 → 目标 → 展开 → 辨析）",
}

# Replace the shell's single .layout content with two panes + switcher.
import re as _re2
layout_re = _re2.compile(r'<div class="layout">.*?</div>\s*(?=<!-- P0 polish: paper popover host)', _re2.S)
new_layout = (
    '<div id="lang-switch" role="group" aria-label="Language">'
    '<button type="button" class="lang-btn active" data-target="en" aria-pressed="true">EN</button>'
    '<button type="button" class="lang-btn" data-target="cn" aria-pressed="false">中文</button>'
    '</div>\n'
    '<div class="layout" id="bilingual-layout">\n'
    + pane_markup(en, "en", "English") + "\n"
    + pane_markup(cn, "cn", "中文") + "\n"
    '</div>'
)
shell, n = layout_re.subn(lambda _m: new_layout, shell, count=1)
if n != 1:
    sys.exit("ERROR: could not locate .layout block in academic template; aborting.")

# --- Switcher CSS + JS (injected just before </head> / </body>) ------------
SWITCH_CSS = """
<style>
/* --- bilingual single-file view ----------------------------------------- */
#lang-switch {
  position: fixed;
  top: 18px;
  right: 22px;
  z-index: 2000;
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid var(--border);
  border-radius: 20px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.10);
  backdrop-filter: blur(6px);
}
#lang-switch .lang-btn {
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--ink-soft);
  background: transparent;
  border: none;
  border-radius: 16px;
  padding: 5px 14px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
#lang-switch .lang-btn:hover { color: var(--primary); }
#lang-switch .lang-btn.active {
  background: var(--primary);
  color: #fff;
}
/* Each pane is itself a .layout grid; inactive pane is hidden. */
.lang-pane {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 48px;
  max-width: 1280px;
  margin: 0 auto;
  padding: 40px 32px;
}
.lang-pane[hidden] { display: none !important; }
/* The outer .layout is now just a neutral host. */
#bilingual-layout {
  display: block;
  max-width: none;
  padding: 0;
  gap: 0;
}
@media (max-width: 900px) {
  .lang-pane { grid-template-columns: 1fr; gap: 20px; padding: 20px 16px; }
}
@media print {
  #lang-switch { display: none !important; }
}
</style>
"""

SWITCH_JS = """
<script>
(function () {
  "use strict";
  var EN = "en", CN = "cn";
  var panes = { en: document.getElementById("pane-en"), cn: document.getElementById("pane-cn") };
  var btns = [].slice.call(document.querySelectorAll("#lang-switch .lang-btn"));

  function setLang(lang) {
    Object.keys(panes).forEach(function (k) {
      if (panes[k]) panes[k].hidden = (k !== lang);
    });
    btns.forEach(function (b) {
      var on = b.getAttribute("data-target") === lang;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    document.documentElement.lang = (lang === "cn" ? "zh-CN" : "en");
    try { localStorage.setItem("aris-survey-lang", lang); } catch (e) {}
    // Re-typeset math for the now-visible pane (MathJax skips hidden content).
    if (window.MathJax && window.MathJax.typesetPromise && panes[lang]) {
      try { window.MathJax.typesetPromise([panes[lang]]); } catch (e) {}
    }
    window.scrollTo(0, 0);
  }
  btns.forEach(function (b) {
    b.addEventListener("click", function () { setLang(b.getAttribute("data-target")); });
  });
  // Default English; honor a previous explicit choice if present.
  var saved = null;
  try { saved = localStorage.getItem("aris-survey-lang"); } catch (e) {}
  setLang(saved === CN ? CN : EN);
})();
</script>
"""

shell = shell.replace("</head>", SWITCH_CSS + "\n</head>", 1)
shell = shell.replace("</body>", SWITCH_JS + "\n</body>", 1)

# Sanity: no template placeholders leaked, two panes present.
if "{{" in shell and "}}" in shell:
    # PAPER_REGISTRY_JSON="{}" is fine; only real placeholders matter.
    import re as _re3
    leaked = _re3.findall(r"\{\{[A-Z_]+\}\}", shell)
    if leaked:
        sys.exit(f"ERROR: unreplaced template placeholders: {leaked}")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(shell, encoding="utf-8")
print(
    f"wrote {OUT} ({len(shell):,} bytes) — EN sha {en['sha_short']}, CN sha {cn['sha_short']}, "
    f"panes=2, default=en"
)
