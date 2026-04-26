# Global News Radar V16

V16 adds explicit multi-keyword search logic and importance-first sorting.

## What changed

- New search logic selector:
  - 交集 AND: search all terms together, e.g. `NVIDIA intel` means NVIDIA + Intel related articles.
  - 聯集 OR: search each term separately and merge results.
- Yahoo Finance RSS behavior:
  - AND mode: only used for single ticker queries to avoid contamination.
  - OR mode: fetches each inferred ticker separately, e.g. NVIDIA -> NVDA, Intel -> INTC.
- Results now sort by importance first:
  - A first
  - then B
  - then C
  - then D
- Within the same importance grade, results sort by source quality and recency.

## Deploy on Streamlit Community Cloud

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
