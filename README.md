# Global News Radar V21

V21 adds natural-language research search powered by Groq.

## What changed

- New search mode:
  - 自然語言研究搜尋
  - 精準關鍵字
- Natural-language mode asks Groq to convert a research question into:
  - focused Google News queries
  - related US tickers
  - include/exclude concepts
  - a short search-strategy explanation
- Example:
  - "AI 軟硬體產業最近有哪些重要新聞？"
  - becomes searches around AI chips, AI servers, data centers, enterprise AI, cloud capex, HBM, networking, cooling, etc.
- Keeps Groq finance-context translation and translation diagnostics.
- Keeps time-range filtering and importance-first sorting.

## Streamlit Secrets

```toml
GROQ_API_KEY = "gsk_your_key_here"
GROQ_MODEL = "llama-3.3-70b-versatile"
```

## Deploy

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
