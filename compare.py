"""
Chunking comparison: semchunk vs LangChain RecursiveCharacterTextSplitter.

Usage:
    uv run compare.py               # generates reports/comparison_report.html (default)
    uv run compare.py --format html
    uv run compare.py --format console

Key algorithmic difference:
  LangChain separators: ["\n\n", "\n", " ", ""]
  semchunk: newlines > tabs > spaces-after-punctuation > punctuation > characters

  When text has spaces, BOTH split on spaces. But semchunk preferentially
  splits at spaces that follow structurally meaningful punctuation (. ; , etc),
  while LangChain splits at whichever space is nearest to the token limit.

  When text has NO spaces, semchunk uses punctuation as splitters,
  while LangChain falls through to "" (character-level splitting).
"""

import argparse
import html
import re
from pathlib import Path
import tiktoken
from tabulate import tabulate

import semchunk
from langchain_text_splitters import RecursiveCharacterTextSplitter

from dataset import DOCUMENTS

CHUNK_SIZE = 150
ENCODING_NAME = "cl100k_base"

enc = tiktoken.get_encoding(ENCODING_NAME)


def token_count(text: str) -> int:
    return len(enc.encode(text))


sc_chunker = semchunk.chunkerify(enc, CHUNK_SIZE)
lc_chunker = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name=ENCODING_NAME, chunk_size=CHUNK_SIZE, chunk_overlap=0, strip_whitespace=True,
)


# ---------------------------------------------------------------------------
# Shared scoring
# ---------------------------------------------------------------------------

def compute_scores(chunks: list[str]) -> dict:
    """Compute quality metrics for a set of chunks."""
    sizes = [token_count(c) for c in chunks]
    total = sum(sizes)
    n = len(sizes)
    starts_lower = 0
    split_code = 0
    ends_at_sentence = 0

    for c in chunks:
        first = c.lstrip()
        if first and first[0].islower():
            starts_lower += 1
        if c.count("```") % 2 != 0:
            split_code += 1
        orig = c.rstrip()
        if re.search(r'[.!?]\s*$', orig) or re.search(r'[.!?]\s', orig[max(0, len(orig) - 5):]):
            ends_at_sentence += 1

    util = round(100 * total / (n * CHUNK_SIZE), 1)
    sent_boundary = round(100 * ends_at_sentence / n, 1) if n else 0
    tiny = sum(1 for s in sizes if s < CHUNK_SIZE * 0.25)
    return {
        "n": n, "avg_tok": round(total / n, 1), "util": util,
        "sent_boundary": sent_boundary, "tiny": tiny,
        "starts_lower": starts_lower, "split_code": split_code,
    }


