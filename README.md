# Global News Radar V25

V25 is the token-saving dual-model version.

## What changed

- Adds Groq usage modes:
  - 省 token
  - 平衡
  - 高品質
- Adds dual-model settings:
  - `GROQ_MODEL_LIGHT`
  - `GROQ_MODEL_HEAVY`
- Model routing:
  - Natural-language search planning: LIGHT
  - Bulk title translation: LIGHT
  - Top few title refinements: HEAVY
  - AI event summary: LIGHT or HEAVY selectable
- Saves tokens by translating only the top N ranked articles instead of all articles.
- Keeps:
  - 8-hour AI / semiconductor heat radar
  - Groq event summary
  - industry relationship graph
  - time range filtering
  - heat score ranking

## Recommended Streamlit Secrets

```toml
GROQ_API_KEY = "gsk_your_key_here"
GROQ_MODEL_LIGHT = "llama-3.1-8b-instant"
GROQ_MODEL_HEAVY = "llama-3.3-70b-versatile"
```

Backward compatibility:

```toml
GROQ_MODEL = "llama-3.3-70b-versatile"
```

still works as the heavy model, but the two-model setup is recommended.

## Suggested usage

- Daily scanning:
  - Groq 使用模式：省 token or 平衡
  - 事件總結模型：light or heavy
  - 總結讀取：5～8
- Deeper research:
  - Groq 使用模式：高品質
  - 事件總結模型：heavy
  - 總結讀取：10～12

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
