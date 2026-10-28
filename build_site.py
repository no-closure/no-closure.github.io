"""Build the project page (site/index.html) from the TMLR source, its macros, figures and the all-network table.

Run from the project root:  python3 site/build_site.py
Prose is lifted from the paper (first sentences of each results section), so the page cannot drift from it.
"""
import glob
import html
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, "papers/tmlr/tmlr_closure.tex")
BIB = os.path.join(ROOT, "papers/references.bib")
ASSETS = os.path.join(ROOT, "papers/assets")
FIGDIR = os.path.join(ROOT, "figures")
OUT = os.path.join(ROOT, "site")
os.makedirs(os.path.join(OUT, "fig"), exist_ok=True)

ARXIV_ID = None                       # fill in once posted
CODE_URL = "https://github.com/no-closure/closure"
PAPER_PDF = "paper/closure.pdf"

# ---------------------------------------------------------------- macros
MACROS = {}
for f in sorted(glob.glob(os.path.join(ASSETS, "numbers*.tex"))):
    for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{(.*)\}\s*$", open(f).read(), flags=re.M):
        MACROS[m.group(1)] = m.group(2)

# ---------------------------------------------------------------- bib → "Kim et al., 2021"
BIBS = {}
for blk in re.split(r"\n(?=@)", open(BIB).read()):
    m = re.match(r"@\w+\{(\w+),", blk)
    if not m:
        continue
    au = re.search(r"author\s*=\s*\{(.*?)\}\s*,?\s*\n", blk, flags=re.S)
    yr = re.search(r"year\s*=\s*\{(\d{4})\}", blk)
    names = [a.strip() for a in re.split(r"\s+and\s+", au.group(1).replace("\n", " "))] if au else ["?"]
    surn = [re.sub(r"\{\\ss\}", "ß", n.split(",")[0]).strip("{} ") for n in names]
    first = surn[0] if len(surn) == 1 else (f"{surn[0]} & {surn[1]}" if len(surn) == 2 else f"{surn[0]} et al.")
    BIBS[m.group(1)] = (first, yr.group(1) if yr else "")

SRC = open(TEX).read()

# figure labels → numbers (order of appearance), subsection labels → titles
FIGLABELS = re.findall(r"\\begin\{figure\}.*?\\label\{(fig:[^}]*)\}", SRC, flags=re.S)
FIGNUM = {l: i + 1 for i, l in enumerate(FIGLABELS)}
TABLABELS = re.findall(r"\\begin\{table\}.*?\\label\{(tab:[^}]*)\}", SRC, flags=re.S)
TABNUM = {l: i + 1 for i, l in enumerate(TABLABELS)}
SECTITLE = {m.group(2): m.group(1) for m in re.finditer(r"\\(?:sub)?section\{([^}]*)\}\s*\\label\{([^}]*)\}", SRC)}


def cite(keys, textual):
    out = []
    for k in keys.split(","):
        a, y = BIBS.get(k.strip(), (k, ""))
        out.append(f"{a} ({y})" if textual else f"{a}, {y}")
    return "; ".join(out) if textual else "(" + "; ".join(out) + ")"


def ref(label):
    if label in FIGNUM:
        return f"Fig.&nbsp;{FIGNUM[label]}"
    if label in TABNUM:
        return f"Table&nbsp;{TABNUM[label]}"
    if label in SECTITLE:
        return f"the section “{SECTITLE[label]}”"
    return label


def math(s):
    s = s.replace(r"\dagger", "†").replace(r"\cdot", "·").replace("^*", "<sup>*</sup>").replace("^†", "<sup>†</sup>")
    s = s.replace(r"\times", "×").replace(r"\pm", "±").replace(r"\bar C", "C̄").replace(r"\gamma", "γ")
    s = s.replace(r"\lVert", "‖").replace(r"\rVert", "‖").replace(r"\alpha", "α").replace(r"\leftarrow", "←")
    s = s.replace(r"\in", "∈").replace(r"\{", "{").replace(r"\}", "}").replace(r"\,", " ")
    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\^\{([^}]*)\}", r"<sup>\1</sup>", s)
    s = re.sub(r"_\{([^}]*)\}", r"<sub>\1</sub>", s)
    s = re.sub(r"\^(\w)", r"<sup>\1</sup>", s)
    s = re.sub(r"_(\w)", r"<sub>\1</sub>", s)
    s = s.replace("--", "–").replace(">", "&gt;").replace("<", "&lt;")
    s = s.replace("&lt;sup&gt;", "<sup>").replace("&lt;/sup&gt;", "</sup>").replace("&lt;sub&gt;", "<sub>").replace("&lt;/sub&gt;", "</sub>")
    return f"<i>{s}</i>"


