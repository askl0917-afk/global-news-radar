# Global News Radar V24

V24 adds Groq event summarization at the top of the unified news feed.

## What changed

- Adds AI 事件總結 on top of 統合新聞流.
- Groq reads the top high-heat / high-importance news and summarizes:
  - What these events mean
  - Main events
  - Possible impacts
  - What to track next
- Adds sidebar controls:
  - 搜尋後產生 Groq 事件總結
  - 總結讀取前幾則新聞
- Keeps:
  - natural-language research search
  - 8-hour AI / semiconductor heat radar defaults
  - Groq finance translation
  - industry relationship graph

## Notes

The summary is based on headlines and metadata, not full article bodies.
It should be treated as analyst-style first-pass synthesis, not final due diligence.

## Streamlit Secrets

```toml
GROQ_API_KEY = "gsk_your_key_here"
GROQ_MODEL = "llama-3.3-70b-versatile"
```

## Deploy

Upload:

```text
app.py
requirements.txt
README.md
```

Recommended Python version:

```text
3.12
```
