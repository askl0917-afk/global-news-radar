# Global News Radar V28

V28 adds one-click copy-to-clipboard for the Markdown news bundle.

## Why

The user wants to avoid:
- downloading files
- finding the file in iOS Files
- uploading it back to ChatGPT

V28 changes the workflow to:

```text
Search news in the App
→ Press "一鍵複製 Markdown 新聞包"
→ Open ChatGPT
→ Paste directly
```

## What changed

Added:
- 一鍵複製 Markdown 新聞包
- 手動複製備用區
- 下載備用區

Kept:
- Natural-language research search
- 8-hour AI / semiconductor heat radar
- Groq dual-model translation controls
- Heat score ranking
- Industry relationship graph
- Markdown / CSV download fallback

Removed earlier:
- App-side Groq long summary

## Notes

Some mobile browsers may block automatic clipboard access inside embedded components.
If that happens, use the "手動複製備用區" text area.

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