def tex2html(s):
    s = s.replace("\n", " ")
    s = re.sub(r"\\textbf\{([^}]*)\}", r"<b>\1</b>", s)
    s = re.sub(r"\\emph\{([^}]*)\}", r"<em>\1</em>", s)
    s = re.sub(r"\\citep\[([^\]]*)\]\[([^\]]*)\]\{([^}]*)\}", lambda m: f"({m.group(1)} {cite(m.group(3), True)}{m.group(2)})", s)
    s = re.sub(r"\\citep\{([^}]*)\}", lambda m: cite(m.group(1), False), s)
    s = re.sub(r"\\citet\{([^}]*)\}", lambda m: cite(m.group(1), True), s)
    s = re.sub(r"\\citealp\{([^}]*)\}", lambda m: cite(m.group(1), False)[1:-1], s)
    s = re.sub(r"(Fig\.|Figs\.|Table|Section|Appendix|Sections)~\\ref\{([^}]*)\}", lambda m: ref(m.group(2)), s)
    s = re.sub(r"\\ref\{([^}]*)\}", lambda m: ref(m.group(1)), s)
    s = re.sub(r"\\([A-Za-z]+)\{\}", lambda m: MACROS.get(m.group(1), m.group(0)), s)
    s = re.sub(r"\\([A-Za-z]+)(?![A-Za-z])", lambda m: MACROS.get(m.group(1), m.group(0)), s)
    s = s.replace(r"\textdegree{}", "°").replace(r"\textdegree", "°")
    s = re.sub(r"\$([^$]*)\$", lambda m: math(m.group(1)), s)
    s = s.replace(r"\%", "%").replace(r"\,", " ").replace("~", "&nbsp;").replace("--", "–").replace("``", "“").replace("''", "”")
    s = s.replace(r"\&", "&amp;").replace(r"\_", "_").replace("\\ ", " ").replace(r"\dagger", "†")
    s = re.sub(r"\\footnote\{[^}]*\}", "", s)
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    assert "??" not in s, s
    return s


def sentences(label_or_title, n):
    """First n sentences (or the listed line indices) of the (sub)section with this title, figures/tables removed."""
    m = re.search(r"\\(?:sub)?section\{" + re.escape(label_or_title) + r"\}(.*?)(?=\\(?:sub)?section|\\end\{document\})", SRC, flags=re.S)
    body = m.group(1)
    body = re.sub(r"\\begin\{(figure|table)\}.*?\\end\{\1\}", "", body, flags=re.S)
    body = re.sub(r"\\label\{[^}]*\}", "", body)
    sents = [x.strip() for x in body.strip().split("\n") if x.strip()]
    pick = sents[:n] if isinstance(n, int) else [sents[i] for i in n]
    return " ".join(tex2html(x) for x in pick)


def caption(label):
    for blk in re.findall(r"\\begin\{figure\}.*?\\end\{figure\}", SRC, flags=re.S):
        if "\\label{" + label + "}" in blk:
            return tex2html(re.search(r"\\caption\{(.*)\}\s*\\label\{", blk, flags=re.S).group(1))
    raise KeyError(label)


