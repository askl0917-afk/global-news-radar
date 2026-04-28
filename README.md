# Global News Radar V23

V23 adds a default "last 8 hours AI / semiconductor heat radar" workflow.

## What changed

- Default search question: 最近 8 小時討論度最高的 AI 或半導體相關新聞
- Adds selectable time range: 最近 8 小時
- Default time range is 8 hours.
- Default maximum news count is 40.
- Adds heat_score as an approximation of discussion heat for RSS-based sources.
- Ranking prioritizes: heat_score → importance → source quality → recency.
- Each news card displays heat_score.
- Keeps Groq natural-language research search, Groq finance translation, and V22 industry relationship graph.

## Important

RSS sources do not provide true social discussion volume. heat_score is a proxy based on source quality, AI/semiconductor relevance, market-moving wording, recency, and topic density.

## Deploy

Upload app.py, requirements.txt, README.md.

## Streamlit Secrets

```toml
GROQ_API_KEY = "gsk_your_key_here"
GROQ_MODEL = "llama-3.3-70b-versatile"
```