def judge(sc: dict, lc: dict) -> tuple[str, str, list[str]]:
    """Compare two score dicts. Returns (winner, emoji, reasons).
    Winner is 'semchunk', 'langchain', or 'tie'."""
    sc_pts, lc_pts = 0, 0
    reasons = []

    if sc["sent_boundary"] > lc["sent_boundary"] + 5:
        sc_pts += 2
        reasons.append(f'better sentence alignment ({sc["sent_boundary"]}% vs {lc["sent_boundary"]}%)')
    elif lc["sent_boundary"] > sc["sent_boundary"] + 5:
        lc_pts += 2
        reasons.append(f'better sentence alignment ({lc["sent_boundary"]}% vs {sc["sent_boundary"]}%)')

    if sc["starts_lower"] < lc["starts_lower"]:
        sc_pts += 2
        reasons.append(f'fewer mid-sentence starts ({sc["starts_lower"]} vs {lc["starts_lower"]})')
    elif lc["starts_lower"] < sc["starts_lower"]:
        lc_pts += 2
        reasons.append(f'fewer mid-sentence starts ({lc["starts_lower"]} vs {sc["starts_lower"]})')

    if sc["util"] > lc["util"] + 3:
        sc_pts += 1
        reasons.append(f'better utilization ({sc["util"]}% vs {lc["util"]}%)')
    elif lc["util"] > sc["util"] + 3:
        lc_pts += 1
        reasons.append(f'better utilization ({lc["util"]}% vs {sc["util"]}%)')

    if sc["tiny"] < lc["tiny"]:
        sc_pts += 1
        reasons.append(f'fewer tiny chunks ({sc["tiny"]} vs {lc["tiny"]})')
    elif lc["tiny"] < sc["tiny"]:
        lc_pts += 1
        reasons.append(f'fewer tiny chunks ({lc["tiny"]} vs {sc["tiny"]})')

    if sc["split_code"] < lc["split_code"]:
        sc_pts += 1
        reasons.append(f'fewer split code blocks ({sc["split_code"]} vs {lc["split_code"]})')
    elif lc["split_code"] < sc["split_code"]:
        lc_pts += 1
        reasons.append(f'fewer split code blocks ({lc["split_code"]} vs {sc["split_code"]})')

    if sc_pts > lc_pts:
        return "semchunk", "\U0001f3c6", reasons
    elif lc_pts > sc_pts:
        return "langchain", "\U0001f3c6", reasons
    else:
        return "tie", "\U0001f91d", reasons


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def show_chunks(label: str, chunks: list[str]):
    print(f"\n--- {label} ({len(chunks)} chunks) ---")
    for i, c in enumerate(chunks):
        tok = token_count(c)
        preview = c[:130].replace("\n", "\\n")
        suffix = "..." if len(c) > 130 else ""
        print(f"  [{i:>2}] ({tok:>3} tok) {preview}{suffix}")


def run_console():
    summary = []

    for doc_name, text in DOCUMENTS.items():
        doc_tok = token_count(text)
        print(f"\n{'='*80}")
        print(f"  {doc_name}  ({doc_tok} tokens, chunk_size={CHUNK_SIZE})")
        print(f"{'='*80}")

        sc = sc_chunker(text)
        lc = lc_chunker.split_text(text)

        sc_scores = compute_scores(sc)
        lc_scores = compute_scores(lc)

        metrics_map = [
            ("num_chunks",      "n"),
            ("avg_tok",         "avg_tok"),
            ("utilization_%",   "util"),
            ("tiny(<25%)",      "tiny"),
            ("starts_lowercase","starts_lower"),
            ("sentence_end_%",  "sent_boundary"),
        ]
        rows = []
        for label, key in metrics_map:
            sv, lv = sc_scores[key], lc_scores[key]
            flag = ""
            if isinstance(sv, (int, float)) and isinstance(lv, (int, float)):
                if key in ("starts_lower", "tiny"):
                    flag = " <" if sv < lv else (" >" if sv > lv else "")
                elif key in ("sent_boundary", "util"):
                    flag = " <" if sv > lv else (" >" if sv < lv else "")
            rows.append([label, sv, lv, flag])

        print(tabulate(rows, headers=["Metric", "semchunk", "LangChain", "better"], tablefmt="github"))
        show_chunks("semchunk", sc)
        show_chunks("LangChain", lc)

        summary.append({
            "doc": doc_name, "tokens": doc_tok,
            "sc_n": sc_scores["n"], "lc_n": lc_scores["n"],
            "sc_util": sc_scores["util"], "lc_util": lc_scores["util"],
            "sc_tiny": sc_scores["tiny"], "lc_tiny": lc_scores["tiny"],
            "sc_sent": sc_scores["sent_boundary"], "lc_sent": lc_scores["sent_boundary"],
            "sc_lower": sc_scores["starts_lower"], "lc_lower": lc_scores["starts_lower"],
        })

    print(f"\n\n{'='*80}")
    print("  OVERALL SUMMARY")
    print(f"{'='*80}\n")

    headers = ["Document", "Tok", "SC#", "LC#", "SC Util%", "LC Util%",
               "SC Sent%", "LC Sent%", "SC Lower", "LC Lower"]
    rows = [[
        r["doc"], r["tokens"], r["sc_n"], r["lc_n"],
        r["sc_util"], r["lc_util"],
        r["sc_sent"], r["lc_sent"], r["sc_lower"], r["lc_lower"],
    ] for r in summary]
    print(tabulate(rows, headers=headers, tablefmt="github"))

    n = len(summary)

    def avg(key):
        return round(sum(r[key] for r in summary) / n, 1)

    print(f"\nAverages:")
    print(f"  Utilization:        semchunk {avg('sc_util')}%  vs  LangChain {avg('lc_util')}%")
    print(f"  Sentence endings:   semchunk {avg('sc_sent')}%  vs  LangChain {avg('lc_sent')}%")
    print(f"  Starts lowercase:   semchunk {sum(r['sc_lower'] for r in summary)}  vs  LangChain {sum(r['lc_lower'] for r in summary)}")


# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------

COLORS = [
    "#e3f2fd", "#fff3e0", "#e8f5e9", "#fce4ec", "#f3e5f5",
    "#e0f7fa", "#fff8e1", "#e8eaf6", "#fbe9e7", "#f1f8e9",
    "#e1f5fe", "#fff9c4", "#e0f2f1", "#ffebee", "#ede7f6",
]


def find_chunk_spans(text: str, chunks: list[str]) -> list[tuple[int, int]]:
    """Find (start, end) character offsets for each chunk in the original text."""
    spans = []
    search_from = 0
    for chunk in chunks:
        idx = text.find(chunk, search_from)
        if idx == -1:
            stripped = chunk.strip()
            idx = text.find(stripped, search_from)
            if idx == -1:
                continue
            spans.append((idx, idx + len(stripped)))
            search_from = idx + len(stripped)
        else:
            spans.append((idx, idx + len(chunk)))
            search_from = idx + len(chunk)
    return spans


def render_highlighted_text(text: str, spans: list[tuple[int, int]], chunks: list[str]) -> str:
    """Render text as HTML with chunk regions color-coded and labeled."""
    parts = []
    last_end = 0

    for i, (start, end) in enumerate(spans):
        color = COLORS[i % len(COLORS)]
        tok = token_count(chunks[i]) if i < len(chunks) else "?"

        if start > last_end:
            gap = html.escape(text[last_end:start])
            parts.append(f'<span class="gap">{gap}</span>')

        chunk_text = html.escape(text[start:end])
        parts.append(
            f'<span class="chunk" style="background:{color};">'
            f'<span class="chunk-label">chunk {i} ({tok} tok)</span>'
            f'{chunk_text}</span>'
        )
        last_end = end

    if last_end < len(text):
        gap = html.escape(text[last_end:])
        parts.append(f'<span class="gap">{gap}</span>')

    return "".join(parts)


def build_metrics_html(scores: dict) -> str:
    return (
        f"<b>{scores['n']}</b> chunks &nbsp;|&nbsp; "
        f"avg <b>{scores['avg_tok']}</b> tok &nbsp;|&nbsp; "
        f"util <b>{scores['util']}%</b> &nbsp;|&nbsp; "
        f"sentence ends <b>{scores['sent_boundary']}%</b>"
    )


