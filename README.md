# Global News Radar V19

V19 adds Groq API status checking and Groq finance-context translation.

## What changed

- Adds Groq translation mode:
  - Groq AI 財經翻譯優先
  - 只用免費機翻
  - 不翻譯只保留原文
- Shows Groq API status on the main page and sidebar:
  - Groq API：已啟用
  - Groq API：未設定
- If Groq key is not configured, app falls back to free machine translation.
- Keeps V17 time range selection.
- Keeps AND / OR keyword logic.
- Keeps importance-first sorting.

## Streamlit Secrets

Put this in Streamlit App Settings → Secrets:

```toml
GROQ_API_KEY = "gsk_your_key_here"
GROQ_MODEL = "llama-3.1-8b-instant"
```

Do not put your key in GitHub or source code.

## Deploy

Main file path:

```text
app.py
```

Recommended Python version:

```text
3.12
```
