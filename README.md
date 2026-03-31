# semchunk vs LangChain: Chunking Comparison

A side-by-side comparison of [semchunk](https://github.com/umarbutler/semchunk) and [LangChain's RecursiveCharacterTextSplitter](https://python.langchain.com/docs/concepts/text_splitters/) across 9 document types designed to expose real algorithmic differences.

## Results

| Metric | semchunk | LangChain |
|--------|----------|-----------|
| Documents won | **8 / 9** | 0 / 9 |
| Sentence-ending chunks | **81.5%** | 42.6% |
| Mid-sentence starts | **4** | 11 |
| Avg utilization | 71.7% | 70.0% |


## How to run

```bash
uv sync

# Generate markdown report (default) — saved to reports/comparison_report.md
uv run compare.py

# Console output with metrics table
uv run compare.py --format console
```

## Files

| File | Purpose |
|------|---------|
| `dataset.py` | 9 test documents with comments explaining what each one tests |
| `compare.py` | Runs the comparison — markdown report by default, `--format console` for terminal output |
| `pyproject.toml` | Project dependencies, managed with uv |

## Key finding

Both libraries behave identically on well-formatted text with paragraph breaks. The difference appears in dense, unstructured text — the kind produced by PDF extraction, web scraping, and OCR:

- **On prose with spaces**: semchunk splits at the space *after* a sentence-ending punctuation mark; LangChain splits at whichever space is nearest to the token limit, often mid-sentence.
- **On text with no spaces** (CSV data, URLs, ARNs): semchunk falls back to splitting at punctuation (`;` `,` `/`), keeping records intact; LangChain falls back to character-level splitting, producing mangled fragments.

The trade-off: on well-structured prose, LangChain can pack chunks more tightly (e.g. 96% vs 64% on one document), producing fewer chunks and fewer embedding API calls. However, on unstructured data without spaces, LangChain's utilization collapses (as low as 28%) due to character-level splitting, while semchunk stays consistent. Overall utilization is nearly identical: semchunk 71.7% vs LangChain 70.0%.