ABSTRACT = tex2html(re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", SRC, flags=re.S).group(1))

# ---------------------------------------------------------------- figures → png
def fig(name, dpi=150):
    base, ext = os.path.splitext(name)
    out = os.path.join(OUT, "fig", base + ".png")
    src = os.path.join(ASSETS, name) if os.path.exists(os.path.join(ASSETS, name)) else os.path.join(FIGDIR, name)
    if ext == ".pdf":
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile", src, os.path.join(OUT, "fig", base)], check=True)
    else:
        subprocess.run(["cp", src, out], check=True)
    return f"fig/{base}.png"


# ---------------------------------------------------------------- table
def table_html():
    rows = [l for l in open(os.path.join(ASSETS, "table_all.tex")).read().split("\n") if "&" in l]
    head = [tex2html(c.strip()) for c in rows[0].rstrip("\\").split("&")]
    out = ["<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in head) + "</tr></thead><tbody>"]
    for r in rows[1:]:
        cells = [tex2html(c.strip()) for c in r.rstrip("\\").split("&")]
        out.append("<tr>" + "".join(f"<t{'h' if i == 0 else 'd'}>{c}</t{'h' if i == 0 else 'd'}>" for i, c in enumerate(cells)) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


TABLE_NOTE = tex2html(re.search(r"\\caption\{(All networks\..*?)\}\s*\\label\{tab:all\}", SRC, flags=re.S).group(1))

# ---------------------------------------------------------------- sections
S = []  # (id, title, [blocks])
S.append(("stimuli", "Stimuli sized in patch units",
          [("p", sentences("Stimuli", 3)), ("f", fig("stimuli_contact_sheet.png"), caption("fig:stimuli"))]))
S.append(("illusory", "Illusory contours are at most weakly represented",
          [("p", sentences("Illusory contours are at most weakly represented", 3)),
           ("f", fig("fig_behaviour.pdf"), caption("fig:behaviour"))]))
S.append(("arrangement", "Fine-tuned transformers integrate fragments, and the arrangement matters",
          [("p", sentences("Fine-tuned transformers integrate fragments, and the arrangement matters", 3))]))
S.append(("where", "Where closure emerges, and what the maps show",
          [("p", sentences("Where closure emerges, and what the maps show", 3)),
           ("f", fig("fig_layers.pdf"), caption("fig:layers"), "narrow"),
           ("f2", fig("example_labels_dinov2.png"), fig("example_shap_dinov2.png"), caption("fig:example"))]))
S.append(("recurrence", "Recurrence does not consistently add closure",
          [("p", sentences("Recurrence does not consistently add closure", [0, 7, 5, 6, 10])),
           ("f", fig("fig_recurrence.pdf"), caption("fig:recurrence"))]))
S.append(("tracing", "Networks trained to trace contours link pieces but do not complete them",
          [("p", sentences("Networks trained to trace contours link pieces but do not complete them", 2)),
           ("f", fig("fig_tracing.pdf"), caption("fig:tracing"))]))
S.append(("gap", "The bridgeable gap is far smaller than the receptive field",
          [("p", sentences("Accuracy falls with the number of empty patches", 2)),
           ("f", fig("fig_tokens.pdf"), caption("fig:tokens"), "narrow"),
           ("p", sentences("The bridgeable gap is far smaller than the receptive field", 4)),
           ("f", fig("gap_schematic.pdf"), caption("fig:gapschem")),
           ("f2v", fig("gap_curves.pdf"), fig("gap_vs_reach.pdf"), caption("fig:gapreach"))]))
S.append(("inside", "What happens inside the gap",
          [("p", sentences("What happens inside the gap", 3)),
           ("f", fig("fig_gapdyn.pdf"), caption("fig:gapdyn")),
           ("p", sentences("Little evidence of boundary completion", 3))]))
S.append(("probe", "Between the inducers",
          [("p", sentences("Nothing is represented between the inducers", [0, 5, 6, 7])),
           ("f", fig("fig_probe.pdf"), caption("fig:probe"))]))
S.append(("patch", "Activation patching",
          [("p", sentences("The transformers' Kanizsa evidence does not pass through the gaps", [0, 2, 4])),
           ("f", fig("fig_gap_patch.png"), caption("fig:patch"), "narrow"),
           ("p", sentences("The transformers' Kanizsa evidence does not pass through the gaps", [5, 6, 7]))]))
S.append(("cued", "Cued segmentation circuits",
          [("p", sentences("Circuits trained for incremental grouping label an illusory surface only across small gaps, and without needing recurrence", [0, 1, 2, 10, 11, 12])),
           ("f", fig("fig_cued_gap.pdf"), caption("fig:cuedgap")),
           ("p", sentences("Circuits trained for incremental grouping label an illusory surface only across small gaps, and without needing recurrence", [15, 25])),
           ("p", sentences("Circuits trained for incremental grouping label an illusory surface only across small gaps, and without needing recurrence", [26, 28, 29, 32]))]))
S.append(("audit", "Published closure measures fail null observers",
          [("p", sentences("Auditing published closure measures", [0, 4, 2, 3])),
           ("f", fig("fig_ce_stimuli.pdf"), caption("fig:cestim")),
           ("f", fig("fig_audit.pdf"), caption("fig:audit")),
           ("f", fig("fig_audit2.pdf"), caption("fig:audit2"))]))
S.append(("faith", "Saliency overlays are often not faithful",
          [("p", sentences("Saliency overlays are often not faithful", 3)),
           ("f", fig("fig_faith.pdf"), caption("fig:faith"), "narrow")]))
S.append(("table", "Results for every network", [("t", table_html(), TABLE_NOTE)]))

# ---------------------------------------------------------------- copy overrides (site/copy.json, written from an Astra rewrite)
import json
HERO = {"lead": "Can a network that recognizes a complete outline still recognize it with the corners removed, and does it do better than on the same pieces rotated in place? The same question for Kanizsa figures. Each dot is one network's accuracy on that condition (chance 0.10, red; 1.00, green; hover for the value).",
        "tldr": MACROS['nnNets'] + " networks, stimuli sized in patch units, matched controls and null observers: deep networks group nearby, consistently oriented contour pieces; they do not close gaps, and illusory contours are at most weakly represented."}
copy_src = {"hero": HERO, "sections": [{"id": i, "title": t, "paragraphs": [b[1] for b in blocks if b[0] == "p"]} for i, t, blocks in S]}
json.dump(copy_src, open(os.path.join(OUT, "copy_src.json"), "w"), indent=1, ensure_ascii=False)
if os.path.exists(os.path.join(OUT, "copy.json")):
    ov = json.load(open(os.path.join(OUT, "copy.json")))
    HERO.update(ov.get("hero", {}))
    for sec in ov.get("sections", []):
        for k, (i, t, blocks) in enumerate(S):
            if i == sec["id"]:
                ps = iter(sec.get("paragraphs", []))
                nb = [("p", next(ps, b[1])) if b[0] == "p" else b for b in blocks]
                S[k] = (i, sec.get("title", t), nb)

# ---------------------------------------------------------------- teaser (contact-sheet crops + accuracy dots from Table 1)
from PIL import Image
sheet = Image.open(os.path.join(FIGDIR, "stimuli_contact_sheet.png"))
PW, PH = sheet.width // 12, sheet.height // 4
TEASER = [("Complete outline", 0, "complete", None), ("Corners removed", 3, "frag.", None), ("Same pieces, rotated", 4, "frag.", "CI frag."),
          ("Kanizsa figure", 6, "Kanizsa", None), ("Inducers rotated", 7, "Kanizsa", "CI Kan.")]
for i, (_, col, _, _) in enumerate(TEASER):
    sheet.crop((col * PW + 2, 18, (col + 1) * PW - 2, PH - 18)).save(os.path.join(OUT, "fig", f"teaser{i}.png"))

ROWS = {}
rows = [l for l in open(os.path.join(ASSETS, "table_all.tex")).read().split("\n") if "&" in l]
COLS = [c.strip() for c in rows[0].rstrip("\\").split("&")]
for r in rows[1:]:
    cells = [c.strip() for c in r.rstrip("\\").split("&")]
    ROWS[re.sub(r"\$.*?\$", "", cells[0])] = dict(zip(COLS[1:], cells[1:]))
DOTNETS = ["VGG16 (frozen)", "ResNet50", "ViT-B/16", "DINOv2-S", "Looped ViT-B/16", "fGRU-H", "$\\gamma$-net", "deep fGRU D4", "DN fGRU L8"]
DOTNETS = [n for n in DOTNETS if n in ROWS or n.replace("$\\gamma$", "") in ROWS]


def acc(net, col, ci):
    row = ROWS.get(net) or ROWS.get(net.replace("$\\gamma$", ""))
    if row is None or row[col] == "--" or (ci and row[ci] == "--"):
        return None
    v = float(row[col])
    if ci:
        v -= float(row[ci])
    return v


def dot(v):
    if v is None:
        return '<span class="dot" style="background:var(--rule)" title="not measured"></span>'
    hue = 10 + 110 * max(0.0, min(1.0, (v - 0.1) / 0.9))   # red at chance, green at 1.0
    return f'<span class="dot" style="background:hsl({hue:.0f} 70% 48%)" title="{v:.2f}"></span>'


teaser = '<div class="teaser">'
for i, (name, col, c1, c2) in enumerate(TEASER):
    dots = "".join(dot(acc(n, c1, c2)) for n in DOTNETS)
    teaser += f'<div class="tcell"><img src="fig/teaser{i}.png" alt="{name}"><div class="tname">{name}</div><div class="dots">{dots}</div></div>'
teaser += "</div>"
legend = " · ".join(tex2html(n) for n in DOTNETS)

# ---------------------------------------------------------------- html
def block(b):
    if b[0] == "p":
        return f"<p>{b[1]}</p>"
    if b[0] == "f":
        cls = ' class="narrow"' if len(b) > 3 else ""
        return f'<figure{cls}><img src="{b[1]}" alt="" loading="lazy"><figcaption>{b[2]}</figcaption></figure>'
    if b[0] == "f2":
        return f'<figure><img src="{b[1]}" alt="" loading="lazy"><img src="{b[2]}" alt="" loading="lazy"><figcaption>{b[3]}</figcaption></figure>'
    if b[0] == "f2v":
        return f'<figure><img src="{b[1]}" alt="" loading="lazy"><img class="narrow" src="{b[2]}" alt="" loading="lazy"><figcaption>{b[3]}</figcaption></figure>'
    if b[0] == "t":
        return f'<div class="tablewrap">{b[1]}</div><p class="note">{b[2]}</p>'


body = ""
for i, t, blocks in S:
    body += f'<section id="{i}"><h2>{t}</h2>' + "".join(block(b) for b in blocks) + "</section>\n"

ICON_PDF = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M6 2h8l6 6v14H6zM13 3.5V9h5.5z"/></svg>'
ICON_GH = '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M8 0a8 8 0 0 0-2.5 15.6c.4.1.5-.2.5-.4v-1.5c-2.2.5-2.7-1-2.7-1-.4-.9-.9-1.2-.9-1.2-.7-.5.1-.5.1-.5.8.1 1.2.8 1.2.8.7 1.3 1.9.9 2.4.7.1-.5.3-.9.5-1.1-1.8-.2-3.6-.9-3.6-4 0-.9.3-1.6.8-2.1-.1-.2-.4-1 .1-2.1 0 0 .7-.2 2.2.8a7.5 7.5 0 0 1 4 0c1.5-1 2.2-.8 2.2-.8.5 1.1.2 1.9.1 2.1.5.5.8 1.2.8 2.1 0 3.1-1.9 3.8-3.6 4 .3.3.6.8.6 1.5v2.2c0 .2.1.5.6.4A8 8 0 0 0 8 0z"/></svg>'
ICON_Q = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M6 17h3l2-4V7H5v6h3zm8 0h3l2-4V7h-6v6h3z"/></svg>'
paper_btn = (f'<a class="btn" href="https://arxiv.org/abs/{ARXIV_ID}">{ICON_PDF} arXiv</a>' if ARXIV_ID
             else f'<a class="btn" href="{PAPER_PDF}">{ICON_PDF} Paper</a>')
bibtex = html.escape("""@article{tenwolde2026closure,
  title   = {Waiting for Closure: Deep Networks Still Do Not Complete Contours},
  author  = {TenWolde, Benjamin},
  journal = {arXiv preprint},
  year    = {2026}
}""")
nav = "".join(f'<a href="#{i}">{t}</a>' for i, t, _ in S)

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Waiting for Closure</title>
<meta name="description" content="Deep networks integrate contours locally but do not perceive illusory closure: {MACROS['nnNets']} networks tested with patch-aware stimuli and null observers.">
<style>
:root{{--bg:#ffffff;--fg:#212529;--muted:#6c757d;--rule:#e6e6e6;--card:#f6f6f6;--btn:#363636;--btnfg:#ffffff;--accent:#b4231c;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#161616;--fg:#e8e8e8;--muted:#9a9a9a;--rule:#2c2c2c;--card:#202020;--btn:#e8e8e8;--btnfg:#161616;--accent:#ef8a83;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#161616;--fg:#e8e8e8;--muted:#9a9a9a;--rule:#2c2c2c;--card:#202020;--btn:#e8e8e8;--btnfg:#161616;--accent:#ef8a83;color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font-family:"Helvetica Neue Light","HelveticaNeue-Light","Helvetica Neue",Helvetica,Arial,system-ui,sans-serif;font-weight:300;font-size:18px;line-height:1.55}}
main{{max-width:900px;margin:0 auto;padding-block:44px 80px;padding-inline:20px}}
header{{text-align:center;margin-bottom:28px}}
h1{{font-size:clamp(26px,4vw,34px);line-height:1.25;font-weight:400;margin:0 0 10px;text-wrap:balance}}
.venue{{font-size:19px;margin:0 0 14px}}
.authors{{font-size:17px;margin:0 0 2px}}
.affil{{font-size:15px;color:var(--muted);margin:0 0 20px}}
.btns{{display:flex;flex-wrap:wrap;gap:8px;justify-content:center}}
.btn{{display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:500;color:var(--btnfg);background:var(--btn);border-radius:999px;padding:7px 16px;text-decoration:none}}
.btn:hover{{opacity:.85}}
.teaser{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:30px 0 8px}}
.tcell img{{width:100%;max-width:100%;height:auto;border:1px solid var(--rule);border-radius:4px;display:block}}
.tname{{font-size:13px;text-align:center;margin-top:6px}}
.dots{{display:flex;justify-content:center;gap:4px;margin-top:5px;flex-wrap:wrap}}
.dot{{width:11px;height:11px;border-radius:50%;display:inline-block}}
.lead{{font-size:16px;color:var(--muted);margin:0 0 6px}}
.legend{{font-size:12.5px;color:var(--muted);margin:0 0 28px}}
h2{{font-size:24px;font-weight:400;line-height:1.25;margin:46px 0 10px;text-wrap:balance}}
.abstract h2{{margin-top:10px}}
.tldr{{font-size:20px;margin:26px 0 0;padding-left:16px;border-left:3px solid var(--accent)}}
figure{{margin:22px 0}} figure img{{display:block;width:100%;max-width:100%;height:auto;margin:0 auto 6px}}
figure.narrow img,img.narrow{{max-width:540px}}
figcaption,.note{{font-size:14px;line-height:1.5;color:var(--muted);margin-top:8px}}
.tablewrap{{overflow-x:auto;margin:16px 0 8px}}
table{{border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}}
th,td{{padding:5px 9px;text-align:right;border-bottom:1px solid var(--rule);font-weight:300}} th:first-child,td:first-child{{text-align:left}}
thead th{{border-bottom:2px solid var(--fg);font-weight:500}}
pre{{background:var(--card);border-radius:6px;padding:16px;font-size:13px;overflow-x:auto;line-height:1.45}}
a{{color:var(--accent)}}
nav{{font-size:13px;display:flex;flex-wrap:wrap;gap:6px 14px;justify-content:center;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:12px 0;margin:0 0 10px}}
nav a{{color:var(--muted);text-decoration:none}} nav a:hover{{color:var(--accent)}}
footer{{font-size:13px;color:var(--muted);margin-top:60px;border-top:1px solid var(--rule);padding-top:16px}}
@media (max-width:600px){{.teaser{{grid-template-columns:repeat(3,1fr)}}}}
</style>
</head>
<body>
<main>
<header>
<h1>Waiting for Closure: Deep Networks Still Do Not Complete Contours</h1>
<p class="venue">Preprint, 2026</p>
<p class="authors">Benjamin TenWolde</p>
<p class="affil">University of California San Diego</p>
<div class="btns">{paper_btn}<a class="btn" href="{CODE_URL}">{ICON_GH} Code &amp; stimuli</a><a class="btn" href="#cite">{ICON_Q} BibTeX</a></div>
</header>

{teaser}
<p class="lead">{HERO['lead']}</p>
<p class="legend">Dots, left to right: {legend}.</p>
<nav>{nav}</nav>

<section class="abstract"><h2>Abstract</h2><p>{ABSTRACT}</p></section>
<p class="tldr">{HERO['tldr']}</p>

{body}

<section id="cite"><h2>BibTeX</h2>
<pre>{bibtex}</pre>
</section>
<footer>Page generated from the paper source; figures and numbers are those of the paper. Contact: bendotten@gmail.com</footer>
</main>
</body>
</html>
"""
open(os.path.join(OUT, "index.html"), "w").write(page)
print("wrote site/index.html", len(page) // 1000, "kB;", len(os.listdir(os.path.join(OUT, "fig"))), "figures")
