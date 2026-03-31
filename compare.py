"""
Chunking comparison: semchunk vs LangChain RecursiveCharacterTextSplitter.

Usage:
    uv run compare.py                  # generates reports/comparison_report.md (default)
    uv run compare.py --format markdown
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
        return "semchunk", "🏆", reasons
    elif lc_pts > sc_pts:
        return "langchain", "🏆", reasons
    else:
        return "tie", "🤝", reasons


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
            ("num_chunks",       "n"),
            ("avg_tok",          "avg_tok"),
            ("utilization_%",    "util"),
            ("tiny(<25%)",       "tiny"),
            ("starts_lowercase", "starts_lower"),
            ("sentence_end_%",   "sent_boundary"),
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
# Markdown output
# ---------------------------------------------------------------------------

def chunks_to_md(chunks: list[str]) -> str:
    """Format a list of chunks as a fenced code block with index and token count."""
    lines = []
    for i, c in enumerate(chunks):
        tok = token_count(c)
        preview = c.replace("\n", "\\n")
        lines.append(f"[{i}] ({tok} tok) {preview}")
    return "```\n" + "\n".join(lines) + "\n```"


def run_markdown():
    sections = []
    summary = []
    wins = {"semchunk": 0, "langchain": 0, "tie": 0}

    for doc_name, text in DOCUMENTS.items():
        doc_tok = token_count(text)
        sc_chunks = sc_chunker(text)
        lc_chunks = lc_chunker.split_text(text)

        sc_scores = compute_scores(sc_chunks)
        lc_scores = compute_scores(lc_chunks)
        winner, emoji, reasons = judge(sc_scores, lc_scores)
        wins[winner] += 1

        winner_label = {"semchunk": "semchunk wins", "langchain": "LangChain wins", "tie": "Tie"}[winner]
        reasons_str = " · ".join(reasons) if reasons else "identical output"

        metrics_rows = [
            ["chunks",           sc_scores["n"],            lc_scores["n"]],
            ["avg tokens",       sc_scores["avg_tok"],      lc_scores["avg_tok"]],
            ["utilization %",    sc_scores["util"],         lc_scores["util"]],
            ["tiny chunks",      sc_scores["tiny"],         lc_scores["tiny"]],
            ["starts lowercase", sc_scores["starts_lower"], lc_scores["starts_lower"]],
            ["sentence end %",   sc_scores["sent_boundary"],lc_scores["sent_boundary"]],
        ]
        metrics_table = tabulate(
            metrics_rows, headers=["Metric", "semchunk", "LangChain"], tablefmt="github"
        )

        sections.append(
            f"## {doc_name} ({doc_tok} tokens)\n\n"
            f"{emoji} **{winner_label}** — {reasons_str}\n\n"
            f"{metrics_table}\n\n"
            f"<details>\n<summary>semchunk chunks ({sc_scores['n']})</summary>\n\n"
            f"{chunks_to_md(sc_chunks)}\n\n"
            f"</details>\n\n"
            f"<details>\n<summary>LangChain chunks ({lc_scores['n']})</summary>\n\n"
            f"{chunks_to_md(lc_chunks)}\n\n"
            f"</details>\n"
        )

        summary.append({
            "doc": doc_name, "tokens": doc_tok,
            "sc_util": sc_scores["util"], "lc_util": lc_scores["util"],
            "sc_sent": sc_scores["sent_boundary"], "lc_sent": lc_scores["sent_boundary"],
            "sc_lower": sc_scores["starts_lower"], "lc_lower": lc_scores["starts_lower"],
            "winner": winner,
        })

    # Overall winner
    if wins["semchunk"] > wins["langchain"]:
        overall = f'🏆 **Overall winner: semchunk** — won {wins["semchunk"]} of {len(DOCUMENTS)} documents'
    elif wins["langchain"] > wins["semchunk"]:
        overall = f'🏆 **Overall winner: LangChain** — won {wins["langchain"]} of {len(DOCUMENTS)} documents'
    else:
        overall = f'🤝 **Overall: Tie** — {wins["semchunk"]} wins each, {wins["tie"]} ties'

    n = len(summary)

    def avg(key):
        return round(sum(r[key] for r in summary) / n, 1)

    summary_rows = [
        [r["doc"], r["tokens"], r["sc_util"], r["lc_util"],
         r["sc_sent"], r["lc_sent"], r["sc_lower"], r["lc_lower"],
         "✅ semchunk" if r["winner"] == "semchunk" else ("✅ LangChain" if r["winner"] == "langchain" else "🤝 tie")]
        for r in summary
    ]
    summary_table = tabulate(
        summary_rows,
        headers=["Document", "Tokens", "SC Util%", "LC Util%", "SC Sent%", "LC Sent%", "SC Lower", "LC Lower", "Winner"],
        tablefmt="github",
    )

    page = (
        f"# Chunking Comparison: semchunk vs LangChain\n\n"
        f"chunk\\_size = {CHUNK_SIZE} tokens | tokenizer = {ENCODING_NAME} | {len(DOCUMENTS)} documents\n\n"
        f"{overall}\n\n"
        f"| | semchunk | LangChain |\n"
        f"|---|---|---|\n"
        f"| Avg utilization | {avg('sc_util')}% | {avg('lc_util')}% |\n"
        f"| Avg sentence end % | {avg('sc_sent')}% | {avg('lc_sent')}% |\n"
        f"| Total lowercase starts | {sum(r['sc_lower'] for r in summary)} | {sum(r['lc_lower'] for r in summary)} |\n\n"
        f"{summary_table}\n\n"
        f"---\n\n"
        + "\n---\n\n".join(sections)
    )

    output = Path("reports") / "comparison_report.md"
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
        choices=["markdown", "console"],
        default="markdown",
        help="Output format: markdown (default) or console",
    )
    args = parser.parse_args()

    if args.format == "console":
        run_console()
    else:
        run_markdown()
