# Global News Radar V22

V22 replaces the old generic relationship graph with an industry relationship graph MVP.

## What changed

- New tab name: 產業關係圖.
- The old source/category/country graph is replaced by a graph based on:
  - companies
  - topics / technologies
  - supply chain relationships
  - competitive relationships
  - event/theme impacts
- Relationship modes:
  - 全部關係
  - 供應鏈圖
  - 競爭圖
  - 事件傳導圖
- Adds a relationship evidence table:
  - source
  - target
  - relation
  - strength
  - supporting news evidence
- Starts with a CPU / AI dictionary:
  - Intel, AMD, Nvidia, Arm, Qualcomm, TSMC
  - AWS, Azure, Google, Meta
  - HBM, AI server, AI inference, AI PC, x86 vs Arm

## Notes

This is an MVP. It uses a curated dictionary and article titles. It does not yet read full article bodies.

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