def run_html():
    sections = []
    wins = {"semchunk": 0, "langchain": 0, "tie": 0}

    for doc_name, text in DOCUMENTS.items():
        doc_tok = token_count(text)
        sc_chunks = sc_chunker(text)
        lc_chunks = lc_chunker.split_text(text)

        sc_spans = find_chunk_spans(text, sc_chunks)
        lc_spans = find_chunk_spans(text, lc_chunks)

        sc_html = render_highlighted_text(text, sc_spans, sc_chunks)
        lc_html = render_highlighted_text(text, lc_spans, lc_chunks)

        sc_scores = compute_scores(sc_chunks)
        lc_scores = compute_scores(lc_chunks)
        sc_metrics = build_metrics_html(sc_scores)
        lc_metrics = build_metrics_html(lc_scores)

        winner, emoji, reasons = judge(sc_scores, lc_scores)
        wins[winner] += 1

        if winner == "semchunk":
            banner_class = "winner-sc"
            banner_text = f"{emoji} semchunk wins"
            sc_col_class = "col col-winner"
            lc_col_class = "col"
        elif winner == "langchain":
            banner_class = "winner-lc"
            banner_text = f"{emoji} LangChain wins"
            sc_col_class = "col"
            lc_col_class = "col col-winner"
        else:
            banner_class = "winner-tie"
            banner_text = f"{emoji} Tie"
            sc_col_class = "col"
            lc_col_class = "col"

        reasons_html = " &bull; ".join(html.escape(r) for r in reasons) if reasons else "identical output"

        sections.append(f"""
        <div class="doc-section">
            <div class="doc-header">
                <h2>{html.escape(doc_name)} <span class="doc-tokens">({doc_tok} tokens)</span></h2>
                <div class="banner {banner_class}">{banner_text}</div>
            </div>
            <div class="reasons">{reasons_html}</div>
            <div class="columns">
                <div class="{sc_col_class}">
                    <h3>semchunk</h3>
                    <div class="metrics">{sc_metrics}</div>
                    <pre class="text-display">{sc_html}</pre>
                </div>
                <div class="{lc_col_class}">
                    <h3>LangChain RecursiveCharacterTextSplitter</h3>
                    <div class="metrics">{lc_metrics}</div>
                    <pre class="text-display">{lc_html}</pre>
                </div>
            </div>
        </div>""")

    if wins["semchunk"] > wins["langchain"]:
        overall_class = "overall-sc"
        overall = f'🏆 Overall winner: <span class="ow-name">semchunk</span> &mdash; won {wins["semchunk"]} of {len(DOCUMENTS)} documents'
    elif wins["langchain"] > wins["semchunk"]:
        overall_class = "overall-lc"
        overall = f'🏆 Overall winner: <span class="ow-name">LangChain</span> &mdash; won {wins["langchain"]} of {len(DOCUMENTS)} documents'
    else:
        overall_class = "overall-tie"
        overall = f'🤝 Overall: <span class="ow-name">Tie</span> &mdash; {wins["semchunk"]} wins each, {wins["tie"]} ties'

    scoreboard = (
        f'<span class="sb-item sb-sc">semchunk {wins["semchunk"]}</span>'
        f'<span class="sb-item sb-lc">LangChain {wins["langchain"]}</span>'
        f'<span class="sb-item sb-tie">Ties {wins["tie"]}</span>'
    )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Chunking Comparison: semchunk vs LangChain</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #1a1a2e; color: #e0e0e0; padding: 2rem; }}
    h1 {{ text-align: center; margin-bottom: 0.5rem; color: #fff; font-size: 1.8rem; }}
    .subtitle {{ text-align: center; color: #888; margin-bottom: 1.5rem; font-size: 0.95rem; }}

    .overall-banner {{ text-align: center; font-size: 1.3rem; font-weight: 700;
                       padding: 1rem 1.5rem; border-radius: 10px; margin-bottom: 1rem; }}
    .overall-sc  {{ background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%);
                    border: 2px solid #4caf50; color: #e8f5e9; }}
    .overall-lc  {{ background: linear-gradient(135deg, #e65100 0%, #ef6c00 100%);
                    border: 2px solid #ff9800; color: #fff3e0; }}
    .overall-tie {{ background: linear-gradient(135deg, #37474f 0%, #546e7a 100%);
                    border: 2px solid #78909c; color: #eceff1; }}
    .ow-name {{ font-size: 1.5rem; }}

    .scoreboard {{ text-align: center; margin-bottom: 2rem; }}
    .sb-item {{ display: inline-block; padding: 0.35rem 1rem; border-radius: 6px;
                font-weight: 600; font-size: 0.9rem; margin: 0 0.4rem; }}
    .sb-sc  {{ background: #1b5e20; color: #a5d6a7; }}
    .sb-lc  {{ background: #e65100; color: #ffcc80; }}
    .sb-tie {{ background: #37474f; color: #b0bec5; }}

    .doc-section {{ margin-bottom: 3rem; border: 1px solid #333; border-radius: 8px;
                    padding: 1.5rem; background: #16213e; }}
    .doc-header {{ display: flex; justify-content: space-between; align-items: center;
                   margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem; }}
    .doc-header h2 {{ color: #e0e0e0; font-size: 1.3rem; margin: 0; }}
    .doc-tokens {{ color: #888; font-weight: normal; font-size: 0.9rem; }}

    .banner {{ padding: 0.3rem 1rem; border-radius: 6px; font-weight: 700;
               font-size: 0.85rem; white-space: nowrap; }}
    .winner-sc  {{ background: #1b5e20; color: #a5d6a7; border: 1px solid #4caf50; }}
    .winner-lc  {{ background: #e65100; color: #ffcc80; border: 1px solid #ff9800; }}
    .winner-tie {{ background: #37474f; color: #b0bec5; border: 1px solid #78909c; }}

    .reasons {{ font-size: 0.8rem; color: #999; margin-bottom: 1rem; padding-left: 0.2rem; }}

    .columns {{ display: flex; gap: 1.5rem; }}
    .col {{ flex: 1; min-width: 0; border: 2px solid transparent; border-radius: 8px;
            padding: 0.75rem; }}
    .col-winner {{ border-color: #4caf50; background: rgba(76,175,80,0.05); }}
    .col h3 {{ color: #ccc; margin-bottom: 0.5rem; font-size: 1rem;
               padding-bottom: 0.3rem; border-bottom: 1px solid #333; }}
    .col-winner h3 {{ color: #a5d6a7; border-bottom-color: #4caf50; }}

    .metrics {{ font-size: 0.8rem; color: #aaa; margin-bottom: 0.5rem; padding: 0.4rem 0; }}
    .metrics b {{ color: #e0e0e0; }}
    .text-display {{ white-space: pre-wrap; word-wrap: break-word; font-family: 'SF Mono',
                     'Fira Code', 'Consolas', monospace; font-size: 0.78rem; line-height: 1.5;
                     background: #0f0f23; padding: 1rem; border-radius: 6px;
                     max-height: 600px; overflow-y: auto; border: 1px solid #2a2a4a; }}
    .chunk {{ position: relative; border-radius: 3px; color: #1a1a1a; }}
    .chunk-label {{ position: relative; display: inline-block; font-size: 0.65rem;
                    font-weight: 700; color: #fff; background: #e53935; padding: 1px 5px;
                    border-radius: 3px; margin-right: 2px; vertical-align: top;
                    line-height: 1.4; }}
    .gap {{ color: #ef5350; background: rgba(239,83,80,0.15); border-radius: 2px; }}

    .legend {{ text-align: center; margin-bottom: 2rem; font-size: 0.85rem; color: #999; }}
    .legend span {{ display: inline-block; margin: 0 1rem; }}
    .legend .swatch {{ display: inline-block; width: 14px; height: 14px; border-radius: 3px;
                       vertical-align: middle; margin-right: 4px; }}
</style>
</head>
<body>
<h1>Chunking Comparison: semchunk vs LangChain</h1>
<p class="subtitle">chunk_size = {CHUNK_SIZE} tokens &nbsp;|&nbsp; tokenizer = {ENCODING_NAME} &nbsp;|&nbsp; {len(DOCUMENTS)} documents</p>

<div class="overall-banner {overall_class}">{overall}</div>
<div class="scoreboard">{scoreboard}</div>

<div class="legend">
    <span><span class="swatch" style="background:#e3f2fd;"></span> Each color = one chunk</span>
    <span><span class="swatch" style="background:rgba(239,83,80,0.15);border:1px solid #ef5350;"></span> Red = text between chunks (trimmed whitespace)</span>
    <span>Red labels show chunk index and token count</span>
</div>
{"".join(sections)}
</body>
</html>"""

    output = Path("reports") / "comparison_report.html"
    output.parent.mkdir(exist_ok=True)
    output.write_text(page, encoding="utf-8")

    print(f"Saved: {output}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare semchunk vs LangChain chunking.")
    parser.add_argument(
        "--format",
        choices=["html", "console"],
        default="html",
        help="Output format: html (default) or console",
    )
    args = parser.parse_args()

    if args.format == "console":
        run_console()
    else:
        run_html()
