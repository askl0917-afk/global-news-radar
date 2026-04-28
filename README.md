# Global News Radar V27

V27 removes the App-side Groq event summary and keeps one-click news bundle export.

## Why

The App should focus on:
- fetching news
- ranking by heat
- translating only top items when needed
- building industry relationship graphs
- exporting a clean research bundle

Long-form event interpretation can be done in ChatGPT by uploading the Markdown bundle.
This saves Groq tokens and avoids hitting daily limits.

## What changed

Removed:
- Groq 事件總結
- 總結讀取前幾則新聞
- 事件總結模型 light/heavy

Kept:
- Natural-language research search
- 8-hour AI / semiconductor heat radar
- Groq dual-model translation controls
- Heat score ranking
- Industry relationship graph
- Markdown / CSV news bundle downloads

## Recommended workflow

1. Search and rank news in the App.
2. Download Markdown 新聞包.
3. Upload the Markdown to ChatGPT.
4. Ask ChatGPT to produce:
   - event summary
   - impact matrix
   - company / supply-chain implications
   - follow-up tracking list

## Recommended Streamlit Secrets

```toml
GROQ_API_KEY = "gsk_your_key_here"
GROQ_MODEL_LIGHT = "llama-3.1-8b-instant"
GROQ_MODEL_HEAVY = "llama-3.3-70b-versatile"
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
